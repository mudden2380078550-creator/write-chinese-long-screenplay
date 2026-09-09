"""Single-host locking and recoverable, optimistic multi-file commits."""
import copy
import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .errors import require, HarnessError
from .storage import read_json, encode, digest, inside, atomic_text, write_json

replace_file = atomic_text


@contextmanager
def lock(root):
    path = inside(root, '.harness/writer.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = open(path, 'a+b')
    stream.seek(0, 2)
    if stream.tell() == 0:
        stream.write(b'0')
        stream.flush()
    stream.seek(0)
    acquired = False
    try:
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise HarnessError('PROJECT_BUSY', '项目有其他写者，请稍后重试', 3) from exc
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


def ensure_clean(root):
    require(not inside(root, '.harness/pending.json').exists(), '存在未完成事务，先运行 project recover', 'RECOVERY_REQUIRED', 4)


def commit(root, expected_revision, changes, metadata, acceptance_id=None):
    from .project import load
    root = Path(root).resolve()
    with lock(root):
        ensure_clean(root)
        current = load(root)
        receipts = current['metadata'].get('receipts', {})
        if acceptance_id and acceptance_id in receipts:
            return receipts[acceptance_id]
        require(current['revision'] == expected_revision, '项目修订已改变，请重新准备上下文', 'REVISION_CONFLICT', 3)
        new = copy.deepcopy(metadata)
        new['revision'] = 'rev-' + uuid4().hex
        hashes = dict(current['metadata']['files'])
        for relative, content in changes.items():
            inside(root, relative)
            require(relative != 'project.json' and not relative.startswith('.harness/'), '不能直接改项目控制文件')
            require(isinstance(content, str), '事务内容必须为文本')
            hashes[relative] = digest(content)
        new['files'] = hashes
        receipt = {'revision': new['revision'], 'acceptance_id': acceptance_id}
        if acceptance_id:
            new.setdefault('receipts', {})[acceptance_id] = receipt
        after = dict(changes)
        after['project.json'] = encode(new)
        before = {}
        for relative in after:
            path = inside(root, relative)
            before[relative] = path.read_text(encoding='utf-8') if path.is_file() else None
        journal = {'old_revision': expected_revision, 'new_revision': new['revision'], 'before': before, 'after': after}
        pending = inside(root, '.harness/pending.json')
        write_json(pending, journal)
        # The manifest is replaced last. Until then readers see pending and stop.
        for relative, content in after.items():
            replace_file(inside(root, relative), content)
        pending.unlink()
        return receipt


def recover(root):
    root = Path(root).resolve()
    with lock(root):
        pending = inside(root, '.harness/pending.json')
        if not pending.exists():
            return {'status': 'clean'}
        journal = read_json(pending)
        manifest = read_json(inside(root, 'project.json'))
        require(manifest['revision'] in (journal['old_revision'], journal['new_revision']), '修订与恢复记录不一致', 'RECOVERY_CONFLICT', 4)
        if manifest['revision'] == journal['new_revision']:
            for relative, content in journal['after'].items():
                require(inside(root, relative).read_text(encoding='utf-8') == content, '提交后文件不完整，需人工检查', 'RECOVERY_CONFLICT', 4)
            result = 'completed'
        else:
            # Refuse to destroy a third party edit made after interruption.
            for relative, previous in journal['before'].items():
                path = inside(root, relative)
                actual = path.read_text(encoding='utf-8') if path.is_file() else None
                require(actual in (previous, journal['after'][relative]), f'恢复期间发现外部编辑：{relative}', 'RECOVERY_CONFLICT', 4)
            for relative, previous in journal['before'].items():
                path = inside(root, relative)
                if previous is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_text(path, previous)
            result = 'rolled_back'
        pending.unlink()
        return {'status': result}
