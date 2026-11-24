---
id: docs.issue-006
title: "Blender 5.2 没有 `action.fcurves`(Slotted Action)"
summary: "新版动画用 slotted action,曲线要经 `fcurve_ensure_for_datablock` 访问。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/006-Blender-5.2-没有-action.fcurves-Slotted-Action.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：Blender 5.2 没有 `action.fcurves`(Slotted Action)

**TL;DR**:新版动画用 slotted action,曲线要经 `fcurve_ensure_for_datablock` 访问。

- 问题:`action.fcurves` 报 `'Action' object has no attribute 'fcurves'`
- 根因:Blender 5.x 引入 slotted action,ActionSlot 无 fcurves,slot.handle 是 int 句柄
- 解决:`fcu = action.fcurve_ensure_for_datablock(obj, 'location', index=0)`(index 必须关键字)
- 预防:访问动画数据前先探测 action 结构;旧教程的 action.fcurves 在 5.x 失效
