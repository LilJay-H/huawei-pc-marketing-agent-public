"""Select a student task and load the editable writing contract; no model calls."""
import hashlib
import json
import re
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent / 'harness'


def scene_cards():
    return json.loads((DIRECTORY / 'scenes.json').read_text(encoding='utf-8'))['scenes']


def validate_selection(task):
    selected = task.get('micro_scene_id')
    if not selected:
        return []
    card = next((x for x in scene_cards() if x['id'] == selected), None)
    if card is None or task.get('scene') not in card['broad_scenes']:
        return ['细分场景与校园场景不匹配，请重新选择']
    return []


def build_harness(task):
    errors = validate_selection(task)
    if errors:
        raise RuntimeError(errors[0])
    candidates = [x for x in scene_cards() if task.get('scene') in x['broad_scenes']]
    selected = next((x for x in candidates if x['id'] == task.get('micro_scene_id')), None)
    reason = '用户指定细分场景'
    if selected is None and candidates:
        text = ' '.join(str(task.get(k, '')) for k in ['goal', 'requirements', 'audience']).lower()
        # Prefer a specific activity ("想学 AI") over broad state labels ("新生").
        selected = max(candidates, key=lambda x: sum(len(word) for word in x['keywords'] if word in text))
        reason = '根据任务关键词匹配；无匹配时使用当前大类的首张场景卡，可手动修改'
    manifest = {name: hashlib.sha256((DIRECTORY / name).read_bytes()).hexdigest()
                for name in ['README.md', 'voice.md', 'scenes.json', 'review.md', 'publish-precheck.md', 'publish-rules.json']}
    return {'version': '1.0', 'scene': selected, 'selection_reason': reason if selected else
            '此场景尚无细分卡：围绕用户实际任务写作，不编造画像',
            'authority': '场景卡只决定表达和检索方向；产品能力必须由本次产品原文证明',
            'manifest': manifest}


def writing_instructions():
    return '\n\n'.join((DIRECTORY / name).read_text(encoding='utf-8')
                        for name in ['README.md', 'voice.md', 'publish-precheck.md'])


def review_instructions():
    return (DIRECTORY / 'review.md').read_text(encoding='utf-8')


def check_copy(draft):
    content = draft['markdown']
    issues = []
    if re.search(r'\[(?:D|I)\d+\]|\bSKU\b|SHA256|原文证据清单|审稿反馈', content, re.I):
        issues.append('消费者正文混入内部核验内容；保留必要使用条件，将证据移到独立字段')
    for claim in draft.get('claims', []):
        if not claim.get('claim', '').strip() or claim['claim'] not in content:
            issues.append('claims.claim 必须对应正文的连续原句：' + claim.get('claim', ''))
    return issues
