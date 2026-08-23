from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED_FILES = (
    "AGENTS.md",
    "project.md",
    "background/story-background.md",
    "bible/series-bible.md",
    "bible/characters/_template.md",
    "plot/master-plot.md",
    "outlines/master-outline.md",
    "chapters/_template.md",
    "ledger/author-decisions.md",
    "ledger/story-ledger.json",
    "style/novel-style.md",
)
CANON_DIRS = ("background", "bible", "plot", "outlines", "chapters", "style")
FORBIDDEN_OPTION_PATTERNS = (
    r"方案\s*[A-CＡ-Ｃ]",
    r"可以是.{0,20}也可以是",
    r"待作者拍板",
    r"\bPENDING\b",
    r"\bEXPLORE\b",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验中文长篇小说项目")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def issue(items: list[dict[str, str]], path: Path, code: str, message: str) -> None:
    items.append({"file": str(path), "code": code, "message": message})


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    values: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def validate(root: Path, strict: bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file():
            issue(errors, path, "required-file", f"缺少小说项目文件：{relative}")

    project_path = root / "project.md"
    if project_path.is_file():
        metadata = frontmatter(read(project_path))
        if metadata.get("mode") != "novel":
            issue(errors, project_path, "mode", "project.md 的 mode 必须为 novel")
        if metadata.get("format") != "novel":
            issue(errors, project_path, "format", "project.md 的 format 必须为 novel")
        if metadata.get("schema_version") != "2":
            issue(errors, project_path, "schema", "小说项目 schema_version 必须为 2")

    decisions = root / "ledger" / "author-decisions.md"
    if decisions.is_file():
        text = read(decisions)
        if "## D-" not in text:
            issue(warnings, decisions, "no-decisions", "尚未登记作者决策；可接受于 seed 阶段")
        for block in re.split(r"(?=^## D-)", text, flags=re.MULTILINE):
            if not block.strip().startswith("## D-"):
                continue
            status = re.search(r"^状态：(.+)$", block, flags=re.MULTILINE)
            choice = re.search(r"^作者选择：(.+)$", block, flags=re.MULTILINE)
            if status and status.group(1).strip() == "CANON":
                if not choice or not choice.group(1).strip() or "{{" in choice.group(1):
                    issue(errors, decisions, "canon-choice", "CANON 决策缺少唯一作者选择")
    else:
        issue(errors, decisions, "decision-register", "缺少作者决策登记表")

    ledger_path = root / "ledger" / "story-ledger.json"
    if ledger_path.is_file():
        try:
            ledger = json.loads(read(ledger_path))
            if ledger.get("schema_version") != 2:
                issue(errors, ledger_path, "ledger-schema", "story-ledger.json schema_version 必须为 2")
            for key in ("decision_changes", "open_questions", "uncertainties"):
                if not isinstance(ledger.get(key), list):
                    issue(errors, ledger_path, "ledger-field", f"台账字段 {key} 必须为数组")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issue(errors, ledger_path, "ledger-parse", str(exc))

    for directory in CANON_DIRS:
        base = root / directory
        if not base.is_dir():
            issue(errors, base, "canon-directory", f"缺少正史目录：{directory}")
            continue
        for path in base.rglob("*.md"):
            if path.name.startswith("_"):
                continue
            text = read(path)
            for pattern in FORBIDDEN_OPTION_PATTERNS:
                if re.search(pattern, text):
                    target = errors if strict else warnings
                    issue(target, path, "unresolved-option", f"正史文件残留未决方案表达：{pattern}")
    return errors, warnings


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    errors, warnings = validate(root, args.strict)
    result = {"project_root": str(root), "mode": "novel", "errors": errors, "warnings": warnings}
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in errors:
            print(f"ERROR [{item['code']}] {item['file']}: {item['message']}")
        for item in warnings:
            print(f"WARN  [{item['code']}] {item['file']}: {item['message']}")
        print(f"SUMMARY: mode=novel errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

