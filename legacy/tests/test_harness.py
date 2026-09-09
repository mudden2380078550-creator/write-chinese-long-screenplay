from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class HarnessTests(unittest.TestCase):
    def make_project(self, root: Path) -> None:
        write(
            root / "project.md",
            """---
id: test-project
type: project
title: "测试项目"
language: zh-CN
format: series
schema_version: 2
story_engine: causal-value
structure_adapters: []
status: seed
---
# 测试项目
""",
        )
        write(root / "AGENTS.md", "使用 harness 状态作为创作约束。\n")
        write(root / "style" / "screenplay-style.md", "# 风格\n\n中文网文节奏。\n")
        write(root / "background" / "story-background.md", "# 背景\n\n系统会发布任务。\n")
        write(root / "bible" / "series-bible.md", "# 系列圣经\n\n主角靠任务升级。\n")
        write(root / "outline" / "master-outline.md", "# 总纲\n\n主角进入试炼塔。\n")
        write(root / "outline" / "episodes" / "E001.md", "# E001\n\n第二场必须不用影步逃脱。\n")
        write(
            root / "ledger" / "story-ledger.json",
            json.dumps(
                {
                    "schema_version": 2,
                    "project_title": "测试项目",
                    "format": "series",
                    "updated": "2026-09-03",
                    "scene_summaries": [],
                    "state_changes": [],
                    "knowledge_changes": [],
                    "relationship_changes": [],
                    "object_changes": [],
                    "clue_changes": [],
                    "thread_changes": [],
                    "value_changes": [],
                    "decision_changes": [],
                    "audience_evidence": [],
                    "open_questions": [],
                    "uncertainties": [],
                },
                ensure_ascii=False,
            ),
        )
        write(
            root / "harness" / "abilities.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "items": [
                        {
                            "id": "ability-shadow-step",
                            "name": "影步",
                            "status": "deprecated",
                            "introduced_in": "S001",
                            "author_note": "废弃这个技能，不要再让它解决关键冲突。",
                            "generation_policy": {
                                "allow_use": False,
                                "allow_mention": True,
                                "must_avoid_scenes": ["逃脱", "潜入", "追击"],
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        )

    def test_context_pack_includes_harness_bans(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            output = root / "context.md"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build_context.py"),
                    "--project-root",
                    str(root),
                    "--episode",
                    "1",
                    "--scene",
                    "2",
                    "--query",
                    "影步 逃脱",
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            context = output.read_text(encoding="utf-8")
            self.assertIn("Harness 控制台", context)
            self.assertIn("废弃能力", context)
            self.assertIn("影步", context)
            self.assertIn("不要再让它解决关键冲突", context)

    def test_validate_harness_rejects_disallowed_ability_use(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            draft = root / "screenplay" / "scenes" / "E001-S002.md"
            write(draft, "主角发动影步，直接逃出了包围圈。\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_harness.py"),
                    "--project-root",
                    str(root),
                    "--target-file",
                    str(draft),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ability-shadow-step", result.stdout)
            self.assertIn("deprecated", result.stdout)

    def test_validate_harness_allows_plain_deprecated_mention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            draft = root / "screenplay" / "scenes" / "E001-S002.md"
            write(draft, "长老提醒众人：影步已经废弃，不能再拿来解决逃脱问题。\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_harness.py"),
                    "--project-root",
                    str(root),
                    "--target-file",
                    str(draft),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validate_harness_rejects_alias_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            abilities = root / "harness" / "abilities.json"
            data = json.loads(abilities.read_text(encoding="utf-8"))
            data["items"][0]["aliases"] = ["暗影步", "Shadow Step"]
            data["items"][0]["generation_policy"]["forbidden_usage_patterns"] = [
                "发动(?:影步|暗影步|Shadow Step)"
            ]
            write(abilities, json.dumps(data, ensure_ascii=False))
            draft = root / "screenplay" / "scenes" / "E001-S002.md"
            write(draft, "主角发动暗影步，避开了追击。\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_harness.py"),
                    "--project-root",
                    str(root),
                    "--target-file",
                    str(draft),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("pattern=", result.stdout)

    def test_harness_context_respects_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            abilities = root / "harness" / "abilities.json"
            data = json.loads(abilities.read_text(encoding="utf-8"))
            data["items"].extend(
                {
                    "id": f"ability-extra-{index}",
                    "name": f"长名字技能{index}",
                    "status": "active",
                    "author_note": "普通可用技能，不应该挤占关键禁令预算。" * 8,
                    "generation_policy": {"allow_use": True},
                }
                for index in range(30)
            )
            write(abilities, json.dumps(data, ensure_ascii=False))
            output = root / "context.md"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "build_context.py"),
                    "--project-root",
                    str(root),
                    "--episode",
                    "1",
                    "--scene",
                    "2",
                    "--max-tokens",
                    "1000",
                    "--query",
                    "逃脱",
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            context = output.read_text(encoding="utf-8")
            self.assertIn("影步", context)
            self.assertLessEqual(len(context), 1700)

    def test_update_harness_state_patches_existing_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            payload = root / "state-update.json"
            write(
                payload,
                json.dumps(
                    {
                        "updates": [
                            {
                                "file": "abilities.json",
                                "id": "ability-shadow-step",
                                "mode": "patch",
                                "patch": {
                                    "status": "active",
                                    "author_note": "恢复为可用，但不能解决最终战。",
                                    "generation_policy": {"allow_use": True},
                                },
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "update_harness_state.py"),
                    "--project-root",
                    str(root),
                    "--input",
                    str(payload),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((root / "harness" / "abilities.json").read_text(encoding="utf-8"))
            item = data["items"][0]
            self.assertEqual(item["status"], "active")
            self.assertEqual(item["generation_policy"]["allow_use"], True)
            self.assertIn("最终战", item["author_note"])

    def test_update_harness_state_accepts_external_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as project_tmp, tempfile.TemporaryDirectory() as payload_tmp:
            root = Path(project_tmp)
            self.make_project(root)
            payload = Path(payload_tmp) / "state-update.json"
            write(
                payload,
                json.dumps(
                    {
                        "updates": [
                            {
                                "file": "abilities.json",
                                "id": "ability-shadow-step",
                                "mode": "patch",
                                "patch": {"author_note": "外部审定包可以驱动 harness 回写。"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "update_harness_state.py"),
                    "--project-root",
                    str(root),
                    "--input",
                    str(payload),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((root / "harness" / "abilities.json").read_text(encoding="utf-8"))
            self.assertIn("外部审定包", data["items"][0]["author_note"])


if __name__ == "__main__":
    unittest.main()
