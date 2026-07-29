# 项目模型与正典层级

## 电影项目

```text
AGENTS.md
project.md
background/
  story-background.md         前史、社会背景和当前余波
bible/
  feature-bible.md            主题、人物网络、世界和终局约束
  characters/                 人物小传
  world/                      地点、机构和世界规则
outline/
  synopsis.md                 故事梗概
  treatment.md                故事处理稿
  sequence-outline.md         幕/序列结构
  scene-outline.md            逐场大纲
screenplay/scenes/            正文正典，S001.md
ledger/story-ledger.json
ledger/revision-log.md
style/screenplay-style.md
reviews/                      可再生自审报告
exports/                      可再生编译稿
```

## 剧集项目

```text
bible/series-bible.md
outline/master-outline.md
outline/episodes/
screenplay/scenes/            正文正典，E001-S001.md
```

其余公共目录与电影相同。

## 权威与状态

冲突时使用：

1. 用户当前明确指令；
2. `locked` 或 `final` 场次；
3. 最新确认场次正文；
4. 有正文证据的台账；
5. 人物、背景和世界设定；
6. 处理稿、逐场/分集大纲；
7. 灵感与候选方案。

大纲是计划，不是已经发生的事实。人物卡中的秘密不等于人物或观众知道。

## 电影场次

路径：

```text
screenplay/scenes/S001.md
```

frontmatter：

```yaml
---
id: S001
type: scene
scene: 1
act: 1
sequence: 1
title: "工作标题"
status: draft
location: "地点"
time_of_day: "日"
interior_exterior: "内"
story_time: ""
characters:
  - char-name
threads:
  - main
source_files:
  - bible/characters/char-name.md
  - background/story-background.md
created: 2026-01-01
updated: 2026-01-01
---
```

场景标头：

```text
场景标头：1 医院走廊 日 内
```

## 剧集场次

路径为 `screenplay/scenes/E001-S001.md`，frontmatter 增加 `episode: 1`，场景标头为：

```text
场景标头：1-1 医院走廊 日 内
```

## 场次正文容器

H2 必须依次且各出现一次：

1. `## 场次卡`
2. `## 正文`
3. `## 连续性`
4. `## 改稿备注`

场次卡至少记录：

- 结构位置；
- 来源依据；
- 人物依据；
- 背景依据；
- 世界规则；
- 场次任务；
- 观众入口；
- 入场状态；
- 场面转折；
- 观众更新；
- 出场状态；
- 禁止矛盾。

## 稳定标识

- 人物、地点、规则、线索、道具和线程使用稳定 ASCII ID。
- 中文显示名可以改，ID 不随之改变。
- 电影场次使用三位补零 `S001`；剧集使用 `E001-S001`。
- 拍摄稿锁号后，删除场号不自动复用；插入号由项目规则决定。

## 来源追溯

- `source_files` 必须是项目相对路径。
- 电影场次至少引用一个人物、背景、世界观或大纲来源。
- 引用只证明本场依赖该来源，不代表正文必须复述它。
- 自审时必须验证路径存在，并检查正文是否违背其硬约束。

## 正典与输出

- 只有正文已发生或用户已锁定的内容进入事实台账。
- 不确定项进入 `uncertainties`。
- `reviews/` 与 `exports/` 可删除再生成。
- 修改必须回到来源或 `screenplay/scenes/`，不手工修补编译稿。
