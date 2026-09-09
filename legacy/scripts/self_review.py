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
    STRUCTURE_ADAPTERS,
    atomic_write_text,
    extract_h2_sections,
    labeled_value,
    list_scene_files,
    parse_frontmatter,
    project_metadata,
    read_text,
    require_inside,
    scene_identity,
    unresolved,
)
from validate_project import DIALOGUE_RE, validate_project


FOCUSES = ("scene", "dialogue", "structure", "continuity", "full")
EXPOSITION_TRIGGERS = (
    "你还记得",
    "你也知道",
    "你应该知道",
    "正如你所知",
    "事情是这样的",
    "让我告诉你",
)
# 只把 Humanizer-zh 的中文问题分类用于高确定性提示；不复制其改写提示词、
# 检测器或评分。格式、语义和人物声音问题仍由 references/natural-chinese.md
# 交给模型结合当前场景判断，避免把正常中文误报成“AI 味”。
AI_STYLE_PATTERNS = (
    (
        "内容01-意义拔高",
        re.compile(r"(?:时代|文明|历史|命运)[^。！？\n]{0,18}(?:证明|象征|注脚|注定)"),
    ),
    (
        "内容02-名望背书",
        re.compile(r"(?:广受关注|备受瞩目|业内公认|众所周知|媒体报道|权威专家)"),
    ),
    (
        "内容03-抽象分析",
        re.compile(r"(?:他|她|人物|主角)(?:感到|意识到|内心|深知|明白了)"),
    ),
    (
        "内容04-宣传广告腔",
        re.compile(r"(?:无缝|卓越|极具价值|充满活力|令人叹为观止|赋能|引领)"),
    ),
    (
        "内容05-模糊归因",
        re.compile(r"(?:有人认为|普遍认为|业内指出|专家表示|据有关方面|大家都知道)"),
    ),
    (
        "内容06-提纲式总结",
        re.compile(r"(?:挑战与未来|未来展望|问题在于|接下来的重点|总体来看)"),
    ),
    (
        "语言07-AI高频词",
        re.compile(r"(?:此外|至关重要|深入探讨|彰显|格局|织锦|关键性|值得注意的是)"),
    ),
    (
        "语言09-否定排比",
        re.compile(r"(?:不是[^。！？\n]{0,30}而是|不仅[^。！？\n]{0,30}(?:而且|还))"),
    ),
    (
        "语言12-虚假范围",
        re.compile(r"(?:从[^。！？\n]{1,20}到[^。！？\n]{1,20}|无论[^。！？\n]{1,20}都)"),
    ),
    (
        "交流19-协作元话语",
        re.compile(r"(?:下面我将|根据你的要求|本场重点是|接下来我们|以下内容)"),
    ),
    (
        "交流20-能力免责声明",
        re.compile(r"(?:知识截止|截至目前资料|我无法确认|模型无法|资料显示我)"),
    ),
    (
        "交流21-无依据肯定",
        re.compile(r"(?:你说得对|这个决定很正确|你做得很好|非常正确|这是明智的选择)"),
    ),
    (
        "交流22-填充短语",
        re.compile(r"(?:与此同时|就在这时|不难发现|需要指出的是|正如你所知|事情是这样的|让我告诉你)"),
    ),
    (
        "交流24-通用积极结论",
        re.compile(r"(?:这意味着|由此可见|这充分说明|希望仍在|未来会更好|总而言之)"),
    ),
)
MIND_TRIGGERS = ("内心", "心里想", "意识到", "感到", "五味杂陈")
ADAPTER_LABELS = {
    "field": (
        "菲尔德·情节点Ⅰ",
        "菲尔德·情节点Ⅱ",
        "菲尔德·结局",
    ),
    "mckee": (
        "麦基·激励事件",
        "麦基·进展纠葛",
        "麦基·危机",
        "麦基·高潮",
        "麦基·结局",
    ),
    "save-the-cat": (
        "救猫咪·开场画面",
        "救猫咪·阐明主题",
        "救猫咪·布局铺垫",
        "救猫咪·触发事件",
        "救猫咪·展开讨论",
        "救猫咪·进入第二幕",
        "救猫咪·副线故事",
        "救猫咪·玩闹和游戏",
        "救猫咪·中点",
        "救猫咪·反派逼近",
        "救猫咪·失去一切",
        "救猫咪·灵魂黑夜",
        "救猫咪·进入第三幕",
        "救猫咪·结局",
        "救猫咪·终场画面",
    ),
}
SAVE_CAT_POSITION_RANGES = {
    "救猫咪·开场画面": (0, 3),
    "救猫咪·阐明主题": (2, 10),
    "救猫咪·布局铺垫": (0, 15),
    "救猫咪·触发事件": (8, 18),
    "救猫咪·展开讨论": (10, 25),
    "救猫咪·进入第二幕": (18, 30),
    "救猫咪·副线故事": (20, 38),
    "救猫咪·玩闹和游戏": (20, 58),
    "救猫咪·中点": (43, 57),
    "救猫咪·反派逼近": (48, 78),
    "救猫咪·失去一切": (68, 82),
    "救猫咪·灵魂黑夜": (70, 88),
    "救猫咪·进入第三幕": (75, 88),
    "救猫咪·结局": (78, 100),
    "救猫咪·终场画面": (97, 100),
}
MAJOR_WARNING_CODES = {
    "placeholder",
    "dialogue-subtext",
    "character-voice",
    "source-card-mismatch",
    "structure-map-field",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 v2 中文剧本分层自审报告")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--focus", choices=FOCUSES, default="full")
    parser.add_argument(
        "--adapter",
        action="append",
        choices=tuple(sorted(STRUCTURE_ADAPTERS)),
        help="显式选择结构适配器；可重复。省略时读取 project.md",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


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


def active_adapters(root: Path, explicit: list[str] | None) -> list[str]:
    if explicit is not None:
        return list(dict.fromkeys(explicit))
    metadata = project_metadata(root)
    values = metadata.get("structure_adapters", [])
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value) in STRUCTURE_ADAPTERS]


