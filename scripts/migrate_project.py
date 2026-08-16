from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from screenplay_io import (
    LEDGER_LIST_KEYS,
    V2_REQUIRED_CARD_FIELDS,
    atomic_write_json,
    atomic_write_text,
    extract_h2_sections,
    join_table_row,
    labeled_value,
    list_scene_files,
    parse_frontmatter,
    project_format,
    read_text,
    require_inside,
    split_table_row,
    unresolved,
)
from validate_project import (
    FEATURE_SOURCE_MARKERS,
    STRUCTURE_LABELS,
    validate_project,
)


PENDING = "【待补】"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="显式迁移中文长剧本项目到 v2")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="应用可确定的迁移，并在项目 backups/ 中建立备份",
    )
    return parser.parse_args()


def insert_contract(text: str) -> tuple[str, list[str]]:
    metadata, _ = parse_frontmatter(text)
    changes: list[str] = []
    updated = text

    def set_scalar(key: str, value: str, message: str) -> None:
        nonlocal updated
        pattern = rf"^{re.escape(key)}:.*$"
        if re.search(pattern, updated, re.MULTILINE):
            updated = re.sub(pattern, f"{key}: {value}", updated, count=1, flags=re.MULTILINE)
        else:
            match = re.search(r"^format:.*$", updated, re.MULTILINE)
            if not match:
                raise ValueError("project.md 缺少 format，无法安全插入 v2 契约")
            updated = (
                updated[: match.end()]
                + f"\n{key}: {value}"
                + updated[match.end() :]
            )
        changes.append(message)

    if metadata.get("schema_version") != 2:
        set_scalar("schema_version", "2", "设置 schema_version: 2")
    if metadata.get("story_engine") != "causal-value":
        set_scalar(
            "story_engine",
            "causal-value",
            "设置 story_engine: causal-value",
        )
    if not isinstance(metadata.get("structure_adapters"), list):
        pattern = r"^structure_adapters:.*$(?:\n  - .*$)*"
        if re.search(pattern, updated, re.MULTILINE):
            updated = re.sub(
                pattern,
                "structure_adapters: []",
                updated,
                count=1,
                flags=re.MULTILINE,
            )
            changes.append("设置 structure_adapters: []")
        else:
            set_scalar(
                "structure_adapters",
                "[]",
                "设置 structure_adapters: []",
            )
    if not isinstance(metadata.get("status"), str) or not metadata.get("status"):
        set_scalar("status", "planning", "设置 status: planning")
    today = date.today().isoformat()
    if not isinstance(metadata.get("created"), str) or not metadata.get("created"):
        set_scalar("created", today, f"设置 created: {today}")
    if not isinstance(metadata.get("updated"), str) or not metadata.get("updated"):
        set_scalar("updated", today, f"设置 updated: {today}")
    return updated, changes


def old_or_new(card: str, new_label: str, old_label: str | None = None) -> str:
    value = labeled_value(card, new_label)
    if value:
        return value
    if old_label:
        value = labeled_value(card, old_label)
        if value:
            return value
    return ""


def pending_with_hint(value: str, hint_name: str) -> str:
    if value and value != "-":
        return f"{PENDING}（旧{hint_name}：{value}）"
    return PENDING


