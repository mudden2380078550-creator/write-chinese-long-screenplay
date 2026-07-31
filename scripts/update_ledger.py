from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from screenplay_io import (
    LEDGER_ARRAY_KEYS,
    atomic_write_json,
    project_contract,
    project_format,
    require_inside,
)


SCENE_ID_RE = re.compile(r"^(?:E(?P<episode>\d{3})-)?S(?P<scene>\d{3})$")
ARRAY_KEYS = LEDGER_ARRAY_KEYS
INPUT_KEYS = {"scene_id", "summary", *ARRAY_KEYS}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="追加已确认场次的连续性状态")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def append_unique(target: list[Any], values: list[Any], scene_id: str) -> None:
    for value in values:
        if isinstance(value, dict):
            item = dict(value)
            item.setdefault("scene_id", scene_id)
        else:
            item = {"scene_id": scene_id, "value": value}
        if item not in target:
            target.append(item)


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("输入 JSON 顶层必须是对象")
        unknown = sorted(set(payload) - INPUT_KEYS)
        if unknown:
            raise ValueError(f"未知字段：{', '.join(unknown)}")
        scene_id = str(payload.get("scene_id", ""))
        match = SCENE_ID_RE.fullmatch(scene_id)
        if not match:
            raise ValueError("scene_id 必须形如 S001 或 E001-S001")

        root = args.project_root.resolve()
        _, contract_errors = project_contract(root)
        if contract_errors:
            raise ValueError("项目不是有效 v2：" + "；".join(contract_errors))
        format_name = project_format(root)
        if format_name == "feature" and match.group("episode") is not None:
            raise ValueError("电影项目的 scene_id 必须形如 S001")
        if format_name != "feature" and match.group("episode") is None:
            raise ValueError("剧集项目的 scene_id 必须形如 E001-S001")
        scene_path = root / "screenplay" / "scenes" / f"{scene_id}.md"
        require_inside(scene_path, root)
        if not scene_path.is_file():
            raise ValueError(f"找不到正典场次：{scene_path}")
        ledger_path = root / "ledger" / "story-ledger.json"
        require_inside(ledger_path, root)
        ledger = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
        if not isinstance(ledger, dict):
            raise ValueError("story-ledger.json 顶层必须是对象")
        if ledger.get("schema_version") != 2:
            raise ValueError("story-ledger.json schema_version 必须为 2")
        if ledger.get("format") != format_name:
            raise ValueError("story-ledger.json format 与项目不一致")

        for key in ("scene_summaries", *ARRAY_KEYS):
            ledger.setdefault(key, [])
            if not isinstance(ledger[key], list):
                raise ValueError(f"台账字段 {key} 必须是数组")

        if "summary" in payload:
            summary = str(payload["summary"]).strip()
            if not summary:
                raise ValueError("summary 不能为空")
            ledger["scene_summaries"] = [
                item
                for item in ledger["scene_summaries"]
                if not isinstance(item, dict) or item.get("scene_id") != scene_id
            ]
            ledger["scene_summaries"].append(
                {"scene_id": scene_id, "summary": summary}
            )

        for key in ARRAY_KEYS:
            values = payload.get(key, [])
            if not isinstance(values, list):
                raise ValueError(f"{key} 必须是 JSON 数组")
            append_unique(ledger[key], values, scene_id)

        ledger["updated"] = date.today().isoformat()
        if args.dry_run:
            print(json.dumps(ledger, ensure_ascii=False, indent=2))
        else:
            atomic_write_json(ledger_path, ledger)
            print(f"OK: 已更新台账：{ledger_path}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