def adapter_position(value: str, total_scenes: int) -> float | None:
    percent = re.search(r"(?<!\d)(\d{1,3}(?:\.\d+)?)\s*%", value)
    if percent:
        result = float(percent.group(1))
        return result if 0 <= result <= 100 else None
    scene_match = re.search(r"\bS0*(\d{1,3})\b", value, re.IGNORECASE)
    if not scene_match or total_scenes <= 0:
        return None
    scene = int(scene_match.group(1))
    if not 1 <= scene <= total_scenes:
        return None
    if total_scenes == 1:
        return 0.0
    return (scene - 1) * 100 / (total_scenes - 1)


def review_adapters(
    root: Path,
    adapters: list[str],
    findings: dict[str, list[dict[str, str]]],
) -> None:
    if not adapters:
        return
    path = root / "outline" / "structure-map.md"
    if not path.is_file():
        add_finding(
            findings,
            "blocking",
            "adapter-structure-map",
            str(path),
            "启用电影结构适配器但缺少统一结构图",
        )
        return
    try:
        _, body = parse_frontmatter(read_text(path))
    except (OSError, ValueError) as exc:
        add_finding(
            findings, "blocking", "adapter-structure-map", str(path), str(exc)
        )
        return
    feature_scenes = list_scene_files(root, "feature")
    total_scenes = max(
        (scene_identity(scene_path)[2] for scene_path in feature_scenes),
        default=0,
    )
    for adapter in adapters:
        missing = [
            label
            for label in ADAPTER_LABELS[adapter]
            if unresolved(labeled_value(body, label))
        ]
        if missing:
            level = "minor" if adapter == "save-the-cat" else "major"
            message = (
                f"{adapter} 适配器缺少映射：{', '.join(missing)}。"
                + (
                    "十五节拍位置只作提示，不构成阻断。"
                    if adapter == "save-the-cat"
                    else "请用人物选择和后果填写，不要只写术语。"
                )
            )
            add_finding(findings, level, f"adapter-{adapter}", str(path), message)
        if adapter != "save-the-cat":
            continue
        missing_positions: list[str] = []
        deviations: list[str] = []
        for label, expected_range in SAVE_CAT_POSITION_RANGES.items():
            value = labeled_value(body, label)
            if unresolved(value):
                continue
            position = adapter_position(value, total_scenes)
            if position is None:
                missing_positions.append(label.removeprefix("救猫咪·"))
                continue
            low, high = expected_range
            if not low <= position <= high:
                deviations.append(
                    f"{label.removeprefix('救猫咪·')}={position:.1f}%（参考 {low}–{high}%）"
                )
        if missing_positions:
            add_finding(
                findings,
                "minor",
                "adapter-save-the-cat-position-missing",
                str(path),
                "以下节拍未提供 `S001` 或百分比位置，无法做位置提示："
                + "、".join(missing_positions)
                + "。此项不阻断。",
            )
        if deviations:
            add_finding(
                findings,
                "minor",
                "adapter-save-the-cat-position",
                str(path),
                "节拍位置偏离常用参考区间："
                + "；".join(deviations)
                + "。只作诊断，不得据此强改人物因果。",
            )


