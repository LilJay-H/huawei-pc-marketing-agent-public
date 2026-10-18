import unittest
from unittest.mock import patch

from agent import check_task, generate, extract_facts, semantic_review
from writing_harness import build_harness, check_copy


class HarnessTests(unittest.TestCase):
    def test_selection_and_invalid_pair(self):
        task = dict(scene='课堂与图书馆', goal='期末复习')
        self.assertEqual(build_harness(task)['scene']['id'], 'S06')
        ai_task = dict(scene='开学购机', audience='刚上大学、想学AI的大学生',
                       goal='针对想学AI的大学生生成营销文案')
        self.assertEqual(build_harness(ai_task)['scene']['id'], 'S03')
        task['micro_scene_id'] = 'S05'
        self.assertEqual(build_harness(task)['scene']['id'], 'S05')
        task['scene'] = '论文答辩'
        self.assertTrue(any('不匹配' in x for x in check_task(task)))

    def test_legacy_scene_does_not_invent_portrait(self):
        self.assertIsNone(build_harness({'scene': '实习办公'})['scene'])

    def test_copy_keeps_conditions_but_rejects_internal_markers_and_stale_claims(self):
        draft = {'markdown': '此功能需要支持的设备。', 'claims': [{'claim': '此功能需要支持的设备。'}]}
        self.assertEqual(check_copy(draft), [])
        draft['markdown'] += '[D1]'
        self.assertTrue(check_copy(draft))
        draft['markdown'] = '其他正文'
        self.assertTrue(any('连续原句' in x for x in check_copy(draft)))

    def test_snapshot_rewrite_reselects_scene_and_repair_keeps_contract(self):
        task = dict(scene='课堂与图书馆', micro_scene_id='S06', platform='海报', product='测试型号')
        evidence = dict(status='retrieved', documents=[{'id': 'D1', 'text': '约 1.3 kg'}], images=[],
                        harness=build_harness({'scene': '开学购机'}))
        draft = dict(markdown='约 1.3 kg', claims=[dict(claim='约 1.3 kg', source_id='D1', quote='约 1.3 kg')])
        with patch('agent.env', return_value='configured'), patch('agent.extract_facts', return_value={'facts': [{}], 'conflicts': []}) as extract, \
             patch('agent.llm', return_value=draft) as model, patch('agent.audit', side_effect=[['修订'], []]), \
             patch('agent.semantic_review', return_value=[]):
            result = generate(task, evidence, {'markdown': '旧稿'})
        self.assertEqual(result['status'], 'checked_draft')
        self.assertEqual(extract.call_args.args[1]['harness']['scene']['id'], 'S06')
        self.assertEqual(model.call_count, 2)
        for call in model.call_args_list:
            self.assertIn('原帖', call.args[0])
            self.assertEqual(call.args[1]['harness']['scene']['id'], 'S06')

    def test_extract_and_review_receive_scene_without_treating_it_as_evidence(self):
        task = dict(scene='课堂与图书馆', product='型号')
        evidence = dict(task=task, documents=[], images=[], harness=build_harness(task))
        with patch('agent.llm', return_value={'facts': [], 'conflicts': []}) as model:
            extract_facts(task, evidence)
        self.assertIn('不是事实', model.call_args.args[0])
        self.assertEqual(model.call_args.args[1]['harness'], evidence['harness'])
        with patch('agent.llm', return_value={'issues': []}) as model:
            semantic_review({'markdown': '正文'}, evidence)
        self.assertIn('harness', model.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
