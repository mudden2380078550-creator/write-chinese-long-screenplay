"""Lossless source staging; host extraction is an explicit proposal."""
import re
import copy
from pathlib import Path

from . import project
from .errors import require
from .storage import inside, digest, read_json, write_json, atomic_text, encode

ROUTES = {
    '背景': 'background', '背景设定': 'background', '世界背景': 'background',
    '人物': 'character', '人物设定': 'character', '角色': 'character', '主角': 'character', '主角状态': 'character',
    '技能': 'ability', '能力': 'ability', '道具': 'item', '装备': 'item', '物品': 'item',
    '任务': 'quest', '成长': 'progression', '等级': 'progression', '属性': 'progression', '进阶': 'progression',
    '世界规则': 'world-rule', '规则': 'world-rule', '阵营': 'faction', '组织': 'faction',
    '时间线': 'fact', '连续性': 'fact', '大纲': 'outline', '总纲': 'outline', '卷纲': 'outline', '章纲': 'outline',
    '作者指令': 'policy', '作者禁令': 'policy',
}


def sections(text):
    # Fenced code can contain # without starting a document heading.
    result, heading, lines, fence, start = [], '未分类', [], None, 1
    for n, line in enumerate(text.splitlines(), 1):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)[0]
            fence = None if fence == token else token if fence is None else fence
        match = re.match(r'^#\s+(.+?)\s*$', line) if fence is None else None
        if match:
            if lines or heading != '未分类':
                result.append({'heading': heading, 'text': '\n'.join(lines), 'line': start, 'route': ROUTES.get(heading)})
            heading, lines, start = match.group(1), [], n
        else:
            lines.append(line)
    if lines or heading != '未分类':
        result.append({'heading': heading, 'text': '\n'.join(lines), 'line': start, 'route': ROUTES.get(heading)})
    return result


def stage(root, source):
    current = project.load(root)
    source = Path(source).resolve()
    require(source.is_file(), '资料文件不存在')
    require(source.suffix.lower() in {'.md', '.txt', '.json'}, '首版支持UTF-8 Markdown/TXT/JSON；请先转换其他格式')
    raw = source.read_text(encoding='utf-8-sig')
    key = 'source-' + digest(raw)[:24]
    report_path = inside(root, f'proposals/{key}.json')
    if report_path.exists():
        previous = read_json(report_path)
        require(digest(inside(root, previous['source_file']).read_text(encoding='utf-8')) == previous['source_hash'], '已归档来源被修改')
        return previous
    source_file = f'sources/{key}{source.suffix.lower()}'
    atomic_text(inside(root, source_file), raw)
    parsed = sections(raw)
    report = {'id': key, 'project_id': current['id'], 'base_revision': current['revision'], 'source_file': source_file,
              'source_hash': digest(raw), 'original_name': source.name, 'sections': parsed,
              'unclassified': [s for s in parsed if s['route'] is None], 'status': 'staged',
              'entities': [], 'policies': [], 'units': [],
              'extraction_note': '原文已归档。请宿主AI将明确事实填入提案；推断和冲突留在uncertainties，不自动进入正典。',
              'uncertainties': []}
    if source.suffix.lower() == '.json':
        structured = read_json(source)
        require(isinstance(structured, dict), '结构化资料必须是对象')
        for field in ('entities', 'policies', 'units', 'uncertainties'):
            if field in structured:
                require(isinstance(structured[field], list), f'{field}必须是数组')
                report[field] = structured[field]
    write_json(report_path, report)
    return report


def apply(root, proposal_id):
    from .models import identifier
    from . import transactions
    current = project.load(root)
    proposal = read_json(inside(root, f'proposals/{identifier(proposal_id)}.json'))
    receipt_id = 'import-' + proposal_id
    if receipt_id in current['metadata']['receipts']:
        return current['metadata']['receipts'][receipt_id]
    require(proposal.get('project_id') == current['id'], '提案不属于当前项目')
    require(proposal['base_revision'] == current['revision'], '导入提案已过期，重新审定最新状态', 'REVISION_CONFLICT', 3)
    require(digest(inside(root, proposal['source_file']).read_text(encoding='utf-8')) == proposal['source_hash'], '来源被改动')
    require(not proposal.get('uncertainties'), '仍有未解决冲突/推断，先审定或移出本次接受集合', 'IMPORT_REVIEW_REQUIRED', 1)
    require(any(proposal.get(k) for k in ('entities', 'policies', 'units')), '只有来源归档，没有结构化提案；请宿主先整理资料', 'IMPORT_REVIEW_REQUIRED', 1)
    # Configuration commit and its import receipt must share the same transaction.
    entities = copy.deepcopy(proposal.get('entities', []))
    for entity in entities:
        entity.setdefault('provenance', []).append({'source_id': proposal_id, 'file': proposal['source_file'], 'method': 'host-reviewed-import'})
    return project.configure(root, entities=entities, policies=proposal.get('policies'),
                             units=proposal.get('units') or None, expected_revision=proposal['base_revision'],
                             acceptance_id=receipt_id,
                             extra_files={proposal['source_file']: inside(root, proposal['source_file']).read_text(encoding='utf-8'),
                                          f'canon/history/{receipt_id}.json': encode(proposal)})
