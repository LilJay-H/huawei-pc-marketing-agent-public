import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from dataset import unpack


class DatasetTests(unittest.TestCase):
    def test_unpack_preserves_utf8(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            z = base / 'data.zip'
            with zipfile.ZipFile(z, 'w') as archive:
                archive.writestr('v7/测试.md', '测试正文'.encode())
            unpack(z, base / 'v7', hashlib.sha256(z.read_bytes()).hexdigest())
            self.assertEqual((base / 'v7/测试.md').read_text(encoding='utf-8'), '测试正文')

    def test_wrong_hash_and_traversal_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            z = base / 'data.zip'
            with zipfile.ZipFile(z, 'w') as archive:
                archive.writestr('v7/../../outside.txt', 'blocked')
            with self.assertRaises(RuntimeError):
                unpack(z, base / 'v7', 'wrong')
            with self.assertRaises(RuntimeError):
                unpack(z, base / 'v7', hashlib.sha256(z.read_bytes()).hexdigest())
            self.assertFalse((base.parent / 'outside.txt').exists())
