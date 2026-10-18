import unittest
from unittest.mock import patch
from verification import image_checks, compliance_checks
from agent import run_agent


class VerificationTests(unittest.TestCase):
    def evidence(self, product='MateBook D 14', version='2024'):
        # Synthetic fixture: not Huawei product evidence or a real marketing result.
        return {'task': {'product': product, 'version': version},
                'documents': [{'id': 'D1', 'title': '图片索引.csv', 'text':
                               '文件名,产品型号,来源页面\nfixture.png,HUAWEI MateBook D 14 2024,https://example.invalid\n'}],
                'images': [{'id': 'I1', 'title': 'fixture.png'}]}

    def test_matching_indexed_model_and_year(self):
        r = image_checks(self.evidence(), [{'image_id': 'I1'}])
        self.assertEqual(r[0]['status'], 'catalog_match')

    def test_wrong_model_or_year_is_mismatch(self):
        for e in [self.evidence(product='MateBook D 16'), self.evidence(version='2025')]:
            self.assertEqual(image_checks(e, [{'image_id': 'I1'}])[0]['status'], 'mismatch')

    def test_missing_index_or_year_never_passes(self):
        e = self.evidence(version='')
        self.assertEqual(image_checks(e, [{'image_id': 'I1'}])[0]['status'], 'unverified')

    def test_harmony_alias_requires_matching_local_directory_identity(self):
        e = self.evidence(product='HUAWEI MateBook 14', version='')
        e['documents'][0]['text'] = '文件名,产品型号,来源页面\nfixture.png,HUAWEI MateBook 14（鸿蒙版）,https://example.invalid\n'
        e['source_kind'] = 'local_v7'
        e['product_identity'] = {'directory_model': 'HUAWEI MateBook 14', 'category': '01-鸿蒙电脑'}
        self.assertEqual(image_checks(e, [{'image_id': 'I1'}])[0]['status'], 'catalog_match')
        for change in [dict(source_kind='ima_live'), dict(product_identity={}),
                       dict(product_identity={'directory_model': 'HUAWEI MateBook 14', 'category': '02-MateBook-Windows'}),
                       dict(product_identity={'directory_model': '其他型号', 'category': '01-鸿蒙电脑'})]:
            with self.subTest(change=change):
                self.assertEqual(image_checks({**e, **change}, [{'image_id': 'I1'}])[0]['status'], 'mismatch')
        e['task']['version'] = 'Windows 11'
        self.assertEqual(image_checks(e, [{'image_id': 'I1'}])[0]['status'], 'unverified')

    def test_index_without_model_is_unverified_not_a_false_mismatch(self):
        e = self.evidence()
        e['documents'][0]['text'] = '文件名,画面说明,商品页URL\nfixture.png,测试图片,https://example.invalid\n'
        result = image_checks(e, [{'image_id': 'I1'}])[0]
        self.assertEqual(result['status'], 'unverified')
        self.assertIn('缺少产品型号字段', result['reason'])
        e['documents'] = []
        self.assertEqual(image_checks(e, [{'image_id': 'I1'}])[0]['status'], 'unverified')

    def test_dynamic_offer_and_absolute_claim_flagged(self):
        self.assertGreaterEqual(len(compliance_checks('全网最低，售价3999元，享教育优惠。')), 3)
        self.assertEqual(compliance_checks('补贴情况待确认。100% sRGB 仅为测试字符串。'), [])

    def test_incomplete_task_does_not_call_provider(self):
        with patch('agent.generate') as generate:
            r = run_agent({})
        self.assertEqual(r['status'], 'needs_input')
        generate.assert_not_called()

    def test_failure_preserves_trace_without_success(self):
        t = dict(product='测试型号', audience='学生', scene='开学购机', platform='海报', goal='咨询')
        with patch('agent.generate', side_effect=RuntimeError('资料获取次数已达上限')):
            r = run_agent(t)
        self.assertEqual(r['status'], 'failed')
        self.assertEqual(r['trace'][-1]['status'], 'failed')
        self.assertNotIn('draft', r)

    def test_report_contains_hash_and_rewrite_mode(self):
        t = dict(product='MateBook D 14', version='2024', audience='学生', scene='开学购机', platform='海报', goal='咨询')
        e = self.evidence()
        d = {'markdown': '测试', 'claims': [], 'image_plan': [{'image_id': 'I1'}]}
        r = {**e, 'status': 'needs_review', 'draft': d, 'issues': ['测试待复核']}
        with patch('agent.generate', return_value=r):
            result = run_agent(t, e, d, mode='snapshot_rewrite')
        self.assertEqual(len(result['evidence_manifest'][0]['sha256']), 64)
        self.assertEqual(result['mode'], 'snapshot_rewrite')
        self.assertEqual(result['verification']['images'][0]['status'], 'catalog_match')


if __name__ == '__main__':
    unittest.main()
