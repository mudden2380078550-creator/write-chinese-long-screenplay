# 中文长剧本创作 Skill v2

[English](README_EN.md)

![License](https://img.shields.io/github/license/mudden2380078550-creator/write-chinese-long-screenplay)
![Release](https://img.shields.io/github/v/release/mudden2380078550-creator/write-chinese-long-screenplay)
![Stars](https://img.shields.io/github/stars/mudden2380078550-creator/write-chinese-long-screenplay)

> **让 AI 写 100 场不崩。** 中文长剧本最难的不是文笔，而是 80 场之后的连续性与人物声音——本 Skill 把它变成一套可执行流程：只填两个输入板块，其余由 Skill 内部完成。

面向 **Codex、Claude Code、DeepSeek Harness (dsh)、zcode** 等主流 AI Agent 的中文电影与剧集长剧本写作 Skill。它遵循业界通用的 Agent Skills（`SKILL.md`）开放规范，同一份技能本体可直接被多家 Agent 加载与调用，无需为每家单独改写。

新版只要求两个创作输入：背景设定、人物设定（含人物小传）。其余故事骨架、场景因果、连续性和对白检查由 Skill 内部完成。

## 设计基础（基于什么做的）

本 Skill 建立在明确的组合之上，这也是它能跨 Agent 工作的原因：

- **技术基础**：采用 Agent Skills（`SKILL.md`）开放规范——`name`/`description` 驱动路由，`references/`、`scripts/`、`assets/` 提供结构化资源。Codex、Claude Code、dsh 等均原生支持该规范，因此技能本体不需要为各家 Agent 单独适配。内部脚本全部使用 **Python 标准库**，无第三方依赖，任何能运行 Python 3.10+ 的环境都能执行确定性校验。
- **剧作方法**：概念映射参考悉德·菲尔德（Syd Field）的电影剧本结构方法、罗伯特·麦基（Robert McKee）的故事与对白方法、布莱克·斯奈德（Blake Snyder）的电影编剧方法。这些理论被压缩为**内部诊断框架**，用户不需要先学习菲尔德、麦基或救猫咪的术语。
- **中文校准**：去 AI 味检查借用 [Humanizer-zh](https://github.com/op7418/Humanizer-zh) 公开的 24 类中文问题分类，改写为剧本场景检查清单；不引入其改写提示词、检测器、分数、声音模板或代码。

更精确的版权与方法来源见文末「版权与方法来源」。

## 支持哪些 Agent

| Agent | 技能目录 | 说明 |
| --- | --- | --- |
| Codex | `~/.codex/skills/write-chinese-long-screenplay/` | 原生支持 `SKILL.md` |
| Claude Code | `~/.claude/skills/write-chinese-long-screenplay/` | 原生支持 `SKILL.md` |
| DeepSeek Harness (dsh) | `~/.dsh/skills/write-chinese-long-screenplay/` | dsh 通过 skill-filesystem 插件扫描该目录，并把技能作为可调用工具注入模型目录 |
| zcode 及其余遵循 Agent Skills 规范的 Agent | 按各自文档中的 skills 目录放置 | 同一份 `SKILL.md` 直接可用 |

## 只保留两个创作板块

### 1. 背景设定

填写时代、地点、制度、历史余波、世界规则、资源、限制、代价、认知差异和不可改变的事实。每条设定都要能改变人物选择或产生可见后果。

文件：`background/story-background.md`

### 2. 人物设定

填写人物小传、欲望、需要、错误信念、保护策略、资源、限制、秘密、知识边界、关系交换、压力下的行为、语言习惯和最终选择。

文件：`bible/characters/*.md`

电影圣经、结构图、序列、场次卡、台账和审查报告仍会生成，但它们是内部工作资料，不是要求用户学习的第三、第四、第五个创作板块。

## 中文 AI 味与校准

当前版本把“去 AI 味”作为独立检查：只借用 [Humanizer-zh](https://github.com/op7418/Humanizer-zh) 公开的中文问题分类，并改写为剧本场景清单。它不引入对方的改写提示词、检测器、分数、声音模板或代码；自动脚本只提示高确定性模式，不把检测分数当作目标。

清单覆盖四组共 24 类问题：内容拔高与广告腔、AI 高频语言与假对称、格式装饰泄漏、协作元话语与空泛结论。剧本还会区分动作描写、对白和格式，避免把正常的重复、破折号、引号或“是”误判为问题。完整清单见 `references/natural-chinese.md`。

最有效的校准材料不是“自然一点”，而是用户自己的改写对照：

```text
原句：
不自然的原因：是太完整、太解释、太像谁，还是不符合人物关系？
改写：
希望保留的效果：
```

将 5–20 组这样的对照放进 `style/screenplay-style.md` 的“真实中文样本”区。它会校准当前项目的语气，但不会永久训练基础模型；永久改变模型需要另行制作数据集和微调。真实片段只用于学习句法、节奏和人物差异，不要提交有版权的整段文本。

## 内部写作内核

统一内核：

```text
主题命题 → 主角欲望 → 激励性扰动 → 递进复杂化
→ 不可回头点 → 危机选择 → 高潮行动 → 结局价值与余波
```

单场内核：

```text
来源 → 视点/目标 → 冲突/策略 → 预期结果 → 实际结果
→ 结果落差 → 转折 → 价值变化 → 下场压力
```

作者理论只作为内部诊断资料，不要求用户选择适配器、填写十五节拍或用百分比安排场次。核心判断始终是人物在背景限制下的选择、反制、代价和变化。

中文正文会额外执行局部去模板化审查，重点处理说明性对白、抽象心理、同声同气、过度工整和金句式收束；没有命中问题的句子不为追求变化而改写。详见 `references/natural-chinese.md`。

## 要求

- 支持 `SKILL.md` 的 Agent 环境（Codex / Claude Code / dsh / zcode 等）
- Python 3.10+
- Git（克隆安装时）

脚本只使用 Python 标准库。

## 安装

克隆仓库：

```bash
git clone https://github.com/mudden2380078550-creator/write-chinese-long-screenplay.git
```

把技能目录放入对应 Agent 的 skills 目录（Windows PowerShell 用 `Copy-Item -Recurse`，macOS/Linux 用 `cp -r`）：

| Agent | 命令示例（macOS / Linux） |
| --- | --- |
| Codex | `cp -r write-chinese-long-screenplay ~/.codex/skills/` |
| Claude Code | `cp -r write-chinese-long-screenplay ~/.claude/skills/` |
| dsh | `cp -r write-chinese-long-screenplay ~/.dsh/skills/` |
| zcode 等 | 按各自文档的 skills 目录放置 |

也可以直接克隆到目标目录，例如：

```powershell
git clone https://github.com/mudden2380078550-creator/write-chinese-long-screenplay.git `
  "$HOME\.codex\skills\write-chinese-long-screenplay"
```

DeepSeek Harness 用户也可以直接以 bundle 安装（`package.json` 声明了 `dsh.bundle`）：

```sh
dsh plugin add "github:mudden2380078550-creator/write-chinese-long-screenplay"
```

安装后新建任务；若 skill 未出现，请重启对应 Agent。dsh 会监听 skills 目录变化并自动更新技能目录。

## 初始化 v2 项目

```powershell
python "<skill-dir>\scripts\init_project.py" `
  --project-root "D:\screenplays\my-feature" `
  --title "片名" `
  --format feature
```

初始化后只需填写背景设定和人物设定；作者理论适配器属于兼容层，默认不启用。

项目契约：

```yaml
schema_version: 2
story_engine: causal-value
structure_adapters: []
```

## 迁移旧项目

先预览：

```powershell
python "<skill-dir>\scripts\migrate_project.py" `
  --project-root "<project-root>" `
  --report "<project-root>\reviews\v2-migration.md"
```

确认后应用：

```powershell
python "<skill-dir>\scripts\migrate_project.py" `
  --project-root "<project-root>" `
  --apply
```

应用前会把改写文件备份到项目 `backups/`，并把连续性台账升级到 schema v2。人物动机、故事价值、冲突和结果落差不会被自动猜测，未解决字段会保持严格校验阻断。

迁移退出码 `0` 表示应用后严格校验通过；`1` 表示报告已生成或迁移已应用，但仍有阻断项。

## 上下文与自审

上下文档位：

| 档位 | 默认预算 |
| --- | ---: |
| `scene-light` | 约 4,000 tokens |
| `scene` | 约 7,000 tokens |
| `scene-complex` | 约 12,000 tokens |
| `batch` | 约 16,000 tokens |
| `sequence` | 约 4,200 tokens |
| `dialogue-review` | 约 3,200 tokens |
| `structure-review` | 约 6,000 tokens |
| `full-review` | 约 8,000 tokens |

`review` 保留为 `full-review` 的兼容别名。

```powershell
python "<skill-dir>\scripts\build_context.py" `
  --project-root "<project-root>" `
  --scene 18 `
  --profile scene `
  --query "人物 地点 线索 规则" `
  --source-file "bible/characters/char-id.md" `
  --output "<临时目录>\scene-context.md"

python "<skill-dir>\scripts\build_context.py" `
  --project-root "<project-root>" `
  --scene-from 18 `
  --scene-to 23 `
  --profile batch `
  --query "本批人物 地点 线索 规则 序列目标" `
  --output "<临时目录>\S018-S023-batch-context.md"

python "<skill-dir>\scripts\self_review.py" `
  --project-root "<project-root>" `
  --focus dialogue `
  --strict `
  --output "<project-root>\reviews\dialogue-review.md"
```

`--focus` 可取 `scene`、`dialogue`、`structure`、`continuity`、`full`。

`scene-light` 用于过场和低设定负荷场；`scene` 是普通正文默认档；`scene-complex` 用于群戏、重大揭示和高潮。`batch` 只构建连续 1–8 场的共享上下文；每写完一场仍需更新台账，再为下一场生成局部上下文。每约30场先做严格校验，再按场景、对白、连续性和结构分层审查，不把全部正文无差别塞入一次模型上下文。

上下文输出默认拒绝覆盖已有文件；确认替换临时上下文时添加 `--force`。

## 校验、编译和测试

```powershell
python "<skill-dir>\scripts\validate_project.py" `
  --project-root "<project-root>" `
  --strict

python "<skill-dir>\scripts\compile_screenplay.py" `
  --project-root "<project-root>" `
  --output "<project-root>\exports\screenplay.md"

python -m unittest discover -s tests -v
```

编译器会再次执行严格校验；存在 schema、来源或必填场次问题时拒绝导出。

自动脚本只能判断确定性问题。人物动机、潜台词、情感效果和高潮质量仍须由模型或编辑结合正文审查。

## 版权与方法来源

本 Skill 的概念映射参考了悉德·菲尔德的电影剧本结构方法、罗伯特·麦基的故事与对白方法，以及布莱克·斯奈德的电影编剧方法；去 AI 味检查分类参考了 [Humanizer-zh](https://github.com/op7418/Humanizer-zh) 公开的中文问题清单。仓库只包含原创的术语矩阵、工作流、模板和校验代码，不包含书籍文件、长篇原文或可替代原书的章节摘要。

## 许可证

Copyright © 2026 kobayashikayoubi。

本项目采用 [GNU General Public License v3.0 only](LICENSE)。
