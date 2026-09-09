import copy

from .errors import require
from .models import object_keys, identifier, validate_state, number


def apply_candidate(view, candidate, unit, units):
    after = copy.deepcopy(view)
    entities = after['entities']
    for use in candidate['uses']:
        object_keys(use, {'entity_id', 'evidence', 'count'}, 'use')
        eid = identifier(use.get('entity_id'))
        require(eid in entities, f'使用未知实体：{eid}')
        require(isinstance(use.get('evidence'), str) and use['evidence'] and use['evidence'] in candidate['draft'], 'use必须引用正文中的原文证据')
        count = use.get('count', 1)
        require(type(count) is int and count > 0, 'use.count必须是正整数')
        entity = entities[eid]
        require(entity.get('lifecycle', 'active') not in {'locked', 'lost', 'consumed', 'retired', 'unknown'}, f'实体当前不可用：{eid}')
        for prereq in entity.get('prerequisites', []):
            require(entities[prereq].get('lifecycle') in {'completed', 'acquired', 'active'}, f'前置条件未满足：{prereq}')
        if entity.get('cooldown'):
            cooldown = entity['cooldown']
            now = unit.get('story_time')
            require(now is not None, f'{eid}有冷却但本章故事时间未知', 'CLOCK_REQUIRED')
            require(count == 1, '带冷却能力须逐次明确故事时间，不支持count>1')
            require(now >= cooldown.get('ready_at', 0), f'{eid}冷却未结束')
            cooldown['ready_at'] = now + cooldown['duration']
        if entity.get('cost'):
            resource = entities[entity['cost']['resource_id']]
            cost = entity['cost']['amount'] * count
            require(resource['quantity'] >= cost, f"资源不足：{resource['id']}需要{cost}，只有{resource['quantity']}")
            resource['quantity'] -= cost
    seen = set()
    for change in candidate['state_changes']:
        object_keys(change, {'id', 'before', 'after'}, 'state_change')
        eid = identifier(change.get('id'))
        require(eid in entities and eid not in seen, '状态变化目标不存在或重复')
        seen.add(eid)
        # before refers to the result after declared usage has applied its cost.
        require(change.get('before') == entities[eid], f'{eid}的before与使用后状态不符')
        require(isinstance(change.get('after'), dict) and change['after'].get('id') == eid, '不允许修改实体ID')
        require(change['after'].get('type') == entities[eid]['type'], '普通剧情变化不能修改实体类型')
        entities[eid] = copy.deepcopy(change['after'])
    for entity in candidate['new_facts']:
        require(isinstance(entity, dict), 'new_facts条目必须为entity对象')
        eid = identifier(entity.get('id'))
        require(eid not in entities, '新增事实ID已经存在')
        entities[eid] = copy.deepcopy(entity)
    # A historical view may predate entities referenced only by future outlines.
    validate_state(entities, {}, [unit])
    return after
