# v2 辅助脚本输入

## 目录

- [`write_scene.py`](#write_scenepy)
- [`update_ledger.py`](#update_ledgerpy)
- [`build_context.py`](#build_contextpy)
- [`create_project_from_package.py`](#create_project_from_packagepy)
- [`self_review.py`](#self_reviewpy)
- [`validate_harness.py`](#validate_harnesspy)
- [`update_harness_state.py`](#update_harness_statepy)

所有 JSON 使用 UTF-8，字段名使用英文，创作内容使用项目语言。

## `write_scene.py`

电影示例：

```json
{
  "scene": 18,
  "act": 2,
  "sequence": 4,
  "title": "退潮仓库",
  "status": "draft",
  "location": "旧港七号仓库",
  "time_of_day": "夜",
  "interior_exterior": "内",
  "story_time": "失踪后第三天 02:10",
  "characters": ["char-gu-qing", "char-luo-zhou"],
  "viewpoint_character": "char-gu-qing",
  "display_characters": "顾晴、罗舟",
  "threads": ["main", "sister"],
  "source_files": [
    "bible/characters/gu-qing.md",
    "background/story-background.md",
    "bible/world/tide-rule.md",
    "outline/scene-outline.md"
  ],
  "source_character_facts": [
    "顾晴试图控制局面，不愿承认自己害怕封闭空间。"
  ],
  "source_background_facts": [
    "十年前的码头事故仍被港务公司压下。"
  ],
  "source_world_rules": [
    "退潮后的检修通道只开放二十分钟。"
  ],
  "forbidden_contradictions": [
    "顾晴此时还不知道罗舟参与过旧事故。"
  ],
  "scene_objective": "顾晴要在通道关闭前拿到账本。",
  "story_value": "控制权",
  "entry_value": "顾晴控制行动，罗舟被迫配合。",
  "primary_conflict": "罗舟掌握潮汐风险，却拒绝交出路线控制。",
  "tactic": "顾晴用证据和时间压力逼罗舟服从。",
  "expected_result": "罗舟交出路线，顾晴独自完成取证。",
  "actual_result": "罗舟锁门并证明潮水会提前回灌。",
  "result_gap": "顾晴的威胁反而让唯一知路的人掌握逃生权。",
  "turn": "罗舟锁上外门，准确说出提前回灌时间。",
  "audience_entry": "观众知道顾晴拿到仓库编号，不知道来源。",
  "audience_update": "罗舟比顾晴更了解仓库结构。",
  "exit_value": "顾晴必须依赖罗舟才能离开。",
  "next_pressure": "两人必须在互不信任中共用唯一逃生路线。",
  "dialogue_subtext": "顾晴要求合作，实际在掩饰失去控制的恐惧。",
  "character_voice": "顾晴用短句和程序性词汇压缩情绪；罗舟以具体时间反制。",
  "draft": "△ 铁门在顾晴身后合拢。她没有回头，只把手电调到最亮。\n\n顾晴：二十分钟，拿东西，走人。",
  "continuity": [],
  "revision_notes": []
}
```

剧集增加 `episode`，不使用 `act`、`sequence` 也可。所有载体共享 v2 场景内核。

约束：

- `viewpoint_character` 必须在 `characters` 中；
- `source_files` 和 `source_character_facts` 不得为空；
- `entry_value` 与 `exit_value` 不得相同；
- `expected_result` 与 `actual_result` 不得相同；
- 所有 v2 场景文本字段不得为空或含 `【待补】`；
- `source_files` 只能引用项目内现存文件；
- 场次已存在时拒绝覆盖。

## `update_ledger.py`

```json
{
  "scene_id": "S018",
  "summary": "顾晴被迫把逃生控制权交给罗舟。",
  "state_changes": [],
  "knowledge_changes": [],
  "relationship_changes": [],
  "object_changes": [],
  "clue_changes": [],
  "thread_changes": [],
  "value_changes": [
    {
      "value": "控制权",
      "from": "顾晴控制",
      "to": "顾晴依赖罗舟"
    }
  ],
  "decision_changes": [],
  "audience_evidence": [],
  "open_questions": [],
  "uncertainties": []
}
```

## `build_context.py`

```powershell
python build_context.py --project-root . --scene 18 `
  --profile scene `
  --query "顾晴 仓库 潮汐" `
  --source-file "bible/characters/gu-qing.md" `
  --output context.md
```

正文档位为 `scene-light`（约 4,000）、`scene`（约 7,000）、`scene-complex`（约 12,000）和 `batch`（约 16,000 tokens）。`batch` 必须同时传入 `--scene-from` 与 `--scene-to`，范围须递增且最多连续 8 场：

```powershell
python build_context.py --project-root . `
  --scene-from 18 --scene-to 23 --profile batch `
  --query "顾晴 罗舟 仓库 潮汐 序列目标" `
  --output batch-context.md
```

其他档位为 `sequence`、`dialogue-review`、`structure-review`、`full-review`；`review` 是 `full-review` 的兼容别名。`--max-tokens` 可覆盖档位预算，最小为 500。输出文件已存在时拒绝覆盖；确认替换临时上下文时显式添加 `--force`。

Harness 控制台会占用独立预算，并优先保留禁用、废弃、锁定和查询命中的条目。

## `create_project_from_package.py`

```powershell
python create_project_from_package.py `
  --package "D:\资料包\my-novel.md" `
  --project-root "D:\novels\my-novel" `
  --title "书名" `
  --format series
```

资料包必须是 Markdown。一级标题用于路由：`背景设定` 写入 `background/story-background.md`；`人物设定` 按二级标题写入 `bible/characters/*.md`；`技能`、`道具`、`任务`、`世界规则`、`阵营`、`时间线`、`连续性`、`作者指令` 会转入对应 `harness/*.json`。Harness 区每条使用项目符号：

```text
- 影步：status=deprecated；author_note=废弃这个技能，不要再让它解决关键冲突；allow_use=false；allow_mention=true；aliases=暗影步,Shadow Step
```

该脚本只做首轮归档，不解决互相矛盾或含糊的正典事实。

## `self_review.py`

```powershell
python self_review.py --project-root . --focus dialogue --strict `
  --adapter mckee --output reviews/dialogue-review.md
```

`--focus` 可取 `scene | dialogue | structure | continuity | full`。`--adapter` 可重复；省略时读取项目 `structure_adapters`。

## `validate_harness.py`

```powershell
python validate_harness.py --project-root . `
  --target-file "screenplay/scenes/E001-S002.md"
```

该脚本读取 `harness/*.json`，检查正文是否使用 `status` 为 `deprecated`、`disabled`、`forbidden`、`retired`、`locked`，或 `generation_policy.allow_use` 为 `false` 的条目。它会检查 `name`、`id`、`aliases` 和 `generation_policy.forbidden_usage_patterns`。`allow_mention: true` 时，单纯说明“该项已废弃/禁用”不会被当作违规；实际发动、装备、依靠或用它破局会被拦截。命中时返回 1，并输出条目 `id`、状态、匹配原因和作者注释。

## `update_harness_state.py`

```json
{
  "updates": [
    {
      "file": "abilities.json",
      "id": "ability-shadow-step",
      "mode": "patch",
      "patch": {
        "status": "deprecated",
        "author_note": "废弃这个技能，不要再让它解决关键冲突。",
        "generation_policy": {
          "allow_use": false,
          "allow_mention": true
        }
      }
    },
    {
      "file": "inventory.json",
      "id": "item-black-key",
      "mode": "upsert",
      "item": {
        "id": "item-black-key",
        "name": "黑钥匙",
        "status": "active",
        "author_note": "只能开启第七层门，不能泛化成万能钥匙。",
        "generation_policy": {
          "allow_use": true
        }
      }
    }
  ]
}
```

允许更新的文件为 `harness/author-directives.json`、`protagonist.json`、`abilities.json`、`inventory.json`、`quests.json`、`progression.json`、`world-rules.json`、`factions.json`、`timeline.json` 和 `continuity-ledger.json`。输入 JSON 可以在项目外的临时目录；脚本只允许写入项目内 harness 文件。`patch` 只修改已有条目；`upsert` 可新增或合并条目。先用 `--dry-run` 预览，再写入。
