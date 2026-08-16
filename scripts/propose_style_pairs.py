from __future__ import annotations

import argparse
import sys
from pathlib import Path

from screenplay_io import (
    atomic_write_text,
    extract_h2_sections,
    list_scene_files,
    parse_frontmatter,
    project_format,
    read_text,
    require_inside,
)
from self_review import AI_STYLE_PATTERNS, EXPOSITION_TRIGGERS
from validate_project import DIALOGUE_RE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成对白风格校准候选对（待确认）")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--style-file", type=Path)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1:
        print("ERROR: --limit 必须 ≥ 1", file=sys.stderr)
        return 2
    root = args.project_root.resolve()
    style_file = (
        (root / "style" / "screenplay-style.md").resolve()
        if args.style_file is None
        else args.style_file.resolve()
    )
    try:
        require_inside(style_file, root)
        format_name = project_format(root)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    candidates: list[tuple[str, str, str]] = []
    for path in list_scene_files(root, format_name):
        try:
            _, body = parse_frontmatter(read_text(path))
            _, sections = extract_h2_sections(body)
        except (OSError, ValueError):
            continue
        draft = sections.get("正文", "")
        for raw_line in draft.splitlines():
            line = raw_line.strip()
            if not line or not DIALOGUE_RE.match(line):
                continue
            hits = [
                label for label, pattern in AI_STYLE_PATTERNS if pattern.search(line)
            ]
            if any(trigger in line for trigger in EXPOSITION_TRIGGERS):
                hits.append("对白解释（EXPOSITION）")
            for label in hits:
                if not any(candidate[0] == line for candidate in candidates):
                    candidates.append((line, label, str(path)))
                if len(candidates) >= args.limit:
                    break
            if len(candidates) >= args.limit:
                break
        if len(candidates) >= args.limit:
            break

    existing = read_text(style_file) if style_file.is_file() else ""
    unique = [
        (line, label, path)
        for line, label, path in candidates
        if f"原句：{line}" not in existing
    ][: args.limit]
    if not unique:
        print("OK: 没有新的候选对（全部已存在于风格表）")
        return 0

    blocks = ["\n## 候选改写对（待确认）\n"]
    for line, label, path in unique:
        blocks.append(
            f"\n- 原句：{line}\n"
            f"  命中的问题：{label}\n"
            f"  来源：{path}\n"
            "  不自然的原因：\n"
            "  改写：\n"
            "  希望保留的效果：\n"
        )
    content = "".join(blocks)
    if args.dry_run:
        print(content, end="")
        return 0
    if style_file.is_file():
        atomic_write_text(style_file, existing.rstrip() + "\n" + content)
    else:
        atomic_write_text(style_file, content)
    print(f"OK: 已追加 {len(unique)} 组候选对：{style_file}")
    print("提醒：改写由模型生成、你确认后回填，脚本只生成 原句/命中问题。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