def migrate_scene(text: str) -> tuple[str, list[str], list[str]]:
    metadata, body = parse_frontmatter(text)
    names, sections = extract_h2_sections(body)
    if names != ["场次卡", "正文", "连续性", "改稿备注"]:
        return text, [], ["H2 结构不合法，未自动修改"]
    card = sections["场次卡"]
    characters = metadata.get("characters", [])
    if not isinstance(characters, list):
        characters = []

    viewpoint = old_or_new(card, "视点人物")
    if not viewpoint and len(characters) == 1:
        viewpoint = str(characters[0])
    viewpoint = viewpoint or PENDING
    entry = old_or_new(card, "入场价值")
    if not entry:
        entry = pending_with_hint(labeled_value(card, "入场状态"), "入场状态")
    exit_value = old_or_new(card, "出场价值")
    if not exit_value:
        exit_value = pending_with_hint(labeled_value(card, "出场状态"), "出场状态")

    values = {
        "场景标头": labeled_value(card, "场景标头") or PENDING,
        "结构位置": labeled_value(card, "结构位置") or "-",
        "来源依据": labeled_value(card, "来源依据") or PENDING,
        "人物依据": labeled_value(card, "人物依据") or PENDING,
        "背景依据": labeled_value(card, "背景依据") or "-",
        "世界规则": labeled_value(card, "世界规则") or "-",
        "视点人物": viewpoint,
        "场景目标": old_or_new(card, "场景目标", "场次任务") or PENDING,
        "故事价值": old_or_new(card, "故事价值") or PENDING,
        "入场价值": entry,
        "主冲突": old_or_new(card, "主冲突") or PENDING,
        "策略": old_or_new(card, "策略") or PENDING,
        "预期结果": old_or_new(card, "预期结果") or PENDING,
        "实际结果": old_or_new(card, "实际结果") or PENDING,
        "结果落差": old_or_new(card, "结果落差") or PENDING,
        "场面转折": labeled_value(card, "场面转折") or PENDING,
        "观众入口": labeled_value(card, "观众入口") or "-",
        "观众更新": labeled_value(card, "观众更新") or PENDING,
        "出场价值": exit_value,
        "下场压力": old_or_new(card, "下场压力") or PENDING,
        "对白潜台词": old_or_new(card, "对白潜台词") or "-",
        "人物语言": old_or_new(card, "人物语言") or "-",
        "禁止矛盾": labeled_value(card, "禁止矛盾") or "-",
        "故事时间": labeled_value(card, "故事时间")
        or str(metadata.get("story_time", ""))
        or "-",
        "出场人物": labeled_value(card, "出场人物")
        or "、".join(str(item) for item in characters)
        or "-",
        "两难选项": labeled_value(card, "两难选项") or "-",
    }
    ordered = (
        "场景标头",
        "结构位置",
        "来源依据",
        "人物依据",
        "背景依据",
        "世界规则",
        "视点人物",
        "场景目标",
        "故事价值",
        "入场价值",
        "主冲突",
        "策略",
        "预期结果",
        "实际结果",
        "结果落差",
        "场面转折",
        "观众入口",
        "观众更新",
        "出场价值",
        "下场压力",
        "对白潜台词",
        "人物语言",
        "禁止矛盾",
        "故事时间",
        "出场人物",
        "两难选项",
    )
    new_card = "\n".join(f"{label}：{values[label]}" for label in ordered)
    migrated_body = body.replace(
        f"## 场次卡\n\n{card}", f"## 场次卡\n\n{new_card}", 1
    )
    frontmatter_end = text.replace("\r\n", "\n").find("\n---\n", 4)
    if frontmatter_end < 0:
        raise ValueError("场次缺少结束 frontmatter")
    prefix = text.replace("\r\n", "\n")[: frontmatter_end + 5]
    migrated = prefix + migrated_body
    unresolved_fields = [
        field
        for field in V2_REQUIRED_CARD_FIELDS
        if field != "禁止矛盾"
        and (unresolved(values.get(field, "")) or values.get(field) == "-")
    ]
    changes = ["重建 v2 场次卡"] if migrated != text.replace("\r\n", "\n") else []
    return migrated, changes, unresolved_fields


def copy_backup(root: Path, backup_root: Path, path: Path) -> None:
    relative = path.resolve().relative_to(root.resolve())
    destination = backup_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def structure_template(skill_root: Path) -> str:
    path = (
        skill_root
        / "assets"
        / "feature-project-template"
        / "outline"
        / "structure-map.md"
    )
    return read_text(path).replace("{{DATE}}", date.today().isoformat())


def render_asset_template(
    skill_root: Path,
    format_name: str,
    relative: str,
    title: str,
) -> str:
    template_name = (
        "feature-project-template" if format_name == "feature" else "project-template"
    )
    path = skill_root / "assets" / template_name / relative
    if not path.is_file():
        raise ValueError(f"找不到 v2 模板：{path}")
    return (
        read_text(path)
        .replace("{{DATE}}", date.today().isoformat())
        .replace("{{TITLE}}", title)
        .replace(
            "{{TITLE_YAML}}",
            title.replace("\\", "\\\\").replace('"', '\\"'),
        )
        .replace("{{TITLE_JSON}}", json.dumps(title, ensure_ascii=False)[1:-1])
        .replace("{{FORMAT}}", format_name)
    )


