import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from jobs import JobQueue
import server


class JobTests(unittest.TestCase):
    def wait(self, queue, job_id):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            result = queue.read(job_id)
            if result and result['status'] == 'completed':
                return result
            time.sleep(.005)
        self.fail('Job did not finish')

    def test_serial_execution_capacity_and_recovery(self):
        queue = JobQueue(capacity=2)
        started, release = threading.Event(), threading.Event()
        def first():
            started.set()
            release.wait(3)
            return {'status': 'checked_draft'}
        first_id = queue.submit(first)
        try:
            self.assertTrue(started.wait(1))
            second_id = queue.submit(lambda: {'status': 'needs_review'})
            self.assertEqual(queue.read(second_id)['status'], 'queued')
            self.assertEqual(queue.read(second_id)['ahead'], 1)
            with self.assertRaises(RuntimeError):
                queue.submit(lambda: {})
        finally:
            release.set()
        self.assertEqual(self.wait(queue, first_id)['result']['status'], 'checked_draft')
        self.assertEqual(self.wait(queue, second_id)['result']['status'], 'needs_review')
        self.assertEqual(self.wait(queue, queue.submit(lambda: {'ok': True}))['result'], {'ok': True})

    def test_failed_worker_does_not_leak_or_stop_next_job(self):
        queue = JobQueue()
        def fail():
            raise RuntimeError('private-provider-credential')
        result = self.wait(queue, queue.submit(fail))
        self.assertNotIn('private-provider-credential', json.dumps(result))
        self.assertEqual(result['result']['status'], 'failed')
        self.assertEqual(self.wait(queue, queue.submit(lambda: {'ok': True}))['result'], {'ok': True})

    def test_retention_and_unknown_identifiers(self):
        queue = JobQueue(retained=1)
        old = queue.submit(lambda: {})
        self.wait(queue, old)
        current = queue.submit(lambda: {})
        self.wait(queue, current)
        self.assertIsNone(queue.read(old))
        self.assertIsNone(queue.read('not-a-real-task'))
        with queue.lock:
            queue.jobs[current]['finished'] -= 2000
        self.assertIsNone(queue.read(current))

    def test_http_queued_generation_and_origin_allowlist(self):
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        url = 'http://127.0.0.1:' + str(http.server_port)
        settings = {'APP_ASYNC_JOBS': '1', 'APP_ALLOWED_HOSTS': 'review.example',
                    'APP_ALLOWED_ORIGINS': 'https://review.example'}
        queue = JobQueue()
        try:
            with patch('server.env', side_effect=lambda key, default='': settings.get(key, default)), \
                 patch('server.JOBS', queue), patch('server.run_agent', return_value={'status': 'model_required'}) as run:
                headers = {'Host': 'review.example', 'Origin': 'https://review.example', 'Content-Type': 'application/json'}
                req = urllib.request.Request(url + '/api/generate', b'{}', headers)
                with urllib.request.urlopen(req) as response:
                    self.assertEqual(response.status, 202)
                    accepted = json.load(response)
                self.wait(queue, accepted['job_id'])
                req = urllib.request.Request(url + '/api/jobs/' + accepted['job_id'], headers={'Host': 'review.example'})
                with urllib.request.urlopen(req) as response:
                    self.assertEqual(json.load(response)['result']['status'], 'model_required')
                run.assert_called_once()
                for field, value in [('Host', 'attacker.example'), ('Origin', 'https://review.example.attacker.invalid')]:
                    req = urllib.request.Request(url + '/api/generate', b'{}', {**headers, field: value})
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(req)
                    self.assertEqual(caught.exception.code, 403)
                    caught.exception.close()
                run.assert_called_once()
        finally:
            http.shutdown()
            http.server_close()
            thread.join()
