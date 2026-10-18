import unittest
from unittest.mock import patch
from publish_precheck import scan, finish
from agent import semantic_review


class PublishPrecheckTests(unittest.TestCase):
    def test_candidate_is_not_a_verdict_and_source_dates_are_visible(self):
        report = scan({'markdown': '屏幕覆盖100% sRGB'}, '小红书', today='2026-10-18')
        self.assertEqual(report['status'], 'awaiting_semantic_review')
        self.assertTrue(report['rule_review_due'])
        findings = [dict(candidate_id=c['id'], decision='allow', reason='这是待核产品色域参数，不是效果保证') for c in report['candidates']]
        self.assertEqual(finish(report, findings), [])
        self.assertTrue(report['not_checked'])

    def test_missing_or_duplicate_decisions_stop_delivery(self):
        report = scan({'markdown': '全网最好'}, '小红书')
        with self.assertRaises(RuntimeError):
            finish(report, [])
        finding = dict(candidate_id='C1', decision='allow', reason='理由')
        with self.assertRaises(RuntimeError):
            finish(report, [finding, finding])

    def test_scans_captions_and_keeps_platform_scope(self):
        draft = dict(markdown='正常提到微信', image_plan=[dict(caption='加我微信领取')])
        report = scan(draft, '小红书')
        self.assertTrue(report['candidates'])
        self.assertTrue(all(c['field'].startswith('image_plan.') for c in report['candidates']))
        other = scan(draft, '公众号')
        self.assertFalse(any(c['rule_id'].endswith('R05') for c in other['candidates']))
        self.assertFalse(any(r['scope']=='xiaohongshu' for r in other['semantic_rules']))

    def test_semantic_review_returns_actionable_findings(self):
        draft = {'markdown': '加我微信领取'}
        evidence = dict(task=dict(product='型号', platform='小红书'), documents=[], images=[])
        report = scan(draft, '小红书')
        result = dict(issues=[], precheck_findings=[dict(candidate_id=c['id'], decision='revise',
                      reason='存在站外承接指令，需核适用规则', suggestion='删除领取指令，直接给出正文内的方法') for c in report['candidates']])
        with patch('agent.llm', return_value=result):
            issues = semantic_review(draft, evidence)
        self.assertTrue(issues)
        self.assertEqual(evidence['publish_precheck']['status'], 'needs_review')
        self.assertIn('删除', evidence['publish_precheck']['findings'][0]['suggestion'])


if __name__ == '__main__':
    unittest.main()
