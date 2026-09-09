import copy
import re
from uuid import uuid4

from . import project, context, policy, state, transactions
from .errors import require, HarnessError
from .models import object_keys, identifier, validate_state
from .storage import inside, read_json, write_json, atomic_text, encode, digest


def run_path(root, run_id, name):
    return inside(root, f'runs/{identifier(run_id)}/{name}')


def load_run(root, run_id, allow_stale=False):
    current = project.load(root)
    run = read_json(run_path(root, run_id, 'run.json'))
    require(run.get('id') == run_id and run.get('project_id') == current['id'], 'run不属于当前作品')
    if not allow_stale:
        require(run['base_revision'] == current['revision'], '运行基于旧修订，请重新prepare', 'REVISION_CONFLICT', 3)
    return current, run


def prepare(root, unit_id, budget=14000, revision_mode=False):
    current = project.load(root)
    require(not current['metadata'].get('migration_pending'), '旧harness资料尚未审定，先完成迁移报告中的条目', 'MIGRATION_REVIEW_REQUIRED', 1)
    require(revision_mode or unit_id not in current['metadata']['accepted'], '章节已接受；改稿使用 --revision')
    if revision_mode and unit_id in current['metadata']['accepted']:
        accepted = current['metadata']['accepted'][unit_id]
        event = read_json(inside(root, f"canon/history/{accepted['event_id']}.json"))
        later_accepted = any(uid in current['metadata']['accepted'] for uid in current['metadata']['units'][current['metadata']['units'].index(unit_id) + 1:])
        if not later_accepted:
            require(current['entities'] == event['after']['entities'], '接受后作者已调整实体；请建立修订分支以免覆盖新设定', 'REVISION_REBASE_REQUIRED', 3)
    pack = context.build(root, unit_id, budget)
    run = dict(pack, id='run-' + uuid4().hex, project_id=current['id'], unit_id=unit_id,
               status='prepared', revision_mode=revision_mode)
    write_json(run_path(root, run['id'], 'run.json'), run)
    atomic_text(run_path(root, run['id'], 'context.md'), run['context'])
    return run


def submit(root, run_id, candidate):
    current, run = load_run(root, run_id)
    require(run_id not in current['metadata'].get('receipts', {}), '已接受的运行不可修改')
    object_keys(candidate, {'run_id', 'base_revision', 'draft', 'uses', 'state_changes', 'new_facts', 'uncertainties'}, 'candidate')
    require(candidate.get('run_id') == run_id and candidate.get('base_revision') == run['base_revision'], '候选run或版本不匹配')
    require(isinstance(candidate.get('draft'), str) and candidate['draft'].strip(), '正文不能为空')
    for key in ('uses', 'state_changes', 'new_facts'):
        require(isinstance(candidate.get(key), list), f'{key}必须是数组')
    write_json(run_path(root, run_id, 'candidate.json'), candidate)
    run['status'] = 'submitted'
    write_json(run_path(root, run_id, 'run.json'), run)
    return {'id': run_id, 'status': 'submitted'}


