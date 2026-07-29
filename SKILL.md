---
name: write-chinese-long-screenplay
description: 规划、创作、续写、改写和自审中文电影及剧集剧本。用于从人物小传、故事背景、世界观、主题和情节设定生成可拍摄正文，维护结构、连续性与来源追溯，并执行校验、编译和改稿。
---

# 中文长剧本写作

将人物、背景和世界规则转成当前压力、人物选择与可见后果。保持项目正典稳定，用受限上下文写作，不把设定复制成说明性对白。

## 核心规则

- 先读项目 `AGENTS.md`、`project.md` 和目标载体资料。
- 用户当前指令优先；正文事实高于大纲计划。详细层级见 [project-model.md](references/project-model.md)。
- 人物只能使用当时已经获得的信息；作者真相、人物认知和观众证据必须分开。
- 动作写可见可听结果；对白必须对另一人物实施行动。
- 新增事实要有来源；不确定内容进入候选或 `uncertainties`，不得静默成为正典。
- 不覆盖既有场次。改稿先列根因场、影响范围和锁定项。
- 自动脚本只查高确定性问题；语义自审仍须由模型或编辑完成。

## 选择路径

读取 `project.md` 的 `format`：

- `feature`：电影，场次 `S001.md`。读取 [feature-film-workflow.md](references/feature-film-workflow.md)。
- `series`、`short-drama`、`animation`：剧集，场次 `E001-S001.md`。读取 [long-form-architecture.md](references/long-form-architecture.md)。

只在需要时加载：

- 来源转戏：[source-to-screenplay.md](references/source-to-screenplay.md)
- 格式：[chinese-screenplay-format.md](references/chinese-screenplay-format.md)
- 场景、对白、表演：[scene-dialogue-performance.md](references/scene-dialogue-performance.md)
- 台账与改稿：[continuity-revision.md](references/continuity-revision.md)
- 自审：[self-review.md](references/self-review.md)
- 当前类型：[genre-engines.md](references/genre-engines.md) 中对应部分
- 脚本 JSON：[tool-input-schemas.md](references/tool-input-schemas.md)

不要一次读取全部 references。

## 初始化

仅在用户要求新建项目时运行：

```powershell
python "<skill-dir>\scripts\init_project.py" `
  --project-root "<project-root>" `
  --title "<片名>" `
  --format feature
```

剧集将 `feature` 换成 `series`、`short-drama` 或 `animation`。初始化拒绝覆盖非空目录。

## 电影正文工作流

若用户已有材料，从现有成熟阶段开始；否则依次建立：

1. 人物小传、故事背景、世界规则；
2. 梗概与处理稿；
3. 幕/序列结构；
4. 逐场大纲；
5. 场次正文；
6. 台账、自审、改稿和编译。

写场前，把相关来源事实转换为：

`来源事实 → 当前压力 → 人物策略 → 视听证据 → 观众推断 → 禁止矛盾`

一场至少明确：即时目标、阻碍、换招、转折、观众更新和退出状态。资料不足以决定身份、动机、规则或结局时，停在大纲或列出假设，不伪造正文。

## 构建受限上下文

单场正文默认约 3,200 tokens：

```powershell
python "<skill-dir>\scripts\build_context.py" `
  --project-root "<project-root>" `
  --scene 18 `
  --profile scene `
  --query "人物、地点、线索或规则" `
  --source-file "bible/characters/char-id.md" `
  --source-file "background/story-background.md" `
  --output "<临时目录>\scene-context.md"
```

档位：

- `scene`：显式来源、目标大纲、目标/前两场、紧凑台账；默认不读未来场。
- `sequence`：约 5,000 tokens，用于处理稿、序列或分集规划。
- `review`：约 8,000 tokens，用于全稿审查。

`--max-tokens` 可覆盖档位预算。仅在改稿回归需要验证后一场时使用 `--include-next-scene`。剧集项目增加 `--episode N`。

## 写入场次

场次必须包含以下 H2，且各出现一次：

1. `## 场次卡`
2. `## 正文`
3. `## 连续性`
4. `## 改稿备注`

电影 frontmatter 使用 `S001`，剧集使用 `E001-S001`。`source_files` 记录本场真正依赖的人物、背景、世界和大纲文件；正文使用 `△` 动作段和 `人物名：对白`。

先把场次数据写入临时 JSON，再执行：

```powershell
python "<skill-dir>\scripts\write_scene.py" `
  --project-root "<project-root>" `
  --input "<临时目录>\scene.json" `
  --dry-run
```

核实后去掉 `--dry-run`。脚本拒绝覆盖已存在场次。

## 台账

只记录正文已发生或用户已锁定的状态变化：

```powershell
python "<skill-dir>\scripts\update_ledger.py" `
  --project-root "<project-root>" `
  --input "<临时目录>\scene-state.json" `
  --dry-run
```

核实后去掉 `--dry-run`。人物知识、关系、物件、线索和观众证据分开记录。

## 自审与完成门禁

每个序列、重要转折、单集或完整初稿运行：

```powershell
python "<skill-dir>\scripts\self_review.py" `
  --project-root "<project-root>" `
  --strict `
  --compact `
  --output "<project-root>\reviews\self-review.md"
```

`--compact` 省略重复的静态审查模板；需要完整工作表时去掉。然后按 [self-review.md](references/self-review.md) 完成来源忠实度、因果与人物、观众盲读、电影性与可表演性、结构与节奏五遍语义审查。

结构校验与编译：

```powershell
python "<skill-dir>\scripts\validate_project.py" `
  --project-root "<project-root>" `
  --strict

python "<skill-dir>\scripts\compile_screenplay.py" `
  --project-root "<project-root>" `
  --output "<project-root>\exports\screenplay.md"
```

完成前必须满足：

- `blocking` 为零，`major` 已修复或由用户明确接受；
- 人物行动符合其欲望、知识、关系和压力；
- 关键观众推断有正文视听证据；
- 入场与出场状态实质不同；
- 高潮使用已建立机制并由人物选择完成；
- 正文、台账、自审报告和编译稿同步。
