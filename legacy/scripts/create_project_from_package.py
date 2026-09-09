from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from harness_io import HARNESS_FILES, load_json
from screenplay_io import atomic_write_json, atomic_write_text, read_text


SECTION_ALIASES = {
    "背景设定": "background",
    "背景": "background",
    "世界背景": "background",
    "人物设定": "characters",
    "人物": "characters",
    "角色": "characters",
    "技能": "abilities.json",
    "能力": "abilities.json",
    "道具": "inventory.json",
    "装备": "inventory.json",
    "物品": "inventory.json",
    "任务": "quests.json",
    "世界规则": "world-rules.json",
    "规则": "world-rules.json",
    "阵营": "factions.json",
    "组织": "factions.json",
    "时间线": "timeline.json",
    "连续性": "continuity-ledger.json",
    "作者指令": "author-directives.json",
    "作者禁令": "author-directives.json",
    "主角": "protagonist.json",
    "主角状态": "protagonist.json",
    "成长": "progression.json",
    "等级": "progression.json",
    "成长体系": "progression.json",
    "大纲": "outline",
    "故事大纲": "outline",
}
PINYIN_HINTS = {
    "林": "lin",
    "澈": "che",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从明确标题的 Markdown 资料包初始化长篇创作项目")
    parser.add_argument("--package", required=True, type=Path, help="Markdown 资料包")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--format", choices=("feature", "series", "short-drama", "animation"), default="series")
    return parser.parse_args()


def split_h1_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^#\s+(.+?)\s*$", text, re.MULTILINE))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        sections[title] = (sections[title] + "\n\n" + content) if title in sections else content
    return sections


def split_h2_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
    if not matches and text.strip():
        return [("未命名人物", text.strip())]
    result: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            result.append((title, body))
    return result


def slugify(value: str) -> str:
    ascii_value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    if ascii_value:
        return ascii_value
    converted = [PINYIN_HINTS.get(char, f"u{ord(char):x}") for char in value if not char.isspace()]
    return "-".join(converted) or "item"


def parse_scalar(value: str) -> Any:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return value.strip()


def parse_bullet(line: str, filename: str) -> dict[str, Any] | None:
    match = re.match(r"^\s*[-*]\s+(.+?)(?:[:：](.*))?$", line)
    if not match:
        return None
    name = match.group(1).strip()
    rest = (match.group(2) or "").strip()
    item: dict[str, Any] = {
        "id": f"{Path(filename).stem}-{slugify(name)}",
        "name": name,
        "status": "active",
        "author_note": "",
        "generation_policy": {"allow_use": True},
    }
    prose = []
    for field in re.split(r"[；;]", rest):
        if not field.strip() or "=" not in field:
            if field.strip():
                prose.append(field.strip())
            continue
        key, raw_value = field.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if key == "allow_use":
            item["generation_policy"]["allow_use"] = parse_scalar(value)
        elif key == "allow_mention":
            item["generation_policy"]["allow_mention"] = parse_scalar(value)
        elif key == "aliases":
            item["aliases"] = [part.strip() for part in re.split(r"[,，、]", value) if part.strip()]
        elif key == "forbidden_usage_patterns":
            item["generation_policy"]["forbidden_usage_patterns"] = [
                part.strip() for part in re.split(r"[,，]", value) if part.strip()
            ]
        elif key in {"status", "author_note", "introduced_in"}:
            item[key] = parse_scalar(value)
        else:
            item[key] = parse_scalar(value)
    if prose:
        item["description"] = "；".join(prose)
    item["source_text"] = line
    return item


def append_harness_items(root: Path, filename: str, body: str) -> None:
    if filename not in HARNESS_FILES:
        return
    path = root / "harness" / filename
    data = load_json(path) if path.is_file() else {"schema_version": 1, "items": []}
    if not isinstance(data, dict):
        data = {"schema_version": 1, "items": []}
    items = data.setdefault("items", [])
    if not isinstance(items, list):
        raise ValueError(f"{filename} 的 items 必须是数组")
    for line in body.splitlines():
        item = parse_bullet(line, filename)
        if item:
            items.append(item)
    data["updated"] = date.today().isoformat()
    atomic_write_json(path, data)


def write_background(root: Path, body: str) -> None:
    if body.strip():
        atomic_write_text(root / "background" / "story-background.md", "# 背景设定\n\n" + body.strip() + "\n")


def write_characters(root: Path, body: str) -> None:
    for name, content in split_h2_sections(body):
        path = root / "bible" / "characters" / f"{slugify(name)}.md"
        suffix = 2
        while path.exists():
            path = root / "bible" / "characters" / f"{slugify(name)}-{suffix}.md"
            suffix += 1
        atomic_write_text(path, f"# {name}\n\n{content.strip()}\n")


def run_init_project(project_root: Path, title: str, format_name: str) -> None:
    script = Path(__file__).resolve().parent / "init_project.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--title",
            title,
            "--format",
            format_name,
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or result.stdout.strip())


def main() -> int:
    args = parse_args()
    try:
        package = args.package.resolve()
        project_root = args.project_root.resolve()
        if not package.is_file():
            raise ValueError(f"资料包不存在：{package}")
        source = read_text(package)
        run_init_project(project_root, args.title, args.format)
        atomic_write_text(project_root / "imports" / "source-package.md", source)
        sections = split_h1_sections(source)
        imported = []
        unknown = []
        unparsed = []
        for heading, body in sections.items():
            route = SECTION_ALIASES.get(heading.strip())
            if route == "background":
                write_background(project_root, body)
                imported.append("background/story-background.md")
            elif route == "characters":
                write_characters(project_root, body)
                imported.append("bible/characters/*.md")
            elif isinstance(route, str) and route.endswith(".json"):
                append_harness_items(project_root, route, body)
                imported.append(f"harness/{route}")
                if any(line.strip() and parse_bullet(line, route) is None for line in body.splitlines()):
                    unparsed.append(heading)
            elif route == "outline":
                target = "sequence-outline.md" if args.format == "feature" else "master-outline.md"
                atomic_write_text(project_root / "outline" / target, "# 大纲\n\n" + body + "\n")
                imported.append(f"outline/{target}")
            else:
                unknown.append(heading)
        report = {"source_archive": "imports/source-package.md", "imported": imported, "unknown_sections": unknown, "unparsed_sections": unparsed, "note": "原始资料完整存档；未结构化内容须人工审定。"}
        atomic_write_json(project_root / "imports" / "import-report.json", report)
        print(f"OK: 已从资料包创建项目：{project_root}")
        print("导入：" + ("，".join(dict.fromkeys(imported)) if imported else "无可识别板块"))
        print("未识别板块：" + ("，".join(unknown) or "无") + "；未结构化内容：" + ("，".join(unparsed) or "无") + "；完整原文：imports/source-package.md")
        return 0
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
