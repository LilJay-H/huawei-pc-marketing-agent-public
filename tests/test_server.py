import json
import threading
import time
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import server


class RewriteAPITests(unittest.TestCase):
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

    def setUp(self):
        server.SESSIONS.clear()
        self.old = {'run_id': 'synthetic-test', 'started_at': '2026-10-18T00:00:00+00:00',
                    'task': {'product': '测试型号', 'version': '2024', 'platform': '小红书'},
                    'draft': {'markdown': '测试'}, 'documents': [], 'images': [], 'warnings': [], 'search_hits': 0}
        server.remember(self.old)

    def request(self, body, origin=None):
        headers = {'Host': '127.0.0.1:8765', 'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        req = urllib.request.Request(self.url + '/api/rewrite', json.dumps(body).encode(), headers)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def test_model_change_never_reuses_evidence(self):
        with patch('server.run_agent') as run:
            code, _ = self.request({'run_id': self.old['run_id'], 'product': '其他型号'})
        self.assertEqual(code, 400)
        run.assert_not_called()

    def test_expired_snapshot_rejected(self):
        server.SESSIONS[self.old['run_id']] = (time.monotonic() - 1900, self.old)
        code, _ = self.request({'run_id': self.old['run_id']})
        self.assertEqual(code, 400)

    def test_rewrite_records_original_evidence_time(self):
        result = {**self.old, 'run_id': 'synthetic-new', 'started_at': '2026-10-18T00:10:00+00:00'}
        with patch('server.run_agent', return_value=result) as run:
            code, d = self.request({'run_id': self.old['run_id'], 'platform': '公众号', 'requirements': '缩短'})
        self.assertEqual(code, 200)
        self.assertEqual(d['parent_run_id'], self.old['run_id'])
        self.assertEqual(d['evidence_started_at'], self.old['started_at'])
        self.assertEqual(run.call_args.kwargs['mode'], 'snapshot_rewrite')
        self.assertEqual(run.call_args.args[0]['platform'], '公众号')

    def test_foreign_origin_rejected(self):
        code, _ = self.request({'run_id': self.old['run_id']}, 'https://example.invalid')
        self.assertEqual(code, 403)

    def test_frontend_assets_have_correct_content_types(self):
        for path, content_type in [('/', 'text/html'), ('/styles.css', 'text/css'),
                                   ('/app.js', 'text/javascript')]:
            with self.subTest(path=path), urllib.request.urlopen(self.url + path) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), content_type)
                self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
                self.assertTrue(response.read())

    def test_config_exposes_missing_field_names_without_secret_values(self):
        settings = {'LLM_BASE_URL': 'https://example.invalid', 'LLM_API_KEY': '', 'LLM_MODEL': 'test-model'}
        with patch('server.env', side_effect=lambda key, default='': settings.get(key, default)):
            with urllib.request.urlopen(self.url + '/api/config') as response:
                data = json.load(response)
        self.assertFalse(data['model_configured'])
        self.assertEqual(data['model_missing_fields'], ['LLM_API_KEY'])
        self.assertNotIn('https://example.invalid', json.dumps(data))
        self.assertNotIn('test-model', json.dumps(data))

    def test_rewrite_preserves_product_identity_for_image_checks(self):
        self.old['product_identity'] = {'directory_model': '测试型号', 'category': '01-鸿蒙电脑'}
        with patch('server.run_agent', return_value={**self.old, 'run_id': 'identity-new'}) as run:
            code, _ = self.request({'run_id': self.old['run_id']})
        self.assertEqual(code, 200)
        self.assertEqual(run.call_args.args[1]['product_identity'], self.old['product_identity'])

    def test_static_route_does_not_expose_arbitrary_files(self):
        for path in ['/.env', '/server.py', '/web/../server.py', '/styles.css/../server.py']:
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(self.url + path)
            self.assertEqual(caught.exception.code, 404)
            caught.exception.close()
