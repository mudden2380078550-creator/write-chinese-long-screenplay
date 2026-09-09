---
name: write-chinese-long-screenplay
description: Use when creating, continuing, revising, or reviewing Chinese novels and screenplays that need persistent outlines, character state, abilities, inventory, continuity, or author controls, including projects started from a source package.
---

# 中文长篇创作 Harness

用本 Skill 处理创作意图，用附带 harness 程序保存和提交作品状态。工具与每本作品各自独立，聊天历史不作为正典存储。

入口为本 Skill 目录下的 `scripts/harness.py`，使用当前环境可用的 Python 3.10+ 执行。运行 `python <skill-dir>/scripts/harness.py --help` 查看命令。不要依赖上一次会话的 Python 绝对路径。

## 项目识别

- 有 `project.json`：执行 `project doctor --project <作品目录>`，按 v3 流程工作。
- 只有 `project.md`：这是旧剧本工程。旧脚本仍可用；迁移时执行 `project migrate --source <旧目录> --root <新目录>`。迁移复制原件，不猜历史状态；查看迁移报告的 unresolved。
- 新项目：用户说“新建某项目并给资料包”即授权初始化、整理明确资料和提出创作建议。运行 `project new --root <作品目录> --title <书名> --format novel`；剧本按实际载体选择 format。作品不要放到 Skill 或工具源码里。

## 资料包与自动填入

先读 [工作流与协议](references/harness-workflow.md)。执行 `import stage --project <目录> --source <资料包>` 后读取原件及提案。

由你将用户明确设定整理为 entities、policies、units，写入 `proposals/<source-id>.json`。人物小传、背景、大纲长文保留在来源中，并通过 entity.description、provenance 及 unit.outline 带入本章；不要只归档却遗漏写作必需内容。未知段落完整保留；冲突、推断及原创建议不冒充作者已定事实。

用户已经授权整理的明确事实，可执行 `import apply`。只就影响作品方向的冲突或缺失选择询问作者，不要求作者手写 JSON。不要把缺少能力限制解释成无限制能力。

## 写作与接受

1. 章纲、人物、资源或作者政策调整，通过 `project configure --input <配置JSON>`；这是作者配置入口，普通剧情自动回写走候选提案。
2. 写正文前执行 `unit prepare --unit <章节ID>`，实际读取返回的 context 文件。它含章纲、写前状态、政策和接场末段。预算不足须调整任务或预算。
3. 写候选正文与 uses、state_changes、new_facts，再执行 `unit submit --run <ID> --input <候选JSON>`。uses 逐项提供正文原文证据；已声明技能使用会自动扣已配置的资源成本，不要重复扣减。
4. 执行 `unit check`。结合上下文和正文做语义审查：真实使用与回忆/否定是否区分，人物是否知道该信息，数值和时间是否合理，作者禁令是否被绕过，新事实是否获授权。审查依据写入 review JSON，再用 `unit check --review <JSON>`；不能仅为了通过程序填 pass。
5. 作者已授权写入正式章节且审查通过，执行 `unit accept`。若只要求试写/看候选，停在候选阶段。正式正文和状态由该命令一起提交。
6. 下一章重新 prepare。换会话后从 project doctor、state show、章纲及未完成 runs 恢复工作。

小说允许心理活动、引号对白和不同叙述视角；不要套用电影可拍摄性规则。剧本方法按需要阅读原有 `references/core-story-engine.md`、`references/scene-dialogue-performance.md`；中文局部审查可参考 `references/natural-chinese.md`，不要机械删除正常词汇。

## 改稿与控制

作者说“废弃影步”时保存独立 policy，保留角色获得过它的事实。用 scope 指明生效章节；allow_use=false 禁止发动，allow_mention 控制提及。

最新章节用 `unit prepare --revision`；已有后续章节的历史变化先 `revision impact`，再用 `revision fork --project <原作品> --root <修订目录> --unit <起始章ID>` 建立修订副本。只重新核对既有章节可用 `unit revalidate --unit <ID> --review <JSON>`，不重复扣资源。历史未知或配置冲突按程序报告处理，不能用当前状态补造过去。

不要直接编辑 canon、manuscript 或 project.json 绕过校验。WORKSPACE_CHANGED 表示正式文件被外部改动；RECOVERY_REQUIRED 先运行 project recover；REVISION_CONFLICT 重新读取项目并准备候选。Skill是流程入口，程序校验只覆盖已实现的确定性规则；语义和文学审查仍由作者/宿主负责。
