"""Explicit validation for the versioned protocol; no permissive JSON coercion."""
import math
import re

from .errors import require

ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$')
TYPES = {'character', 'resource', 'ability', 'item', 'quest', 'world-rule', 'faction', 'fact', 'progression'}
ENTITY_KEYS = {'id', 'type', 'name', 'aliases', 'owner_id', 'lifecycle', 'description', 'mechanics',
               'cost', 'cooldown', 'quantity', 'limits', 'attributes', 'provenance', 'knowledge',
               'prerequisites', 'author_note', 'extensions'}
POLICY_KEYS = {'id', 'target_ids', 'strength', 'effect', 'scope', 'author_note', 'provenance', 'extensions'}
UNIT_KEYS = {'id', 'title', 'outline', 'entity_ids', 'pov_id', 'thread_ids', 'story_time', 'extensions'}


def object_keys(value, allowed, label):
    require(isinstance(value, dict), f'{label}必须是对象')
    require(not set(value) - allowed, f'{label}未知字段：{sorted(set(value) - allowed)}')


def identifier(value):
    require(isinstance(value, str) and ID.fullmatch(value), f'非法ID：{value}')
    require(value.upper() not in {'CON', 'PRN', 'AUX', 'NUL', *[f'COM{i}' for i in range(1, 10)], *[f'LPT{i}' for i in range(1, 10)]}, 'ID不能使用系统保留名称')
    return value


def text(value, label):
    require(isinstance(value, str) and value.strip(), f'{label}不能为空')


def number(value, label):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, f'{label}必须是非负有限数值')


def ids(values, label):
    require(isinstance(values, list), f'{label}必须是数组')
    for value in values:
        identifier(value)
    require(len(set(values)) == len(values), f'{label}含重复ID')


def optional_common(value):
    for key in ('description', 'author_note'):
        if key in value:
            require(isinstance(value[key], str), f'{key}必须是字符串')
    if 'provenance' in value:
        require(isinstance(value['provenance'], list) and all(isinstance(x, dict) for x in value['provenance']), 'provenance必须是来源对象数组')
    if 'extensions' in value:
        require(isinstance(value['extensions'], dict), 'extensions必须是对象')


def validate_entity(entity):
    object_keys(entity, ENTITY_KEYS, 'entity')
    optional_common(entity)
    identifier(entity.get('id'))
    text(entity.get('name'), 'name')
    require(entity.get('type') in TYPES, '未知entity.type')
    if 'owner_id' in entity:
        identifier(entity['owner_id'])
    if 'quantity' in entity:
        number(entity['quantity'], 'quantity')
    if 'aliases' in entity:
        require(isinstance(entity['aliases'], list) and all(isinstance(x, str) and x.strip() for x in entity['aliases']), 'aliases必须是非空字符串数组')
    if 'lifecycle' in entity:
        require(entity['lifecycle'] in {'active', 'acquired', 'locked', 'lost', 'consumed', 'completed', 'failed', 'retired', 'unknown'}, '未知lifecycle')
    if 'cost' in entity:
        cost = entity['cost']
        object_keys(cost, {'resource_id', 'amount'}, 'cost')
        identifier(cost.get('resource_id'))
        number(cost.get('amount'), 'cost.amount')
    if 'cooldown' in entity:
        cooldown = entity['cooldown']
        object_keys(cooldown, {'duration', 'unit', 'ready_at'}, 'cooldown')
        number(cooldown.get('duration'), 'cooldown.duration')
        require(cooldown.get('unit') == 'second', '首版冷却使用second与显式故事秒数')
        if 'ready_at' in cooldown:
            number(cooldown['ready_at'], 'cooldown.ready_at')
    if 'prerequisites' in entity:
        ids(entity['prerequisites'], 'prerequisites')
    if 'knowledge' in entity:
        require(isinstance(entity['knowledge'], dict), 'knowledge必须是对象')


def validate_policy(policy):
    object_keys(policy, POLICY_KEYS, 'policy')
    optional_common(policy)
    identifier(policy.get('id'))
    ids(policy.get('target_ids', []), 'target_ids')
    require(policy.get('strength') in {'hard', 'soft'}, 'strength必须是hard或soft')
    text(policy.get('author_note'), 'author_note')
    effect = policy.get('effect')
    object_keys(effect, {'allow_use', 'allow_mention', 'forbidden_usage_patterns'}, 'effect')
    for key in ('allow_use', 'allow_mention'):
        if key in effect:
            require(type(effect[key]) is bool, f'{key}必须是布尔值')
    patterns = effect.get('forbidden_usage_patterns', [])
    require(isinstance(patterns, list), 'patterns必须是数组')
    for value in patterns:
        text(value, 'pattern')
        try:
            re.compile(value)
        except re.error as exc:
            require(False, f'无效正则：{exc}')
    if 'scope' in policy:
        object_keys(policy['scope'], {'from_unit_id', 'to_unit_id'}, 'scope')
        for value in policy['scope'].values():
            identifier(value)


def validate_state(entities, policies, units):
    require(isinstance(entities, dict) and isinstance(policies, dict) and isinstance(units, list), '无效状态集合')
    all_ids = list(entities) + list(policies) + [u.get('id') for u in units]
    for value in all_ids:
        identifier(value)
    require(len({x.casefold() for x in all_ids}) == len(all_ids), '跨类型/大小写重复ID')
    unit_ids = [u['id'] for u in units]
    for key, entity in entities.items():
        validate_entity(entity)
        require(entity['id'] == key, 'entity键与ID不一致')
        for ref in ([entity['owner_id']] if entity.get('owner_id') else []) + entity.get('prerequisites', []):
            require(ref in entities, f'引用实体不存在：{ref}')
        if 'cost' in entity:
            resource = entities.get(entity['cost']['resource_id'])
            require(resource is not None and resource['type'] == 'resource' and 'quantity' in resource, '消耗必须引用带数量的resource')
    for unit in units:
        object_keys(unit, UNIT_KEYS, 'unit')
        optional_common(unit)
        identifier(unit.get('id'))
        text(unit.get('title'), 'unit.title')
        text(unit.get('outline'), 'unit.outline')
        ids(unit.get('entity_ids', []), 'entity_ids')
        ids(unit.get('thread_ids', []), 'thread_ids')
        for ref in unit.get('entity_ids', []) + ([unit['pov_id']] if unit.get('pov_id') else []):
            require(ref in entities, f'章纲引用实体不存在：{ref}')
        if 'story_time' in unit:
            number(unit['story_time'], 'story_time')
    for key, policy in policies.items():
        validate_policy(policy)
        require(policy['id'] == key, 'policy键与ID不一致')
        for ref in policy.get('target_ids', []):
            require(ref in entities, f'政策目标不存在：{ref}')
        for ref in policy.get('scope', {}).values():
            require(ref in unit_ids, f'政策章节不存在：{ref}')
        scope = policy.get('scope', {})
        if 'from_unit_id' in scope and 'to_unit_id' in scope:
            require(unit_ids.index(scope['from_unit_id']) <= unit_ids.index(scope['to_unit_id']), '政策范围反向')
