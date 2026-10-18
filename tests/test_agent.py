import unittest
from unittest.mock import patch
from agent import audit, check_task, generate, llm, extract_facts, quote_matches, semantic_review, SCENES, PLATFORMS


class SafetyTests(unittest.TestCase):
    def test_quote_layout_whitespace_only(self):
        self.assertTrue(quote_matches('重量约 1.3 kg', '重量约\n1.3  kg'))
        self.assertFalse(quote_matches('重量约 1.2 kg', '重量约\n1.3  kg'))

    def test_conflict_stops_before_drafting(self):
        evidence = {'status': 'retrieved', 'documents': [{'id': 'D1', 'text': '原文'}]}
        with patch('agent.retrieve', return_value=evidence), patch('agent.env', return_value='configured'), \
             patch('agent.extract_facts', return_value={'facts': [], 'conflicts': ['同配置参数矛盾']}), patch('agent.llm') as model:
            result = generate({})
        self.assertEqual(result['status'], 'blocked')
        self.assertNotIn('draft', result)
        model.assert_not_called()

    def test_fabricated_extracted_fact_rejected(self):
        result = {'facts': [{'source_id': 'D1', 'quote': '虚构参数'}], 'conflicts': []}
        with patch('agent.llm', return_value=result):
            with self.assertRaises(RuntimeError):
                extract_facts({}, {'documents': [{'id': 'D1', 'text': '原文'}]})

    def test_quote_repair_is_bounded_and_still_requires_exact_evidence(self):
        invalid = {'facts': [{'source_id': 'D1', 'quote': '改写过的引文'}], 'conflicts': []}
        valid = {'facts': [{'source_id': 'D1', 'quote': '原文'}], 'conflicts': []}
        evidence = {'documents': [{'id': 'D1', 'text': '原文'}]}
        with patch('agent.llm', side_effect=[invalid, valid]) as model:
            self.assertEqual(extract_facts({}, evidence), valid)
        self.assertEqual(model.call_count, 2)
        self.assertIn('repair_error', model.call_args.args[1])
        with patch('agent.llm', return_value=invalid) as model:
            with self.assertRaisesRegex(RuntimeError, '无法匹配原文'):
                extract_facts({}, evidence)
        self.assertEqual(model.call_count, 2)

    def test_review_shape_repair_keeps_reported_issues(self):
        evidence = {'task': {'product': '测试型号', 'platform': '海报'}, 'documents': [], 'images': []}
        invalid = {'issues': [{'text': '需要补充条件'}], 'precheck_findings': []}
        valid = {'issues': ['需要补充条件'], 'precheck_findings': []}
        with patch('agent.llm', side_effect=[invalid, valid]) as model:
            self.assertEqual(semantic_review({'markdown': '测试正文'}, evidence), ['需要补充条件'])
        self.assertEqual(model.call_count, 2)
        with patch('agent.llm', return_value=invalid) as model:
            with self.assertRaisesRegex(RuntimeError, '格式无效'):
                semantic_review({'markdown': '测试正文'}, evidence)
        self.assertEqual(model.call_count, 2)

    def test_writer_uses_catalog_matched_candidates_when_enough_exist(self):
        task = {'product': '测试型号', 'platform': '小红书', 'scene': '开学购机'}
        images = [{'id': 'I' + str(i), 'title': '测试图'} for i in range(4)]
        evidence = {'status': 'retrieved', 'task': task,
                    'documents': [{'id': 'D1', 'text': '测试原文'}], 'images': images}
        checks = [{'image_id': x['id'], 'status': 'catalog_match' if i < 3 else 'unverified'}
                  for i, x in enumerate(images)]
        draft = {'markdown': '测试正文', 'claims': [], 'image_plan': []}
        with patch('agent.retrieve', return_value=evidence), patch('agent.env', return_value='configured'), \
             patch('agent.extract_facts', return_value={'facts': [{}], 'conflicts': []}), \
             patch('agent.image_checks', return_value=checks), patch('agent.audit', return_value=[]), \
             patch('agent.semantic_review', return_value=[]), patch('agent.llm', return_value=draft) as model:
            result = generate(task)
        self.assertEqual([x['id'] for x in model.call_args.args[1]['images']], ['I0', 'I1', 'I2'])
        self.assertEqual(len(result['images']), 4)

    def test_semantic_issue_is_repaired_and_rechecked(self):
        task = {'product': '测试型号', 'platform': '海报'}
        evidence = {'status': 'retrieved', 'task': task, 'documents': [{'id': 'D1', 'text': '约 1.3 kg'}], 'images': [{'id': 'I1'}]}
        draft = {'markdown': '约 1.3 kg', 'claims': [{'claim': '约 1.3 kg', 'source_id': 'D1', 'quote': '约 1.3 kg'}],
                 'image_plan': [{'image_id': 'I1', 'position': '主图', 'caption': '型号图'}], 'conflicts': [], 'pending': []}
        with patch('agent.retrieve', return_value=evidence), patch('agent.env', return_value='configured'), \
             patch('agent.extract_facts', return_value={'facts': [{'quote': '约 1.3 kg'}], 'conflicts': []}), \
             patch('agent.llm', return_value=draft) as model, \
             patch('agent.image_checks', return_value=[]), \
             patch('agent.semantic_review', side_effect=[['补充限定条件'], []]) as reviewer:
            result = generate(task)
        self.assertEqual(result['status'], 'checked_draft')
        self.assertEqual(model.call_count, 2)
        self.assertEqual(reviewer.call_count, 2)

    def test_duplicate_images_rejected(self):
        e = {'documents': [], 'images': [{'id': 'I1'}], 'task': {'platform': '朋友圈'}}
        img = {'image_id': 'I1', 'position': '主图', 'caption': '图'}
        d = {'markdown': '内容', 'claims': [], 'image_plan': [img, img]}
        self.assertIn('同一图片被重复选用', audit(d, e))

    def test_ima_daily_limit_is_not_reported_as_missing_model(self):
        task = dict(product='型号', audience='学生', scene='开学购机', platform='小红书', goal='咨询')
        with patch('agent.Ima') as factory:
            ima = factory.return_value
            ima.kb.return_value = 'internal-test-id'
            ima.call.return_value = {'info_list': []}
            ima.product_files.return_value = [{'title': '产品事实.md'}]
            ima.read.side_effect = RuntimeError('资料获取次数已达上限，请明天再尝试')
            from agent import retrieve
            with self.assertRaisesRegex(RuntimeError, '次数已达上限'):
                retrieve(task)

    def test_deepseek_structured_request(self):
        settings = {'LLM_BASE_URL': 'https://api.deepseek.com', 'LLM_API_KEY': 'test-only', 'LLM_MODEL': 'deepseek-flash'}
        response = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"ok":true}'}}]}
        with patch('agent.env', side_effect=lambda k: settings[k]), patch('agent.request_json', return_value=response) as request:
            self.assertEqual(llm('Return JSON', {}), {'ok': True})
        url, body, headers = request.call_args.args
        self.assertEqual(url, 'https://api.deepseek.com/chat/completions')
        self.assertEqual(body['response_format'], {'type': 'json_object'})
        self.assertEqual(body['thinking'], {'type': 'disabled'})

    def test_generation_without_model_does_not_fake_draft(self):
        evidence = {'status': 'retrieved', 'documents': [{'id': 'D1', 'text': '事实'}]}
        with patch('agent.retrieve', return_value=evidence), patch('agent.env', return_value=''):
            result = generate({})
        self.assertEqual(result['status'], 'model_required')
        self.assertNotIn('draft', result)

    def test_platform_and_scene_strategies_change(self):
        self.assertNotEqual(SCENES['社团创作']['focus'], SCENES['课堂与图书馆']['focus'])
        self.assertNotEqual(PLATFORMS['小红书']['style'], PLATFORMS['公众号']['style'])
        self.assertNotEqual(PLATFORMS['小红书']['min_images'], PLATFORMS['公众号']['min_images'])

    def test_missing_task_asks(self):
        self.assertGreaterEqual(len(check_task({})), 5)

    def test_specialist_software_requires_details(self):
        t = dict(product='MateBook', audience='学生', goal='咨询', platform='小红书', scene='专业软件')
        self.assertTrue(check_task(t))

    def test_fabricated_quote_and_image_blocked(self):
        evidence = {'documents': [{'id': 'D1', 'text': '重量约 1.3 kg'}], 'images': [], 'task': {'platform': '小红书'}}
        draft = {'markdown': '全网最低', 'claims': [{'source_id': 'D1', 'quote': '价格999', 'claim': '低价'}],
                 'image_plan': [{'image_id': 'I999'}]}
        issues = audit(draft, evidence)
        self.assertTrue(any('证据' in x for x in issues))
        self.assertTrue(any('配图不在' in x for x in issues))
        self.assertTrue(any('风险表达' in x for x in issues))

    def test_exact_quote_and_valid_image(self):
        e = {'documents': [{'id': 'D1', 'text': '机身重量约 1.3 kg。'}], 'images': [{'id': 'I1'}], 'task': {'platform': '海报'}}
        d = {'markdown': '机身重量约 1.3 kg [D1]', 'claims': [{'source_id': 'D1', 'quote': '机身重量约 1.3 kg。'}],
             'image_plan': [{'image_id': 'I1', 'position': '主图', 'caption': '产品图'}]}
        self.assertEqual(audit(d, e), [])


if __name__ == '__main__':
    unittest.main()
