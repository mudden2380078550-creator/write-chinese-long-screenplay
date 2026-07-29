from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from screenplay_io import (
    atomic_write_text,
    project_format,
    require_inside,
    scene_id_for,
    strict_int,
    yaml_list,
    yaml_string,
)


COMMON_REQUIRED = ("scene", "title", "location", "time_of_day", "interior_exterior")
STATUSES = {"outline", "draft", "revision", "final", "locked"}
TIME_VALUES = {"日", "夜", "晨", "昏", "连续"}
SPACE_VALUES = {"内", "外", "内外"}
LIST_FIELDS = (
    "characters",
    "threads",
    "source_files",
    "source_character_facts",
    "source_background_facts",
    "source_world_rules",
    "forbidden_contradictions",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="安全创建中文电影或剧集场次")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="完成全部校验并把待写内容输出到标准输出，不创建文件",
    )
    return parser.parse_args()


def as_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{key} 必须是 JSON 数组")
    return [str(item).strip() for item in value if str(item).strip()]


def bullet_block(value: Any, empty: str = "-") -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value) if value else empty
    text = str(value or "").strip()
    return text or empty


def card_list(values: list[str]) -> str:
    return "；".join(values)


def validate_source_files(project_root: Path, source_files: list[str]) -> None:
    for relative in source_files:
        relative_path = Path(relative)
        if relative_path.is_absolute():
            raise ValueError(f"source_files 必须使用项目相对路径：{relative}")
        source = (project_root / relative_path).resolve()
        require_inside(source, project_root)
        if not source.is_file():
            raise ValueError(f"来源文件不存在：{relative}")


def main() -> int:
    args = parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("输入 JSON 顶层必须是对象")
        missing = [key for key in COMMON_REQUIRED if key not in data]
        if missing:
            raise ValueError(f"缺少字段：{', '.join(missing)}")

        root = args.project_root.resolve()
        format_name = project_format(root)
        is_feature = format_name == "feature"
        scene = strict_int(data["scene"], "scene", 1, 999)
        episode: int | None = None
        if not is_feature:
            if "episode" not in data:
                raise ValueError("剧集场次缺少 episode")
            episode = strict_int(data["episode"], "episode", 1, 999)

        title = str(data["title"]).strip()
        location = str(data["location"]).strip()
        if not title or not location:
            raise ValueError("title 与 location 不能为空")
        time_of_day = str(data["time_of_day"]).strip()
        interior_exterior = str(data["interior_exterior"]).strip()
        if time_of_day not in TIME_VALUES:
            raise ValueError(f"time_of_day 必须是：{', '.join(sorted(TIME_VALUES))}")
        if interior_exterior not in SPACE_VALUES:
            raise ValueError(
                f"interior_exterior 必须是：{', '.join(sorted(SPACE_VALUES))}"
            )
        status = str(data.get("status", "draft"))
        if status not in STATUSES:
            raise ValueError(f"status 必须是：{', '.join(sorted(STATUSES))}")

        lists = {key: as_list(data, key) for key in LIST_FIELDS}
        if is_feature and not lists["source_files"]:
            raise ValueError("电影场次必须提供至少一个 source_files 来源")
        validate_source_files(root, lists["source_files"])

        scene_id = scene_id_for(format_name, scene, episode)
        target = root / "screenplay" / "scenes" / f"{scene_id}.md"
        require_inside(target, root)
        if target.exists():
            raise FileExistsError(f"场次已存在，拒绝覆盖：{target}")

        today = date.today().isoformat()
        story_time = str(data.get("story_time", "")).strip()
        display_characters = str(
            data.get("display_characters") or "、".join(lists["characters"])
        ).strip()
        draft = str(data.get("draft", "")).strip()
        if not draft:
            draft = "△ 待写：用可见、可听、可表演的动作进入场面。"

        if is_feature:
            act = strict_int(data.get("act", 0), "act", 0, 99)
            sequence = strict_int(data.get("sequence", 0), "sequence", 0, 999)
            identity_frontmatter = (
                f"scene: {scene}\nact: {act}\nsequence: {sequence}\n"
            )
            structure_position = f"第 {act} 幕 / 序列 {sequence}"
            header_number = str(scene)
        else:
            identity_frontmatter = f"episode: {episode}\nscene: {scene}\n"
            structure_position = f"第 {episode} 集"
            header_number = f"{episode}-{scene}"

        text = f"""---
id: {scene_id}
type: scene
{identity_frontmatter}title: {yaml_string(title)}
status: {status}
location: {yaml_string(location)}
time_of_day: {yaml_string(time_of_day)}
interior_exterior: {yaml_string(interior_exterior)}
story_time: {yaml_string(story_time)}
characters:{yaml_list(lists["characters"])}
threads:{yaml_list(lists["threads"])}
source_files:{yaml_list(lists["source_files"])}
created: {today}
updated: {today}
---

# {scene_id} {title}

## 场次卡

场景标头：{header_number} {location} {time_of_day} {interior_exterior}
结构位置：{structure_position}
来源依据：{card_list(lists["source_files"])}
人物依据：{card_list(lists["source_character_facts"])}
背景依据：{card_list(lists["source_background_facts"])}
世界规则：{card_list(lists["source_world_rules"])}
场次任务：{str(data.get("scene_task", "")).strip()}
观众入口：{str(data.get("audience_entry", "")).strip()}
入场状态：{str(data.get("entry_state", "")).strip()}
场面转折：{str(data.get("turn", "")).strip()}
观众更新：{str(data.get("audience_update", "")).strip()}
出场状态：{str(data.get("exit_state", "")).strip()}
禁止矛盾：{card_list(lists["forbidden_contradictions"])}
故事时间：{story_time}
出场人物：{display_characters}

## 正文

{draft}

## 连续性

{bullet_block(data.get("continuity", []))}

## 改稿备注

{bullet_block(data.get("revision_notes", []))}
"""
        if args.dry_run:
            print(text, end="")
            print(f"\nDRY-RUN: 校验通过，未创建场次：{target}", file=sys.stderr)
            return 0
        atomic_write_text(target, text)
        print(f"OK: 已创建{('电影' if is_feature else '剧集')}场次：{target}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
