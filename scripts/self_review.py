from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from screenplay_io import (
    atomic_write_text,
    extract_h2_sections,
    parse_frontmatter,
    read_text,
    require_inside,
    scene_identity,
)
from validate_project import DIALOGUE_RE, validate_project


CARD_FIELDS = (
    "来源依据",
    "人物依据",
    "背景依据",
    "世界规则",
    "场次任务",
    "观众入口",
    "入场状态",
    "场面转折",
    "观众更新",
    "出场状态",
    "禁止矛盾",
)
EXPOSITION_TRIGGERS = (
    "你还记得",
    "你也知道",
    "你应该知道",
    "正如你所知",
    "事情是这样的",
    "让我告诉你",
)
MIND_TRIGGERS = ("内心", "心里想", "意识到", "感到", "五味杂陈")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成中文剧本确定性自审报告")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="只输出摘要与自动发现，省略量化表和静态语义审查模板",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def card_value(card: str, label: str) -> str:
    match = re.search(rf"^{re.escape(label)}：(.*)$", card, re.MULTILINE)
    return match.group(1).strip() if match else ""


def add_finding(
    findings: dict[str, list[dict[str, str]]],
    level: str,
    code: str,
    file: str,
    message: str,
) -> None:
    item = {"code": code, "file": file, "message": message}
    if item not in findings[level]:
        findings[level].append(item)


