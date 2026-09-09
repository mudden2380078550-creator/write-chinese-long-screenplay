import copy
from pathlib import Path
from uuid import uuid4

from . import __version__, SCHEMA_VERSION
from .errors import require
from .models import validate_state, identifier, text
from .storage import inside, encode, digest, read_json, write_json, atomic_text
from . import transactions


def create(root, title, format_name='novel'):
    root = Path(root).resolve()
    text(title, 'title')
    require(format_name in {'novel', 'feature', 'series', 'short-drama', 'animation'}, '未知载体')
    require(not root.exists() or (root.is_dir() and not any(root.iterdir())), '目标项目必须不存在或为空')
    root.mkdir(parents=True, exist_ok=True)
    metadata = {'schema_version': SCHEMA_VERSION, 'id': 'book-' + uuid4().hex, 'title': title,
                'format': format_name, 'revision': 'rev-' + uuid4().hex, 'units': [],
                'accepted': {}, 'receipts': {}, 'events': [], 'files': {}}
    files = {
        'harness.lock.json': encode({'tool': 'narrative-harness', 'version': __version__, 'schema_version': SCHEMA_VERSION}),
        'canon/history/initial.json': encode({'entities': {}, 'policies': {}}),
        'AGENTS.md': '# 创作项目\n\n通过 harness 准备上下文、提交候选、检查并接受正文。\n正式状态由 canon/ 保存；作者政策独立保存在 canon/policies/。\n不要直接改 project.json、canon/ 或 manuscript/；通过提案更新。\n小说允许心理叙述和引号对白；剧本按相应场次规则写作。\n',
    }
    for relative, content in files.items():
        atomic_text(inside(root, relative), content)
        metadata['files'][relative] = digest(content)
    write_json(inside(root, 'project.json'), metadata)
    atomic_text(inside(root, '.gitignore'), '.harness/\nexports/\n__pycache__/\n')
    return {'id': metadata['id'], 'revision': metadata['revision'], 'root': str(root)}


def load(root):
    root = Path(root).resolve()
    transactions.ensure_clean(root)
    metadata = read_json(inside(root, 'project.json'))
    require(isinstance(metadata, dict) and metadata.get('schema_version') == SCHEMA_VERSION, '需要schema v3项目；旧项目先迁移')
    require(isinstance(metadata.get('files'), dict), '缺少文件清单')
    require(isinstance(metadata.get('units'), list) and len(set(metadata['units'])) == len(metadata['units']), '无效章节排序清单')
    require(isinstance(metadata.get('accepted'), dict) and isinstance(metadata.get('events'), list) and isinstance(metadata.get('receipts'), dict), '无效接受/历史清单')
    for uid, accepted in metadata['accepted'].items():
        require(uid in metadata['units'] and isinstance(accepted, dict), '接受记录没有对应章节')
        require(accepted.get('file') == f'manuscript/{uid}.md' and accepted['file'] in metadata['files'], '接受记录正文路径无效')
        eid = identifier(accepted.get('event_id'))
        require(eid in metadata['events'] and f'canon/history/{eid}.json' in metadata['files'], '接受记录历史事件缺失')
    entities, policies = {}, {}
    for relative, expected in metadata['files'].items():
        path = inside(root, relative)
        require(path.is_file() and digest(path.read_text(encoding='utf-8')) == expected,
                f'文件在正式提交之外发生改变：{relative}', 'WORKSPACE_CHANGED', 3)
        collection = entities if relative.startswith('canon/entities/') else policies if relative.startswith('canon/policies/') else None
        if collection is not None:
            value = read_json(path)
            require(isinstance(value, dict) and value.get('id') == path.stem, '实体文件名与ID不符')
            require(value['id'] not in collection, '重复实体ID')
            collection[value['id']] = value
    for directory in ('canon', 'outline', 'manuscript'):
        folder = root / directory
        if folder.exists():
            for path in folder.rglob('*'):
                if path.is_file():
                    relative = path.relative_to(root).as_posix()
                    require(relative in metadata['files'], f'未追踪的正式文件：{relative}', 'WORKSPACE_CHANGED', 3)
    units = [read_json(inside(root, f'outline/{identifier(uid)}.json')) for uid in metadata['units']]
    validate_state(entities, policies, units)
    for uid, accepted in metadata['accepted'].items():
        event = read_json(inside(root, f"canon/history/{accepted['event_id']}.json"))
        require(event.get('unit_id') == uid and event.get('kind') in {'unit-accept', 'legacy-accept'}, '接受记录与历史事件不一致')
        draft = inside(root, accepted['file']).read_text(encoding='utf-8').rstrip('\n')
        require(digest(draft) == event['draft_hash'], '正文与接受事件哈希不一致')
    lock_data = read_json(inside(root, 'harness.lock.json'))
    require(lock_data.get('version') == __version__ and lock_data.get('schema_version') == SCHEMA_VERSION, '工具版本与作品锁不兼容')
    # Recheck manifest and pending so a concurrent writer cannot return a mixed view.
    transactions.ensure_clean(root)
    require(read_json(inside(root, 'project.json'))['revision'] == metadata['revision'], '读取期间项目已改变', 'REVISION_CONFLICT', 3)
    return {'root': root, 'metadata': metadata, 'id': metadata['id'], 'revision': metadata['revision'],
            'entities': entities, 'policies': policies, 'units': units}


