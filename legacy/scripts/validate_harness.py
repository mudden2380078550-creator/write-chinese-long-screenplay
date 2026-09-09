from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from harness_io import disallowed_usages
from screenplay_io import read_text, require_inside, parse_frontmatter, extract_h2_sections


USAGE_CUE_PATTERN = re.compile(
    r"(发动|施展|使用|启用|激活|开启|催动|祭出|装备|借助|依靠|凭借|用|靠|拿来|"
    r"解决|逃出|逃脱|潜入|追击|反杀|击败|通关|破局)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验正文是否违背 harness 作者控制项")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target-file", required=True, type=Path)
    return parser.parse_args()


def term_occurrences(text: str, terms: list[str]) -> list[tuple[str, int]]:
    matches: list[tuple[str, int]] = []
    for term in terms:
        if not term:
            continue
        for match in re.finditer(re.escape(term), text, re.IGNORECASE):
            matches.append((match.group(0), match.start()))
    return matches


def looks_like_usage(text: str, index: int, term: str) -> bool:
    # Local lexical heuristic, not a semantic proof. Contrast starts a new clause.
    before = re.split(r"[。！？；，\n]|但是|却|还是|而是", text[max(0,index-40):index])[-1]
    after = re.split(r"[。！？；，\n]|但是|却|还是|而是", text[index+len(term):index+len(term)+28])[0]
    negation = r"(?:没有|并未|未曾|没|不曾|不能|不要|不再|禁止|不得|未|不)\s*(?:再|曾|能|敢)?\s*$"
    for cue in USAGE_CUE_PATTERN.finditer(before):
        if not re.search(negation, before[:cue.start()]):
            return True
    if any(marker in after for marker in ("废弃", "禁用", "不能", "禁止")):
        return False
    for cue in USAGE_CUE_PATTERN.finditer(after):
        if not re.search(negation, after[:cue.start()]):
            return True
    return False


def match_disallowed_usage(text: str, item: dict[str, object]) -> tuple[bool, str]:
    patterns = item.get("patterns")
    compiled = []
    if isinstance(patterns, list):
        for pattern in patterns:
            try:
                compiled.append((pattern, re.compile(str(pattern), re.IGNORECASE)))
            except re.error as exc:
                raise ValueError(f"无效 forbidden_usage_patterns：{pattern}: {exc}") from exc
    for pattern, regex in compiled:
        if regex.search(text):
            return True, f"pattern={pattern}"

    terms = item.get("terms")
    if not isinstance(terms, list):
        terms = [str(item.get("name", ""))]
    occurrences = term_occurrences(text, [str(term) for term in terms])
    if not occurrences:
        return False, ""

    if item.get("allow_mention") is False:
        return True, f"mention={occurrences[0][0]}"

    for term, index in occurrences:
        if looks_like_usage(text, index, term):
            return True, f"usage={term}"
    return False, ""


def main() -> int:
    args = parse_args()
    try:
        root = args.project_root.resolve()
        target = args.target_file.resolve()
        require_inside(target, root)
        if not target.is_file():
            raise ValueError(f"目标文件不存在：{target}")
        text = read_text(target)
        body = text
        if text.lstrip().startswith("---"):
            _, body = parse_frontmatter(text)
        _, sections = extract_h2_sections(body)
        if "正文" in sections:
            text = sections["正文"]
        items = disallowed_usages(root)
        # Validate every configured expression before scanning any prose.
        for item in items:
            match_disallowed_usage("", item)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    findings = []
    for item in items:
        matched, reason = match_disallowed_usage(text, item)
        if matched:
            item = dict(item)
            item["match"] = reason
            findings.append(item)

    if not findings:
        print("OK: 词法规则未发现 harness 禁用项使用；不代表语义或连续性完整验证。")
        return 0

    print("HARNESS VIOLATION: 正文使用了禁用或废弃状态项。")
    for item in findings:
        print(
            f"- {item['file']} / {item['id']} / {item['name']}: "
            f"status={item['status']}；match={item.get('match', 'unknown')}；"
            f"作者注释={item['author_note'] or '无'}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
