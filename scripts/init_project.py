from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

from screenplay_io import atomic_write_text, read_text


FORMATS = ("feature", "series", "short-drama", "animation")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="初始化中文长剧本 Markdown 工程")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--format", choices=FORMATS, default="series")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.title.strip() or "\n" in args.title or "\r" in args.title:
        print("ERROR: 项目名不能为空或包含换行。", file=sys.stderr)
        return 2

    try:
        project_root = args.project_root.resolve()
        if project_root.exists():
            if not project_root.is_dir():
                raise ValueError(f"项目根路径不是目录：{project_root}")
            if any(project_root.iterdir()):
                raise ValueError(f"目标目录非空，拒绝覆盖：{project_root}")

        skill_dir = Path(__file__).resolve().parent.parent
        template_name = (
            "feature-project-template"
            if args.format == "feature"
            else "project-template"
        )
        template_root = skill_dir / "assets" / template_name
        if not template_root.is_dir():
            raise ValueError(f"找不到项目模板：{template_root}")

        project_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(template_root, project_root, dirs_exist_ok=True)

        today = date.today().isoformat()
        replacements = {
            "{{TITLE}}": args.title.strip(),
            "{{TITLE_YAML}}": args.title.strip()
            .replace("\\", "\\\\")
            .replace('"', '\\"'),
            "{{TITLE_JSON}}": json.dumps(args.title.strip(), ensure_ascii=False)[1:-1],
            "{{FORMAT}}": args.format,
            "{{DATE}}": today,
        }
        for path in project_root.rglob("*"):
            if not path.is_file():
                continue
            text = read_text(path)
            for token, value in replacements.items():
                text = text.replace(token, value)
            atomic_write_text(path, text)
    except (OSError, UnicodeError, ValueError, shutil.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"OK: 已初始化中文长剧本项目：{project_root}")
    print(f"格式：{args.format}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
