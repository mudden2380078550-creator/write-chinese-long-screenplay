# Harness v3 输入与使用

以下均通过 `python <skill-dir>/scripts/harness.py` 调用；已安装Python包时也可用 `harness`。核心只使用Python标准库，不自动调用外部模型或产生API账单。

## 配置与资料提案

`project configure --project <root> --input <json>` 接受完整实体替换、政策替换和完整章节列表。省略的集合不变；相同id为更新，普通字段拼写错误报错。必须保留已有章节顺序；章节只能追加或修改大纲。

```json
{
  "entities": [
    {"id": "hero", "type": "character", "name": "林澈", "description": "寻找姐姐，惧怕失去同伴。"},
    {"id": "spirit", "type": "resource", "name": "灵力", "owner_id": "hero", "quantity": 50},
    {"id": "step", "type": "ability", "name": "影步", "aliases": ["暗影步"], "owner_id": "hero", "mechanics": {"range_meters": 10}, "cost": {"resource_id": "spirit", "amount": 30}}
  ],
  "policies": [
    {"id": "retire-step", "target_ids": ["step"], "strength": "hard", "effect": {"allow_use": false, "allow_mention": true}, "scope": {"from_unit_id": "ch2"}, "author_note": "第二章起弃用，不再安排靠它逃脱的情节。"}
  ],
  "units": [
    {"id": "ch1", "title": "入塔", "outline": "林澈进入试炼塔，在门前发现姐姐留下的记号。", "entity_ids": ["hero", "step"]},
    {"id": "ch2", "title": "上楼", "outline": "不再使用影步，靠观察找到楼梯。", "entity_ids": ["hero"]}
  ]
}
```

长篇总纲可以作为独立来源归档；每章 `outline` 必须包含本章目标、必要的全局承诺、不得提前揭示的内容，不依赖未注入的长文。`entity_ids` 是精确依赖集合；人物自动扩展其持有的能力和资源。

支持 entity.type：character、resource、ability、item、quest、world-rule、faction、fact、progression。数值使用真数字，布尔用 true/false；不把字符串“false”当成布尔。

entity可包含 description、mechanics、limits、attributes、knowledge、provenance、author_note、extensions；已实现明确成本检查。cooldown格式为 `{duration: 60, unit: "second", ready_at: 120}`，章纲story_time为明确的故事秒数；没有时间则不能宣称已冷却。物品消耗通过明确的state_changes记录，不能假设每次使用钥匙都会消耗钥匙。

作者政策 strength=hard/soft；effect支持 allow_use、allow_mention、forbidden_usage_patterns。target_ids为空的全局自由文本政策必进入上下文，但不能由正则独立验证其含义。scope可使用from_unit_id、to_unit_id。

`import stage` 对TXT/Markdown保留完整原文、重复标题、未分类段；不会伪装成已完成语义抽取。宿主填写相应提案的 entities/policies/units 后，清楚分离 uncertainties，再执行import apply。原文明确事实可按已有授权接受；冲突未解决时apply返回1。

## 候选与审查

prepare返回run_id、base_revision及context/run文件相对路径；候选必须使用实际返回值。

```json
{
  "run_id": "实际prepare返回的ID",
  "base_revision": "实际prepare返回的修订号",
  "draft": "林澈发动影步，落在门前。他蹲下，用指腹抹去门框上的灰。",
  "uses": [{"entity_id": "step", "evidence": "发动影步"}],
  "state_changes": [],
  "new_facts": []
}
```

state_changes是 `{id, before: 完整实体, after: 完整实体}` 数组；before是uses自动消耗应用后的状态。普通候选不能更新policies。new_facts必须是完整的新entity，接受前由作者授权或明确创作授权覆盖。

审查文件：

```json
{"verdict": "pass", "notes": "逐句核对后，本章只使用已学影步一次；50灵力扣30后为20；人物未提前获知姐姐去向，符合本章政策与大纲。"}
```

这是一份审查记录，不是触发自动通过的口令。发现问题时填fail并写证据。未提供语义审查时check返回needs_review；有明确违规时仍会blocked。

## 返回与恢复

所有业务结果是JSON。退出码0成功，1待审/阻断，2参数或环境错误，3版本冲突/需要重建修订基础，4需要恢复。--help和--version为普通文字。

`unit revalidate`核对已有正文，不重放消耗；设置修改后出现needs_revalidation时使用。历史状态改写会影响后文；当前版本拒绝直接覆盖有后续已接受章节的状态，先在独立修订副本中操作。

工具不自动同步Git。同步作品时包括project.json、harness.lock.json、canon、outline、manuscript、sources、proposals及runs；排除.harness和exports。一次只在一个设备接受正典；同步后运行doctor。

旧版兼容脚本位于同一scripts目录。新v3项目只使用harness入口；旧脚本仍针对project.md v2，不能混用到v3项目。

迁移报告有未审旧harness时，新章prepare会被阻断。先将采用的数据通过configure或import apply写入，再给 `project migration-confirm --review <JSON>` 提供 `{verdict: "pass", notes: "逐项采用/舍弃理由", resolved_files: [迁移报告中全部unresolved.file]}`。这要求实际审定，不允许直接清空migration_pending字段。

历史改稿可运行 `revision fork --project <原目录> --root <新目录> --unit <起始章节>`。新副本归档父项目的正式文件，恢复该章写前状态并保留之前章节；从起始章重新接受正文。当前政策/章纲若引用历史上不存在的实体，fork会拒绝并要求先明确修订基础，不静默补造实体。