def snapshot(data):
    return copy.deepcopy({'entities': data['entities'], 'policies': data['policies']})


def configure(root, entities=None, policies=None, units=None, expected_revision=None, acceptance_id=None, extra_files=None):
    """Explicit author configuration; ordinary draft changes use workflow.accept."""
    current = load(root)
    metadata = copy.deepcopy(current['metadata'])
    updated = snapshot(current)
    changes = dict(extra_files or {})
    for values, kind in ((entities, 'entities'), (policies, 'policies')):
        if values is None:
            continue
        require(isinstance(values, list), f'{kind}必须为数组')
        seen = set()
        for item in values:
            require(isinstance(item, dict), '条目必须是对象')
            key = identifier(item.get('id'))
            require(key not in seen, '输入包含重复ID')
            seen.add(key)
            updated[kind][key] = copy.deepcopy(item)
            changes[f'canon/{kind}/{key}.json'] = encode(item)
    new_units = current['units'] if units is None else copy.deepcopy(units)
    validate_state(updated['entities'], updated['policies'], new_units)
    if units is not None:
        old_ids = metadata['units']
        new_ids = [u['id'] for u in units]
        require(new_ids[:len(old_ids)] == old_ids, '现有章节ID及顺序不可静默改变；可更新章纲或追加章节')
        metadata['units'] = new_ids
        for unit in units:
            changes[f"outline/{unit['id']}.json"] = encode(unit)
    if metadata['accepted']:
        # A conservative impact boundary: existing chapters require explicit revalidation.
        for accepted in metadata['accepted'].values():
            accepted['needs_revalidation'] = True
    event_id = 'event-' + uuid4().hex
    event = {'id': event_id, 'kind': 'author-config', 'base_revision': current['revision'],
             'before': snapshot(current), 'after': updated}
    changes[f'canon/history/{event_id}.json'] = encode(event)
    metadata['events'].append(event_id)
    return transactions.commit(root, expected_revision or current['revision'], changes, metadata, acceptance_id=acceptance_id)


def doctor(root):
    data = load(root)
    state = read_json(inside(root, 'canon/history/initial.json'))
    for event_id in data['metadata']['events']:
        event = read_json(inside(root, f'canon/history/{identifier(event_id)}.json'))
        require(event['before'] == state, '历史事件链与前置状态不一致', 'HISTORY_CONFLICT', 3)
        state = event['after']
    require(state == snapshot(data), '历史重放与当前实体状态不一致', 'HISTORY_CONFLICT', 3)
    return {'id': data['id'], 'revision': data['revision'], 'entities': len(data['entities']),
            'units': len(data['units']), 'accepted': len(data['metadata']['accepted']),
            'needs_revalidation': [k for k, v in data['metadata']['accepted'].items() if v.get('needs_revalidation')]}
