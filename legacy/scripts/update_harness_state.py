from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from harness_io import HARNESS_FILES, load_json
from screenplay_io import atomic_write_json, require_inside


INPUT_KEYS = {"updates"}
UPDATE_KEYS = {"file", "id", "mode", "item", "patch"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="根据已审定变更更新 harness 状态库")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} 必须是 JSON 对象")
    return value


def item_key(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("name") or "")


def merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def apply_update(document: dict[str, Any], update: dict[str, Any]) -> str:
    unknown = sorted(set(update) - UPDATE_KEYS)
    if unknown:
        raise ValueError(f"未知更新字段：{', '.join(unknown)}")
    target_id = str(update.get("id", "")).strip()
    if not target_id:
        raise ValueError("每条更新必须提供 id")
    mode = str(update.get("mode", "patch"))
    items = document.get("items", [])
    if not isinstance(items, list):
        raise ValueError("harness 文件的 items 必须是数组")
    seen = set()
    for item in items:
        validate_item(item)
        key = item_key(item)
        if key in seen:
            raise ValueError(f"重复条目 id：{key}")
        seen.add(key)
    index = next((i for i, item in enumerate(items) if isinstance(item, dict) and item_key(item) == target_id), None)

    if mode == "patch":
        patch = require_object(update.get("patch"), "patch")
        if index is None:
            raise ValueError(f"找不到要 patch 的条目：{target_id}")
        if "id" in patch and patch["id"] != items[index].get("id"):
            raise ValueError("patch 不允许修改 id")
        merged = merge_dict(items[index], patch)
        validate_item(merged)
        items[index] = merged
        return f"patched {target_id}"

    if mode == "upsert":
        item = dict(require_object(update.get("item"), "item"))
        item.setdefault("id", target_id)
        if item_key(item) != target_id:
            raise ValueError("item.id 必须与更新 id 一致")
        validate_item(merge_dict(items[index], item) if index is not None else item)
        document["items"] = items
        if index is None:
            items.append(item)
            return f"inserted {target_id}"
        items[index] = merge_dict(items[index], item)
        return f"updated {target_id}"

    raise ValueError("mode 只支持 patch 或 upsert")


def validate_item(item: Any) -> None:
    item = require_object(item, "items[]")
    if not isinstance(item.get("id"), str) or not item["id"].strip():
        raise ValueError("条目 id 必须是非空字符串")
    if "generation_policy" in item:
        policy = require_object(item["generation_policy"], "generation_policy")
        for key in ("allow_use", "allow_mention"):
            if key in policy and not isinstance(policy[key], bool):
                raise ValueError(f"{key} 必须是布尔值")
    if "aliases" in item and (not isinstance(item["aliases"], list) or any(not isinstance(v, str) for v in item["aliases"])):
        raise ValueError("aliases 必须是字符串数组")


def main() -> int:
    args = parse_args()
    try:
        root = args.project_root.resolve()
        input_path = args.input.resolve()
        if not input_path.is_file():
            raise ValueError(f"输入 JSON 不存在：{input_path}")
        payload = require_object(load_json(input_path), "输入 JSON")
        unknown = sorted(set(payload) - INPUT_KEYS)
        if unknown:
            raise ValueError(f"未知字段：{', '.join(unknown)}")
        updates = payload.get("updates")
        if not isinstance(updates, list) or not updates:
            raise ValueError("updates 必须是非空数组")

        changed: dict[Path, dict[str, Any]] = {}
        messages = []
        for raw in updates:
            update = require_object(raw, "updates[]")
            filename = str(update.get("file", "")).strip()
            if filename not in HARNESS_FILES:
                raise ValueError(f"不允许更新的 harness 文件：{filename}")
            path = root / "harness" / filename
            require_inside(path, root)
            document = changed.get(path)
            if document is None:
                document = require_object(load_json(path), filename) if path.is_file() else {"schema_version": 1, "items": []}
            message = apply_update(document, update)
            document["updated"] = date.today().isoformat()
            changed[path] = document
            messages.append(f"{filename}: {message}")

        if args.dry_run:
            for path, document in changed.items():
                print(f"--- {path.relative_to(root).as_posix()} ---")
                print(json.dumps(document, ensure_ascii=False, indent=2))
        else:
            for path, document in changed.items():
                atomic_write_json(path, document)
            for message in messages:
                print(f"OK: {message}")
        return 0
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
