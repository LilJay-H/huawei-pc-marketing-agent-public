import json
import time
import threading
from collections import OrderedDict
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from agent import ROOT, SCENES, PLATFORMS, env, Ima, retrieve, run_agent
from writing_harness import scene_cards
from local_kb import LocalKnowledgeBase

SESSIONS = OrderedDict()
SESSION_LOCK = threading.Lock()


def remember(result, snapshot_time=None):
    if result.get('draft'):
        with SESSION_LOCK:
            SESSIONS[result['run_id']] = (snapshot_time or time.monotonic(), result)
            while len(SESSIONS) > 20:
                SESSIONS.popitem(last=False)
    return result


def public(result):
    # Signed media links are transient; never persist them in repository logs.
    return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, data, code=200):
        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ['/api/local-image', '/api/products']:
            if self.headers.get('Host') not in ['127.0.0.1:8765', 'localhost:8765']:
                return self.reply({'error': 'Host rejected'}, 403)
            try:
                kb = LocalKnowledgeBase(env('LOCAL_KB_PATH', 'knowledge-base/v7'))
                if parsed.path == '/api/products':
                    return self.reply({'source_mode': 'local', 'products': kb.products()})
                raw, mime = kb.image(parse_qs(parsed.query).get('file', [''])[0])
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(raw)
                return
            except (RuntimeError, OSError):
                return self.reply({'error': '本地资料不可用或请求路径无效。'}, 404)
        if self.path == '/api/config':
            return self.reply({'scenes': SCENES, 'micro_scenes': scene_cards(), 'platforms': PLATFORMS,
                               'local_configured': (ROOT / env('LOCAL_KB_PATH', 'knowledge-base/v7')).is_dir() or (ROOT / 'knowledge-base/v7.zip').is_file(),
                               'default_source': env('DEFAULT_SOURCE_MODE', 'local'),
                               'ima_configured': all(env(k) for k in ['IMA_OPENAPI_CLIENTID', 'IMA_OPENAPI_APIKEY']),
                               'model_missing_fields': [k for k in ['LLM_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL'] if not env(k)],
                               'model_configured': all(env(k) for k in ['LLM_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL'])})
        assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8')}
        if parsed.path not in assets:
            return self.reply({'error': 'Not found'}, 404)
        filename, content_type = assets[parsed.path]
        raw = (ROOT / 'web' / filename).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        # Local service: block cross-origin requests and oversized input.
        if self.headers.get('Host') not in ['127.0.0.1:8765', 'localhost:8765']:
            return self.reply({'error': 'Host rejected'}, 403)
        origin = self.headers.get('Origin')
        if origin and origin not in ['http://127.0.0.1:8765', 'http://localhost:8765']:
            return self.reply({'error': 'Origin rejected'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 20000:
                return self.reply({'error': '请求过大或为空'}, 400)
            task = json.loads(self.rfile.read(length))
            if not isinstance(task, dict) or any(not isinstance(v, str) for v in task.values()):
                return self.reply({'error': '请求字段必须为文本'}, 400)
            if self.path == '/api/connect':
                if task.get('source_mode') == 'local':
                    kb = LocalKnowledgeBase(env('LOCAL_KB_PATH', 'knowledge-base/v7'))
                    return self.reply({'message': '本地 v7 可读取，包含 ' + str(len(kb.products())) + ' 个重点型号；非实时 ima 结果。'})
                Ima().kb()
                return self.reply({'message': '已连接指定 ima 共享知识库'})
            if self.path == '/api/retrieve':
                return self.reply(public(retrieve(task)))
            if self.path == '/api/generate':
                return self.reply(public(remember(run_agent(task))))
            if self.path == '/api/rewrite':
                with SESSION_LOCK:
                    saved = SESSIONS.get(task.pop('run_id', ''))
                if not saved or time.monotonic() - saved[0] > 1800:
                    return self.reply({'error': '原稿证据快照已过期或服务已重启，请重新检索生成。'}, 400)
                old = saved[1]
                merged = {**old['task'], **task}
                if any(merged.get(k, 'ima' if k == 'source_mode' else '') != old['task'].get(k, 'ima' if k == 'source_mode' else '') for k in ['product', 'version', 'source_mode']):
                    return self.reply({'error': '型号、版本或资料模式已改变，请重新检索，不能复用旧证据。'}, 400)
                evidence = {k: old[k] for k in ['documents', 'images', 'warnings', 'search_hits', 'source_kind', 'knowledge_base', 'source_note', 'snapshot_modified_at', 'product_identity'] if k in old}
                evidence['status'] = 'retrieved'
                result = run_agent(merged, evidence, old['draft'], mode='snapshot_rewrite')
                result['parent_run_id'] = old['run_id']
                result['evidence_started_at'] = old.get('evidence_started_at', old['started_at'])
                return self.reply(public(remember(result, saved[0])))
            return self.reply({'error': 'Not found'}, 404)
        except RuntimeError as e:
            return self.reply({'error': str(e)}, 400)
        except Exception:
            return self.reply({'error': '处理失败，请检查输入或接口返回格式；未交付未经核验内容。'}, 500)


if __name__ == '__main__':
    print('Campus Agent: http://127.0.0.1:8765', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
