import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from narrative_harness import project, workflow


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / '作品'
        self.env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')

    def cli(self, *args, code=0):
        result = subprocess.run([sys.executable, '-B', '-m', 'narrative_harness', *map(str, args)], capture_output=True, text=True, encoding='utf-8', env=self.env)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_cli_end_to_end_and_no_automatic_semantic_pass(self):
        self.cli('project', 'new', '--root', self.root, '--title', '测试小说')
        config = Path(self.tmp.name) / 'config.json'
        config.write_text(json.dumps({'units': [{'id': 'c1', 'title': '开篇', 'outline': '一名旅客进城。', 'entity_ids': []}]}), encoding='utf-8')
        self.cli('project', 'configure', '--project', self.root, '--input', config)
        run = self.cli('unit', 'prepare', '--project', self.root, '--unit', 'c1')['data']
        candidate = Path(self.tmp.name) / 'draft.json'
        candidate.write_text(json.dumps({'run_id': run['id'], 'base_revision': run['base_revision'], 'draft': '旅客推开城门。他想起了母亲。', 'uses': [], 'state_changes': [], 'new_facts': []}), encoding='utf-8')
        self.cli('unit', 'submit', '--project', self.root, '--run', run['id'], '--input', candidate)
        self.cli('unit', 'check', '--project', self.root, '--run', run['id'], code=1)
        review = Path(self.tmp.name) / 'review.json'
        review.write_text(json.dumps({'verdict': 'pass', 'notes': '正文符合章纲；无状态变化或禁用能力。'}), encoding='utf-8')
        self.cli('unit', 'check', '--project', self.root, '--run', run['id'], '--review', review)
        self.cli('unit', 'accept', '--project', self.root, '--run', run['id'])
        self.cli('project', 'doctor', '--project', self.root)
        self.cli('export', '--project', self.root)
        self.assertIn('母亲', (self.root / 'exports/manuscript.md').read_text(encoding='utf-8'))

    def test_cli_errors_are_json_and_bad_command_nonzero(self):
        result = self.cli('project', 'doctor', '--project', self.root, code=2)
        self.assertFalse(result['ok'])
        result = self.cli('nonsense', code=2)
        self.assertEqual(result['code'], 'ARGUMENT_ERROR')

    def test_legacy_migration_preserves_original_and_marks_unknown_history(self):
        legacy = Path(self.tmp.name) / 'legacy'
        legacy.mkdir()
        (legacy / 'project.md').write_text('---\ntitle: 旧作品\nformat: series\nschema_version: 2\n---\n', encoding='utf-8')
        scenes = legacy / 'screenplay/scenes'
        scenes.mkdir(parents=True)
        raw = '---\nid: E001-S001\n---\n# 第一场\n\n## 正文\n\n△ 门开了。\n'
        (scenes / 'E001-S001.md').write_text(raw, encoding='utf-8')
        self.cli('project', 'migrate', '--source', legacy, '--root', self.root)
        self.assertEqual((scenes / 'E001-S001.md').read_text(encoding='utf-8'), raw)
        self.assertEqual((self.root / 'sources/legacy/screenplay/scenes/E001-S001.md').read_text(encoding='utf-8'), raw)
        data = project.load(self.root)
        self.assertTrue(data['metadata']['accepted']['E001-S001']['history_unknown'])
        project.doctor(self.root)

    def test_migration_pending_requires_explicit_review(self):
        legacy = Path(self.tmp.name) / 'old'
        (legacy / 'harness').mkdir(parents=True)
        (legacy / 'project.md').write_text('---\ntitle: 旧作\nformat: series\n---\n', encoding='utf-8')
        (legacy / 'harness/abilities.json').write_text(json.dumps({'items': [{'id': 'a', 'name': '影步'}]}), encoding='utf-8')
        report = self.cli('project', 'migrate', '--source', legacy, '--root', self.root)['data']
        self.assertTrue(project.load(self.root)['metadata']['migration_pending'])
        review = Path(self.tmp.name) / 'migration-review.json'
        review.write_text(json.dumps({'verdict': 'pass', 'notes': '旧影步经作者决定不纳入此修订；原件仍保留。',
                                      'resolved_files': [entry['file'] for entry in report['unresolved']]}), encoding='utf-8')
        self.cli('project', 'migration-confirm', '--project', self.root, '--review', review)
        self.assertFalse(project.load(self.root)['metadata']['migration_pending'])


if __name__ == '__main__':
    unittest.main()
