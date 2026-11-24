---
id: docs.issue-029
title: "自定义属性显示名就是键名(update(name=) 无效)"
summary: "想让控制面板滑块显示中文,没有\"改显示名\"的 API;显示名 = 键名,直接把键设成中文即可。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/029-自定义属性显示名就是键名-update-name=-无效.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：自定义属性显示名就是键名(update(name=) 无效)

**TL;DR**:想让控制面板滑块显示中文,没有"改显示名"的 API;显示名 = 键名,直接把键设成中文即可。

- 问题:自定义属性键是 `max_up`,想界面显示「最大上移」,尝试 `id_properties_ui(k).update(name='最大上移')` 报错
- 根因:Blender 自定义属性**显示名与键名是同一个东西**,`update()` 只接受 `min/max/description` 等,不接受 `name`
- 解决:直接用中文键 `obj['最大上移']=1.0`,逻辑读取也同步用中文键;`bob()` 函数读 `ctrl['最大上移']` 等
- 预防:自定义属性要中文 UI → 键即中文;纯内部属性(基准/种子)可保留英文避免混淆