def include_warning(focus: str, code: str) -> bool:
    if focus == "full":
        return True
    if focus == "dialogue":
        return code in {
            "no-dialogue",
            "dialogue-subtext",
            "character-voice",
            "quoted-dialogue",
            "long-line",
        }
    if focus == "structure":
        return code in {"structure-map-field", "scene-gap", "no-scenes"}
    if focus == "continuity":
        return code in {
            "source-card-mismatch",
            "source-missing",
            "missing-episode-outline",
            "scene-gap",
        }
    return code not in {"structure-map-field", "missing-episode-outline"}


def semantic_sections(focus: str) -> list[str]:
    sections: list[str] = []
    if focus in {"scene", "full"}:
        sections.extend(
            [
                "\n### 场景因果与价值\n\n",
                "- [ ] 视点人物的场景目标是可观察变化，不是情绪或主题。\n",
                "- [ ] 主冲突会主动反制，结果落差迫使人物换招。\n",
                "- [ ] 转折来自行动、反制或新证据，而非作者便利。\n",
                "- [ ] 入场与出场描述同一故事价值的实质变化。\n",
                "- [ ] 下场压力使后续场景因果上必要。\n",
            ]
        )
    if focus in {"dialogue", "full"}:
        sections.extend(
            [
                "\n### 对白与表演\n\n",
                "- [ ] 每句对白在争取、拒绝、试探、遮掩或改变关系。\n",
                "- [ ] 文本与潜台词存在可表演距离，未把心理说明写进动作。\n",
                "- [ ] 遮住人物名后，仍能从策略、知识和语言选择辨认说话者。\n",
                "- [ ] 删除双方已知事实的完整复述和无行动解释。\n",
            ]
        )
    if focus in {"continuity", "full"}:
        sections.extend(
            [
                "\n### 来源与连续性\n\n",
                "- [ ] 人物只使用当时已获得的知识。\n",
                "- [ ] 背景与世界规则以压力和成本生效，不以说明性对白复制。\n",
                "- [ ] 关系、伤势、物件、线索、承诺和观众证据已进入台账。\n",
                "- [ ] 新事实均能追溯到项目来源或用户明确授权。\n",
            ]
        )
    if focus in {"structure", "full"}:
        sections.extend(
            [
                "\n### 全片结构\n\n",
                "- [ ] 激励性扰动使原有策略不再足够。\n",
                "- [ ] 递进复杂化提升代价、范围、亲密度或不可逆性。\n",
                "- [ ] 危机是互不兼容且均有代价的选择。\n",
                "- [ ] 高潮由人物选择完成，并造成全片最大价值变化。\n",
                "- [ ] 作者适配器只诊断功能，不替代人物因果。\n",
            ]
        )
    return sections


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
        adapters = active_adapters(root, args.adapter)
    except (OSError, ValueError) as exc:
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
            findings, "blocking", item["code"], item["file"], item["message"]
        )
    for item in structural_warnings:
        if not include_warning(args.focus, item["code"]):
            continue
        level = "major" if item["code"] in MAJOR_WARNING_CODES else "minor"
        add_finding(findings, level, item["code"], item["file"], item["message"])

    if args.focus in {"structure", "full"} and format_name == "feature":
        review_adapters(root, adapters, findings)

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

        if args.focus in {"continuity", "full"}:
            for character in characters:
                character_id = str(character)
                if character_id not in character_ids:
                    add_finding(
                        findings,
                        "blocking" if args.strict else "major",
                        "character-source",
                        str(path),
                        f"人物 {character_id} 没有对应人物卡",
                    )

        dialogue_chars = 0
        action_chars = 0
        ai_style_hits: list[str] = []
        for line_number, raw_line in enumerate(draft.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            if args.focus in {"scene", "dialogue", "full"}:
                ai_style_hits.extend(
                    label for label, pattern in AI_STYLE_PATTERNS if pattern.search(line)
                )
            dialogue = DIALOGUE_RE.match(line)
            if dialogue:
                dialogue_text = line.split("：", 1)[1]
                dialogue_chars += len(dialogue_text)
                if args.focus in {"dialogue", "full"}:
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
                            f"对白可能向共同知情者解释设定：{line}",
                        )
            elif line.startswith("△"):
                action_chars += len(line)
                if args.focus in {"scene", "full"} and any(
                    trigger in line for trigger in MIND_TRIGGERS
                ):
                    add_finding(
                        findings,
                        "major",
                        "unfilmable-action",
                        str(path),
                        f"动作段可能包含不可拍心理：{line}",
                    )

        if len(ai_style_hits) >= 2:
            add_finding(
                findings,
                "minor",
                "ai-template-language",
                str(path),
                "命中 Humanizer-zh 中文问题清单中的高确定性模式："
                + "、".join(sorted(set(ai_style_hits)))
                + "。仅作局部审查提示，不自动改写整场。",
            )

        metrics["scenes"] += 1
        metrics["dialogue_chars"] += dialogue_chars
        metrics["action_chars"] += action_chars
        if format_name == "feature":
            sequence_scenes[str(metadata.get("sequence", 0))] += 1
        source_trace_rows.append(
            f"| {scene_id} | {labeled_value(card, '视点人物') or '缺失'} | "
            f"{labeled_value(card, '故事价值') or '缺失'} | "
            f"{len(source_files)} | {labeled_value(card, '下场压力') or '缺失'} |"
        )

    result: dict[str, Any] = {
        "project_root": str(root),
        "format": format_name,
        "focus": args.focus,
        "adapters": adapters,
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
        lines = [f"\n## {title}\n\n"]
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
        f"- 焦点：{args.focus}\n",
        f"- 结构适配器：{', '.join(adapters) or '无'}\n",
        f"- 场次数：{metrics['scenes']}\n",
        f"- 生成时间：{result['generated']}\n",
        f"- Blocking：{len(findings['blocking'])}\n",
        f"- Major：{len(findings['major'])}\n",
        f"- Minor：{len(findings['minor'])}\n",
        "\n> 自动检查只识别高确定性信号。动机、潜台词、情感和高潮质量必须完成下方语义审查。\n",
    ]
    report.extend(render_findings("blocking", "Blocking"))
    report.extend(render_findings("major", "Major"))
    report.extend(render_findings("minor", "Minor"))
    if not args.compact:
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
                    f"序列 {key}={value}"
                    for key, value in sorted(sequence_scenes.items())
                )
                + "\n"
            )
        report.extend(
            [
                "\n## 场景证据索引\n\n",
                "| 场次 | 视点人物 | 故事价值 | 来源数 | 下场压力 |\n",
                "| --- | --- | --- | ---: | --- |\n",
                *(f"{row}\n" for row in source_trace_rows),
                "\n## 语义审查（必须人工或模型完成）\n",
                *semantic_sections(args.focus),
                "\n## 编辑结论\n\n",
                "- 接受的风险：\n",
                "- 必须修复：\n",
                "- 根因场与下游影响：\n",
                "- 修订后的回归结果：\n",
            ]
        )
    else:
        report.append(
            "\n> 紧凑报告未附语义工作表；仍须按 `references/self-review.md` 完成对应焦点审查。\n"
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
