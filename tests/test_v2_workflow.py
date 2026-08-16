from __future__ import annotations

import contextlib
import io
import json
import re
import runpy
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
TEST_TMP = SKILL_ROOT / ".test-tmp-v2"
sys.path.insert(0, str(SCRIPTS))


def run_script(name: str, *args: str) -> SimpleNamespace:
    stdout = io.StringIO()
    stderr = io.StringIO()
    previous_argv = sys.argv
    returncode = 0
    try:
        sys.argv = [str(SCRIPTS / name), *map(str, args)]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                runpy.run_path(str(SCRIPTS / name), run_name="__main__")
            except SystemExit as exc:
                returncode = int(exc.code or 0)
    finally:
        sys.argv = previous_argv
    return SimpleNamespace(
        returncode=returncode, stdout=stdout.getvalue(), stderr=stderr.getvalue()
    )


@contextmanager
def workspace_temp():
    TEST_TMP.mkdir(exist_ok=True)
    path = TEST_TMP / f"case-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


def fill_structure_map(root: Path) -> None:
    path = root / "outline" / "structure-map.md"
    text = path.read_text(encoding="utf-8")
    values = {
        "主题命题": "信任得以建立，因为主角选择承担共同风险。",
        "反命题": "关系走向背叛，因为人物只保护自己的控制权。",
        "外在欲望": "主角要找到失踪账本。",
        "内在需要": "主角需要学会把控制权交给可信任的人。",
        "核心行动线": "主角追查账本并揭开港务公司旧事故。",
        "激励性扰动": "主角收到失踪者留下的仓库编号。",
        "递进复杂化": "对手封锁证据并迫使盟友暴露秘密。",
        "不可回头点": "主角公开指控港务公司，失去内部退路。",
        "危机选择": "主角必须在保住证据与救出盟友之间选择。",
        "高潮行动": "主角销毁唯一能自保的副本以换取盟友生还。",
        "结局价值": "控制权转化为共同承担。",
        "余波": "两人公开证词，同时面对职业与法律代价。",
    }
    for label, value in values.items():
        text = text.replace(f"{label}：\n", f"{label}：{value}\n", 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def add_character(root: Path) -> None:
    path = root / "bible" / "characters" / "char-main.md"
    path.write_text(
        """---
id: char-main
type: character
name: "顾晴"
status: active
---

# 顾晴

- 外在欲望：找到失踪账本。
- 内在需要：学会共享控制权。
- 知识边界：尚不知道盟友参与过旧事故。
""",
        encoding="utf-8",
        newline="\n",
    )


def scene_payload(scene: int) -> dict[str, object]:
    return {
        "scene": scene,
        "act": 1,
        "sequence": 1,
        "title": f"仓库-{scene}",
        "status": "draft",
        "location": "旧港仓库",
        "time_of_day": "夜",
        "interior_exterior": "内",
        "story_time": f"第三天 02:{scene:02d}",
        "characters": ["char-main"],
        "viewpoint_character": "char-main",
        "display_characters": "顾晴",
        "threads": ["main"],
        "source_files": ["bible/characters/char-main.md"],
        "source_character_facts": ["顾晴用控制细节掩饰恐惧。"],
        "source_background_facts": [],
        "source_world_rules": [],
        "forbidden_contradictions": ["顾晴尚不知道盟友参与旧事故。"],
        "scene_objective": f"顾晴要取得第 {scene} 份记录。",
        "story_value": "控制权",
        "entry_value": f"顾晴掌握第 {scene} 个入口。",
        "primary_conflict": "管理员拒绝开放记录柜，并准备触发警报。",
        "tactic": "顾晴用伪造的检修单制造时间压力。",
        "expected_result": "管理员交出记录后离开。",
        "actual_result": "管理员锁死出口并触发静默警报。",
        "result_gap": "伪造文件暴露顾晴不属于检修系统，使出口先被封锁。",
        "turn": "警报灯没有发声却由绿转红。",
        "audience_entry": "观众知道顾晴使用假身份。",
        "audience_update": "港务公司早已为假检修单设置识别规则。",
        "exit_value": f"管理员掌握第 {scene} 个出口，顾晴失去退路。",
        "next_pressure": "顾晴必须在保安抵达前找到另一条离开路径。",
        "dialogue_subtext": "顾晴表现得像例行检修，实际在测试管理员是否知情。",
        "character_voice": "顾晴使用短句、时间和编号压缩情绪。",
        "draft": "△ 警报灯由绿转红。顾晴把检修单折回口袋。\n\n顾晴：柜门打开。现在。",
        "continuity": [],
        "revision_notes": [],
    }


def distinct_voice_draft() -> str:
    jia = [
        "嗯。柜门打开吧。",
        "啊？别装了。",
        "行，我等着。",
        "呢？钥匙呢？",
        "哦。那你走吧。",
        "嘿，别碰。",
        "算了，我自己来。",
        "喂，站住。",
        "走吧走吧。",
        "停。现在。",
        "别磨蹭。",
        "真够了。",
        "你走吧。",
        "嗯，就这样。",
        "行了。",
        "快说。",
    ]
    yi = [
        "请您将检修单交到前台登记。",
        "恕我直言，您并不属于检修系统。",
        "按照港务条例，本区需要双重授权。",
        "这件事我必须向值班室核实。",
        "您的通行证已经超出有效范围。",
        "请勿触碰该设备。",
        "根据记录，您并未获得本层权限。",
        "我必须请您立即离开。",
        "这不符合规定。",
        "我需要向上级报告此事。",
        "您的请求无法被批准。",
        "按照规定，我需要核对您的身份。",
        "此处禁止无关人员停留。",
        "请您配合登记。",
        "您是否理解此处的安全要求？",
        "请立即停步。",
    ]
    return "\n\n".join(
        f"{name}：{line}"
        for index in range(16)
        for name, line in (("甲", jia[index]), ("乙", yi[index]))
    )


def clone_voice_draft() -> str:
    line = "这件事轮不到你来定。"
    return "\n\n".join(
        f"{name}：{line}"
        for index in range(16)
        for name in ("丙", "丁")
    )


def write_min_scene(root: Path, number: int) -> None:
    scene_id = f"S{number:03d}"
    card = "\n".join(
        [
            f"场景标头：{number} 地点 夜 内",
            "来源依据：bible/characters/char-main.md",
            "人物依据：char-main",
            "视点人物：char-main",
            f"场景目标：目标{number}",
            "故事价值：控制权",
            f"入场价值：入{number}",
            f"主冲突：冲突{number}",
            f"策略：策略{number}",
            f"预期结果：预期{number}",
            f"实际结果：实际{number}",
            f"结果落差：落差{number}",
            f"场面转折：转折{number}",
            f"观众更新：更新{number}",
            f"出场价值：出{number}",
            f"下场压力：压{number}",
            "禁止矛盾：无",
        ]
    )
    text = (
        f"---\n"
        f"id: {scene_id}\n"
        f"type: scene\n"
        f"scene: {number}\n"
        f"act: 1\n"
        f"sequence: 1\n"
        f'title: "T{number}"\n'
        f'status: draft\n'
        f'location: "地点"\n'
        f'time_of_day: "夜"\n'
        f'interior_exterior: "内"\n'
        f'characters:\n  - "char-main"\n'
        f"threads: []\n"
        f'source_files:\n  - "bible/characters/char-main.md"\n'
        f"created: 2026-01-01\n"
        f"updated: 2026-01-01\n"
        f"---\n\n"
        f"# {scene_id} T{number}\n\n"
        f"## 场次卡\n\n"
        f"{card}\n\n"
        f"## 正文\n\n"
        f"△ 动作{number}。\n\n"
        f"## 连续性\n\n-\n\n## 改稿备注\n\n-\n"
    )
    (root / "screenplay" / "scenes" / f"{scene_id}.md").write_text(
        text, encoding="utf-8", newline="\n"
    )


class V2WorkflowTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(TEST_TMP, ignore_errors=True)

    def init_feature(self, root: Path, *extra: str) -> None:
        result = run_script(
            "init_project.py",
            "--project-root",
            str(root),
            "--title",
            "潮线",
            "--format",
            "feature",
            *extra,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def write_scene(self, root: Path, payload: dict[str, object]) -> None:
        input_path = root / f"scene-{payload['scene']}.json"
        input_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8", newline="\n"
        )
        result = run_script(
            "write_scene.py",
            "--project-root",
            str(root),
            "--input",
            str(input_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_init_declares_v2_and_adapter(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root, "--adapter", "mckee")
            project = (root / "project.md").read_text(encoding="utf-8")
            self.assertIn("schema_version: 2", project)
            self.assertIn("story_engine: causal-value", project)
            self.assertIn('"mckee"', project)
            self.assertTrue((root / "outline" / "structure-map.md").is_file())
            background = (root / "background" / "story-background.md").read_text(
                encoding="utf-8"
            )
            character_template = (
                root / "bible" / "characters" / "_template.md"
            ).read_text(encoding="utf-8")
            feature_bible = (root / "bible" / "feature-bible.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("用户输入板块之一", background)
            self.assertIn("用户输入板块之一", character_template)
            self.assertIn("内部故事桥接文件", feature_bible)

    def test_episodic_project_shares_v2_but_rejects_film_adapter(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "剧集"
            result = run_script(
                "init_project.py",
                "--project-root",
                str(root),
                "--title",
                "长夜",
                "--format",
                "series",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            project = (root / "project.md").read_text(encoding="utf-8")
            self.assertIn("schema_version: 2", project)
            self.assertIn("story_engine: causal-value", project)
            validate = run_script("validate_project.py", "--project-root", str(root))
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

            rejected = run_script(
                "init_project.py",
                "--project-root",
                str(Path(temp) / "错误剧集"),
                "--title",
                "错误",
                "--format",
                "series",
                "--adapter",
                "field",
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("仅用于电影项目", rejected.stderr)

    def test_end_to_end_three_scenes_validate_review_compile(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            fill_structure_map(root)
            for scene in range(1, 4):
                self.write_scene(root, scene_payload(scene))

            validate = run_script(
                "validate_project.py", "--project-root", str(root), "--strict"
            )
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

            review = run_script(
                "self_review.py",
                "--project-root",
                str(root),
                "--focus",
                "full",
                "--strict",
                "--compact",
            )
            self.assertEqual(review.returncode, 0, review.stdout + review.stderr)

            compile_result = run_script(
                "compile_screenplay.py", "--project-root", str(root)
            )
            self.assertEqual(
                compile_result.returncode,
                0,
                compile_result.stdout + compile_result.stderr,
            )
            compiled = (root / "exports" / "screenplay.md").read_text(encoding="utf-8")
            self.assertEqual(compiled.count("警报灯由绿转红"), 3)

    def test_write_scene_rejects_static_value_and_no_gap(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            payload = scene_payload(1)
            payload["exit_value"] = payload["entry_value"]
            input_path = root / "invalid.json"
            input_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
                newline="\n",
            )
            result = run_script(
                "write_scene.py",
                "--project-root",
                str(root),
                "--input",
                str(input_path),
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("必须发生实质变化", result.stderr)

            payload = scene_payload(1)
            payload["actual_result"] = payload["expected_result"]
            input_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
                newline="\n",
            )
            no_gap = run_script(
                "write_scene.py",
                "--project-root",
                str(root),
                "--input",
                str(input_path),
            )
            self.assertEqual(no_gap.returncode, 2)
            self.assertIn("不能相同", no_gap.stderr)

            payload = scene_payload(1)
            payload["next_pressure"] = ""
            input_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
                newline="\n",
            )
            missing = run_script(
                "write_scene.py",
                "--project-root",
                str(root),
                "--input",
                str(input_path),
            )
            self.assertEqual(missing.returncode, 2)
            self.assertIn("next_pressure 不能为空", missing.stderr)

    def test_context_budget_and_review_alias(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            self.write_scene(root, scene_payload(1))
            output = root / "scene-context.md"
            result = run_script(
                "build_context.py",
                "--project-root",
                str(root),
                "--scene",
                "1",
                "--profile",
                "scene",
                "--max-tokens",
                "700",
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            context = output.read_text(encoding="utf-8")
            self.assertLessEqual(len(context), 1250)
            self.assertIn("预算：约 700 tokens", context)

            alias = run_script(
                "build_context.py",
                "--project-root",
                str(root),
                "--profile",
                "review",
                "--output",
                str(root / "review-context.md"),
            )
            self.assertEqual(alias.returncode, 0, alias.stdout + alias.stderr)
            self.assertIn("档位：full-review", alias.stdout)

    def test_adaptive_scene_profiles_and_batch_range(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            self.write_scene(root, scene_payload(1))

            expected_budgets = {
                "scene-light": 4000,
                "scene": 7000,
                "scene-complex": 12000,
            }
            for profile, budget in expected_budgets.items():
                output = root / f"{profile}.md"
                result = run_script(
                    "build_context.py",
                    "--project-root",
                    str(root),
                    "--scene",
                    "2",
                    "--profile",
                    profile,
                    "--output",
                    str(output),
                )
                self.assertEqual(
                    result.returncode, 0, result.stdout + result.stderr
                )
                context = output.read_text(encoding="utf-8")
                self.assertIn(f"预算：约 {budget} tokens", context)

            batch_output = root / "batch.md"
            batch = run_script(
                "build_context.py",
                "--project-root",
                str(root),
                "--scene-from",
                "2",
                "--scene-to",
                "5",
                "--profile",
                "batch",
                "--query",
                "顾晴 仓库",
                "--source-file",
                "bible/characters/char-main.md",
                "--output",
                str(batch_output),
            )
            self.assertEqual(batch.returncode, 0, batch.stdout + batch.stderr)
            context = batch_output.read_text(encoding="utf-8")
            self.assertIn("目标：电影第 2–5 场", context)
            self.assertIn("预算：约 16000 tokens", context)
            self.assertIn("本文件是批次共享上下文", context)
            self.assertIn("顾晴", context)

            too_many = run_script(
                "build_context.py",
                "--project-root",
                str(root),
                "--scene-from",
                "2",
                "--scene-to",
                "10",
                "--profile",
                "batch",
                "--output",
                str(root / "too-many.md"),
            )
            self.assertEqual(too_many.returncode, 2)
            self.assertIn("最多构建连续 8 场", too_many.stderr)

            incomplete = run_script(
                "build_context.py",
                "--project-root",
                str(root),
                "--scene-from",
                "2",
                "--profile",
                "batch",
                "--output",
                str(root / "incomplete.md"),
            )
            self.assertEqual(incomplete.returncode, 2)
            self.assertIn("必须同时提供", incomplete.stderr)

    def test_self_review_flags_repeated_template_language(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            payload = scene_payload(1)
            payload["draft"] = (
                "△ 与此同时，顾晴把钥匙收回掌心。\n\n"
                "顾晴：这意味着你已经输了。\n\n"
                "△ 就在这时，门外响起脚步。"
            )
            self.write_scene(root, payload)
            result = run_script(
                "self_review.py",
                "--project-root",
                str(root),
                "--focus",
                "dialogue",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            minor_codes = {item["code"] for item in data["findings"]["minor"]}
            self.assertIn("ai-template-language", minor_codes)
            messages = [
                item["message"]
                for item in data["findings"]["minor"]
                if item["code"] == "ai-template-language"
            ]
            self.assertTrue(any("Humanizer-zh 中文问题清单" in message for message in messages))

    def test_natural_chinese_reference_has_24_categories(self) -> None:
        path = SKILL_ROOT / "references" / "natural-chinese.md"
        text = path.read_text(encoding="utf-8")
        numbers = [
            int(match.group(1))
            for match in re.finditer(r"^(\d+)\.\s+\*\*", text, re.MULTILINE)
        ]
        self.assertEqual(numbers, list(range(1, 25)))
        self.assertIn("只借用 [Humanizer-zh]", text)
        self.assertIn("不把检测分数当作写作目标", text)

    def test_save_the_cat_adapter_is_advisory(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root, "--adapter", "save-the-cat")
            fill_structure_map(root)
            result = run_script(
                "self_review.py",
                "--project-root",
                str(root),
                "--focus",
                "structure",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            codes = {item["code"] for item in data["findings"]["minor"]}
            self.assertIn("adapter-save-the-cat", codes)
            self.assertFalse(data["findings"]["blocking"])

    def test_author_adapters_are_reviewed_independently(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(
                root,
                "--adapter",
                "field",
                "--adapter",
                "mckee",
                "--adapter",
                "save-the-cat",
            )
            fill_structure_map(root)
            path = root / "outline" / "structure-map.md"
            text = path.read_text(encoding="utf-8")
            text = text.replace("菲尔德·情节点Ⅰ：\n", "菲尔德·情节点Ⅰ：主角主动公开证据。\n")
            text = text.replace("菲尔德·情节点Ⅱ：\n", "菲尔德·情节点Ⅱ：主角选择牺牲自保副本。\n")
            text = text.replace("菲尔德·结局：\n", "菲尔德·结局：公开证词后的新秩序。\n")
            path.write_text(text, encoding="utf-8", newline="\n")

            result = run_script(
                "self_review.py",
                "--project-root",
                str(root),
                "--focus",
                "structure",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            major_codes = {item["code"] for item in data["findings"]["major"]}
            minor_codes = {item["code"] for item in data["findings"]["minor"]}
            self.assertNotIn("adapter-field", major_codes | minor_codes)
            self.assertIn("adapter-mckee", major_codes)
            self.assertIn("adapter-save-the-cat", minor_codes)

    def test_migration_preview_apply_backup_and_blockers(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "旧剧集"
            (root / "screenplay" / "scenes").mkdir(parents=True)
            (root / "reviews").mkdir()
            (root / "ledger").mkdir()
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            project_text = """---
id: old-project
type: project
title: "旧项目"
format: series
---

# 旧项目
"""
            (root / "project.md").write_text(
                project_text, encoding="utf-8", newline="\n"
            )
            (root / "ledger" / "story-ledger.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "scene_summaries": [],
                        "state_changes": [],
                        "knowledge_changes": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
                newline="\n",
            )
            scene_text = """---
id: E001-S001
type: scene
episode: 1
scene: 1
title: "旧场"
status: draft
location: "家"
time_of_day: "夜"
interior_exterior: "内"
characters:
  - "char-a"
threads: []
source_files: []
created: 2026-01-01
updated: 2026-01-01
---

# E001-S001 旧场

## 场次卡

场景标头：1-1 家 夜 内
结构位置：第 1 集
来源依据：-
人物依据：-
背景依据：-
世界规则：-
场次任务：人物要离开家。
观众入口：-
入场状态：人物仍在家。
场面转折：门被锁上。
观众更新：门锁来自外部。
出场状态：人物被困。
禁止矛盾：-

## 正文

△ 门从外面锁上。

## 连续性

-

## 改稿备注

-
"""
            scene_path = root / "screenplay" / "scenes" / "E001-S001.md"
            scene_path.write_text(scene_text, encoding="utf-8", newline="\n")

            preview = run_script(
                "migrate_project.py", "--project-root", str(root)
            )
            self.assertEqual(preview.returncode, 1, preview.stdout + preview.stderr)
            self.assertEqual(
                (root / "project.md").read_text(encoding="utf-8"), project_text
            )
            self.assertTrue((root / "reviews" / "v2-migration.md").is_file())

            applied = run_script(
                "migrate_project.py", "--project-root", str(root), "--apply"
            )
            self.assertEqual(applied.returncode, 1, applied.stdout + applied.stderr)
            migrated_project = (root / "project.md").read_text(encoding="utf-8")
            self.assertIn("schema_version: 2", migrated_project)
            self.assertIn("story_engine: causal-value", migrated_project)
            self.assertIn("【待补】", scene_path.read_text(encoding="utf-8"))
            self.assertIn("两难选项：-", scene_path.read_text(encoding="utf-8"))
            ledger = json.loads(
                (root / "ledger" / "story-ledger.json").read_text(encoding="utf-8")
            )
            self.assertEqual(ledger["schema_version"], 2)
            self.assertEqual(ledger["format"], "series")
            self.assertEqual(ledger["value_changes"], [])
            self.assertEqual(ledger["decision_changes"], [])
            backups = list((root / "backups").glob("v1-to-v2-*"))
            self.assertEqual(len(backups), 1)
            self.assertTrue((backups[0] / "project.md").is_file())
            self.assertTrue((backups[0] / "ledger" / "story-ledger.json").is_file())

            validate = run_script(
                "validate_project.py", "--project-root", str(root), "--strict"
            )
            self.assertEqual(validate.returncode, 1)
            self.assertIn("card-field-value", validate.stdout)

    def test_feature_act_and_sequence_are_positive_strict_integers(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            payload = scene_payload(1)
            payload["act"] = 0
            input_path = root / "invalid-act.json"
            input_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
                newline="\n",
            )
            rejected = run_script(
                "write_scene.py",
                "--project-root",
                str(root),
                "--input",
                str(input_path),
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("act 必须在 1..99", rejected.stderr)

            self.write_scene(root, scene_payload(1))
            scene_path = root / "screenplay" / "scenes" / "S001.md"
            text = scene_path.read_text(encoding="utf-8").replace(
                "act: 1", "act: 0", 1
            )
            scene_path.write_text(text, encoding="utf-8", newline="\n")
            strict = run_script(
                "validate_project.py",
                "--project-root",
                str(root),
                "--strict",
                "--json",
            )
            data = json.loads(strict.stdout)
            codes = {item["code"] for item in data["errors"]}
            self.assertIn("act-range", codes)

    def test_compile_refuses_a_scene_that_fails_strict_validation(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            fill_structure_map(root)
            self.write_scene(root, scene_payload(1))
            scene_path = root / "screenplay" / "scenes" / "S001.md"
            text = scene_path.read_text(encoding="utf-8").replace(
                "下场压力：顾晴必须在保安抵达前找到另一条离开路径。",
                "下场压力：-",
                1,
            )
            scene_path.write_text(text, encoding="utf-8", newline="\n")

            strict = run_script(
                "validate_project.py", "--project-root", str(root), "--strict"
            )
            self.assertEqual(strict.returncode, 1)
            compile_result = run_script(
                "compile_screenplay.py", "--project-root", str(root)
            )
            self.assertEqual(compile_result.returncode, 2)
            self.assertIn("严格校验未通过", compile_result.stderr)
            self.assertFalse((root / "exports" / "screenplay.md").exists())

    def test_migration_builds_a_missing_ledger_and_uses_post_apply_gate(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "旧剧集"
            (root / "screenplay" / "scenes").mkdir(parents=True)
            (root / "reviews").mkdir()
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (root / "project.md").write_text(
                """---
id: old-project
type: project
title: "旧项目"
format: series
---

# 旧项目
""",
                encoding="utf-8",
                newline="\n",
            )
            applied = run_script(
                "migrate_project.py", "--project-root", str(root), "--apply"
            )
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            ledger_path = root / "ledger" / "story-ledger.json"
            self.assertTrue(ledger_path.is_file())
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertEqual(ledger["schema_version"], 2)
            self.assertEqual(ledger["format"], "series")
            self.assertIn("knowledge_changes", ledger)
            strict = run_script(
                "validate_project.py", "--project-root", str(root), "--strict"
            )
            self.assertEqual(strict.returncode, 0, strict.stdout + strict.stderr)

            feature = Path(temp) / "旧电影"
            (feature / "screenplay" / "scenes").mkdir(parents=True)
            (feature / "reviews").mkdir()
            (feature / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (feature / "project.md").write_text(
                """---
id: old-feature
type: project
title: "旧电影"
format: feature
---

# 旧电影
""",
                encoding="utf-8",
                newline="\n",
            )
            feature_result = run_script(
                "migrate_project.py",
                "--project-root",
                str(feature),
                "--apply",
            )
            self.assertEqual(feature_result.returncode, 1)
            report = (feature / "reviews" / "v2-migration.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("structure-map-field", report)
            self.assertIn("严格校验阻断", report)

    def test_migration_upgrades_known_v1_feature_sources(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "旧电影模板"
            self.init_feature(root)
            bible_path = root / "bible" / "feature-bible.md"
            bible = bible_path.read_text(encoding="utf-8")
            bible = bible.replace("## 主题命题", "## 主题与承诺")
            bible = bible.replace(
                "- 主题命题（价值结果，因为人物如何行动）：\n", ""
            )
            bible = bible.replace(
                "- 反命题（相反价值结果，因为人物如何行动）：\n", ""
            )
            bible = bible.replace("- 外在欲望：", "- 外部目标：")
            bible = bible.replace("- 内在需要：", "- 内部需要：")
            bible = bible.replace("- 核心行动线：\n", "")
            bible = bible.replace("- 余波必须展示的价值状态：\n", "")
            bible_path.write_text(bible, encoding="utf-8", newline="\n")

            sequence_path = root / "outline" / "sequence-outline.md"
            sequence = sequence_path.read_text(encoding="utf-8")
            new_sequence_header = (
                "| 序列 | 幕 | 故事价值 | 进入价值 | 序列任务 | 递进压力 | "
                "关键选择 | 序列转折 | 退出价值 | 下序列压力 |"
            )
            sequence = sequence.replace(
                new_sequence_header,
                "| 序列 | 幕 | 进入状态 | 序列任务 | 压力 | 关键选择 | 转折 | 退出状态 |",
            )
            sequence_path.write_text(sequence, encoding="utf-8", newline="\n")

            scene_outline_path = root / "outline" / "scene-outline.md"
            scene_outline = scene_outline_path.read_text(encoding="utf-8")
            current_header = (
                "| 场 | 幕/序列 | 地点/日夜/内外 | 来源 | 视点人物 | 场景目标 | "
                "故事价值 | 入场价值 | 主冲突/策略 | 预期→实际/落差 | 转折 | "
                "观众更新 | 出场价值 | 下场压力 |"
            )
            scene_outline = scene_outline.replace(
                current_header,
                "| 场 | 幕/序列 | 地点/日夜/内外 | 来源 | 人物目标 | 背景/规则压力 | "
                "策略与反制 | 转折 | 观众更新 | 出场状态 |",
            )
            scene_outline_path.write_text(
                scene_outline, encoding="utf-8", newline="\n"
            )

            result = run_script(
                "migrate_project.py", "--project-root", str(root), "--apply"
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "主题命题（价值结果，因为人物如何行动）",
                bible_path.read_text(encoding="utf-8"),
            )
            self.assertIn(
                new_sequence_header,
                sequence_path.read_text(encoding="utf-8"),
            )
            self.assertIn(
                current_header,
                scene_outline_path.read_text(encoding="utf-8"),
            )
            backups = list((root / "backups").glob("v1-to-v2-*"))
            self.assertEqual(len(backups), 1)
            self.assertTrue(
                (backups[0] / "outline" / "sequence-outline.md").is_file()
            )

    def test_context_uses_relevant_sections_and_protects_existing_output(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            material = root / "background" / "long-material.md"
            material.write_text(
                "# 长材料\n\n## 无关历史\n\n"
                + ("无关内容。" * 2000)
                + "\n\n## 潮汐密钥\n\n蓝色钥匙只能在最低潮时打开闸门。\n",
                encoding="utf-8",
                newline="\n",
            )
            output = root / "context.md"
            result = run_script(
                "build_context.py",
                "--project-root",
                str(root),
                "--scene",
                "1",
                "--profile",
                "scene",
                "--query",
                "潮汐密钥",
                "--max-tokens",
                "700",
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            context = output.read_text(encoding="utf-8")
            self.assertIn("蓝色钥匙只能在最低潮时打开闸门", context)

            protected = run_script(
                "build_context.py",
                "--project-root",
                str(root),
                "--scene",
                "1",
                "--profile",
                "scene",
                "--max-tokens",
                "700",
                "--output",
                str(output),
            )
            self.assertEqual(protected.returncode, 2)
            self.assertIn("输出文件已存在", protected.stderr)
            forced = run_script(
                "build_context.py",
                "--project-root",
                str(root),
                "--scene",
                "1",
                "--profile",
                "scene",
                "--max-tokens",
                "700",
                "--output",
                str(output),
                "--force",
            )
            self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)

    def test_save_the_cat_position_deviation_is_advisory(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root, "--adapter", "save-the-cat")
            fill_structure_map(root)
            path = root / "outline" / "structure-map.md"
            text = path.read_text(encoding="utf-8")
            labels = (
                "开场画面",
                "阐明主题",
                "布局铺垫",
                "触发事件",
                "展开讨论",
                "进入第二幕",
                "副线故事",
                "玩闹和游戏",
                "中点",
                "反派逼近",
                "失去一切",
                "灵魂黑夜",
                "进入第三幕",
                "结局",
                "终场画面",
            )
            for label in labels:
                text = text.replace(
                    f"救猫咪·{label}：\n",
                    f"救猫咪·{label}：S001 | 90% | 人物选择造成后果\n",
                    1,
                )
            path.write_text(text, encoding="utf-8", newline="\n")
            result = run_script(
                "self_review.py",
                "--project-root",
                str(root),
                "--focus",
                "structure",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            codes = {item["code"] for item in data["findings"]["minor"]}
            self.assertIn("adapter-save-the-cat-position", codes)
            self.assertFalse(data["findings"]["blocking"])

    def test_missing_source_and_knowledge_review_are_covered(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            fill_structure_map(root)
            self.write_scene(root, scene_payload(1))
            (root / "bible" / "characters" / "char-main.md").unlink()
            validate = run_script(
                "validate_project.py",
                "--project-root",
                str(root),
                "--strict",
                "--json",
            )
            data = json.loads(validate.stdout)
            codes = {item["code"] for item in data["errors"]}
            self.assertIn("source-missing", codes)

            review = run_script(
                "self_review.py",
                "--project-root",
                str(root),
                "--focus",
                "full",
                "--strict",
            )
            self.assertEqual(review.returncode, 1)
            report = (root / "reviews" / "self-review.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("人物只使用当时已获得的知识", report)
            self.assertIn("character-source", report)

    def test_update_ledger_checks_format_and_persists_v2_changes(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            self.write_scene(root, scene_payload(1))
            payload_path = root / "ledger-update.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "scene_id": "S001",
                        "summary": "顾晴被静默警报困在仓库。",
                        "value_changes": [
                            {
                                "value": "控制权",
                                "from": "顾晴",
                                "to": "管理员",
                            }
                        ],
                        "knowledge_changes": [
                            {"character": "char-main", "learned": "静默警报存在"}
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
                newline="\n",
            )
            updated = run_script(
                "update_ledger.py",
                "--project-root",
                str(root),
                "--input",
                str(payload_path),
            )
            self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
            ledger = json.loads(
                (root / "ledger" / "story-ledger.json").read_text(encoding="utf-8")
            )
            self.assertEqual(ledger["value_changes"][0]["scene_id"], "S001")
            self.assertEqual(
                ledger["knowledge_changes"][0]["character"], "char-main"
            )

            wrong_id = json.loads(payload_path.read_text(encoding="utf-8"))
            wrong_id["scene_id"] = "E001-S001"
            payload_path.write_text(
                json.dumps(wrong_id, ensure_ascii=False),
                encoding="utf-8",
                newline="\n",
            )
            rejected = run_script(
                "update_ledger.py",
                "--project-root",
                str(root),
                "--input",
                str(payload_path),
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("电影项目", rejected.stderr)

    def test_audience_focus_builds_blind_read_report(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            for scene in (1, 2):
                self.write_scene(root, scene_payload(scene))
            result = run_script(
                "self_review.py", "--project-root", str(root), "--focus", "audience"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = (root / "reviews" / "self-review.md").read_text(encoding="utf-8")
            self.assertIn("盲读审读报告", report)
            self.assertIn("哪一场最无聊", report)
            self.assertIn("柜门打开。现在。", report)
            self.assertNotIn("结构适配器", report)

    def test_dialogue_voice_distinct_speakers_not_flagged(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            payload = scene_payload(1)
            payload["draft"] = "△ 两人隔着柜台对峙。\n\n" + distinct_voice_draft()
            self.write_scene(root, payload)
            result = run_script(
                "self_review.py", "--project-root", str(root), "--focus", "dialogue", "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            codes = {item["code"] for item in data["findings"]["minor"]}
            self.assertNotIn("voice-similarity", codes)

    def test_dialogue_voice_clones_flagged(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            payload = scene_payload(1)
            payload["draft"] = "△ 两人同时开口。\n\n" + clone_voice_draft()
            self.write_scene(root, payload)
            result = run_script(
                "self_review.py", "--project-root", str(root), "--focus", "dialogue", "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            codes = {item["code"] for item in data["findings"]["minor"]}
            self.assertIn("voice-similarity", codes)
            messages = [
                item["message"]
                for item in data["findings"]["minor"]
                if item["code"] == "voice-similarity"
            ]
            self.assertTrue(any("丙" in message and "丁" in message for message in messages))

    def test_propose_style_pairs_generates_candidates_and_is_idempotent(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            payload = scene_payload(1)
            payload["draft"] = "△ 门开了。\n\n顾晴：这意味着你已经输了。\n"
            self.write_scene(root, payload)
            style_file = root / "style" / "screenplay-style.md"
            result = run_script(
                "propose_style_pairs.py", "--project-root", str(root)
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = style_file.read_text(encoding="utf-8")
            self.assertIn("候选改写对（待确认）", text)
            self.assertIn("原句：顾晴：这意味着你已经输了。", text)
            self.assertIn("命中的问题：", text)
            self.assertIn("改写：", text)
            rerun = run_script(
                "propose_style_pairs.py", "--project-root", str(root)
            )
            self.assertEqual(rerun.returncode, 0, rerun.stdout + rerun.stderr)
            self.assertIn("没有新的候选对", rerun.stdout)

    def test_sequence_review_flags_plateau_and_no_escalation(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            fill_structure_map(root)
            path = root / "outline" / "sequence-outline.md"
            header = (
                "| 序列 | 幕 | 故事价值 | 进入价值 | 序列任务 | 递进压力 | "
                "关键选择 | 序列转折 | 退出价值 | 下序列压力 |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            )
            rows = "\n".join(
                f"| {n} | 1 | 控制权 | 进{n} | 追查线索 |  |  | 转{n} | 退{n} | 下{n} |"
                for n in range(1, 4)
            )
            path.write_text(header + rows + "\n", encoding="utf-8", newline="\n")
            result = run_script(
                "self_review.py", "--project-root", str(root), "--focus", "structure", "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            codes = {item["code"] for item in data["findings"]["minor"]}
            self.assertIn("sequence-value-plateau", codes)
            self.assertIn("sequence-no-escalation", codes)

    def test_sequence_review_clean_table_not_flagged(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            fill_structure_map(root)
            path = root / "outline" / "sequence-outline.md"
            header = (
                "| 序列 | 幕 | 故事价值 | 进入价值 | 序列任务 | 递进压力 | "
                "关键选择 | 序列转折 | 退出价值 | 下序列压力 |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            )
            values = ("控制权", "信任", "生存")
            escalations = ("代价上升", "范围扩大", "不可逆")
            rows = "\n".join(
                f"| {n} | {n} | {values[n - 1]} | 进{n} | 任务{n} | {escalations[n - 1]} | "
                f"选择{n} | 转{n} | 退{n} | 下{n} |"
                for n in range(1, 4)
            )
            path.write_text(header + rows + "\n", encoding="utf-8", newline="\n")
            result = run_script(
                "self_review.py", "--project-root", str(root), "--focus", "structure", "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            codes = {item["code"] for item in data["findings"]["minor"]}
            self.assertNotIn("sequence-value-plateau", codes)
            self.assertNotIn("sequence-no-escalation", codes)
            self.assertNotIn("sequence-recap", codes)

    def test_sequence_review_flags_missing_middle_subplot(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            for number in range(1, 31):
                write_min_scene(root, number)
            ledger_path = root / "ledger" / "story-ledger.json"
            ledger = {
                "schema_version": 2,
                "format": "feature",
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
            }
            ledger_path.write_text(
                json.dumps(ledger, ensure_ascii=False),
                encoding="utf-8",
                newline="\n",
            )
            result = run_script(
                "self_review.py", "--project-root", str(root), "--focus", "structure", "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            codes = {item["code"] for item in data["findings"]["minor"]}
            self.assertIn("sequence-mid-missing-subplot", codes)

            ledger["relationship_changes"].append(
                {"scene_id": "S015", "from": "甲", "to": "乙", "value": "敌对"}
            )
            ledger_path.write_text(
                json.dumps(ledger, ensure_ascii=False),
                encoding="utf-8",
                newline="\n",
            )
            result2 = run_script(
                "self_review.py", "--project-root", str(root), "--focus", "structure", "--json"
            )
            data2 = json.loads(result2.stdout)
            codes2 = {item["code"] for item in data2["findings"]["minor"]}
            self.assertNotIn("sequence-mid-missing-subplot", codes2)

    def test_dilemma_field_roundtrip_and_advisory(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            fill_structure_map(root)
            payload = scene_payload(1)
            payload["dilemma_options"] = "交出记录保住自由，或销毁记录陷入追击"
            self.write_scene(root, payload)
            scene_text = (
                root / "screenplay" / "scenes" / "S001.md"
            ).read_text(encoding="utf-8")
            self.assertIn("两难选项：交出记录保住自由，或销毁记录陷入追击", scene_text)
            validate = run_script(
                "validate_project.py", "--project-root", str(root), "--strict"
            )
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
            review = run_script(
                "self_review.py", "--project-root", str(root), "--focus", "scene", "--json"
            )
            data = json.loads(review.stdout)
            codes = {item["code"] for item in data["findings"]["minor"]}
            self.assertNotIn("no-dilemma", codes)

            root2 = Path(temp) / "电影2"
            self.init_feature(root2)
            add_character(root2)
            self.write_scene(root2, scene_payload(1))
            review2 = run_script(
                "self_review.py", "--project-root", str(root2), "--focus", "scene", "--json"
            )
            data2 = json.loads(review2.stdout)
            codes2 = {item["code"] for item in data2["findings"]["minor"]}
            self.assertIn("no-dilemma", codes2)

    def test_audience_focus_json_and_compact(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            self.write_scene(root, scene_payload(1))
            report_path = root / "reviews" / "self-review.md"

            as_json = run_script(
                "self_review.py",
                "--project-root",
                str(root),
                "--focus",
                "audience",
                "--json",
            )
            self.assertEqual(as_json.returncode, 0, as_json.stdout + as_json.stderr)
            payload = json.loads(as_json.stdout)
            self.assertEqual(payload["focus"], "audience")
            self.assertIn("柜门打开。现在。", payload["blind_read"])
            self.assertIn("哪一场最无聊", payload["questionnaire"])
            self.assertFalse(report_path.exists())

            compact = run_script(
                "self_review.py",
                "--project-root",
                str(root),
                "--focus",
                "audience",
                "--compact",
            )
            self.assertEqual(compact.returncode, 0, compact.stdout + compact.stderr)
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("盲读正文", report)
            self.assertNotIn("编辑结论", report)

    def test_propose_style_pairs_dry_run_does_not_write(self) -> None:
        with workspace_temp() as temp:
            root = Path(temp) / "电影"
            self.init_feature(root)
            add_character(root)
            payload = scene_payload(1)
            payload["draft"] = "△ 门开了。\n\n顾晴：这意味着你已经输了。\n"
            self.write_scene(root, payload)
            style_file = root / "style" / "screenplay-style.md"
            before = style_file.read_text(encoding="utf-8")
            result = run_script(
                "propose_style_pairs.py", "--project-root", str(root), "--dry-run"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("原句：顾晴：这意味着你已经输了。", result.stdout)
            self.assertEqual(
                style_file.read_text(encoding="utf-8"), before
            )


if __name__ == "__main__":
    unittest.main()
