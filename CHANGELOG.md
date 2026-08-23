# Changelog

本项目采用[语义化版本](https://semver.org/lang/zh-CN/)。

## [v0.3.0] - 2026-08-23

### 新增

- 将 Skill 升级为中文长篇写作总路由，支持小说模式与剧本模式。
- 新增作者决策门禁：探索、待确认、唯一正史和废案四种状态。
- 新增 `references/novel-mode.md` 与 `assets/novel-project-template/`。
- 新增 `scripts/validate_novel_project.py`，检查小说项目结构、决策状态和正史中的未决方案残留。
- `scripts/init_project.py` 新增 `--mode novel`。

### 兼容性

- 默认模式仍为 `screenplay`，既有电影、剧集、短剧和动画项目初始化参数保持兼容。
- 原有剧本场次写入、严格校验、自然中文审查和编译流程保持不变。
