"""Copy-only v2 migration. Missing history is explicitly not invented."""
import copy
import hashlib
import re
import shutil
from pathlib import Path
from uuid import uuid4

from . import project, transactions
from .errors import require
from .storage import inside, read_json, encode, digest, write_json


def migrate(source, root, title=None):
    source, root = Path(source).resolve(), Path(root).resolve()
    require(source.is_dir() and (source / 'project.md').is_file(), '来源不是旧剧本项目')
    require(not root.is_relative_to(source) and not source.is_relative_to(root), '来源与目标目录必须彼此独立')
    raw_meta = (source / 'project.md').read_text(encoding='utf-8-sig')
    match = re.search(r'^format:\s*(.+)$', raw_meta, re.M)
    format_name = match.group(1).strip().strip('"\'') if match else 'series'
    match = re.search(r'^title:\s*(.+)$', raw_meta, re.M)
    old_title = match.group(1).strip().strip('"\'') if match else source.name
    project.create(root, title or old_title, format_name)
    archive = root / 'sources/legacy'
    hashes = {}
    for path in source.rglob('*'):
        relative = path.relative_to(source)
        if any(p in {'.git', '__pycache__', '.harness'} for p in relative.parts):
            continue
        require(not path.is_symlink(), f'迁移不跟随符号链接：{relative}')
        if path.is_file():
            target = inside(archive, relative.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            hashes[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    scenes = sorted((source / 'screenplay/scenes').glob('*.md'))
    scenes = [p for p in scenes if re.fullmatch(r'(?:E\d{3}-)?S\d{3}\.md', p.name)]
    units = [{'id': p.stem, 'title': p.stem, 'outline': '迁移原场次；改写前由作者补充章纲。', 'entity_ids': []} for p in scenes]
    project.configure(root, units=units)
    current = project.load(root)
    metadata = copy.deepcopy(current['metadata'])
    changes, state = {}, project.snapshot(current)
    for path in scenes:
        raw = path.read_text(encoding='utf-8-sig')
        match = re.search(r'^## 正文\s*\n(.*?)(?=^## |\Z)', raw, re.M | re.S)
        require(match is not None and match.group(1).strip(), f'无法识别正文：{path.name}；原文件已归档')
        draft = match.group(1).strip()
        eid = 'event-' + uuid4().hex
        event = {'id': eid, 'kind': 'legacy-accept', 'unit_id': path.stem, 'before': state, 'after': state,
                 'draft_hash': digest(draft), 'history_unknown': True}
        changes[f'canon/history/{eid}.json'] = encode(event)
        changes[f'manuscript/{path.stem}.md'] = draft + '\n'
        metadata['events'].append(eid)
        metadata['accepted'][path.stem] = {'file': f'manuscript/{path.stem}.md', 'event_id': eid,
                                         'history_unknown': True, 'needs_revalidation': False,
                                         'selected_entities': [], 'source_file': f'sources/legacy/screenplay/scenes/{path.name}'}
    unresolved = []
    for path in (source / 'harness').glob('*.json'):
        data = read_json(path)
        if isinstance(data, dict) and data.get('items'):
            unresolved.append({'file': f'sources/legacy/harness/{path.name}', 'reason': '旧条目须区分实体与作者政策，保留原文待审定'})
    report = {'original_title': old_title, 'source_hashes': hashes, 'copied_scenes': len(scenes),
              'history': 'unknown-before-migration', 'unresolved': unresolved,
              'note': '正文已抽取，原始场次字节完整归档；没有根据当前状态编造历史。旧harness需作为导入提案审定。'}
    changes['canon/history/migration-report.json'] = encode(report)
    metadata['migration_pending'] = bool(unresolved)
    transactions.commit(root, current['revision'], changes, metadata)
    return report


def confirm(root, review):
    from .models import object_keys
    current = project.load(root)
    require(current['metadata'].get('migration_pending'), '没有待确认的迁移')
    object_keys(review, {'verdict', 'notes', 'resolved_files'}, 'migration_review')
    require(review.get('verdict') == 'pass' and isinstance(review.get('notes'), str) and review['notes'].strip(), '需要说明旧条目的采用、重构或舍弃决定')
    report = read_json(inside(root, 'canon/history/migration-report.json'))
    require(isinstance(review.get('resolved_files'), list) and set(review['resolved_files']) == {x['file'] for x in report['unresolved']}, '必须明确覆盖全部待审旧资料文件')
    metadata = copy.deepcopy(current['metadata'])
    metadata['migration_pending'] = False
    review_id = 'migration-review-' + uuid4().hex
    return transactions.commit(root, current['revision'], {f'canon/history/{review_id}.json': encode(review)}, metadata)
