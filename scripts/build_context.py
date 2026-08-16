from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

from screenplay_io import (
    atomic_write_text,
    extract_h2_sections,
    list_scene_files,
    parse_frontmatter,
    project_contract,
    project_format,
    read_text,
    require_inside,
    scene_identity,
)


ALLOWED_SUFFIXES = {".md", ".json"}
PROFILE_BUDGETS = {
    "scene-light": 4000,
    "scene": 7000,
    "scene-complex": 12000,
    "batch": 16000,
    "sequence": 4200,
    "dialogue-review": 3200,
    "structure-review": 6000,
    "full-review": 8000,
    "review": 8000,
}
PROFILE_FILE_CAPS = {
    "scene-light": 2800,
    "scene": 5000,
    "scene-complex": 8000,
    "batch": 8000,
    "sequence": 4200,
    "dialogue-review": 3200,
    "structure-review": 6500,
    "full-review": 8000,
}
CARD_CONTEXT_FIELDS = (
    "场景标头",
    "故事时间",
    "出场人物",
    "视点人物",
    "场景目标",
    "故事价值",
    "入场价值",
    "主冲突",
    "策略",
    "预期结果",
    "实际结果",
    "结果落差",
    "观众入口",
    "场面转折",
    "观众更新",
    "出场价值",
    "下场压力",
    "对白潜台词",
    "人物语言",
    "禁止矛盾",
    "两难选项",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建电影或剧集的受限上下文")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--episode", type=int)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--scene", type=int)
    target.add_argument("--scene-from", type=int)
    parser.add_argument("--scene-to", type=int)
    parser.add_argument("--query", default="")
    parser.add_argument("--source-file", action="append", default=[])
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILE_BUDGETS),
        help=(
            "scene-light=轻量场，scene=标准场，scene-complex=复杂场，"
            "batch=连续 1..8 场共享上下文，sequence=序列规划，"
            "dialogue-review=对白审查，structure-review=结构审查，"
            "full-review=全稿审查；review 为兼容别名"
        ),
    )
    parser.add_argument(
        "--include-next-scene",
        action="store_true",
        help="改稿回归时显式纳入目标或批次后一场；新写场景默认不读未来正文",
    )
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        help="显式允许覆盖已存在的上下文输出文件",
    )
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


