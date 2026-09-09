import re


def applicable(policies, unit_id, order):
    position = order.index(unit_id)
    result = {}
    for key, policy in policies.items():
        scope = policy.get('scope', {})
        first = order.index(scope['from_unit_id']) if scope.get('from_unit_id') else 0
        last = order.index(scope['to_unit_id']) if scope.get('to_unit_id') else len(order) - 1
        if first <= position <= last:
            result[key] = policy
    return result


def usage_in(text, entity):
    """Lexical signal only; independent semantic attestation remains required."""
    terms = [entity['name'], entity['id'], *entity.get('aliases', [])]
    for clause in re.split(r'[。！？\n；]|(?:但是|然而|而是|还是|依然|仍然|却)', text):
        for term in terms:
            for match in re.finditer(re.escape(term), clause, re.IGNORECASE):
                prefix = clause[max(0, match.start() - 20):match.start()]
                suffix = clause[match.end():match.end() + 20]
                verb = re.search(r'(?:发动|施展|使用|启用|激活|开启|催动|祭出|装备|借助|依靠|凭借|用|靠)\s*$', prefix)
                if verb:
                    negation = prefix[:verb.start()]
                    if not re.search(r'(?:没有|并未|未曾|不曾|不能|不再|禁止|不要|未|不)\s*$', negation):
                        return clause.strip()
                if re.match(r'[^，,]{0,6}(?:发动了|生效了|带着.{0,6}逃脱|让.{0,6}逃脱)', suffix):
                    return clause.strip()
    return None


def inspect(draft, entities, policies, uses):
    findings = []
    declared = {use['entity_id'] for use in uses}
    for key, policy in policies.items():
        effect = policy['effect']
        matches = []
        for pattern in effect.get('forbidden_usage_patterns', []):
            if re.search(pattern, draft, re.IGNORECASE):
                matches.append('正文命中显式禁用模式')
        for eid in policy.get('target_ids', []):
            entity = entities.get(eid)
            if not entity:
                continue
            if effect.get('allow_mention') is False:
                if any(re.search(re.escape(term), draft, re.IGNORECASE) for term in [entity['name'], entity['id'], *entity.get('aliases', [])]):
                    matches.append(f'提及不允许出现的实体：{eid}')
            if effect.get('allow_use') is False:
                evidence = usage_in(draft, entity)
                if eid in declared or evidence:
                    matches.append(f'使用禁用实体 {eid}：{evidence or "uses声明"}')
        for message in matches:
            findings.append({'code': 'POLICY_VIOLATION', 'rule_id': key,
                             'severity': 'error' if policy['strength'] == 'hard' else 'warning',
                             'message': message})
    return findings