def evaluate(current, run, candidate, semantic_review):
    findings = []
    after = None
    try:
        object_keys(candidate, {'run_id', 'base_revision', 'draft', 'uses', 'state_changes', 'new_facts', 'uncertainties'}, 'candidate')
        require(isinstance(candidate.get('draft'), str) and candidate['draft'].strip(), '正文不能为空')
        for key in ('uses', 'state_changes', 'new_facts', 'uncertainties'):
            require(isinstance(candidate.get(key, []), list), f'{key}必须是数组')
        require(not candidate.get('uncertainties'), '候选仍有未解决疑问，先审定再接受', 'UNRESOLVED_FACTS', 1)
        require(candidate['run_id'] == run['id'] and candidate['base_revision'] == run['base_revision'], '候选绑定不一致')
        after = state.apply_candidate(run['state_before'], candidate, run['unit'], current['units'])
        findings.extend(policy.inspect(candidate['draft'], run['state_before']['entities'], run['policies'], candidate['uses']))
        declared = {use['entity_id'] for use in candidate['uses']}
        for key, entity in run['state_before']['entities'].items():
            if entity['type'] == 'ability' and policy.usage_in(candidate['draft'], entity) and key not in declared:
                findings.append({'code': 'UNDECLARED_USE', 'severity': 'error', 'message': f'正文使用{key}但uses未声明；请补充状态消耗'})
        if current['metadata']['format'] != 'novel':
            require('△' in candidate['draft'], '剧本正文至少包含一个△动作段；无动作场景请拆分审定')
        require(not re.search(r'【待补】|\{\{|\b(?:TODO|TBD)\b', candidate['draft']), '正文仍有占位内容')
    except (HarnessError, KeyError, TypeError) as exc:
        findings.append({'code': getattr(exc, 'code', 'INVALID_CANDIDATE'), 'severity': 'error', 'message': str(exc)})
    semantic_pass = False
    if semantic_review is not None:
        object_keys(semantic_review, {'verdict', 'notes'}, 'semantic_review')
        require(semantic_review.get('verdict') in {'pass', 'fail'}, '语义审查verdict必须为pass/fail')
        require(isinstance(semantic_review.get('notes'), str) and semantic_review['notes'].strip(), '语义审查必须提供结论依据')
        semantic_pass = semantic_review['verdict'] == 'pass'
        if not semantic_pass:
            findings.append({'code': 'SEMANTIC_REVIEW_FAILED', 'severity': 'error', 'message': semantic_review['notes']})
    status = 'blocked' if any(f['severity'] == 'error' for f in findings) else 'passed' if semantic_pass else 'needs_review'
    return {'status': status, 'findings': findings, 'after': after,
            'coverage': {'lexical_rules': True, 'declared_state_changes': True, 'semantic_review': semantic_pass,
                         'semantic_limit': '语义结论由宿主AI或作者提供；程序不能独立证明自然语言全部符合规则。'}}


def check(root, run_id, semantic_review=None):
    current, run = load_run(root, run_id)
    require(run['status'] in {'submitted', 'checked'}, '先submit候选')
    candidate = read_json(run_path(root, run_id, 'candidate.json'))
    report = evaluate(current, run, candidate, semantic_review)
    report.update(candidate_hash=digest(candidate), context_hash=run['context_hash'], base_revision=run['base_revision'],
                  semantic_review=semantic_review)
    run['status'] = 'checked'
    write_json(run_path(root, run_id, 'report.json'), report)
    write_json(run_path(root, run_id, 'run.json'), run)
    return report


def accept(root, run_id):
    current = project.load(root)
    if run_id in current['metadata']['receipts']:
        return current['metadata']['receipts'][run_id]
    current, run = load_run(root, run_id)
    require(run['status'] == 'checked', '未检查的候选不能接受', 'CHECK_REQUIRED', 1)
    candidate = read_json(run_path(root, run_id, 'candidate.json'))
    report = read_json(run_path(root, run_id, 'report.json'))
    require(report['status'] == 'passed', '检查尚未通过或缺少语义审查', 'CHECK_REQUIRED', 1)
    require(digest(candidate) == report['candidate_hash'], '报告生成后正文已改变', 'STALE_REPORT', 3)
    # Rebuild all authoritative context; edited run files cannot replace policy or state.
    fresh = context.build(root, run['unit_id'], max(len(run['context']) + 1, 14000))
    require(fresh['context_hash'] == run['context_hash'] == report['context_hash'] and
            fresh['state_before'] == run['state_before'] and fresh['policies'] == run['policies'] and fresh['unit'] == run['unit'],
            '上下文或run记录已改变，请重新prepare', 'STALE_REPORT', 3)
    result = evaluate(current, run, candidate, report.get('semantic_review'))
    require(result['status'] == 'passed', '接受前复查失败', 'CHECK_REQUIRED', 1)
    metadata = copy.deepcopy(current['metadata'])
    uid = run['unit_id']
    index = metadata['units'].index(uid)
    is_historical = uid in metadata['accepted'] and any(k in metadata['accepted'] for k in metadata['units'][index + 1:])
    require(not is_historical, '有后续已接受章节；先以新分支或迁移副本修订历史，避免覆盖后续状态', 'HISTORICAL_REVISION_REQUIRES_BRANCH', 3)
    after = result['after']
    # Author policies are current configuration, not subject to draft mutation.
    after['policies'] = copy.deepcopy(current['policies'])
    validate_state(after['entities'], after['policies'], current['units'])
    event_id = 'event-' + uuid4().hex
    manuscript_file = f'manuscript/{uid}.md'
    event = {'id': event_id, 'kind': 'unit-accept', 'unit_id': uid, 'run_id': run_id,
             'base_revision': current['revision'], 'before': project.snapshot(current), 'after': after,
             'unit_before': run['state_before'], 'draft_hash': digest(candidate['draft'].strip())}
    changes = {f'canon/entities/{key}.json': encode(value) for key, value in after['entities'].items()}
    changes[f'canon/history/{event_id}.json'] = encode(event)
    changes[manuscript_file] = candidate['draft'].strip() + '\n'
    # Accepted evidence is frozen and tracked independently from mutable run scratch files.
    changes[f'canon/history/{event_id}-candidate.json'] = encode(candidate)
    changes[f'canon/history/{event_id}-report.json'] = encode(report)
    metadata['events'].append(event_id)
    metadata['accepted'][uid] = {'file': manuscript_file, 'event_id': event_id, 'run_id': run_id,
                                 'needs_revalidation': False, 'selected_entities': run['selected_entities']}
    return transactions.commit(root, run['base_revision'], changes, metadata, acceptance_id=run_id)


