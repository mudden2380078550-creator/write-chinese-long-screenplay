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
    extract_h2_sections,
    list_scene_files,
    parse_frontmatter,
    project_format,
    read_text,
    scene_id_for,
    scene_identity,
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
DIALOGUE_RE = re.compile(r"^[^\s△#|：]{1,20}(?:（[^）]+）)?：.+$")
NOVEL_MIND_WORDS = ("内心", "心里想", "意识到", "感到", "五味杂陈", "命运")
CAMERA_WORDS = ("特写", "推镜", "拉镜", "摇镜", "航拍", "镜头切到")
PLACEHOLDERS = ("待写：", "在这里写")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验中文电影或剧集项目")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def issue(
    collection: list[dict[str, Any]], path: Path, code: str, message: str
) -> None:
    collection.append({"file": str(path), "code": code, "message": message})


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
        required.update({"act", "sequence", "source_files"})
    else:
        required.add("episode")
    missing = sorted(required - metadata.keys())
    if missing:
        issue(errors, path, "frontmatter-keys", f"缺少字段：{', '.join(missing)}")

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

    source_files = metadata.get("source_files", [])
    if isinstance(source_files, list):
        if format_name == "feature" and not source_files:
            target = errors if strict else warnings
            issue(target, path, "no-sources", "电影场次缺少 source_files")
        for relative in source_files:
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

    if not draft.strip():
        issue(errors, path, "empty-draft", "正文为空")
    if any(token in draft for token in PLACEHOLDERS):
        target = errors if strict else warnings
        issue(target, path, "placeholder", "正文仍包含模板占位文字")
    if not any(line.strip().startswith("△") for line in draft.splitlines()):
        issue(warnings, path, "no-action", "正文没有以 △ 开始的动作段")
    if not any(DIALOGUE_RE.match(line.strip()) for line in draft.splitlines()):
        issue(warnings, path, "no-dialogue", "未检测到对白；确认是否为有意无对白场")

    for line_number, raw_line in enumerate(draft.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if len(line) > 180:
            issue(warnings, path, "long-line", f"正文相对行 {line_number} 超过 180 字")
        if DIALOGUE_RE.match(line) and any(mark in line for mark in ('“', '”', '"')):
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
        format_name = project_format(root)
    except (OSError, ValueError) as exc:
        issue(errors, root / "project.md", "project-format", str(exc))
        return "unknown", [], errors, warnings

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

    if format_name == "feature" and feature_scenes:
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