def migrate_ledger(
    path: Path,
    format_name: str,
    skill_root: Path,
    title: str,
) -> tuple[dict[str, Any], list[str], bool]:
    if not path.is_file():
        data = json.loads(
            render_asset_template(
                skill_root,
                format_name,
                "ledger/story-ledger.json",
                title,
            )
        )
        return data, ["新建 v2 ledger/story-ledger.json"], True
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("story-ledger.json 顶层必须是对象")
    changes: list[str] = []
    if data.get("schema_version") != 2:
        data["schema_version"] = 2
        changes.append("设置台账 schema_version: 2")
    if data.get("format") != format_name:
        data["format"] = format_name
        changes.append(f"设置台账 format: {format_name}")
    for key in LEDGER_LIST_KEYS:
        if key not in data:
            data[key] = []
            changes.append(f"新增台账字段 {key}")
        elif not isinstance(data[key], list):
            raise ValueError(f"台账字段 {key} 必须是数组，拒绝自动覆盖")
    return data, changes, False


def upgrade_feature_bible(text: str) -> str:
    updated = text.replace("## 主题与承诺", "## 主题命题", 1)
    updated = updated.replace("- 外部目标：", "- 外在欲望：", 1)
    updated = updated.replace("- 内部需要：", "- 内在需要：", 1)
    updated = updated.replace("- 高潮中的答案：", "- 高潮最终证据：", 1)
    if "主题命题（价值结果，因为人物如何行动）" not in updated:
        updated = updated.replace(
            "- 贯穿问题：",
            "- 贯穿问题：\n"
            "- 主题命题（价值结果，因为人物如何行动）：\n"
            "- 反命题（相反价值结果，因为人物如何行动）：",
            1,
        )
    if "- 核心行动线：" not in updated:
        updated = updated.replace(
            "- 保护策略：",
            "- 保护策略：\n- 核心行动线：",
            1,
        )
    if "- 余波必须展示的价值状态：" not in updated:
        marker = "## 结局约束"
        if marker in updated:
            updated = updated.replace(
                "- 不允许使用的解决方式：",
                "- 不允许使用的解决方式：\n- 余波必须展示的价值状态：",
                1,
            )
    return updated


def upgrade_table(
    text: str,
    old_header: str,
    new_header: str,
    mapper: Any,
) -> str:
    lines = text.splitlines()
    try:
        index = lines.index(old_header)
    except ValueError:
        return text
    lines[index] = new_header
    new_columns = len(split_table_row(new_header))
    if index + 1 < len(lines):
        lines[index + 1] = join_table_row(["---"] * new_columns)
    row_index = index + 2
    while row_index < len(lines) and lines[row_index].lstrip().startswith("|"):
        cells = split_table_row(lines[row_index])
        lines[row_index] = join_table_row(mapper(cells))
        row_index += 1
    return "\n".join(lines).rstrip() + "\n"


def upgrade_sequence_outline(text: str) -> str:
    old_header = (
        "| 序列 | 幕 | 进入状态 | 序列任务 | 压力 | 关键选择 | 转折 | 退出状态 |"
    )
    new_header = (
        "| 序列 | 幕 | 故事价值 | 进入价值 | 序列任务 | 递进压力 | "
        "关键选择 | 序列转折 | 退出价值 | 下序列压力 |"
    )

    def mapper(cells: list[str]) -> list[str]:
        if len(cells) != 8:
            return (cells + [""] * 10)[:10]
        return [
            cells[0],
            cells[1],
            "",
            cells[2],
            cells[3],
            cells[4],
            cells[5],
            cells[6],
            cells[7],
            "",
        ]

    return upgrade_table(text, old_header, new_header, mapper)


def upgrade_scene_outline(text: str) -> str:
    old_header = (
        "| 场 | 幕/序列 | 地点/日夜/内外 | 来源 | 人物目标 | 背景/规则压力 | "
        "策略与反制 | 转折 | 观众更新 | 出场状态 |"
    )
    new_header = (
        "| 场 | 幕/序列 | 地点/日夜/内外 | 来源 | 视点人物 | 场景目标 | "
        "故事价值 | 入场价值 | 主冲突/策略 | 预期→实际/落差 | 转折 | "
        "观众更新 | 出场价值 | 下场压力 |"
    )

    def mapper(cells: list[str]) -> list[str]:
        if len(cells) != 10:
            return (cells + [""] * 14)[:14]
        conflict = "；".join(value for value in (cells[5], cells[6]) if value)
        return [
            cells[0],
            cells[1],
            cells[2],
            cells[3],
            "",
            cells[4],
            "",
            "",
            conflict,
            "",
            cells[7],
            cells[8],
            cells[9],
            "",
        ]

    return upgrade_table(text, old_header, new_header, mapper)


