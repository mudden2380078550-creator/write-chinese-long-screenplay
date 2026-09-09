# Narrative Harness 0.4.0

面向中文小说与剧本的本地创作控制工具。AI负责理解与创作，本程序保存作品状态、构建上下文、检查候选并共同提交正文与状态。保留 `write-chinese-long-screenplay` 作为Codex Skill入口。

工具源码、安装副本和作品目录彼此独立。本项目不会自动调用模型、同步云端或发布作品。

## 使用

本次重构位于 [`refactor/harness`](https://github.com/mudden2380078550-creator/write-chinese-long-screenplay/tree/refactor/harness) 分支。旧版 `main` 与历史 Release 保留；下载新版请使用 [v0.4.0 Release](https://github.com/mudden2380078550-creator/write-chinese-long-screenplay/releases/tag/v0.4.0)，或明确克隆本分支：

```text
git clone --branch refactor/harness https://github.com/mudden2380078550-creator/write-chinese-long-screenplay.git narrative-harness
cd narrative-harness
```

需要Python 3.10+。源码直接运行，无第三方运行依赖：

```text
python scripts/harness.py project new --root ../my-book --title 我的小说 --format novel
python scripts/harness.py import stage --project ../my-book --source ../资料包.md
```

之后让AI读取归档资料并填写 `proposals/<source-id>.json` 中的实体、政策和章节大纲，再执行import apply。用户不必手填JSON；格式由宿主AI处理。程序只做可靠归档，不假装能独立理解自由文本。

安装为命令：

```text
python -m pip install .
harness --help
```

安装到Codex（destination使用你自己的Skill目录）：

```text
python scripts/install_skill.py --destination <skills目录>/write-chinese-long-screenplay --backup-root <备份目录>
```

安装器先验证独立启动器，再备份已有目录，复制修订后的兼容脚本、Skill及核心运行包。备份路径在输出JSON里。安装副本能移动到另一台有Python的设备，不引用本机源码路径。

**不要再把整个工具仓库直接复制到 skills 目录。** 请运行上面的安装器。安装后可以对AI说：“使用 write-chinese-long-screenplay，新建一本系统流小说，项目放在工具目录之外；这是资料包，请整理人物、技能、作者控制和大纲，列出仍需我确认的问题。” AI负责填提案，未解决的关键问题仍需审定，不能保证任意宿主都会正确执行。

升级前备份作品和旧Skill。v2作品使用 `project migrate --help` 查看复制迁移入口，审定迁移报告后再续写，不直接覆盖旧作品。内部开发版0.3.0的锁文件与0.4.0不同，保留原工具处理旧开发项目；不要手工修改版本锁绕过检查。

工具Git仓库只管理工具；每本作品单独建目录、单独选择私有仓库或其他同步方式。本项目没有自动同步功能，同一本作品不要在多个设备同时写入。

完整输入示例见 [工作流协议](integrations/write-chinese-long-screenplay/references/harness-workflow.md)。示范资料见 [examples/package.json](examples/package.json)。

## 主要命令

| 命令 | 用途 |
| --- | --- |
| project new/configure/doctor/recover | 创建、作者配置、完整性检查、恢复中断事务 |
| import stage/apply | 原资料归档、接受审定后的结构化资料 |
| unit prepare/submit/check/accept | 准备上下文、提交候选、检查、接受正文与状态 |
| unit revalidate | 按新政策核对既有章节，不重扣资源 |
| state show --before-unit | 查询某章写前状态 |
| revision impact/fork | 影响范围、从写前状态创建独立修订作品 |
| project migrate | 复制迁移旧v2项目，保留原始文件与历史未知标记 |
| export | 只导出已接受且无需重新审查的正文 |

每个命令可加--help。--budget以字符为单位，不冒充准确token数。业务输出为JSON；0成功，1待审/阻断，2参数/环境错误，3冲突，4需恢复。

## 作品格式与控制

- `project.json` 是项目清单，`harness.lock.json` 锁定工具/数据版本。
- `canon/entities/` 保存技能、资源、物品、人物等正式实体；`canon/policies/` 独立保存作者规则。
- `outline/` 保存独立章节任务书，`manuscript/` 保存已接受正文。
- `canon/history/` 保存初始状态、接受事件及对应候选和检查报告，可重放核对当前状态。
- `runs/` 保存本轮上下文、候选与报告，`sources/` 保留原件，`proposals/` 保存导入提案。
- `.harness/` 是本机锁和中断恢复日志，`exports/` 是可再生输出。

Skill不替代程序控制：未审候选、资源不足、过期修订、篡改的报告和未完成事务均不能按正常命令直接接受。普通候选不能修改作者政策。能力消耗由已声明的uses应用；物品是否消耗通过明确state_changes表达。

## 历史、迁移与边界

新稿可以查询历史写前状态。最新章可修订而不重复消耗；有后续已接受章节时采用revision fork，保留原作品。如果历史视图不能满足当前章纲/政策引用，fork明确拒绝，需先审定修订基础。

旧v2迁移保留原件字节并抽取正文。旧harness条目先列为未审定，不能将当前数据伪装成旧章节的写前状态。迁移属于有报告的转换，不是自动补全历史。

确定性验证由标准库中的显式字段与领域校验实现；交换协议Schema位于 `src/narrative_harness/schemas/`。不支持任意JSON Schema执行。语义检查由宿主AI或作者提供有依据的审查记录，程序并不能证明小说的全部语义和文学质量。

第一版支持本地单写者。Windows使用文件字节锁，POSIX使用flock；中断通过日志恢复。它不提供跨设备分布式锁，也不声称多文件replace天然原子。同步前确保doctor通过，同步后再次检查；本轮只在Windows实测，跨平台CI已配置但需仓库运行后才能声称通过。

## 开发与验证

```text
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s legacy/tests -v
```

测试覆盖真实CLI、独立安装、状态消耗、政策、上下文预算、历史修订、手改检测、锁、逐文件故障恢复和资料保真。测试中的正文是固定验证样本，不代表模型生成质量评估。

原剧本模板、方法与修订后的v2脚本在 `legacy/`，v2与v3入口不可混用。原dsh的根目录插件布局不再是本版本入口，未验证的宿主不能视为即装即用。版本变化见 [CHANGELOG.md](CHANGELOG.md)。项目延续 GPL-3.0-only，完整文本见 [LICENSE](LICENSE)，来源及修改记录见 [NOTICE.md](NOTICE.md)。英文概览见 [README_EN.md](README_EN.md)。
