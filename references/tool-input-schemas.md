# 辅助脚本输入

所有 JSON 使用 UTF-8，字段名使用英文，创作内容使用项目语言。

## 电影 `write_scene.py`

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
  "display_characters": "顾晴、罗舟",
  "threads": ["main", "sister"],
  "source_files": [
    "bible/characters/gu-qing.md",
    "background/story-background.md",
    "bible/world/tide-rule.md",
    "outline/scene-outline.md"
  ],
  "source_character_facts": [
    "顾晴需要控制局面，拒绝承认自己害怕封闭空间。"
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
  "audience_entry": "观众知道顾晴拿到了仓库编号，不知道来源。",
  "scene_task": "顾晴要在通道关闭前拿到账本，同时隐藏幽闭恐惧。",
  "entry_state": "顾晴控制行动，罗舟被迫配合。",
  "turn": "罗舟锁上外门，承认潮水会提前回灌。",
  "audience_update": "罗舟比顾晴更了解仓库结构。",
  "exit_state": "顾晴必须依赖罗舟才能离开。",
  "draft": "△ 铁门在顾晴身后合拢。她没有回头，只把手电调到最亮。\n\n顾晴：二十分钟，拿东西，走人。",
  "continuity": [],
  "revision_notes": []
}
```

电影不使用 `episode`，输出 `S018.md`。

## 剧集 `write_scene.py`

与电影字段相同，但增加：

```json
{
  "episode": 6,
  "scene": 18
}
```

输出 `E006-S018.md`。

约束：

- `status`: `outline | draft | revision | final | locked`
- `scene`、`episode`、`act`、`sequence` 必须是整数；不接受小数或布尔值
- `time_of_day`: `日 | 夜 | 晨 | 昏 | 连续`
- `interior_exterior`: `内 | 外 | 内外`
- `characters`、`threads`、`source_files` 和各类依据字段必须是数组
- `source_files` 使用项目内相对路径，不接受项目外路径或符号链接逃逸
- 场号存在时拒绝覆盖
- `--dry-run` 完成全部校验并输出待写内容，但不创建文件

## `update_ledger.py`

电影使用 `S018`，剧集使用 `E006-S018`：

```json
{
  "scene_id": "S018",
  "summary": "顾晴进入退潮仓库，被迫把逃生控制权交给罗舟。",
  "state_changes": [],
  "knowledge_changes": [],
  "relationship_changes": [],
  "object_changes": [],
  "clue_changes": [],
  "thread_changes": [],
  "audience_evidence": [
    {
      "evidence": "罗舟准确说出回灌时间并锁门",
      "expected_inference": "罗舟熟悉仓库",
      "uncertainty": "他为何熟悉仍未知"
    }
  ],
  "open_questions": [],
  "uncertainties": []
}
```

除 `scene_id` 外字段可省略。摘要替换同场旧摘要；其他完全相同的记录不重复追加。

## `build_context.py`

电影：

```powershell
python build_context.py --project-root . --scene 18 `
  --profile scene `
  --query "顾晴 仓库 潮汐" `
  --source-file "bible/characters/gu-qing.md" `
  --source-file "bible/world/tide-rule.md" `
  --output context.md
```

剧集增加 `--episode`。上下文档位：

- `scene`：默认约 3200 tokens；目标场、前两场、显式来源、目标大纲和紧凑台账；
- `sequence`：默认约 5000 tokens；处理稿、序列/分集大纲和结构资料；
- `review`：默认约 8000 tokens；用于全稿检查。

`--max-tokens` 可覆盖默认预算，最小值为 500。单场默认不读取未来正文；改稿回归需要后一场时显式增加 `--include-next-scene`，且必须同时提供 `--scene`。

## `self_review.py`

```powershell
python self_review.py --project-root . --strict --compact `
  --output reviews/self-review.md
```

`--strict` 将电影场次缺少来源、人物卡缺失和场次卡关键字段缺失列为阻断问题，并以非零状态退出。`--compact` 省略量化表、来源追溯表和静态五遍审查模板；完整报告不加该参数。
