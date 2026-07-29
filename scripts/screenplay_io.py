from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


EPISODIC_SCENE_FILE_RE = re.compile(
    r"^E(?P<episode>\d{3})-S(?P<scene>\d{3})\.md$"
)
FEATURE_SCENE_FILE_RE = re.compile(r"^S(?P<scene>\d{3})\.md$")
SCENE_ID_RE = re.compile(r"^(?:E\d{3}-)?S\d{3}$")
H2_RE = re.compile(r"^## ([^\r\n]+)\s*$", re.MULTILINE)
EPISODIC_FORMATS = {"series", "short-drama", "animation"}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value in {"[]", "{}"}:
        return [] if value == "[]" else {}
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() in {"null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise ValueError("文件缺少起始 YAML frontmatter")
    end = normalized.find("\n---\n", 4)
    if end < 0:
        raise ValueError("文件缺少结束 YAML frontmatter")
    raw = normalized[4:end]
    body = normalized[end + 5 :]
    data: dict[str, Any] = {}
    current_list: str | None = None
    for line_number, line in enumerate(raw.splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item_match = re.match(r"^\s+-\s+(.*)$", line)
        if item_match:
            if current_list is None:
                raise ValueError(f"frontmatter 第 {line_number} 行出现孤立列表项")
            data[current_list].append(_parse_scalar(item_match.group(1)))
            continue
        key_match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$", line)
        if not key_match:
            raise ValueError(f"无法解析 frontmatter 第 {line_number} 行：{line}")
        key, value = key_match.group(1), key_match.group(2) or ""
        if not value:
            data[key] = []
            current_list = key
        else:
            data[key] = _parse_scalar(value)
            current_list = None
    return data, body


def project_metadata(project_root: Path) -> dict[str, Any]:
    path = project_root / "project.md"
    metadata, _ = parse_frontmatter(read_text(path))
    return metadata


def project_format(project_root: Path) -> str:
    value = str(project_metadata(project_root).get("format", "series"))
    if value != "feature" and value not in EPISODIC_FORMATS:
        raise ValueError(f"不支持的项目 format：{value}")
    return value


def extract_h2_sections(body: str) -> tuple[list[str], dict[str, str]]:
    matches = list(H2_RE.finditer(body))
    names = [match.group(1).strip() for match in matches]
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[match.group(1).strip()] = body[start:end].strip()
    return names, sections


def scene_identity(path: Path) -> tuple[str, int | None, int]:
    episodic = EPISODIC_SCENE_FILE_RE.fullmatch(path.name)
    if episodic:
        return (
            "episodic",
            int(episodic.group("episode")),
            int(episodic.group("scene")),
        )
    feature = FEATURE_SCENE_FILE_RE.fullmatch(path.name)
    if feature:
        return "feature", None, int(feature.group("scene"))
    raise ValueError(f"非法场次文件名：{path.name}")


def scene_key(path: Path) -> tuple[int, int]:
    _, episode, scene = scene_identity(path)
    return episode or 0, scene


def scene_id_for(project_type: str, scene: int, episode: int | None = None) -> str:
    if project_type == "feature":
        return f"S{scene:03d}"
    if episode is None:
        raise ValueError("剧集场次缺少 episode")
    return f"E{episode:03d}-S{scene:03d}"


def list_scene_files(
    project_root: Path, expected_format: str | None = None
) -> list[Path]:
    scene_dir = project_root / "screenplay" / "scenes"
    if not scene_dir.exists():
        return []
    paths: list[Path] = []
    for path in scene_dir.iterdir():
        if not path.is_file():
            continue
        if expected_format == "feature":
            matched = FEATURE_SCENE_FILE_RE.fullmatch(path.name)
        elif expected_format in EPISODIC_FORMATS:
            matched = EPISODIC_SCENE_FILE_RE.fullmatch(path.name)
        else:
            matched = FEATURE_SCENE_FILE_RE.fullmatch(
                path.name
            ) or EPISODIC_SCENE_FILE_RE.fullmatch(path.name)
        if matched:
            paths.append(path)
    return sorted(paths, key=scene_key)


def yaml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def yaml_list(values: list[Any]) -> str:
    if not values:
        return " []"
    return "\n" + "\n".join(f"  - {yaml_string(value)}" for value in values)


def require_inside(path: Path, parent: Path) -> None:
    resolved_path = path.resolve()
    resolved_parent = parent.resolve()
    try:
        resolved_path.relative_to(resolved_parent)
    except ValueError as exc:
        raise ValueError(f"路径必须位于 {resolved_parent} 内：{resolved_path}") from exc


def strict_int(
    value: Any,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} 必须是整数")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()):
        parsed = int(value)
    else:
        raise ValueError(f"{field} 必须是整数")
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{field} 必须在 {minimum}..{maximum}")
    return parsed
