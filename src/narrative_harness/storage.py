import hashlib
import json
import os
import tempfile
from pathlib import Path

from .errors import require, HarnessError


def encode(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'


def digest(value):
    if not isinstance(value, str):
        value = encode(value)
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f'重复JSON键：{key}')
        result[key] = value
    return result


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=_pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (OSError, UnicodeError, ValueError) as exc:
        raise HarnessError('INVALID_JSON', f'{path}: {exc}') from exc


def inside(root, relative):
    root = Path(root).resolve()
    relative = str(relative)
    require(relative and '\\' not in relative and not Path(relative).is_absolute(), '需要项目相对POSIX路径')
    require(all(part not in ('..', '.', '') for part in relative.split('/')), '非法相对路径')
    target = (root / relative).resolve()
    require(target.is_relative_to(root) and target != root, f'路径越界：{relative}')
    return target


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.harness-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path, data):
    atomic_text(path, encode(data))
