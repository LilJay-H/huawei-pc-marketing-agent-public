"""Reproducible local entry point. Does not print credentials or internal IDs."""
import argparse
import json
from pathlib import Path
from agent import Ima, env, retrieve, run_agent


def main():
    parser = argparse.ArgumentParser(description='软文工坊 Agent 测试入口')
    parser.add_argument('action', choices=['check', 'retrieve', 'generate'])
    parser.add_argument('--task', type=Path, help='UTF-8 JSON 任务文件')
    parser.add_argument('--source', choices=['ima', 'local'], help='显式选择实时 ima 或本地开发资料')
    parser.add_argument('--output', type=Path, help='完整结果保存位置，建议 outputs/ 内；包含知识库内容，不上传')
    args = parser.parse_args()
    try:
        if args.action == 'check':
            Ima().kb()
            print(json.dumps({'ima': 'connected', 'knowledge_base': env('IMA_KB_NAME', '你的知识库名称'),
                              'model_configured': all(env(k) for k in ['LLM_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL'])}, ensure_ascii=False))
            return 0
        if not args.task:
            parser.error('retrieve/generate 需要 --task')
        task = json.loads(args.task.read_text(encoding='utf-8-sig'))
        if not isinstance(task, dict) or any(not isinstance(v, str) for v in task.values()):
            raise ValueError('任务应为文本字段对象')
        if args.source:
            task['source_mode'] = args.source
        r = (retrieve if args.action == 'retrieve' else run_agent)(task)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'status': r['status'], 'documents': len(r.get('documents', [])),
                          'images': len(r.get('images', [])), 'issues': r.get('issues', []),
                          'run_id': r.get('run_id'), 'error': r.get('error'),
                          'questions': r.get('questions', []), 'warnings': r.get('warnings', [])}, ensure_ascii=False))
        return 1 if r['status'] == 'failed' else (0 if r['status'] in ['retrieved', 'checked_draft'] else 2)
    except (RuntimeError, ValueError, OSError) as e:
        print('测试未完成：' + str(e))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
