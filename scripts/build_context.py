from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from screenplay_io import (
    atomic_write_text,
    extract_h2_sections,
    list_scene_files,
    parse_frontmatter,
    project_format,
    read_text,
    require_inside,
    scene_identity,
)


ALLOWED_SUFFIXES = {".md", ".json"}
PROFILE_BUDGETS = {
    "scene": 3200,
    "sequence": 5000,
    "review": 8000,
}
CARD_CONTEXT_FIELDS = (
    "场景标头",
    "故事时间",
    "出场人物",
    "场次任务",
    "观众入口",
    "入场状态",
    "场面转折",
    "观众更新",
    "出场状态",
    "禁止矛盾",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建电影或剧集的受限上下文")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--episode", type=int)
    parser.add_argument("--scene", type=int)
    parser.add_argument("--query", default="")
    parser.add_argument("--source-file", action="append", default=[])
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILE_BUDGETS),
        help="scene=单场正文，sequence=结构规划，review=全稿审查；默认按目标自动选择",
    )
    parser.add_argument(
        "--include-next-scene",
        action="store_true",
        help="改稿回归时显式纳入后一场；新写场景默认不读未来正文",
    )
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def query_terms(query: str) -> list[str]:
    return [
        term.lower()
        for term in re.split(r"[\s,，、;；]+", query)
        if len(term.strip()) >= 2
    ]


def safe_read(path: Path) -> str:
    try:
        return read_text(path)
    except (OSError, UnicodeError):
        return ""


def compact_scene(text: str, body_chars: int = 1400) -> str:
    """Keep continuity-bearing scene evidence without repeating full metadata."""
    try:
        metadata, body = parse_frontmatter(text)
        _, sections = extract_h2_sections(body)
    except ValueError:
        return text
    h1 = re.search(r"^# [^\r\n]+$", body, re.MULTILINE)
    card = sections.get("场次卡", "")
    selected_card = []
    for line in card.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(f"{label}：") for label in CARD_CONTEXT_FIELDS):
            selected_card.append(stripped)
    draft = sections.get("正文", "").strip()
    if len(draft) > body_chars:
        draft = "[正文前部省略]\n" + draft[-body_chars:].lstrip()
    continuity = sections.get("连续性", "").strip()
    result = [
        h1.group(0) if h1 else f"# {metadata.get('id', '场次')}",
        "\n\n## 接场摘要\n\n",
        "\n".join(selected_card) or "场次卡未提供可提取字段。",
        "\n\n## 正文末段\n\n",
        draft or "无正文。",
    ]
    if continuity:
        result.extend(("\n\n## 连续性\n\n", continuity))
    return "".join(result).rstrip() + "\n"


