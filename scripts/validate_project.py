from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from screenplay_io import (
    EPISODIC_FORMATS,
    LEDGER_LIST_KEYS,
    V2_REQUIRED_CARD_FIELDS,
    extract_h2_sections,
    labeled_value,
    list_scene_files,
    parse_frontmatter,
    project_contract,
    project_format,
    read_text,
    scene_id_for,
    scene_identity,
    unresolved,
)


COMMON_REQUIRED_KEYS = {
    "id",
    "type",
    "scene",
    "title",
    "status",
    "location",
    "time_of_day",
    "interior_exterior",
    "characters",
    "threads",
    "source_files",
    "created",
    "updated",
}
EXPECTED_H2 = ["场次卡", "正文", "连续性", "改稿备注"]
FEATURE_HEADER_RE = re.compile(
    r"^场景标头：(?P<scene>\d+)\s+.+\s+"
    r"(?P<time>日|夜|晨|昏|连续)\s+(?P<space>内|外|内外)$",
    re.MULTILINE,
)
EPISODIC_HEADER_RE = re.compile(
    r"^场景标头：(?P<episode>\d+)-(?P<scene>\d+)\s+.+\s+"
    r"(?P<time>日|夜|晨|昏|连续)\s+(?P<space>内|外|内外)$",
    re.MULTILINE,
)
DIALOGUE_RE = re.compile(r"^[^\s△|：]{1,20}(?:（[^）]+）)?：.+$")
NOVEL_MIND_WORDS = ("内心", "心里想", "意识到", "感到", "五味杂陈", "命运")
CAMERA_WORDS = ("特写", "推镜", "拉镜", "摇镜", "航拍", "镜头切到")
PLACEHOLDERS = ("待写：", "在这里写", "【待补】", "TODO", "TBD")
STRUCTURE_LABELS = (
    "主题命题",
    "反命题",
    "外在欲望",
    "内在需要",
    "核心行动线",
    "激励性扰动",
    "递进复杂化",
    "不可回头点",
    "危机选择",
    "高潮行动",
    "结局价值",
    "余波",
)
CARD_VALUE_FIELDS = tuple(
    field for field in V2_REQUIRED_CARD_FIELDS if field != "禁止矛盾"
)
STATUSES = {"outline", "draft", "revision", "final", "locked"}
TIME_VALUES = {"日", "夜", "晨", "昏", "连续"}
SPACE_VALUES = {"内", "外", "内外"}
FEATURE_SOURCE_MARKERS = {
    "bible/feature-bible.md": (
        "## 主题命题",
        "主题命题（价值结果，因为人物如何行动）",
        "反命题（相反价值结果，因为人物如何行动）",
        "外在欲望",
        "内在需要",
        "核心行动线",
        "余波必须展示的价值状态",
    ),
    "outline/sequence-outline.md": (
        "| 序列 | 幕 | 故事价值 | 进入价值 | 序列任务 | 递进压力 | 关键选择 | 序列转折 | 退出价值 | 下序列压力 |",
    ),
    "outline/scene-outline.md": (
        "| 场 | 幕/序列 | 地点/日夜/内外 | 来源 | 视点人物 | 场景目标 | 故事价值 | 入场价值 | 主冲突/策略 | 预期→实际/落差 | 转折 | 观众更新 | 出场价值 | 下场压力 |",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验 v2 中文电影或剧集项目")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def issue(
    collection: list[dict[str, Any]], path: Path, code: str, message: str
) -> None:
    collection.append({"file": str(path), "code": code, "message": message})


def is_missing_card_value(value: str) -> bool:
    return value == "-" or unresolved(value)


def validate_integer_field(
    errors: list[dict[str, Any]],
    path: Path,
    metadata: dict[str, Any],
    key: str,
    minimum: int,
    maximum: int,
) -> None:
    value = metadata.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        issue(errors, path, f"{key}-type", f"{key} 必须是整数")
    elif not minimum <= value <= maximum:
        issue(
            errors,
            path,
            f"{key}-range",
            f"{key} 必须在 {minimum}..{maximum}",
        )


def validate_feature_source_schema(
    root: Path,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for relative, markers in FEATURE_SOURCE_MARKERS.items():
        path = root / relative
        if not path.is_file():
            continue
        try:
            text = read_text(path)
        except (OSError, UnicodeError) as exc:
            issue(errors, path, "feature-source-parse", str(exc))
            continue
        missing = [marker for marker in markers if marker not in text]
        if missing:
            issue(
                errors,
                path,
                "feature-source-schema",
                f"仍是旧版或不完整模板，缺少：{', '.join(missing)}",
            )
    return errors


def validate_scene(
    path: Path, strict: bool, format_name: str, project_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        kind, episode, scene = scene_identity(path)
        metadata, body = parse_frontmatter(read_text(path))
    except (OSError, ValueError) as exc:
        issue(errors, path, "parse", str(exc))
        return errors, warnings, None

    expected_kind = "feature" if format_name == "feature" else "episodic"
    if kind != expected_kind:
        issue(
            errors,
            path,
            "format-scene-id",
            f"{format_name} 项目不能使用 {path.name} 场次命名",
        )

    required = set(COMMON_REQUIRED_KEYS)
    if format_name == "feature":
        required.update({"act", "sequence"})
    else:
        required.add("episode")
    missing = sorted(required - metadata.keys())
    if missing:
        issue(errors, path, "frontmatter-keys", f"缺少字段：{', '.join(missing)}")

    validate_integer_field(errors, path, metadata, "scene", 1, 999)
    if format_name == "feature":
        validate_integer_field(errors, path, metadata, "act", 1, 99)
        validate_integer_field(errors, path, metadata, "sequence", 1, 999)
    else:
        validate_integer_field(errors, path, metadata, "episode", 1, 999)

    for key in ("id", "title", "location", "created", "updated"):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            issue(errors, path, f"{key}-value", f"{key} 必须是非空字符串")
    if metadata.get("status") not in STATUSES:
        issue(errors, path, "status-value", f"status 必须是：{', '.join(sorted(STATUSES))}")
    if metadata.get("time_of_day") not in TIME_VALUES:
        issue(
            errors,
            path,
            "time-of-day-value",
            f"time_of_day 必须是：{', '.join(sorted(TIME_VALUES))}",
        )
    if metadata.get("interior_exterior") not in SPACE_VALUES:
        issue(
            errors,
            path,
            "interior-exterior-value",
            f"interior_exterior 必须是：{', '.join(sorted(SPACE_VALUES))}",
        )

    if format_name == "feature":
        expected_id = scene_id_for(format_name, scene)
    elif episode is not None:
        expected_id = scene_id_for(format_name, scene, episode)
    else:
        expected_id = f"E???-S{scene:03d}"
    if metadata.get("id") != expected_id:
        issue(errors, path, "id-mismatch", f"id 应为 {expected_id}")
    if metadata.get("type") != "scene":
        issue(errors, path, "type", "type 必须为 scene")
    if metadata.get("scene") != scene:
        issue(errors, path, "number-mismatch", "scene 与文件名不一致")
    if format_name in EPISODIC_FORMATS and metadata.get("episode") != episode:
        issue(errors, path, "episode-mismatch", "episode 与文件名不一致")

    for key in ("characters", "threads", "source_files"):
        value = metadata.get(key, [])
        if not isinstance(value, list):
            issue(errors, path, f"{key}-type", f"{key} 必须是 YAML 数组")
        else:
            for item in value:
                if not isinstance(item, str) or not item.strip():
                    issue(
                        errors,
                        path,
                        f"{key}-value",
                        f"{key} 只能包含非空字符串",
                    )

    characters = metadata.get("characters", [])
    if isinstance(characters, list) and not characters:
        issue(errors, path, "no-characters", "v2 场次至少需要一个人物")

    source_files = metadata.get("source_files", [])
    if isinstance(source_files, list):
        if not source_files:
            issue(errors, path, "no-sources", "v2 场次缺少 source_files")
        for relative in source_files:
            if not isinstance(relative, str) or not relative.strip():
                issue(errors, path, "source-value", "source_files 只能包含非空相对路径")
                continue
            if Path(relative).is_absolute():
                issue(errors, path, "source-absolute", f"来源必须是项目相对路径：{relative}")
                continue
            source = (project_root / str(relative)).resolve()
            try:
                source.relative_to(project_root.resolve())
            except ValueError:
                issue(errors, path, "source-outside", f"来源超出项目：{relative}")
                continue
            if not source.is_file():
                issue(errors, path, "source-missing", f"来源文件不存在：{relative}")

    h1_matches = re.findall(r"^# ([^\r\n]+)$", body, re.MULTILINE)
    expected_h1 = f"{expected_id} {metadata.get('title', '')}".rstrip()
    if len(h1_matches) != 1 or h1_matches[0] != expected_h1:
        issue(errors, path, "h1", f"H1 必须且只能为：# {expected_h1}")

    names, sections = extract_h2_sections(body)
    if names != EXPECTED_H2:
        issue(
            errors,
            path,
            "sections",
            f"H2 必须依次为：{' / '.join(EXPECTED_H2)}；实际：{' / '.join(names)}",
        )
    card = sections.get("场次卡", "")
    draft = sections.get("正文", "")
    header_re = FEATURE_HEADER_RE if format_name == "feature" else EPISODIC_HEADER_RE
    header = header_re.search(card)
    if not header:
        issue(errors, path, "scene-header", "场次卡缺少合法场景标头")
    else:
        if int(header.group("scene")) != scene:
            issue(errors, path, "header-scene", "场景标头场号与文件名不一致")
        if (
            format_name in EPISODIC_FORMATS
            and episode is not None
            and int(header.group("episode")) != episode
        ):
            issue(errors, path, "header-episode", "场景标头集号与文件名不一致")
        if header.group("time") != metadata.get("time_of_day"):
            issue(errors, path, "header-time", "场景标头日夜与 frontmatter 不一致")
        if header.group("space") != metadata.get("interior_exterior"):
            issue(errors, path, "header-space", "场景标头内外与 frontmatter 不一致")

    card_values = {field: labeled_value(card, field) for field in V2_REQUIRED_CARD_FIELDS}
    for field in V2_REQUIRED_CARD_FIELDS:
        if not re.search(rf"^{re.escape(field)}：", card, re.MULTILINE):
            issue(errors, path, "card-field-label", f"场次卡缺少字段：{field}")
    for field in CARD_VALUE_FIELDS:
        if is_missing_card_value(card_values[field]):
            issue(errors, path, "card-field-value", f"场次卡字段未完成：{field}")

    viewpoint = card_values.get("视点人物", "")
    if isinstance(characters, list) and viewpoint and viewpoint not in characters:
        issue(errors, path, "viewpoint-character", "视点人物必须出现在 characters 中")
    if (
        card_values.get("入场价值", "").casefold()
        == card_values.get("出场价值", "").casefold()
        and not is_missing_card_value(card_values.get("入场价值", ""))
    ):
        issue(errors, path, "static-story-value", "入场价值与出场价值没有变化")
    if (
        card_values.get("预期结果", "").casefold()
        == card_values.get("实际结果", "").casefold()
        and not is_missing_card_value(card_values.get("预期结果", ""))
    ):
        issue(errors, path, "no-result-gap", "预期结果与实际结果相同")

    if isinstance(source_files, list):
        source_basis = card_values.get("来源依据", "")
        for relative in source_files:
            if str(relative) not in source_basis:
                issue(
                    warnings,
                    path,
                    "source-card-mismatch",
                    f"source_files 中的来源未出现在场次卡：{relative}",
                )

    if not draft.strip():
        issue(errors, path, "empty-draft", "正文为空")
    if any(token in draft for token in PLACEHOLDERS):
        target = errors if strict else warnings
        issue(target, path, "placeholder", "正文或场次卡仍包含占位内容")
    if not any(line.strip().startswith("△") for line in draft.splitlines()):
        issue(warnings, path, "no-action", "正文没有以 △ 开始的动作段")
    dialogue_lines = [
        line.strip() for line in draft.splitlines() if DIALOGUE_RE.match(line.strip())
    ]
    if not dialogue_lines:
        issue(warnings, path, "no-dialogue", "未检测到对白；确认是否为有意无对白场")
    else:
        for label, code in (
            ("对白潜台词", "dialogue-subtext"),
            ("人物语言", "character-voice"),
        ):
            value = labeled_value(card, label)
            if value in {"", "-"} or unresolved(value):
                issue(
                    warnings,
                    path,
                    code,
                    f"有对白场景未填写{label}",
                )

    for line_number, raw_line in enumerate(draft.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if len(line) > 180:
            issue(warnings, path, "long-line", f"正文相对行 {line_number} 超过 180 字")
        if DIALOGUE_RE.match(line) and any(mark in line for mark in ("“", "”", '"')):
            target = errors if strict else warnings
            issue(target, path, "quoted-dialogue", f"对白不应使用小说式引号：{line}")
        if line.startswith("△") and any(word in line for word in NOVEL_MIND_WORDS):
            issue(
                warnings,
                path,
                "unfilmable-mind",
                f"动作段可能包含不可直接拍摄的心理叙述：{line}",
            )
        if any(word in line for word in CAMERA_WORDS):
            issue(
                warnings,
                path,
                "camera-direction",
                f"检测到镜头术语；确认是否为拍摄稿必要表达：{line}",
            )
    return errors, warnings, metadata


def validate_structure_map(
    root: Path, strict: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    path = root / "outline" / "structure-map.md"
    if not path.is_file():
        issue(errors, path, "feature-source", "缺少电影创作源：outline/structure-map.md")
        return errors, warnings
    try:
        _, body = parse_frontmatter(read_text(path))
    except (OSError, ValueError) as exc:
        issue(errors, path, "structure-map-parse", str(exc))
        return errors, warnings
    target = errors if strict else warnings
    for label in STRUCTURE_LABELS:
        value = labeled_value(body, label)
        if unresolved(value):
            issue(target, path, "structure-map-field", f"统一结构图未完成：{label}")
    return errors, warnings


def validate_project(
    root: Path, strict: bool
) -> tuple[str, list[Path], list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for required in ("AGENTS.md", "project.md"):
        path = root / required
        if not path.is_file():
            issue(errors, path, "project-file", f"缺少项目文件：{required}")
    try:
        project, contract_errors = project_contract(root)
        for message in contract_errors:
            issue(errors, root / "project.md", "project-contract", message)
        if project.get("type") != "project":
            issue(errors, root / "project.md", "project-type", "type 必须为 project")
        for key in ("id", "title", "status", "created", "updated"):
            value = project.get(key)
            if not isinstance(value, str) or not value.strip():
                issue(
                    errors,
                    root / "project.md",
                    "project-field",
                    f"{key} 必须是非空字符串",
                )
        format_name = project_format(root)
        adapters = project.get("structure_adapters", [])
        if format_name in EPISODIC_FORMATS and isinstance(adapters, list) and adapters:
            issue(
                errors,
                root / "project.md",
                "episodic-adapters",
                "电影结构适配器不能应用于剧集项目",
            )
    except (OSError, ValueError) as exc:
        issue(errors, root / "project.md", "project-format", str(exc))
        return "unknown", [], errors, warnings

    ledger_path = root / "ledger" / "story-ledger.json"
    if not ledger_path.is_file():
        issue(errors, ledger_path, "project-ledger", "缺少 ledger/story-ledger.json")
    else:
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
            if not isinstance(ledger, dict):
                raise ValueError("台账顶层必须是对象")
            if ledger.get("schema_version") != 2:
                issue(errors, ledger_path, "ledger-schema", "台账 schema_version 必须为 2")
            if ledger.get("format") != format_name:
                issue(errors, ledger_path, "ledger-format", "台账 format 与项目不一致")
            for key in LEDGER_LIST_KEYS:
                if not isinstance(ledger.get(key), list):
                    issue(errors, ledger_path, "ledger-field", f"台账字段 {key} 必须是数组")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issue(errors, ledger_path, "ledger-parse", str(exc))

    scenes = list_scene_files(root)
    if not scenes:
        issue(warnings, root / "screenplay" / "scenes", "no-scenes", "项目尚无正式场次")

    ids: dict[str, Path] = {}
    episode_scenes: dict[int, list[int]] = defaultdict(list)
    feature_scenes: list[int] = []
    for path in scenes:
        scene_errors, scene_warnings, metadata = validate_scene(
            path, strict, format_name, root
        )
        errors.extend(scene_errors)
        warnings.extend(scene_warnings)
        if metadata:
            scene_id = str(metadata.get("id", ""))
            if scene_id in ids:
                issue(errors, path, "duplicate-id", f"ID 与 {ids[scene_id]} 重复")
            else:
                ids[scene_id] = path
        try:
            kind, episode, scene = scene_identity(path)
        except ValueError:
            continue
        if kind == "feature":
            feature_scenes.append(scene)
        elif episode is not None:
            episode_scenes[episode].append(scene)

    if format_name == "feature":
        structure_errors, structure_warnings = validate_structure_map(root, strict)
        errors.extend(structure_errors)
        warnings.extend(structure_warnings)
        if feature_scenes:
            expected = list(range(min(feature_scenes), max(feature_scenes) + 1))
            missing = sorted(set(expected) - set(feature_scenes))
            if missing:
                issue(
                    warnings,
                    root / "screenplay" / "scenes",
                    "scene-gap",
                    f"电影场号存在空缺：{missing}",
                )
        for required in (
            "background/story-background.md",
            "bible/feature-bible.md",
            "outline/treatment.md",
            "outline/sequence-outline.md",
            "outline/scene-outline.md",
        ):
            path = root / required
            if not path.is_file():
                issue(errors, path, "feature-source", f"缺少电影创作源：{required}")
        errors.extend(validate_feature_source_schema(root))
    elif format_name in EPISODIC_FORMATS:
        for episode, numbers in sorted(episode_scenes.items()):
            expected = list(range(min(numbers), max(numbers) + 1))
            missing = sorted(set(expected) - set(numbers))
            if missing:
                issue(
                    warnings,
                    root / "screenplay" / "scenes",
                    "scene-gap",
                    f"第 {episode} 集场号存在空缺：{missing}",
                )
            outline = root / "outline" / "episodes" / f"E{episode:03d}.md"
            if not outline.exists():
                issue(warnings, outline, "missing-episode-outline", "缺少对应分集大纲")
    return format_name, scenes, errors, warnings


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    format_name, scenes, errors, warnings = validate_project(root, args.strict)
    result = {
        "project_root": str(root),
        "format": format_name,
        "scene_count": len(scenes),
        "errors": errors,
        "warnings": warnings,
    }
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for entry in errors:
            print(f"ERROR [{entry['code']}] {entry['file']}: {entry['message']}")
        for entry in warnings:
            print(f"WARN  [{entry['code']}] {entry['file']}: {entry['message']}")
        print(
            f"SUMMARY: format={format_name} scenes={len(scenes)} "
            f"errors={len(errors)} warnings={len(warnings)}"
        )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
