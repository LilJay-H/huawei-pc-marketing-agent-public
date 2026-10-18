"""Read-only adapter for an explicitly configured local knowledge-base copy."""
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from dataset import ROOT, prepare_bundled_dataset


def canonical(value):
    return re.sub(r'[\s_\-·（）()]', '', value).lower()


class LocalKnowledgeBase:
    def __init__(self, root):
        configured = Path(root).expanduser() if root else None
        self.root = ((Path(__file__).resolve().parent / configured).resolve() if configured and not configured.is_absolute()
                     else configured.resolve() if configured else None)
        if self.root == ROOT / 'knowledge-base/v7' and not (self.root / 'P1-产品参数库').is_dir():
            prepare_bundled_dataset()
        if not self.root or not (self.root / 'P1-产品参数库').is_dir():
            raise RuntimeError('本地知识库未配置或无效，请设置 LOCAL_KB_PATH 指向包含 P1-产品参数库 的目录。')

    def safe_file(self, path):
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root) or not resolved.is_file():
            raise RuntimeError('文件不在配置的知识库范围内。')
        return resolved

    def product_dirs(self):
        result = []
        p1 = self.root / 'P1-产品参数库'
        for section in p1.iterdir():
            if section.is_dir() and section.name.startswith(('01-', '02-', '03-')):
                for product in section.iterdir():
                    if product.is_dir() and product.resolve().is_relative_to(self.root):
                        if (product / '产品事实.md').is_file() or (product / 'article.md').is_file():
                            result.append(product)
        return sorted(result)

    def products(self):
        return [p.name for p in self.product_dirs()]

    def retrieve(self, task):
        candidates = [p for p in self.product_dirs() if canonical(p.name) == canonical(task['product'])]
        if len(candidates) != 1:
            raise RuntimeError('本地库中无法唯一定位型号，请使用本地型号列表中的准确名称。')
        product = candidates[0]
        documents, images, warnings, modified = [], [], [], []
        for p in sorted(product.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in ['.md', '.txt', '.csv', '.png', '.jpg', '.jpeg', '.webp']:
                continue
            safe = self.safe_file(p)
            relative = safe.relative_to(self.root).as_posix()
            item = {'title': safe.name, 'source': '本地副本 / ' + self.root.name + ' / ' + relative}
            modified.append(safe.stat().st_mtime)
            if safe.suffix.lower() in ['.md', '.txt', '.csv']:
                if safe.stat().st_size > 300000:
                    warnings.append('跳过超过300KB的文本：' + safe.name)
                    continue
                try:
                    item.update(id='D' + str(len(documents) + 1), image=False, text=safe.read_text(encoding='utf-8-sig'))
                    documents.append(item)
                except UnicodeError:
                    warnings.append('无法按UTF-8读取：' + safe.name)
            else:
                item.update(id='I' + str(len(images) + 1), image=True,
                            url='/api/local-image?file=' + quote(relative, safe=''))
                images.append(item)
        return {'status': 'retrieved', 'task': task, 'documents': documents, 'images': images,
                'product_identity': {'directory_model': product.name, 'category': product.parent.name},
                'warnings': warnings, 'search_hits': 0, 'source_kind': 'local_v7',
                'knowledge_base': self.root.name, 'source_note': '本地开发资料，不是本次 ima OpenAPI 检索；是否与远端最新版本一致尚未验证。',
                'snapshot_modified_at': datetime.fromtimestamp(max(modified), timezone.utc).isoformat() if modified else None}

    def image(self, relative):
        if not relative or Path(relative).is_absolute():
            raise RuntimeError('图片路径无效。')
        path = self.safe_file(self.root / relative)
        if path.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp'] or path.stat().st_size > 20000000:
            raise RuntimeError('不支持的图片类型或大小。')
        raw = path.read_bytes()
        signatures = {'.png': raw.startswith(b'\x89PNG\r\n\x1a\n'), '.jpg': raw.startswith(b'\xff\xd8\xff'),
                      '.jpeg': raw.startswith(b'\xff\xd8\xff'), '.webp': raw[:4] == b'RIFF' and raw[8:12] == b'WEBP'}
        if not signatures[path.suffix.lower()]:
            raise RuntimeError('图片内容与文件扩展名不符。')
        return raw, mimetypes.guess_type(path.name)[0]
