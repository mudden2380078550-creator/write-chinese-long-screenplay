# 中文长剧本创作 Skill

[English](README_EN.md)

面向 Codex 的中文电影与剧集长剧本写作 Skill。它把人物小传、故事背景、世界观、主题和情节设定组织成可持续迭代的 Markdown 剧本工程，并辅助完成正文生成、连续性维护、自我审查、结构校验和编译。

## 主要能力

- **电影剧本路径**：从人物、背景和世界规则开始，逐步生成梗概、处理稿、序列大纲、逐场大纲和场次正文。
- **多种长剧本格式**：支持电影、常规剧集、短剧和动画项目。
- **人物驱动写作**：将设定转化为当前压力、人物策略、可见行动、对白行为和视听后果。
- **来源追溯**：每场记录真正依赖的人物、背景、世界和大纲文件，降低无来源设定混入正文的风险。
- **连续性台账**：分别维护人物知识、关系、物件、线索、观众证据和未决问题。
- **受限上下文**：按单场、序列或审查任务构建紧凑上下文，减少长项目中的 token 消耗。
- **双层自审**：脚本检查高确定性结构问题，模型或编辑完成因果、人物、观众盲读、电影性和节奏审查。
- **安全写入**：默认拒绝覆盖已存在场次，并支持 `--dry-run` 预览。
- **校验与编译**：检查工程结构、场次编号和引用，再按顺序编译完整 Markdown 剧本。

## 能力边界

本项目不是独立的大语言模型，也不是“一键生成成片”的应用。实际文本质量仍取决于所用模型、输入材料和人工判断。

自动脚本主要处理结构、编号、路径、缺失字段和可确定的连续性问题，不能代替对人物弧光、潜台词、情感真实性或艺术表达的语义判断。目前不直接导出 Final Draft、PDF 或制片排版格式。

## 支持的项目类型

| `format` | 用途 | 场次编号 |
| --- | --- | --- |
| `feature` | 电影 | `S001.md` |
| `series` | 常规剧集 | `E001-S001.md` |
| `short-drama` | 短剧 | `E001-S001.md` |
| `animation` | 动画剧集 | `E001-S001.md` |

## 环境要求

- 支持 `SKILL.md` 的 Codex 环境
- Python 3.10 或更高版本
- Git（使用克隆安装时）

运行脚本只使用 Python 标准库，不需要安装额外 Python 依赖。

## 安装

### Windows PowerShell

```powershell
git clone https://github.com/mudden2380078550-creator/write-chinese-long-screenplay.git `
  "$HOME\.codex\skills\write-chinese-long-screenplay"
```

### macOS / Linux

```bash
git clone https://github.com/mudden2380078550-creator/write-chinese-long-screenplay.git \
  "$HOME/.codex/skills/write-chinese-long-screenplay"
```

安装后新建一个 Codex 任务。如果 Skill 没有出现在可用列表中，请重新启动 Codex。

## 快速开始

可以直接向 Codex 提出：

```text
使用 $write-chinese-long-screenplay，根据这些人物小传、故事背景和世界观，
创建一部 100 分钟悬疑电影的梗概、序列大纲和前三场正文，并执行自我审查。
```

也可以先初始化一个空白电影工程：

```powershell
python "$HOME\.codex\skills\write-chinese-long-screenplay\scripts\init_project.py" `
  --project-root "D:\screenplays\my-feature" `
  --title "片名" `
  --format feature
```

初始化拒绝覆盖非空目录。

## 推荐工作流

1. 建立人物小传、故事背景和世界规则。
2. 明确主题、核心冲突、结局方向和不可改动项。
3. 完成梗概与处理稿。
4. 拆分幕、序列、分集和逐场大纲。
5. 为目标场次构建受限上下文。
6. 生成并审阅场次正文。
7. 更新连续性台账。
8. 运行自审、结构校验和编译。
9. 从根因场开始修改，并回归检查受影响场次。

人物在正文中只能使用当时已经获得的信息。作者真相、人物认知和观众证据应分开维护。

## 常用命令

以下示例用 `<skill-dir>` 表示本仓库或安装目录，用 `<project-root>` 表示剧本工程目录。

### 构建单场上下文

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

默认预算约为：

- `scene`：3,200 tokens
- `sequence`：5,000 tokens
- `review`：8,000 tokens

可用 `--max-tokens` 覆盖预算。新写场景默认不读取未来正文。

### 自我审查

```powershell
python "<skill-dir>\scripts\self_review.py" `
  --project-root "<project-root>" `
  --strict `
  --compact `
  --output "<project-root>\reviews\self-review.md"
```

`--compact` 会省略重复的静态审查模板，以降低输出和 token 消耗。

### 校验与编译

```powershell
python "<skill-dir>\scripts\validate_project.py" `
  --project-root "<project-root>" `
  --strict

python "<skill-dir>\scripts\compile_screenplay.py" `
  --project-root "<project-root>" `
  --output "<project-root>\exports\screenplay.md"
```

## 仓库结构

```text
write-chinese-long-screenplay/
├── SKILL.md                 # Skill 的核心路由与工作流
├── agents/openai.yaml       # Codex 界面元数据
├── assets/                  # 电影与剧集工程模板
├── references/              # 按需加载的写作与审查规范
└── scripts/                 # 初始化、上下文、写入、台账、自审和编译工具
```

`SKILL.md` 只保留核心流程，详细规则放在 `references/` 中按任务加载。不要在一次写作任务中读取全部参考文件。

## 降低 token 消耗

- 单场写作使用 `scene` 上下文档位。
- 只传入本场确实依赖的 `--source-file`。
- 使用具体的 `--query` 筛选人物、地点、线索和规则。
- 新写正文时不要启用 `--include-next-scene`。
- 常规审查使用 `--compact`，需要完整工作表时再关闭。
- 先运行确定性脚本，再让模型处理真正需要语义判断的问题。

## 许可证

Copyright © 2026 kobayashikayoubi。

本项目采用 [GNU General Public License v3.0 only](LICENSE) 授权。你可以使用、修改和再发布本项目，但发布修改版或衍生作品时必须按照 GPL-3.0 的要求提供相应源代码、保留许可证和版权声明，并以兼容的 GPL 条款授权。
