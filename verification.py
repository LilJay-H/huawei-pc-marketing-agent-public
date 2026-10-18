"""Deterministic evidence checks; no network or model calls."""
import csv
import io
import re
from pathlib import PurePosixPath


def canonical_model(value):
    return re.sub(r'[\s_\-·（）()]', '', value).lower().replace('huawei', '').replace('华为', '')


def image_checks(evidence, plan):
    rows = {}
    for doc in evidence.get('documents', []):
        if doc.get('title') == '图片索引.csv':
            for row in csv.DictReader(io.StringIO(doc['text'])):
                rows[row.get('文件名', '')] = row
    images = {x['id']: x for x in evidence.get('images', [])}
    target = canonical_model(evidence['task'].get('product', ''))
    version = evidence['task'].get('version', '').strip()
    identity = evidence.get('product_identity', {})
    # A local directory explicitly identifies the OS family. Never strip OS names
    # globally: a Windows product or unscoped ima result must not match HarmonyOS.
    harmony_directory = (evidence.get('source_kind') == 'local_v7'
                         and identity.get('category') == '01-鸿蒙电脑'
                         and canonical_model(identity.get('directory_model', '')) == target)
    checks = []
    for selected in plan:
        image = images.get(selected.get('image_id'))
        row = rows.get(PurePosixPath((image or {}).get('title', '')).name)
        status, reason = 'unverified', '缺少本次 ima 返回的图片索引，无法核对图片型号'
        if not image:
            status, reason = 'mismatch', '图片不在本次 ima 检索结果中'
        elif row:
            indexed = canonical_model(row.get('产品型号', ''))
            comparison_target = target + '鸿蒙版' if harmony_directory and indexed == target + '鸿蒙版' else target
            # Year can be checked; SKU/OS/colour/visual correctness remain human checks.
            indexed_base = re.sub(r'20\d{2}', '', indexed)
            target_base = re.sub(r'20\d{2}', '', comparison_target)
            years = re.findall(r'20\d{2}', target + version)
            indexed_years = re.findall(r'20\d{2}', indexed)
            if not indexed:
                reason = '图片索引缺少产品型号字段，需补齐型号后核验，不能仅凭所在目录确认'
            elif indexed_base != target_base or (years and indexed_years and set(years) != set(indexed_years)):
                status, reason = 'mismatch', '图片索引中的型号或年份与任务不一致'
            elif indexed_years and not years:
                reason = '图片对应 ' + '/'.join(indexed_years) + ' 款，请补充任务年份后确认'
            elif re.sub(r'20\d{2}|年|款|\s', '', version):
                reason = '任务包含具体配置或系统版本，当前图片索引不足以确认，请人工核对'
            else:
                status, reason = 'catalog_match', '型号/年份与本次 ima 图片索引相符；SKU、画面与授权仍需人工确认'
        checks.append({'image_id': selected.get('image_id'), 'title': (image or {}).get('title', ''),
                       'status': status, 'reason': reason, 'indexed_model': (row or {}).get('产品型号', ''),
                       'source_page': (row or {}).get('来源页面', '')})
    return checks


def compliance_checks(text):
    findings = []
    for pattern, reason in [
        (r'全网最低|绝对领先|永不卡顿|唯一选择|行业第一|吊打|最强|百分百|100%保证', '绝对化或无依据比较'),
        (r'(?:亲测|实测|我用了\d)', '体验或测试表述需要真实依据'),
        (r'(?:[¥￥]\s*\d[\d,.]*|\d[\d,.]*\s*元|\d+(?:\.\d+)?折|立减\s*\d)', '价格/权益需核对SKU、原文及有效期，本版标记人工复核'),
    ]:
        for match in re.finditer(pattern, text):
            findings.append({'text': match.group(), 'reason': reason, 'status': 'needs_review'})
    for sentence in re.split(r'[。！？\n]', text):
        if re.search(r'补贴|国补|教育优惠|免费赠送', sentence) and not re.search(r'未|不|无|待|核实|确认|咨询|为准', sentence):
            findings.append({'text': sentence[:160], 'reason': '优惠或补贴缺少有效期核验，需人工复核', 'status': 'needs_review'})
    return findings