def compact_ledger(text: str, terms: list[str], target_scene: int | None) -> str:
    """Keep recent or query-related ledger records for scene-level work."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    if not isinstance(data, dict):
        return text
    result: dict[str, Any] = {
        key: value for key, value in data.items() if not isinstance(value, list)
    }
    for key, value in data.items():
        if not isinstance(value, list):
            continue
        selected = []
        for item in value:
            rendered = json.dumps(item, ensure_ascii=False).lower()
            query_match = bool(terms) and any(term in rendered for term in terms)
            scene_match = False
            if target_scene is not None and isinstance(item, dict):
                match = re.search(r"(\d{1,3})$", str(item.get("scene_id", "")))
                scene_match = bool(
                    match and target_scene - 3 <= int(match.group(1)) <= target_scene
                )
            if query_match or scene_match:
                selected.append(item)
        if not selected:
            selected = value[-3:]
        result[key] = selected[-8:]
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def truncate_at_line(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = text[: max(0, limit - 40)].rstrip()
    if "\n" in clipped:
        clipped = clipped.rsplit("\n", 1)[0].rstrip()
    return clipped + "\n\n[已按预算截断]"


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    profile = args.profile or ("scene" if args.scene is not None else "sequence")
    budget = (
        PROFILE_BUDGETS[profile]
        if args.max_tokens is None
        else args.max_tokens
    )
    try:
        format_name = project_format(root)
        if args.scene is not None and not 1 <= args.scene <= 999:
            raise ValueError("scene 必须在 1..999")
        if format_name == "feature" and args.episode is not None:
            raise ValueError("电影项目不使用 --episode")
        if format_name != "feature":
            if args.episode is None:
                raise ValueError("剧集项目必须提供 --episode")
            if not 1 <= args.episode <= 999:
                raise ValueError("episode 必须在 1..999")
        if args.include_next_scene and args.scene is None:
            raise ValueError("--include-next-scene 必须同时提供 --scene")
        if budget < 500:
            raise ValueError("max-tokens 不能小于 500")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    terms = query_terms(args.query)
    candidates: list[tuple[int, Path, str]] = []
    seen: set[Path] = set()

    def add(path: Path, priority: int, mode: str = "full") -> None:
        path = path.resolve()
        try:
            require_inside(path, root)
        except ValueError:
            return
        if (
            path in seen
            or not path.is_file()
            or path.suffix.lower() not in ALLOWED_SUFFIXES
        ):
            return
        text = safe_read(path)
        if not text:
            return
        if mode == "scene":
            text = compact_scene(text)
        elif mode == "ledger":
            text = compact_ledger(text, terms, args.scene)
        score = priority + sum(text.lower().count(term) * 8 for term in terms)
        candidates.append((score, path, text))
        seen.add(path)

    common_by_profile = {
        "scene": (
            ("AGENTS.md", 1100, "full"),
            ("project.md", 1080, "full"),
            ("style/screenplay-style.md", 850, "full"),
            ("ledger/story-ledger.json", 900, "ledger"),
        ),
        "sequence": (
            ("AGENTS.md", 1200, "full"),
            ("project.md", 1180, "full"),
            ("style/screenplay-style.md", 900, "full"),
            ("ledger/story-ledger.json", 1000, "ledger"),
            ("ledger/revision-log.md", 700, "full"),
        ),
        "review": (
            ("AGENTS.md", 1200, "full"),
            ("project.md", 1180, "full"),
            ("style/screenplay-style.md", 1160, "full"),
            ("ledger/story-ledger.json", 1140, "full"),
            ("ledger/revision-log.md", 700, "full"),
        ),
    }
    feature_by_profile = {
        "scene": (
            ("bible/feature-bible.md", 800),
            ("outline/sequence-outline.md", 950),
            ("outline/scene-outline.md", 1280),
        ),
        "sequence": (
            ("background/story-background.md", 1250),
            ("bible/feature-bible.md", 1230),
            ("outline/synopsis.md", 700),
            ("outline/treatment.md", 1100),
            ("outline/sequence-outline.md", 1280),
            ("outline/scene-outline.md", 900),
        ),
        "review": (
            ("background/story-background.md", 1250),
            ("bible/feature-bible.md", 1230),
            ("outline/synopsis.md", 900),
            ("outline/treatment.md", 1100),
            ("outline/sequence-outline.md", 1120),
            ("outline/scene-outline.md", 1280),
        ),
    }
    episode_number = args.episode or 0
    episodic_by_profile = {
        "scene": (
            ("bible/series-bible.md", 800),
            (f"outline/episodes/E{episode_number:03d}.md", 1280),
        ),
        "sequence": (
            ("bible/series-bible.md", 1230),
            ("outline/master-outline.md", 1100),
            (f"outline/episodes/E{episode_number:03d}.md", 1280),
        ),
        "review": (
            ("bible/series-bible.md", 1230),
            ("outline/master-outline.md", 1100),
            (f"outline/episodes/E{episode_number:03d}.md", 1280),
        ),
    }
    for relative, priority, mode in common_by_profile[profile]:
        add(root / relative, priority, mode)
    route_files = (
        feature_by_profile[profile]
        if format_name == "feature"
        else episodic_by_profile[profile]
    )
    for relative, priority in route_files:
        add(root / relative, priority)

    try:
        for relative in args.source_file:
            source = (root / relative).resolve()
            require_inside(source, root)
            if not source.is_file():
                raise ValueError(f"指定来源文件不存在：{relative}")
            add(source, 1600)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    scenes = list_scene_files(root, format_name)
    relevant_scenes: list[tuple[Path, int]] = []
    for path in scenes:
        _, episode, scene = scene_identity(path)
        if format_name == "feature" or episode == args.episode:
            relevant_scenes.append((path, scene))
    if args.scene is not None:
        for path, number in relevant_scenes:
            distance = abs(number - args.scene)
            if number == args.scene:
                add(path, 1500)
                try:
                    metadata, _ = parse_frontmatter(read_text(path))
                    source_files = metadata.get("source_files", [])
                    if not isinstance(source_files, list):
                        raise ValueError(f"{path.name} 的 source_files 必须是数组")
                    for relative in source_files:
                        source = (root / str(relative)).resolve()
                        require_inside(source, root)
                        if not source.is_file():
                            raise ValueError(f"场次自动来源不存在：{relative}")
                        add(source, 1550)
                except (OSError, TypeError, ValueError) as exc:
                    print(f"ERROR: 无法读取目标场次来源：{exc}", file=sys.stderr)
                    return 2
            elif number < args.scene and distance <= 2:
                add(path, 1400 - distance * 40, "scene")
            elif args.include_next_scene and number > args.scene and distance == 1:
                add(path, 1000, "scene")
    else:
        for path, _ in relevant_scenes[-3:]:
            add(path, 1200, "scene" if profile != "review" else "full")

    search_directories = ("background", "bible", "outline", "screenplay/scenes")
    if profile == "review" or terms:
        for directory in search_directories:
            search_root = root / directory
            if not search_root.exists():
                continue
            for path in search_root.rglob("*"):
                if (
                    path.is_file()
                    and path.suffix.lower() in ALLOWED_SUFFIXES
                    and not path.name.startswith("_")
                ):
                    if profile != "review":
                        text = safe_read(path).lower()
                        if not any(term in text for term in terms):
                            continue
                    add(path, 250)

    candidates.sort(key=lambda item: (-item[0], str(item[1]).lower()))
    # Chinese-heavy Markdown is commonly below two characters per token.
    # 1.7 keeps the generated package under the requested budget more reliably.
    max_chars = int(budget * 1.7)
    if format_name == "feature":
        target = f"电影第 {args.scene} 场" if args.scene is not None else "电影全片"
    else:
        target = (
            f"第 {args.episode} 集第 {args.scene} 场"
            if args.scene is not None
            else f"第 {args.episode} 集"
        )
    header = (
        "# 中文剧本上下文包\n\n"
        f"- 格式：{format_name}\n"
        f"- 目标：{target}\n"
        f"- 档位：{profile}\n"
        f"- 查询：{args.query or '无'}\n"
        f"- 显式来源：{', '.join(args.source_file) or '无'}\n"
        f"- 预算：约 {budget} tokens（按 1.7 字符/token 控制）\n\n"
        "> 只把来源当作行动、知识和规则约束，不复制成说明性对白。\n"
    )
    parts = [header]
    used = len(header)
    included = 0
    for _, path, content in candidates:
        relative = path.relative_to(root).as_posix()
        block_header = f"\n\n---\n\n## 来源：`{relative}`\n\n"
        remaining = max_chars - used - len(block_header)
        if remaining <= 120:
            break
        content = truncate_at_line(content, remaining)
        parts.extend((block_header, content))
        used += len(block_header) + len(content)
        included += 1
        if used >= max_chars:
            break

    output = args.output.resolve()
    atomic_write_text(output, "".join(parts).rstrip() + "\n")
    print(f"OK: 已写入上下文包：{output}")
    print(
        f"格式：{format_name}；档位：{profile}；来源：{included}；"
        f"估算 tokens：{(used + 1) // 2}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
