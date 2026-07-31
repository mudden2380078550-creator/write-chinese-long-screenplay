from __future__ import annotations

import argparse
import sys
from pathlib import Path

from screenplay_io import (
    atomic_write_text,
    extract_h2_sections,
    list_scene_files,
    parse_frontmatter,
    project_contract,
    project_format,
    project_metadata,
    read_text,
    require_inside,
    scene_identity,
)
from validate_project import validate_project


EXPECTED_H2 = ["场次卡", "正文", "连续性", "改稿备注"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="编译中文电影或剧集 Markdown")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--episode", type=int)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    output = (
        args.output.resolve()
        if args.output
        else (root / "exports" / "screenplay.md").resolve()
    )
    try:
        _, contract_errors = project_contract(root)
        if contract_errors:
            raise ValueError("项目不是有效 v2：" + "；".join(contract_errors))
        format_name = project_format(root)
        _, _, validation_errors, _ = validate_project(root, True)
        if validation_errors:
            codes = ", ".join(
                dict.fromkeys(str(item["code"]) for item in validation_errors)
            )
            raise ValueError(
                f"严格校验未通过（{len(validation_errors)} 项：{codes}）；拒绝编译"
            )
        if format_name == "feature" and args.episode is not None:
            raise ValueError("电影项目不使用 --episode")
        if args.episode is not None and not 1 <= args.episode <= 999:
            raise ValueError("episode 必须在 1..999")
        require_inside(output, root / "exports")
        scenes = list_scene_files(root, format_name)
        if args.episode is not None:
            scenes = [
                path
                for path in scenes
                if scene_identity(path)[1] == args.episode
            ]
        if not scenes:
            raise ValueError("没有可编译的正式场次")

        metadata = project_metadata(root)
        title = str(metadata.get("title") or root.name)
        parts = [f"# {title}\n"]
        current_episode: int | None = None
        compiled = 0
        for path in scenes:
            _, episode, scene = scene_identity(path)
            scene_metadata, body = parse_frontmatter(read_text(path))
            names, sections = extract_h2_sections(body)
            if names != EXPECTED_H2:
                raise ValueError(f"{path.name} 的 H2 结构不合法，先运行校验")
            draft = sections["正文"].strip()
            if not draft:
                raise ValueError(f"{path.name} 的正文为空")
            title_text = str(scene_metadata.get("title", "")).strip()
            header_line = next(
                (
                    line.strip().removeprefix("场景标头：")
                    for line in sections["场次卡"].splitlines()
                    if line.strip().startswith("场景标头：")
                ),
                str(scene),
            )
            if format_name == "feature":
                parts.append(
                    f"\n\n## {header_line}"
                    + (f"｜{title_text}" if title_text else "")
                    + f"\n\n{draft}"
                )
            else:
                if current_episode != episode:
                    parts.append(f"\n\n## 第 {episode} 集\n")
                    current_episode = episode
                parts.append(
                    f"\n\n### {header_line}"
                    + (f"｜{title_text}" if title_text else "")
                    + f"\n\n{draft}"
                )
            compiled += 1

        atomic_write_text(output, "".join(parts).rstrip() + "\n")
        print(f"OK: 已编译 {format_name} 项目 {compiled} 场：{output}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
