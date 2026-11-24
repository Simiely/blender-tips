---
id: docs.issue-007
title: "改 IDProperty 后驱动不重算"
summary: "`obj['vis']=[0]` 后驱动值不变,需 `update_tag()` 强制刷新。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/007-改-IDProperty-后驱动不重算.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：改 IDProperty 后驱动不重算

**TL;DR**:`obj['vis']=[0]` 后驱动值不变,需 `update_tag()` 强制刷新。

- 问题:驱动引用自定义属性,直接赋值后驱动仍取旧值
- 根因:IDProperty 直接赋值不触发依赖图更新通知
- 解决:`ctrl.update_tag()` + `bpy.context.view_layer.update()`
- 预防:用户打关键帧走动画通道自动刷新,无此问题;脚本改值必须 update_tag
