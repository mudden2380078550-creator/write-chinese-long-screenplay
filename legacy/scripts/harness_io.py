from __future__ import annotations

import json
from pathlib import Path
from typing import Any


HARNESS_DIR = "harness"
HARNESS_FILES = (
    "author-directives.json",
    "protagonist.json",
    "abilities.json",
    "inventory.json",
    "quests.json",
    "progression.json",
    "world-rules.json",
    "factions.json",
    "timeline.json",
    "continuity-ledger.json",
)
CONTROL_STATUSES = {"deprecated", "disabled", "forbidden", "retired", "locked"}
DEFAULT_HARNESS_CONTEXT_CHARS = 3500


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_harness(root: Path) -> dict[str, Any]:
    base = root / HARNESS_DIR
    result: dict[str, Any] = {}
    if not base.is_dir():
        return result
    for name in HARNESS_FILES:
        path = base / name
        if not path.is_file():
            continue
        data = load_json(path)
        if isinstance(data, dict):
            result[name] = data
    return result


def iter_items(document: dict[str, Any]) -> list[dict[str, Any]]:
    value = document.get("items")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if "id" in document or "name" in document:
        return [document]
    return []


def is_controlled(item: dict[str, Any]) -> bool:
    status = str(item.get("status", "")).casefold()
    policy = item.get("generation_policy")
    allow_use = True
    if isinstance(policy, dict) and policy.get("allow_use") is False:
        allow_use = False
    return status in CONTROL_STATUSES or not allow_use


def display_name(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("title") or item.get("id") or "未命名")


def item_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("name") or "unknown")


def relevant_text(item: dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False).casefold()


def item_terms(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("name", "title", "id"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    aliases = item.get("aliases")
    if isinstance(aliases, list):
        values.extend(str(alias).strip() for alias in aliases if str(alias).strip())
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        folded = value.casefold()
        if folded not in seen:
            seen.add(folded)
            result.append(value)
    return result


def item_patterns(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for source in (item, item.get("generation_policy")):
        if not isinstance(source, dict):
            continue
        patterns = source.get("forbidden_usage_patterns")
        if isinstance(patterns, list):
            values.extend(str(pattern).strip() for pattern in patterns if str(pattern).strip())
    return values


def item_allow_mention(item: dict[str, Any]) -> bool:
    policy = item.get("generation_policy")
    if isinstance(policy, dict) and policy.get("allow_mention") is False:
        return False
    return True


def truncate_lines(lines: list[str], max_chars: int) -> list[str]:
    if sum(len(line) + 1 for line in lines) <= max_chars:
        return lines
    result: list[str] = []
    used = 0
    omitted = 0
    for line in lines:
        cost = len(line) + 1
        if used + cost > max_chars - 48:
            omitted += 1
            continue
        result.append(line)
        used += cost
    if omitted:
        result.append(f"- [已按 harness 预算省略 {omitted} 条普通状态]")
    return result


def render_harness_context(
    root: Path,
    terms: list[str] | None = None,
    max_chars: int = DEFAULT_HARNESS_CONTEXT_CHARS,
) -> str:
    harness = load_harness(root)
    if not harness:
        return ""
    terms = terms or []
    lines = [
        "## Harness 控制台",
        "",
        "这些条目是外部状态，不是聊天上下文记忆。生成场次或章节时必须服从 `status`、`author_note` 和 `generation_policy`。",
        "",
    ]
    controlled: list[str] = []
    ordinary: list[str] = []
    for filename, document in harness.items():
        for item in iter_items(document):
            rendered = relevant_text(item)
            controlled_item = is_controlled(item) or filename == "author-directives.json"
            if terms and not controlled_item and not any(term.casefold() in rendered for term in terms):
                continue
            policy = item.get("generation_policy") if isinstance(item.get("generation_policy"), dict) else {}
            line = (
                f"- `{filename}` / `{item_id(item)}`：{display_name(item)}；"
                f"status={item.get('status', 'active')}；"
                f"allow_use={policy.get('allow_use', True)}；"
                f"allow_mention={policy.get('allow_mention', True)}；"
                f"作者注释：{item.get('author_note', '无')}"
            )
            aliases = item.get("aliases")
            if isinstance(aliases, list) and aliases:
                line += "；别名：" + "、".join(str(alias) for alias in aliases)
            details = {key: value for key, value in item.items() if key not in {"id", "name", "title", "status", "author_note", "aliases"}}
            if details:
                line += "；详情：" + json.dumps(details, ensure_ascii=False)
            if controlled_item:
                controlled.append(line)
            else:
                ordinary.append(line)
    mandatory = "\n".join(lines + (["### 废弃能力与禁用控制", "", *controlled, ""] if controlled else [])).rstrip() + "\n"
    if len(mandatory) > max_chars:
        raise ValueError(f"必要 harness 控制项需要 {len(mandatory)} 字符，超过预算 {max_chars}；请增加预算")
    ordinary_budget = max(0, max_chars - len(mandatory) - 100)
    if ordinary_budget:
        ordinary = truncate_lines(ordinary, ordinary_budget)
    else:
        ordinary = ["- [普通状态因 harness 预算限制省略；禁用/废弃项已优先保留。]"] if ordinary else []
    if controlled:
        lines.extend(["### 废弃能力与禁用控制", "", *controlled, ""])
    if ordinary:
        lines.extend(["### 可用状态", "", *ordinary, ""])
    if not controlled and not ordinary:
        lines.extend(["### 状态摘要", "", "- 当前查询没有命中特定 harness 条目；仍应遵守全部 harness 文件中的硬约束。", ""])
    rendered = "\n".join(lines).rstrip() + "\n"
    if len(rendered) <= max_chars:
        return rendered
    return mandatory


def disallowed_usages(root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for filename, document in load_harness(root).items():
        for item in iter_items(document):
            if not is_controlled(item):
                continue
            name = display_name(item).strip()
            if not name:
                continue
            result.append(
                {
                    "file": filename,
                    "id": item_id(item),
                    "name": name,
                    "terms": item_terms(item),
                    "patterns": item_patterns(item),
                    "allow_mention": item_allow_mention(item),
                    "status": str(item.get("status", "active")),
                    "author_note": str(item.get("author_note", "")),
                }
            )
    return result
