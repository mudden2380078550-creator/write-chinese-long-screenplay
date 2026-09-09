import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def test_standalone_skill_launcher_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'skills/write-chinese-long-screenplay'
            target.mkdir(parents=True)
            (target / 'SKILL.md').write_text('original skill', encoding='utf-8')
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/install_skill.py'), '--destination', str(target)], capture_output=True, text=True, encoding='utf-8', env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual((Path(report['backup']) / 'SKILL.md').read_text(encoding='utf-8'), 'original skill')
            run = subprocess.run([sys.executable, '-B', str(target / 'scripts/harness.py'), 'project', 'new', '--root', str(Path(tmp) / 'book'), '--title', '安装验证'], cwd=tmp, capture_output=True, text=True, encoding='utf-8', env=env)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertTrue((Path(tmp) / 'book/project.json').is_file())
            self.assertTrue((target / 'scripts/build_context.py').is_file())


if __name__ == '__main__':
    unittest.main()