def compact_ledger(
    text: str,
    terms: list[str],
    target_start: int | None,
    target_end: int | None,
) -> str:
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
            if target_start is not None and isinstance(item, dict):
                match = re.search(r"(\d{1,3})$", str(item.get("scene_id", "")))
                upper = target_end if target_end is not None else target_start
                scene_match = bool(
                    match
                    and target_start - 3 <= int(match.group(1)) <= upper
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


def markdown_sections(text: str) -> list[tuple[str, str]]:
    normalized = text.replace("\r\n", "\n")
    matches = list(re.finditer(r"^(#{1,6})\s+([^\r\n]+)\s*$", normalized, re.MULTILINE))
    if not matches:
        return [("全文", normalized)]
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = 0 if index == 0 else match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        label = match.group(2).strip()
        sections.append((label, normalized[start:end].strip() + "\n"))
    return sections


def select_markdown_sections(
    text: str,
    terms: list[str],
    file_cap: int,
) -> list[tuple[str, str, int]]:
    sections = markdown_sections(text)
    ranked: list[tuple[int, int, str, str]] = []
    for index, (label, content) in enumerate(sections):
        lowered = content.lower()
        term_hits = sum(lowered.count(term) for term in terms)
        # A direct query hit must outrank generic route files; otherwise a small
        # global budget can be consumed before the relevant section is reached.
        score = term_hits * 2000 + (20 if index == 0 else 0)
        ranked.append((score, index, label, content))
    if terms and any(item[0] for item in ranked):
        ranked.sort(key=lambda item: (-item[0], item[1]))
    else:
        ranked.sort(key=lambda item: item[1])

    selected: list[tuple[str, str, int]] = []
    used = 0
    for score, _, label, content in ranked:
        remaining = file_cap - used
        if remaining <= 80:
            break
        clipped = truncate_at_line(content, remaining)
        selected.append((label, clipped, score))
        used += len(clipped)
    return selected


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    has_range = args.scene_from is not None or args.scene_to is not None
    profile = args.profile or (
        "batch" if has_range else ("scene" if args.scene is not None else "sequence")
    )
    profile_key = "full-review" if profile == "review" else profile
    target_start = args.scene if args.scene is not None else args.scene_from
    target_end = args.scene if args.scene is not None else args.scene_to
    budget = (
        PROFILE_BUDGETS[profile]
        if args.max_tokens is None
        else args.max_tokens
    )
    try:
        _, contract_errors = project_contract(root)
        if contract_errors:
            raise ValueError("项目不是有效 v2：" + "；".join(contract_errors))
        format_name = project_format(root)
        if args.scene is not None and not 1 <= args.scene <= 999:
            raise ValueError("scene 必须在 1..999")
        if (args.scene_from is None) != (args.scene_to is None):
            raise ValueError("--scene-from 与 --scene-to 必须同时提供")
        if args.scene_from is not None:
            if not 1 <= args.scene_from <= 999 or not 1 <= args.scene_to <= 999:
                raise ValueError("scene-from 和 scene-to 必须在 1..999")
            if args.scene_from > args.scene_to:
                raise ValueError("scene-from 不能大于 scene-to")
            if args.scene_to - args.scene_from + 1 > 8:
                raise ValueError("batch 单次最多构建连续 8 场")
            if profile_key != "batch":
                raise ValueError("场次范围必须使用 --profile batch")
        if profile_key == "batch" and args.scene_from is None:
            raise ValueError("batch 必须同时提供 --scene-from 与 --scene-to")
        if format_name == "feature" and args.episode is not None:
            raise ValueError("电影项目不使用 --episode")
        if format_name != "feature":
            if args.episode is None:
                raise ValueError("剧集项目必须提供 --episode")
            if not 1 <= args.episode <= 999:
                raise ValueError("episode 必须在 1..999")
        if args.include_next_scene and target_start is None:
            raise ValueError(
                "--include-next-scene 必须提供 --scene 或场次范围"
            )
        if budget < 500:
            raise ValueError("max-tokens 不能小于 500")
        output = args.output.resolve()
        if output.exists() and not args.force:
            raise ValueError("输出文件已存在；如确认覆盖，请显式使用 --force")
        if output.exists() and not output.is_file():
            raise ValueError(f"输出路径不是文件：{output}")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    terms = query_terms(args.query)
    candidate_map: dict[tuple[Path, str], tuple[int, Path, str, str]] = {}

    def add(path: Path, priority: int, mode: str = "full") -> None:
        path = path.resolve()
        try:
            require_inside(path, root)
        except ValueError:
            return
        if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
            return
        text = safe_read(path)
        if not text:
            return
        if mode == "scene":
            text = compact_scene(text)
            prepared = [("接场摘要", truncate_at_line(text, PROFILE_FILE_CAPS[profile_key]), 0)]
        elif mode == "ledger":
            text = compact_ledger(text, terms, target_start, target_end)
            prepared = [("相关台账", truncate_at_line(text, PROFILE_FILE_CAPS[profile_key]), 0)]
        elif path.suffix.lower() == ".md":
            prepared = select_markdown_sections(
                text,
                terms,
                PROFILE_FILE_CAPS[profile_key],
            )
        else:
            prepared = [("全文", truncate_at_line(text, PROFILE_FILE_CAPS[profile_key]), 0)]
        for label, content, section_score in prepared:
            score = (
                priority
                + section_score
                + sum(content.lower().count(term) * 8 for term in terms)
            )
            key = (path, label)
            previous = candidate_map.get(key)
            candidate = (score, path, label, content)
            if previous is None or score > previous[0]:
                candidate_map[key] = candidate

    common_by_profile = {
        "scene-light": (
            ("AGENTS.md", 1100, "full"),
            ("project.md", 1080, "full"),
            ("style/screenplay-style.md", 850, "full"),
            ("ledger/story-ledger.json", 900, "ledger"),
        ),
        "scene": (
            ("AGENTS.md", 1100, "full"),
            ("project.md", 1080, "full"),
            ("style/screenplay-style.md", 850, "full"),
            ("ledger/story-ledger.json", 900, "ledger"),
        ),
        "scene-complex": (
            ("AGENTS.md", 1100, "full"),
            ("project.md", 1080, "full"),
            ("style/screenplay-style.md", 850, "full"),
            ("ledger/story-ledger.json", 1000, "ledger"),
            ("ledger/revision-log.md", 650, "full"),
        ),
        "batch": (
            ("AGENTS.md", 1200, "full"),
            ("project.md", 1180, "full"),
            ("style/screenplay-style.md", 900, "full"),
            ("ledger/story-ledger.json", 1250, "ledger"),
            ("ledger/revision-log.md", 650, "full"),
        ),
        "sequence": (
            ("AGENTS.md", 1200, "full"),
            ("project.md", 1180, "full"),
            ("style/screenplay-style.md", 900, "full"),
            ("ledger/story-ledger.json", 1000, "ledger"),
            ("ledger/revision-log.md", 700, "full"),
        ),
        "dialogue-review": (
            ("AGENTS.md", 1200, "full"),
            ("project.md", 1180, "full"),
            ("style/screenplay-style.md", 1160, "full"),
            ("ledger/story-ledger.json", 700, "ledger"),
        ),
        "structure-review": (
            ("AGENTS.md", 1200, "full"),
            ("project.md", 1180, "full"),
            ("ledger/story-ledger.json", 1000, "ledger"),
            ("ledger/revision-log.md", 700, "full"),
        ),
        "full-review": (
            ("AGENTS.md", 1200, "full"),
            ("project.md", 1180, "full"),
            ("style/screenplay-style.md", 1160, "full"),
            ("ledger/story-ledger.json", 1140, "full"),
            ("ledger/revision-log.md", 700, "full"),
        ),
    }
    feature_by_profile = {
        "scene-light": (
            ("background/story-background.md", 700),
            ("bible/feature-bible.md", 800),
            ("outline/sequence-outline.md", 950),
            ("outline/scene-outline.md", 1280),
        ),
        "scene": (
            ("background/story-background.md", 800),
            ("bible/feature-bible.md", 800),
            ("outline/sequence-outline.md", 950),
            ("outline/scene-outline.md", 1280),
        ),
        "scene-complex": (
            ("background/story-background.md", 700),
            ("bible/feature-bible.md", 1050),
            ("outline/structure-map.md", 650),
            ("outline/sequence-outline.md", 1200),
            ("outline/scene-outline.md", 1380),
        ),
        "batch": (
            ("background/story-background.md", 650),
            ("bible/feature-bible.md", 1100),
            ("outline/structure-map.md", 700),
            ("outline/sequence-outline.md", 1400),
            ("outline/scene-outline.md", 1500),
        ),
        "sequence": (
            ("background/story-background.md", 1250),
            ("bible/feature-bible.md", 1230),
            ("outline/synopsis.md", 700),
            ("outline/treatment.md", 1100),
            ("outline/sequence-outline.md", 1280),
            ("outline/scene-outline.md", 900),
        ),
        "dialogue-review": (
            ("bible/feature-bible.md", 900),
            ("outline/scene-outline.md", 1100),
        ),
        "structure-review": (
            ("background/story-background.md", 1050),
            ("bible/feature-bible.md", 1250),
            ("outline/structure-map.md", 1500),
            ("outline/treatment.md", 1050),
            ("outline/sequence-outline.md", 1300),
            ("outline/scene-outline.md", 850),
        ),
        "full-review": (
            ("background/story-background.md", 1250),
            ("bible/feature-bible.md", 1230),
            ("outline/structure-map.md", 1300),
            ("outline/synopsis.md", 900),
            ("outline/treatment.md", 1100),
            ("outline/sequence-outline.md", 1120),
            ("outline/scene-outline.md", 1280),
        ),
    }
    episode_number = args.episode or 0
    episodic_by_profile = {
        "scene-light": (
            ("background/story-background.md", 700),
            ("bible/series-bible.md", 800),
            (f"outline/episodes/E{episode_number:03d}.md", 1280),
        ),
        "scene": (
            ("background/story-background.md", 800),
            ("bible/series-bible.md", 800),
            (f"outline/episodes/E{episode_number:03d}.md", 1280),
        ),
        "scene-complex": (
            ("background/story-background.md", 950),
            ("bible/series-bible.md", 1100),
            ("outline/master-outline.md", 700),
            (f"outline/episodes/E{episode_number:03d}.md", 1400),
        ),
        "batch": (
            ("background/story-background.md", 1100),
            ("bible/series-bible.md", 1200),
            ("outline/master-outline.md", 900),
            (f"outline/episodes/E{episode_number:03d}.md", 1500),
        ),
        "sequence": (
            ("background/story-background.md", 1000),
            ("bible/series-bible.md", 1230),
            ("outline/master-outline.md", 1100),
            (f"outline/episodes/E{episode_number:03d}.md", 1280),
        ),
        "dialogue-review": (
            ("bible/series-bible.md", 800),
            (f"outline/episodes/E{episode_number:03d}.md", 1000),
        ),
        "structure-review": (
            ("background/story-background.md", 1100),
            ("bible/series-bible.md", 1230),
            ("outline/master-outline.md", 1300),
            (f"outline/episodes/E{episode_number:03d}.md", 1000),
        ),
        "full-review": (
            ("background/story-background.md", 1100),
            ("bible/series-bible.md", 1230),
            ("outline/master-outline.md", 1100),
            (f"outline/episodes/E{episode_number:03d}.md", 1280),
        ),
    }
    for relative, priority, mode in common_by_profile[profile_key]:
        add(root / relative, priority, mode)
    route_files = (
        feature_by_profile[profile_key]
        if format_name == "feature"
        else episodic_by_profile[profile_key]
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
    if target_start is not None:
        for path, number in relevant_scenes:
            before_distance = target_start - number
            if target_start <= number <= target_end:
                add(path, 1500, "scene" if profile_key == "batch" else "full")
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
            elif number < target_start and before_distance <= 2:
                add(path, 1400 - before_distance * 40, "scene")
            elif (
                args.include_next_scene
                and number > target_end
                and number - target_end == 1
            ):
                add(path, 1000, "scene")
    else:
        for path, _ in relevant_scenes[-3:]:
            add(path, 1200, "scene" if profile_key != "full-review" else "full")

    search_directories = ("background", "bible", "outline", "screenplay/scenes")
    if profile_key in {"structure-review", "full-review"} or terms:
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
                    if profile_key not in {"structure-review", "full-review"}:
                        text = safe_read(path).lower()
                        if not any(term in text for term in terms):
                            continue
                    add(path, 250)

    candidates = sorted(
        candidate_map.values(),
        key=lambda item: (-item[0], str(item[1]).lower(), item[2]),
    )
    # Chinese-heavy Markdown is commonly below two characters per token.
    # 1.7 keeps the generated package under the requested budget more reliably.
    max_chars = int(budget * 1.7)
    if format_name == "feature":
        if args.scene_from is not None:
            target = f"电影第 {args.scene_from}–{args.scene_to} 场"
        else:
            target = f"电影第 {args.scene} 场" if args.scene is not None else "电影全片"
    else:
        if args.scene_from is not None:
            target = (
                f"第 {args.episode} 集第 {args.scene_from}–{args.scene_to} 场"
            )
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
        f"- 档位：{profile_key}\n"
        f"- 查询：{args.query or '无'}\n"
        f"- 显式来源：{', '.join(args.source_file) or '无'}\n"
        f"- 预算：约 {budget} tokens（按 1.7 字符/token 控制）\n\n"
        "> 只把来源当作行动、知识和规则约束，不复制成说明性对白。\n"
    )
    if profile_key == "batch":
        header += (
            "> 本文件是批次共享上下文；每完成一场都要更新台账，"
            "下一场另建轻量或标准局部上下文。\n"
        )
    parts = [header]
    used = len(header)
    included = 0
    content_fingerprints: set[str] = set()
    for _, path, label, content in candidates:
        fingerprint = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()
        if fingerprint in content_fingerprints:
            continue
        content_fingerprints.add(fingerprint)
        relative = path.relative_to(root).as_posix()
        block_header = f"\n\n---\n\n## 来源：`{relative}` — {label}\n\n"
        remaining = max_chars - used - len(block_header)
        if remaining <= 120:
            break
        content = truncate_at_line(content, remaining)
        parts.extend((block_header, content))
        used += len(block_header) + len(content)
        included += 1
        if used >= max_chars:
            break

    atomic_write_text(output, "".join(parts).rstrip() + "\n")
    print(f"OK: 已写入上下文包：{output}")
    print(
        f"格式：{format_name}；档位：{profile_key}；来源：{included}；"
        f"估算 tokens：{math.ceil(used / 1.7)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