def migrate_feature_sources(
    root: Path,
    skill_root: Path,
    title: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    upgraders = {
        "bible/feature-bible.md": upgrade_feature_bible,
        "outline/sequence-outline.md": upgrade_sequence_outline,
        "outline/scene-outline.md": upgrade_scene_outline,
    }
    for relative, markers in FEATURE_SOURCE_MARKERS.items():
        path = root / relative
        created = not path.is_file()
        original = (
            ""
            if created
            else read_text(path)
        )
        updated = (
            render_asset_template(skill_root, "feature", relative, title)
            if created
            else upgraders[relative](original)
        )
        missing = [marker for marker in markers if marker not in updated]
        changes: list[str] = []
        if created:
            changes.append(f"新建 {relative}")
        elif updated != original.replace("\r\n", "\n"):
            changes.append(f"升级 {relative} 到 v2 字段")
        results.append(
            {
                "path": path,
                "text": updated,
                "created": created,
                "changes": changes,
                "blockers": [f"{relative} 无法安全补齐：{marker}" for marker in missing],
            }
        )

    scene_template = root / "screenplay" / "scenes" / "_template.md"
    if not scene_template.is_file() or "结果落差：" not in read_text(scene_template):
        results.append(
            {
                "path": scene_template,
                "text": render_asset_template(
                    skill_root,
                    "feature",
                    "screenplay/scenes/_template.md",
                    title,
                ),
                "created": not scene_template.is_file(),
                "changes": ["刷新电影 v2 场次模板"],
                "blockers": [],
            }
        )
    return results


def migrate_episodic_templates(
    root: Path,
    skill_root: Path,
    format_name: str,
    title: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for relative, marker in (
        ("screenplay/scenes/_template.md", "结果落差："),
        ("outline/episodes/_template.md", "结果落差"),
    ):
        path = root / relative
        if path.is_file() and marker in read_text(path):
            continue
        results.append(
            {
                "path": path,
                "text": render_asset_template(skill_root, format_name, relative, title),
                "created": not path.is_file(),
                "changes": [f"刷新剧集 v2 模板：{relative}"],
                "blockers": [],
            }
        )
    return results


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    report = (
        args.report.resolve()
        if args.report
        else (root / "reviews" / "v2-migration.md").resolve()
    )
    try:
        if not root.is_dir():
            raise ValueError(f"项目目录不存在：{root}")
        require_inside(report, root / "reviews")
        project_path = root / "project.md"
        if not project_path.is_file():
            raise ValueError("缺少 project.md")
        format_name = project_format(root)
        skill_root = Path(__file__).resolve().parent.parent
        project_metadata, _ = parse_frontmatter(read_text(project_path))
        title = str(project_metadata.get("title") or root.name)
        project_text, project_changes = insert_contract(read_text(project_path))
        ledger_path = root / "ledger" / "story-ledger.json"
        ledger_data, ledger_changes, ledger_created = migrate_ledger(
            ledger_path,
            format_name,
            skill_root,
            title,
        )

        scene_results: list[dict[str, Any]] = []
        for path in list_scene_files(root):
            migrated, changes, unresolved_fields = migrate_scene(read_text(path))
            scene_results.append(
                {
                    "path": path,
                    "text": migrated,
                    "changes": changes,
                    "unresolved": unresolved_fields,
                }
            )

        structure_path = root / "outline" / "structure-map.md"
        add_structure = format_name == "feature" and not structure_path.is_file()
        source_results = (
            migrate_feature_sources(root, skill_root, title)
            if format_name == "feature"
            else migrate_episodic_templates(
                root,
                skill_root,
                format_name,
                title,
            )
        )
        source_blockers = [
            blocker
            for item in source_results
            for blocker in item["blockers"]
        ]
        backup_root: Path | None = None
        if args.apply:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup_candidate = root / "backups" / f"v1-to-v2-{stamp}"

            def write_migrated(path: Path, text: str, created: bool = False) -> None:
                nonlocal backup_root
                if path.is_file() and not created:
                    copy_backup(root, backup_candidate, path)
                    backup_root = backup_candidate
                atomic_write_text(path, text)

            if project_changes:
                write_migrated(project_path, project_text)
            if ledger_changes:
                if ledger_path.is_file() and not ledger_created:
                    copy_backup(root, backup_candidate, ledger_path)
                    backup_root = backup_candidate
                atomic_write_json(ledger_path, ledger_data)
            for item in scene_results:
                if item["changes"]:
                    write_migrated(item["path"], item["text"])
            for item in source_results:
                if item["changes"]:
                    write_migrated(item["path"], item["text"], item["created"])
            if add_structure:
                atomic_write_text(
                    structure_path,
                    structure_template(skill_root),
                )

        unresolved_total = sum(len(item["unresolved"]) for item in scene_results)
        strict_errors: list[dict[str, Any]] = []
        if args.apply:
            _, _, strict_errors, _ = validate_project(root, True)
        preview_blockers = (
            unresolved_total
            + len(source_blockers)
            + (len(STRUCTURE_LABELS) if add_structure else 0)
        )
        lines = [
            "# v1 → v2 迁移报告\n\n",
            f"- 模式：{'已应用' if args.apply else '仅预览'}\n",
            f"- 项目：`{root}`\n",
            f"- 项目契约变更：{len(project_changes)}\n",
            f"- 台账变更：{len(ledger_changes)}\n",
            f"- 场次：{len(scene_results)}\n",
            f"- 未解决创作字段：{unresolved_total}\n",
            f"- 严格校验阻断：{len(strict_errors) if args.apply else preview_blockers}\n",
            f"- 统一结构图：{'将新增' if add_structure and not args.apply else '已新增' if add_structure else '已存在或不适用'}\n",
        ]
        if backup_root:
            lines.append(f"- 备份：`{backup_root}`\n")
        lines.extend(["\n## 项目变更\n\n"])
        if project_changes:
            lines.extend(f"- {change}\n" for change in project_changes)
        else:
            lines.append("- 项目契约已是 v2。\n")
        lines.append("\n## 台账变更\n\n")
        if ledger_changes:
            lines.extend(f"- {change}\n" for change in ledger_changes)
        else:
            lines.append("- 台账已是 v2。\n")
        lines.append("\n## 模板与来源迁移\n\n")
        source_changes = [
            change for item in source_results for change in item["changes"]
        ]
        if source_changes:
            lines.extend(f"- {change}\n" for change in source_changes)
        else:
            lines.append("- 模板和电影来源结构已是 v2。\n")
        if source_blockers:
            lines.extend(f"- 阻断：{blocker}\n" for blocker in source_blockers)
        lines.append("\n## 场次\n\n")
        if not scene_results:
            lines.append("- 没有正式场次。\n")
        for item in scene_results:
            relative = item["path"].relative_to(root).as_posix()
            status = "；".join(item["changes"]) or "无需结构修改"
            pending = "、".join(item["unresolved"]) or "无"
            lines.append(f"- `{relative}`：{status}；待补：{pending}\n")
        if args.apply:
            lines.append("\n## 应用后严格校验\n\n")
            if strict_errors:
                for item in strict_errors:
                    relative = Path(item["file"])
                    try:
                        display = relative.relative_to(root).as_posix()
                    except ValueError:
                        display = str(relative)
                    lines.append(
                        f"- `[{item['code']}]` `{display}`：{item['message']}\n"
                    )
            else:
                lines.append("- 严格校验通过。\n")
        lines.extend(
            [
                "\n## 下一步\n\n",
                "1. 用人物小传、背景、世界规则和大纲补全所有 `【待补】`。\n",
                "2. 电影项目补全 `outline/structure-map.md`。\n",
                "3. 运行 `validate_project.py --strict`。\n",
                "4. 运行 `self_review.py --focus full --strict`。\n",
                "\n> 迁移不会自动猜测人物动机、故事价值、冲突、结果落差或下场压力。\n",
            ]
        )
        atomic_write_text(report, "".join(lines))
        print(f"OK: 已生成迁移报告：{report}")
        if args.apply:
            print(f"OK: 已应用可确定迁移；备份：{backup_root or '无（仅新增文件）'}")
        else:
            print("PREVIEW: 未修改 project.md、场次或结构图")
        blocking_total = len(strict_errors) if args.apply else preview_blockers
        print(
            f"SUMMARY: scenes={len(scene_results)} unresolved={unresolved_total} "
            f"blocking={blocking_total}"
        )
        return 1 if blocking_total else 0
    except (OSError, ValueError, json.JSONDecodeError, shutil.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
