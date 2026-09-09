# 中文长篇创作 Harness Skill

本安装目录包含v3创作入口与v2剧本兼容脚本。

使用方法：在Codex中调用 `write-chinese-long-screenplay`，给出作品目录与创作要求。可以直接说“新建系统文项目，并整理这份资料包”。AI负责整理输入、写稿和语义审查，程序保存外部状态并验证提交。

命令入口：`python scripts/harness.py --help`。需要Python 3.10+，无需第三方运行库。运行代码在 `scripts/_vendor/narrative_harness/`；移动此Skill时应整体复制，不依赖原电脑源码路径。

详见 [SKILL.md](SKILL.md) 和 [工作流协议](references/harness-workflow.md)。

每本作品保存在独立目录，背景、人物、能力、道具、政策和章纲都必须进入实际上下文。v3项目通过prepare/submit/check/accept流程接受正文与状态；旧project.md项目继续使用兼容脚本或显式迁移。

语义审查仍由AI/作者负责，词法检查不能证明全部小说语义。跨设备一次只在一个设备接受正式状态，同步后执行project doctor。迁移前的历史未知就保持未知，不自动猜测。
