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


class PackageImportTests(unittest.TestCase):
    def test_create_project_from_markdown_package_populates_harness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "资料包.md"
            project = root / "novel"
            write(
                package,
                """# 背景设定

灵能系统通过任务发放奖励，但每次越级使用都有代价。

# 人物设定

## 林澈

外在欲望：找到失踪的姐姐。

# 技能

- 影步：status=deprecated；author_note=废弃这个技能，不要再让它解决关键冲突；allow_use=false；aliases=暗影步,Shadow Step

# 作者指令

- 禁止金手指无代价破局：status=forbidden；author_note=所有胜利必须有代价；allow_use=false
""",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "create_project_from_package.py"),
                    "--package",
                    str(package),
                    "--project-root",
                    str(project),
                    "--title",
                    "灵能试炼",
                    "--format",
                    "series",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            background = (project / "background" / "story-background.md").read_text(encoding="utf-8")
            self.assertIn("灵能系统", background)
            character = (project / "bible" / "characters" / "lin-che.md").read_text(encoding="utf-8")
            self.assertIn("林澈", character)
            abilities = json.loads((project / "harness" / "abilities.json").read_text(encoding="utf-8"))
            ability = abilities["items"][0]
            self.assertEqual(ability["name"], "影步")
            self.assertEqual(ability["status"], "deprecated")
            self.assertEqual(ability["generation_policy"]["allow_use"], False)
            self.assertIn("暗影步", ability["aliases"])
            directives = json.loads((project / "harness" / "author-directives.json").read_text(encoding="utf-8"))
            self.assertTrue(
                any(item["name"] == "禁止金手指无代价破局" for item in directives["items"])
            )


if __name__ == "__main__":
    unittest.main()
