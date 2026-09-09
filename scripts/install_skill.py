"""Install a self-contained skill copy, backing up existing files first."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '.git')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--backup-root', type=Path)
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination == ROOT or destination.is_relative_to(ROOT) or ROOT.is_relative_to(destination):
        raise ValueError('安装目标必须独立于工具源码')
    if destination.exists() and not destination.is_dir():
        raise ValueError('安装目标不是目录')
    with tempfile.TemporaryDirectory(prefix='harness-install-') as tmp:
        stage = Path(tmp) / 'skill'
        shutil.copytree(ROOT / 'legacy', stage, ignore=IGNORE)
        shutil.copytree(ROOT / 'integrations/write-chinese-long-screenplay', stage, dirs_exist_ok=True, ignore=IGNORE)
        shutil.copytree(ROOT / 'src/narrative_harness', stage / 'scripts/_vendor/narrative_harness', ignore=IGNORE)
        check = subprocess.run([sys.executable, '-B', str(stage / 'scripts/harness.py'), '--version'], capture_output=True)
        if check.returncode:
            raise ValueError(check.stderr.decode('utf-8', errors='replace'))
        backup = None
        if destination.exists():
            backup_root = (args.backup_root or destination.parent / '.harness-backups').resolve()
            if backup_root.is_relative_to(destination):
                raise ValueError('备份不能放在待备份的Skill目录内')
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            backup = backup_root / (destination.name + '-' + stamp + '-' + uuid4().hex[:8])
            shutil.copytree(destination, backup, ignore=IGNORE)
        shutil.copytree(stage, destination, dirs_exist_ok=True, ignore=IGNORE)
        print(json.dumps({'installed': str(destination), 'backup': str(backup) if backup else None}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
