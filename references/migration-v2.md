# v1 → v2 迁移

## 原则

- 默认只检查并生成报告。
- `--apply` 才修改项目。
- 应用前把所有将改写的文件复制到 `backups/v1-to-v2-<时间>/`。
- 只自动处理确定映射；不得自动编造人物动机、故事价值、冲突或结果落差。
- 未补完的创作字段使用 `【待补】`，严格校验将其视为阻断项。

## 命令

```powershell
python "<skill-dir>\scripts\migrate_project.py" `
  --project-root "<project-root>" `
  --report "<project-root>\reviews\v2-migration.md"
```

确认报告后：

```powershell
python "<skill-dir>\scripts\migrate_project.py" `
  --project-root "<project-root>" `
  --apply
```

退出码含义：

- `0`：应用后的项目已经通过严格校验；
- `1`：报告已生成或确定性迁移已应用，但仍有创作/结构阻断；
- `2`：输入、路径或文件解析错误。

## 自动处理

- 在 `project.md` 加入 `schema_version: 2`、`story_engine: causal-value`、`structure_adapters: []`。
- 补建或升级连续性台账，并补齐全部 v2 数组字段。
- 把旧“场次任务”确定映射为“场景目标”。
- 为场次卡插入 v2 必需标签；无法推导的内容标为 `【待补】`。
- 升级已知 v1 电影圣经、序列表、逐场表和场次模板。
- 为电影项目补入统一结构图模板，但不填写结构判断。

## 必须人工或模型补写

- 视点人物是否与场景目标一致；
- 故事价值及其入场/出场状态；
- 主冲突和人物策略；
- 预期结果、实际结果和结果落差；
- 转折的因果来源；
- 本场对下一场造成的压力；
- 对白潜台词和人物专属语言。

补写后依次运行严格校验、分层自审和编译。不要仅删除 `【待补】`；必须用项目证据替换。
