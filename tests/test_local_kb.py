import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from local_kb import LocalKnowledgeBase
from agent import retrieve


class LocalKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.product = self.root / 'P1-产品参数库/02-MateBook-Windows/测试型号'
        self.product.mkdir(parents=True)
        (self.product / '产品事实.md').write_text('纯测试事实，不是真实产品资料。', encoding='utf-8')
        images = self.product / 'images'
        images.mkdir()
        # Minimal signature fixture; used for boundary checks, not browser rendering.
        (images / 'fixture.png').write_bytes(b'\x89PNG\r\n\x1a\nfixture')

    def tearDown(self):
        self.temp.cleanup()

    def test_lists_and_reads_local_product(self):
        kb = LocalKnowledgeBase(str(self.root))
        self.assertEqual(kb.products(), ['测试型号'])
        r = kb.retrieve({'product': '测试型号'})
        self.assertEqual(r['source_kind'], 'local_v7')
        self.assertEqual(r['product_identity'], {'directory_model': '测试型号', 'category': '02-MateBook-Windows'})
        self.assertEqual(len(r['documents']), 1)
        self.assertEqual(len(r['images']), 1)
        self.assertTrue(r['images'][0]['url'].startswith('/api/local-image?file='))

    def test_local_mode_never_calls_ima(self):
        task = dict(product='测试型号', audience='学生', scene='开学购机', platform='海报', goal='咨询', source_mode='local')
        with patch('agent.env', return_value=str(self.root)), patch('agent.Ima') as ima:
            r = retrieve(task)
        self.assertEqual(r['source_kind'], 'local_v7')
        ima.assert_not_called()

    def test_path_traversal_rejected(self):
        kb = LocalKnowledgeBase(str(self.root))
        with self.assertRaises(RuntimeError):
            kb.image('../secret.png')
        with self.assertRaises(RuntimeError):
            kb.image(str(self.product / 'images/fixture.png'))

    def test_text_cannot_be_served_as_image(self):
        kb = LocalKnowledgeBase(str(self.root))
        with self.assertRaises(RuntimeError):
            kb.image('P1-产品参数库/02-MateBook-Windows/测试型号/产品事实.md')
        (self.product / 'images/fake.png').write_text('not an image', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            kb.image('P1-产品参数库/02-MateBook-Windows/测试型号/images/fake.png')


if __name__ == '__main__':
    unittest.main()
