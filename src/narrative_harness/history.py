import copy

from . import project
from .errors import require
from .storage import inside, read_json, encode


def before(root, unit_id):
    data = project.load(root)
    require(unit_id in data['metadata']['units'], '未知章节')
    accepted = data['metadata']['accepted'].get(unit_id)
    if accepted:
        require(not accepted.get('history_unknown'), '迁移前的写前状态未知，不能用当前状态反推', 'HISTORY_UNKNOWN')
        event = read_json(inside(root, f"canon/history/{accepted['event_id']}.json"))
        return copy.deepcopy(event.get('unit_before', event['before']))
    index = data['metadata']['units'].index(unit_id)
    require(all(uid in data['metadata']['accepted'] for uid in data['metadata']['units'][:index]), '先完成前序章节，再准备后续章节')
    return project.snapshot(data)


def impact(root, entity_ids):
    data = project.load(root)
    entities = set(entity_ids)
    units = [u['id'] for u in data['units'] if entities.intersection(u.get('entity_ids', []))]
    # Also inspect historical selections; outlines need not list every dependency.
    for uid, accepted in data['metadata']['accepted'].items():
        if entities.intersection(accepted.get('selected_entities', [])) and uid not in units:
            units.append(uid)
    return {'direct_units': units, 'downstream_units': data['metadata']['units'][min((data['metadata']['units'].index(u) for u in units), default=len(data['units'])):]}


def fork(root, destination, unit_id):
    """Create an independent revision workspace at a known chapter boundary."""
    from pathlib import Path
    from uuid import uuid4
    from .models import validate_state
    from . import transactions
    root, destination = Path(root).resolve(), Path(destination).resolve()
    require(not destination.is_relative_to(root) and not root.is_relative_to(destination), '修订副本必须使用独立目录')
    data = project.load(root)
    view = before(root, unit_id)
    # Do not discard current author policies or invent future entities to satisfy references.
    validate_state(view['entities'], data['policies'], data['units'])
    project.create(destination, data['metadata']['title'] + '（修订）', data['metadata']['format'])
    project.configure(destination, entities=list(view['entities'].values()), policies=list(data['policies'].values()), units=data['units'])
    branch = project.load(destination)
    metadata = copy.deepcopy(branch['metadata'])
    metadata['parent_project'] = {'id': data['id'], 'revision': data['revision'], 'before_unit': unit_id}
    changes = {}
    # Archive the parent manifest and every managed text file, including original drafts.
    changes['sources/parent/project.json'] = encode(data['metadata'])
    for relative in data['metadata']['files']:
        changes['sources/parent/' + relative] = inside(root, relative).read_text(encoding='utf-8')
    branch_state = project.snapshot(branch)
    for uid in data['metadata']['units'][:data['metadata']['units'].index(unit_id)]:
        accepted = copy.deepcopy(data['metadata']['accepted'][uid])
        old_event = read_json(inside(root, f"canon/history/{accepted['event_id']}.json"))
        eid = 'event-' + uuid4().hex
        new_event = copy.deepcopy(old_event)
        new_event.update(id=eid, before=branch_state, after=branch_state,
                         unit_before=old_event.get('unit_before', old_event['before']),
                         unit_after=old_event.get('unit_after', old_event['after']), inherited=True)
        changes[f'canon/history/{eid}.json'] = encode(new_event)
        for suffix in ('candidate', 'report'):
            source_path = inside(root, f"canon/history/{accepted['event_id']}-{suffix}.json")
            if source_path.exists():
                changes[f'canon/history/{eid}-{suffix}.json'] = source_path.read_text(encoding='utf-8')
        changes[accepted['file']] = inside(root, accepted['file']).read_text(encoding='utf-8')
        accepted['event_id'] = eid
        metadata['events'].append(eid)
        metadata['accepted'][uid] = accepted
    result = transactions.commit(destination, branch['revision'], changes, metadata)
    return dict(result, root=str(destination), parent_project=data['id'], before_unit=unit_id)
