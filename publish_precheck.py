"""Local candidate scan + structured semantic verdicts; never a platform approval."""
import json
import re
from datetime import date
from pathlib import Path

RULE_FILE = Path(__file__).resolve().parent / 'harness' / 'publish-rules.json'


def scan(draft, platform, today=None):
    rules = json.loads(RULE_FILE.read_text(encoding='utf-8'))
    today = today or date.today().isoformat()
    candidates = []
    fields = [('markdown', draft['markdown'])] + [
        ('image_plan.' + str(i) + '.caption', item.get('caption', ''))
        for i, item in enumerate(draft.get('image_plan', []))]
    for field, content in fields:
        for rule in rules['terms']:
            # XHS contact/engagement policies must not be applied to all platforms.
            if rule['rule'].endswith(('.R05', '.R10', '.R12')) and platform != '小红书':
                continue
            for match in re.finditer(rule['pattern'], content, re.I):
                candidates.append({'id': 'C' + str(len(candidates) + 1), 'field': field,
                    'start': match.start(), 'end': match.end(), 'text': match.group(),
                    'context': content[max(0, match.start()-50):match.end()+50],
                    'rule_id': rule['rule'], 'title': rule['title'], 'severity_hint': rule['severity']})
    semantic = [r for r in rules['semantic_rules'] if r['scope'] == 'common' or platform == '小红书']
    return {'version': rules['version'], 'sources': rules['upstreams'], 'candidates': candidates,
            'semantic_rules': semantic, 'rule_review_due': [r['id'] for r in semantic if r.get('review_after', today) < today],
            'coverage': ['标题与正文文本', '配图说明文本'],
            'not_checked': ['图片实际像素与图中文字', '发布页商业合作/AI声明设置', '账号状态', '平台现行规则实时核验'],
            'status': 'awaiting_semantic_review', 'findings': [],
            'note': '第三方规则快照，仅用于发布前预检；零命中不代表平台一定通过。'}


def finish(report, findings):
    """Require one grounded decision for every candidate; omission fails closed."""
    if not isinstance(findings, list):
        raise RuntimeError('发布预检缺少逐项语境判定，停止交付。')
    candidates = {x['id']: x for x in report['candidates']}
    seen, issues = set(), []
    for finding in findings:
        if not isinstance(finding, dict):
            raise RuntimeError('发布预检判定格式无效。')
        key = finding.get('candidate_id')
        if key not in candidates or key in seen or finding.get('decision') not in ['allow', 'revise', 'uncertain']:
            raise RuntimeError('发布预检候选编号或结论无效。')
        if not isinstance(finding.get('reason'), str) or not finding['reason'].strip():
            raise RuntimeError('发布预检缺少判断理由。')
        if not isinstance(finding.get('suggestion', ''), str):
            raise RuntimeError('发布预检修改建议格式无效。')
        seen.add(key)
        if finding['decision'] != 'allow':
            if not finding.get('suggestion', '').strip():
                raise RuntimeError('发布预检缺少修改或补证建议。')
            c = candidates[key]
            issues.append('发布预检：' + c['text'] + '；' + finding['reason'] + '；' + finding['suggestion'])
    if seen != set(candidates):
        raise RuntimeError('发布预检遗漏候选词句，停止交付。')
    report['findings'] = [{**candidates[f['candidate_id']], **f} for f in findings]
    report['status'] = 'needs_review' if issues else 'text_review_complete'
    return issues


REVIEW_PROMPT = '''发布预检：publish_precheck.candidates 是词面候选，不能见词就判违规。
结合全文、商业目的和产品原文逐条判断。100% sRGB 等有依据参数、否定/反例、正常提到微信，不自动判成承诺或导流。
不因为面向大学生就套用教育培训准入；不把视频号规则套给朋友圈/公众号。
semantic_rules 是带日期的第三方规则摘要，不是本次已核实的官方法律结论；过期或 source_pending 规则只作待核线索。
同时通读正文与图片说明，检查无关键词的虚构体验、夸张效果、标题不一致和诱导行为。缺实际画面不能声称已审图。
返回原有 issues 数组，并增加 precheck_findings 数组，每个候选恰好一条：
{"candidate_id":"C1","decision":"allow|revise|uncertain","reason":"结合上下文的具体理由","suggestion":"需改时给保留原意的具体修改或补证建议"}。
无候选返回空数组。全文发现的其他真实问题放 issues。不得通过谐音、拆字规避；不虚构现行官方条款或已获授权。'''