def load_character_ids(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    directory = root / "bible" / "characters"
    if not directory.exists():
        return result
    for path in directory.glob("*.md"):
        if path.name.startswith("_"):
            continue
        try:
            metadata, _ = parse_frontmatter(read_text(path))
        except (OSError, ValueError):
            continue
        character_id = str(metadata.get("id", ""))
        if character_id:
            result[character_id] = path
    return result


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    output = (
        args.output.resolve()
        if args.output
        else (root / "reviews" / "self-review.md").resolve()
    )
    try:
        require_inside(output, root / "reviews")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    format_name, scenes, structural_errors, structural_warnings = validate_project(
        root, args.strict
    )
    findings: dict[str, list[dict[str, str]]] = {
        "blocking": [],
        "major": [],
        "minor": [],
    }
    for item in structural_errors:
        add_finding(
            findings,
            "blocking",
            item["code"],
            item["file"],
            item["message"],
        )
    for item in structural_warnings:
        level = "major" if item["code"] in {"no-sources", "placeholder"} else "minor"
        add_finding(findings, level, item["code"], item["file"], item["message"])

    character_ids = load_character_ids(root)
    metrics = Counter()
    sequence_scenes: dict[str, int] = defaultdict(int)
    source_trace_rows: list[str] = []

    for path in scenes:
        try:
            metadata, body = parse_frontmatter(read_text(path))
            _, sections = extract_h2_sections(body)
            card = sections.get("场次卡", "")
            draft = sections.get("正文", "")
            _, episode, scene = scene_identity(path)
        except (OSError, ValueError) as exc:
            add_finding(findings, "blocking", "review-parse", str(path), str(exc))
            continue

        scene_id = str(metadata.get("id") or path.stem)
        source_files = metadata.get("source_files", [])
        if not isinstance(source_files, list):
            source_files = []
        characters = metadata.get("characters", [])
        if not isinstance(characters, list):
            characters = []

        for character in characters:
            character = str(character)
            if character.startswith("char-") and character not in character_ids:
                add_finding(
                    findings,
                    "blocking" if args.strict else "major",
                    "character-profile-missing",
                    str(path),
                    f"人物 {character} 没有对应人物小传",
                )
        character_sources = [
            str(value)
            for value in source_files
            if "bible/characters/" in str(value).replace("\\", "/")
        ]
        if any(str(value).startswith("char-") for value in characters) and not character_sources:
            add_finding(
                findings,
                "major",
                "character-source-missing",
                str(path),
                "主要人物出场，但 source_files 未引用人物小传",
            )

        required_card_fields = (
            "来源依据",
            "人物依据",
            "场次任务",
            "观众入口",
            "入场状态",
            "场面转折",
            "观众更新",
            "出场状态",
        )
        for label in required_card_fields:
            if not card_value(card, label):
                add_finding(
                    findings,
                    "blocking" if args.strict else "major",
                    "empty-card-field",
                    str(path),
                    f"场次卡字段为空：{label}",
                )
        entry = card_value(card, "入场状态")
        exit_state = card_value(card, "出场状态")
        if entry and exit_state and entry == exit_state:
            add_finding(
                findings,
                "major",
                "unchanged-state",
                str(path),
                "入场状态与出场状态完全相同",
            )

        dialogue_chars = 0
        action_chars = 0
        for line_number, raw_line in enumerate(draft.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            if DIALOGUE_RE.match(line):
                dialogue_text = line.split("：", 1)[1]
                dialogue_chars += len(dialogue_text)
                if len(dialogue_text) > 120:
                    add_finding(
                        findings,
                        "minor",
                        "long-dialogue",
                        str(path),
                        f"正文相对行 {line_number} 的单次对白超过 120 字",
                    )
                if any(trigger in dialogue_text for trigger in EXPOSITION_TRIGGERS):
                    add_finding(
                        findings,
                        "major",
                        "exposition-dialogue",
                        str(path),
                        f"对白可能在向共同知情者解释设定：{line}",
                    )
            elif line.startswith("△"):
                action_chars += len(line)
                if any(trigger in line for trigger in MIND_TRIGGERS):
                    add_finding(
                        findings,
                        "major",
                        "unfilmable-action",
                        str(path),
                        f"动作段可能包含不可拍心理：{line}",
                    )

        metrics["scenes"] += 1
        metrics["dialogue_chars"] += dialogue_chars
        metrics["action_chars"] += action_chars
        if format_name == "feature":
            sequence_scenes[str(metadata.get("sequence", 0))] += 1
        source_trace_rows.append(
            f"| {scene_id} | {len(characters)} | {len(source_files)} | "
            f"{card_value(card, '人物依据') or '缺失'} | "
            f"{card_value(card, '背景依据') or '未使用/缺失'} | "
            f"{card_value(card, '世界规则') or '未使用/缺失'} |"
        )

    result: dict[str, Any] = {
        "project_root": str(root),
        "format": format_name,
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "counts": {level: len(items) for level, items in findings.items()},
        "metrics": dict(metrics),
        "sequence_scene_counts": dict(sorted(sequence_scenes.items())),
        "findings": findings,
    }
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if findings["blocking"] else 0

    def render_findings(level: str, title: str) -> list[str]:
        lines = [f"\n## {title}\n"]
        items = findings[level]
        if not items:
            lines.append("- 无自动发现。\n")
        else:
            for item in items:
                lines.append(
                    f"- `[{item['code']}]` `{item['file']}`：{item['message']}\n"
                )
        return lines

    report = [
        "# 剧本自审报告\n\n",
        f"- 格式：{format_name}\n",
        f"- 场次数：{metrics['scenes']}\n",
        f"- 生成时间：{result['generated']}\n",
        f"- Blocking：{len(findings['blocking'])}\n",
        f"- Major：{len(findings['major'])}\n",
        f"- Minor：{len(findings['minor'])}\n",
        "\n> 自动检查只识别高确定性信号。以下“语义审查”必须由模型或编辑结合正文完成，不能因自动检查无问题而跳过。\n",
    ]
    report.extend(render_findings("blocking", "Blocking"))
    report.extend(render_findings("major", "Major"))
    report.extend(render_findings("minor", "Minor"))
    if args.compact:
        report.extend(
            [
                "\n> 紧凑报告未附静态五遍审查模板；语义审查要求见 "
                "`references/self-review.md`。\n",
            ]
        )
        atomic_write_text(output, "".join(report))
        print(f"OK: 已生成紧凑自审报告：{output}")
        print(
            f"SUMMARY: blocking={len(findings['blocking'])} "
            f"major={len(findings['major'])} minor={len(findings['minor'])}"
        )
        return 1 if findings["blocking"] else 0

    report.extend(
        [
            "\n## 量化观察\n\n",
            f"- 动作字符：{metrics['action_chars']}\n",
            f"- 对白字符：{metrics['dialogue_chars']}\n",
        ]
    )
    if sequence_scenes:
        report.append(
            "- 序列场次数："
            + "；".join(
                f"序列 {key}={value}" for key, value in sorted(sequence_scenes.items())
            )
            + "\n"
        )
    report.extend(
        [
            "\n## 来源追溯表\n\n",
            "| 场次 | 人物数 | 来源数 | 人物依据 | 背景依据 | 世界规则 |\n",
            "| --- | ---: | ---: | --- | --- | --- |\n",
            *(f"{row}\n" for row in source_trace_rows),
            "\n## 语义审查（必须完成）\n\n",
            "### 1. 来源忠实度\n\n",
            "- [ ] 逐场核对人物小传、背景和世界规则的具体事实。\n",
            "- [ ] 标记人物失真、知识越权、规则无成本和无来源新事实。\n",
            "- [ ] 检查设定是否被复制成说明性对白。\n",
            "\n### 2. 因果与人物\n\n",
            "- [ ] 为每场补全“因为 X，人物选择 Y；Y 导致 Z；因此下一场处理 Q”。\n",
            "- [ ] 检查是否存在更低成本且人物显然会选择的方案。\n",
            "- [ ] 检查关系伤害、承诺和资源变化是否进入后续场次。\n",
            "\n### 3. 观众盲读\n\n",
            "- [ ] 暂停读取设定和大纲，只读编译正文。\n",
            "- [ ] 记录观众能描述、可能推断、仍追问和无法理解的内容。\n",
            "- [ ] 区分有意悬念与缺失基本信息。\n",
            "\n### 4. 电影性与可表演性\n\n",
            "- [ ] 检查动作主体、空间、策略变化、潜台词和可读反应。\n",
            "- [ ] 将不可拍心理和抽象总结转换为行为或视听证据。\n",
            "\n### 5. 结构与节奏\n\n",
            "- [ ] 检查重复功能场、无变化场、假中段和未建立的高潮机制。\n",
            "- [ ] 检查高潮由人物选择完成，余波展示新状态与代价。\n",
            "\n## 编辑结论\n\n",
            "- 接受的风险：\n",
            "- 必须修复：\n",
            "- 根因场与下游影响：\n",
            "- 修订后的回归结果：\n",
        ]
    )
    atomic_write_text(output, "".join(report))
    print(f"OK: 已生成自审报告：{output}")
    print(
        f"SUMMARY: blocking={len(findings['blocking'])} "
        f"major={len(findings['major'])} minor={len(findings['minor'])}"
    )
    return 1 if findings["blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
