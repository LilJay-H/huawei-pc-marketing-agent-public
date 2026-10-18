import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import agent


class TeamConfigTests(unittest.TestCase):
    def test_team_file_fills_blank_template_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.env').write_text('LLM_API_KEY=\nDEFAULT_SOURCE_MODE=local\n', encoding='utf-8')
            (root / '.env.team').write_text('LLM_API_KEY=test-only-private\n', encoding='utf-8')
            with patch.object(agent, 'ROOT', root), patch.dict(os.environ, {}, clear=True):
                agent.load_dotenv()
                self.assertEqual(os.environ['LLM_API_KEY'], 'test-only-private')
                self.assertEqual(os.environ['DEFAULT_SOURCE_MODE'], 'local')

    def test_process_and_personal_config_take_precedence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.env').write_text('LLM_API_KEY=personal-test\n', encoding='utf-8')
            (root / '.env.team').write_text('LLM_API_KEY=team-test\n', encoding='utf-8')
            with patch.object(agent, 'ROOT', root), patch.dict(os.environ, {}, clear=True):
                agent.load_dotenv()
                self.assertEqual(os.environ['LLM_API_KEY'], 'personal-test')
            with patch.object(agent, 'ROOT', root), patch.dict(os.environ, {'LLM_API_KEY': 'process-test'}, clear=True):
                agent.load_dotenv()
                self.assertEqual(os.environ['LLM_API_KEY'], 'process-test')
