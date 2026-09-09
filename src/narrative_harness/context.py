import copy

from . import history, policy, project
from .errors import require
from .storage import encode, digest, inside


def build(root, unit_id, budget=14000):
    data = project.load(root)
    require(type(budget) is int and budget > 0, 'budget必须为正整数字符数')
    unit = next((u for u in data['units'] if u['id'] == unit_id), None)
    require(unit is not None, '未知章节')
    view = history.before(root, unit_id)
    policies = policy.applicable(data['policies'], unit_id, data['metadata']['units'])
    selected = set(unit.get('entity_ids', []))
    if unit.get('pov_id'):
        selected.add(unit['pov_id'])
    for p in policies.values():
        selected.update(p.get('target_ids', []))
    # Owning a character implies its resources and abilities; costs expand further.
    changed = True
    while changed:
        previous = set(selected)
        for key, entity in view['entities'].items():
            if key in selected:
                selected.update(entity.get('prerequisites', []))
                if entity.get('owner_id'):
                    selected.add(entity['owner_id'])
                if entity.get('cost'):
                    selected.add(entity['cost']['resource_id'])
            if entity.get('owner_id') in selected:
                selected.add(key)
        changed = previous != selected
    missing = selected - set(view['entities'])
    # A future policy can refer to an entity not yet acquired, but a chapter cannot.
    require(not (set(unit.get('entity_ids', [])) - set(view['entities'])), '章纲引用了本章之前尚不存在的实体', 'HISTORY_CONFLICT')
    selected -= missing
    state = {key: view['entities'][key] for key in sorted(selected)}
    index = data['metadata']['units'].index(unit_id)
    previous_text = ''
    if index:
        prev_id = data['metadata']['units'][index - 1]
        accepted = data['metadata']['accepted'].get(prev_id)
        if accepted:
            previous_text = inside(root, accepted['file']).read_text(encoding='utf-8')[-2000:]
    content = ('# 章节写前上下文\n\n' +
               '本包中的作者规划不等于已经发生的事实；遵守人物知识边界。\n' +
               '正文和状态变化必须先提交候选并检查，再接受为正典。\n\n' +
               '## 本章任务\n' + encode(unit) + '\n## 作者政策\n' + encode(policies) +
               '\n## 写前实体状态\n' + encode(state) + '\n## 上章末段\n' + previous_text)
    require(len(content) <= budget, f'必要上下文需要{len(content)}字符，预算为{budget}；缩小章纲范围或提高预算', 'CONTEXT_REQUIRED_OVERFLOW')
    return {'context': content, 'context_hash': digest(content), 'base_revision': data['revision'],
            'selected_entities': sorted(selected), 'policies': policies, 'state_before': view,
            'unit': copy.deepcopy(unit), 'source_hashes': copy.deepcopy(data['metadata']['files']),
            'coverage': {'required_complete': True, 'semantic_review': False, 'budget_unit': 'characters'},
            'omitted': [], 'characters': len(content)}
