"""HTTP-to-draft contract tests with synthetic evidence and a fake model transport.
These prove pipeline wiring, not real provider availability or writing quality.
"""
import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import server


class GenerationFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()

    def test_real_pipeline_contract_for_each_platform(self):
        with tempfile.TemporaryDirectory() as folder:
            product = Path(folder) / 'P1-产品参数库/02-MateBook-Windows/测试型号'
            product.mkdir(parents=True)
            (product / '产品事实.md').write_text('接口测试用机身重量约 1 kg。', encoding='utf-8')
            (product / '图片索引.csv').write_text('文件名,产品型号,来源页面\n' + ''.join(
                f'test{i}.png,测试型号,https://example.invalid\n' for i in range(3)), encoding='utf-8')
            for i in range(3):
                (product / f'test{i}.png').write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')
            settings = dict(LLM_BASE_URL='https://api.deepseek.com', LLM_API_KEY='synthetic-test-key',
                            LLM_MODEL='synthetic-test-model', LOCAL_KB_PATH=folder)
            for platform, image_count in [('小红书', 3), ('公众号', 2), ('朋友圈', 1), ('海报', 1)]:
                with self.subTest(platform=platform):
                    calls = []
                    def provider(url, body, headers):
                        calls.append(body)
                        payload = json.loads(body['messages'][1]['content'])
                        if len(calls) == 1:
                            result = {'facts': [{'claim': '接口测试用机身重量约 1 kg。', 'source_id': 'D1',
                                                 'quote': '接口测试用机身重量约 1 kg。', 'conditions': '接口测试数据'}], 'conflicts': []}
                        elif len(calls) == 2:
                            self.assertEqual(payload['task']['platform'], platform)
                            result = {'markdown': '接口测试用机身重量约 1 kg。', 'claims': payload['facts'],
                                      'image_plan': [{'image_id': f'I{i+1}', 'position': '正文后', 'caption': '测试配图'} for i in range(image_count)],
                                      'conflicts': [], 'pending': []}
                        else:
                            result = {'issues': [], 'precheck_findings': []}
                        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(result, ensure_ascii=False)}}]}
                    task = dict(source_mode='local', product='测试型号', audience='测试学生', scene='开学购机',
                                platform=platform, goal='接口验收', version='', requirements='')
                    with patch('agent.env', side_effect=lambda key, default='': settings.get(key, default)), patch('agent.request_json', side_effect=provider):
                        request = urllib.request.Request(self.url + '/api/generate', json.dumps(task).encode(),
                            {'Content-Type': 'application/json', 'Host': '127.0.0.1:8765'})
                        with urllib.request.urlopen(request) as response:
                            result = json.load(response)
                    self.assertEqual(result['status'], 'checked_draft', result.get('issues'))
                    self.assertEqual(len(calls), 3)
                    self.assertEqual(result['draft']['markdown'], '接口测试用机身重量约 1 kg。')
                    self.assertEqual(result['verification']['facts'][0]['status'], 'quote_matched')
                    self.assertTrue(all(x['status'] == 'catalog_match' for x in result['verification']['images']))
                    self.assertEqual(len(result['draft']['image_plan']), image_count)
                    self.assertIn(result['run_id'], server.SESSIONS)
                    self.assertTrue(result['evidence_manifest'])