def revalidate(root, unit_id, semantic_review):
    """Recheck accepted prose against current scoped policies without charging again."""
    current = project.load(root)
    require(unit_id in current['metadata']['accepted'], '章节尚未接受')
    accepted = current['metadata']['accepted'][unit_id]
    event = read_json(inside(root, f"canon/history/{accepted['event_id']}.json"))
    require(not accepted.get('history_unknown'), '迁移旧稿历史未知，不能自动重新验证状态', 'HISTORY_UNKNOWN')
    candidate = read_json(inside(root, f"canon/history/{accepted['event_id']}-candidate.json"))
    unit = next(u for u in current['units'] if u['id'] == unit_id)
    view = event.get('unit_before', event['before'])
    active = policy.applicable(current['policies'], unit_id, current['metadata']['units'])
    run = {'id': candidate['run_id'], 'base_revision': candidate['base_revision'], 'unit': unit,
           'state_before': view, 'policies': active}
    report = evaluate(current, run, candidate, semantic_review)
    require(report['status'] == 'passed', '旧章节复查未通过：' + encode(report['findings']), 'REVALIDATION_REQUIRED', 1)
    require(report['after']['entities'] == event.get('unit_after', event['after'])['entities'], '新章纲使旧状态变化失效，需要修订分支', 'REVISION_REBASE_REQUIRED', 3)
    metadata = copy.deepcopy(current['metadata'])
    metadata['accepted'][unit_id]['needs_revalidation'] = False
    report_id = 'review-' + uuid4().hex
    report.update(unit_id=unit_id, base_revision=current['revision'], candidate_hash=digest(candidate), semantic_review=semantic_review)
    return transactions.commit(root, current['revision'], {f'canon/history/{report_id}.json': encode(report)}, metadata)


def export(root):
    current = project.load(root)
    project.doctor(root)
    require(current['metadata']['accepted'], '没有已接受正文')
    parts = ['# ' + current['metadata']['title']]
    for unit in current['units']:
        accepted = current['metadata']['accepted'].get(unit['id'])
        if accepted:
            require(not accepted.get('needs_revalidation'), f"{unit['id']}受设定变化影响，需要重新审查", 'REVALIDATION_REQUIRED', 1)
            parts.append('## ' + unit['title'] + '\n\n' + inside(root, accepted['file']).read_text(encoding='utf-8'))
    text = '\n\n'.join(parts).rstrip() + '\n'
    atomic_text(inside(root, 'exports/manuscript.md'), text)
    return text
