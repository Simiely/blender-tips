---
id: docs.issue-041
title: "新建轴心空物体后立即读 matrix_world 是单位矩阵,matrix_parent_inverse 变 identity"
summary: "创建空物体后马上读 `matrix_world` 是单位矩阵 → `matrix_parent_inverse = matrix_world.inverted()` 变成 identity → 子对象世界坐标 = 父位置 + 自身位置(翻倍偏移);必须先 `view_layer.update()` 再读。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/041-新建轴心空物体后立即读-matrix_world-是单位矩阵-matrix_parent_inverse-变-identity.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：新建轴心空物体后立即读 matrix_world 是单位矩阵,matrix_parent_inverse 变 identity

**TL;DR**:创建空物体后马上读 `matrix_world` 是单位矩阵 → `matrix_parent_inverse = matrix_world.inverted()` 变成 identity → 子对象世界坐标 = 父位置 + 自身位置(翻倍偏移);必须先 `view_layer.update()` 再读。

- 问题:批量给 168 个灯 parent 到组轴心空物体,灯世界坐标全部 = 轴心位置 + 网格位置(翻倍),跑出集合外
- 根因:轴心空物体刚 `objects.new()` + 设 location,未刷新 depsgraph 时 `matrix_world` 是单位矩阵,`inverted()` 也是 identity → parent 变换没抵消
- 解决:所有轴心空物体创建并设好位置后,先 `bpy.context.view_layer.update()`,再读 `matrix_world` 设 `matrix_parent_inverse`
- 预防:任何"建空物体 + parent + 手动 matrix_parent_inverse"的脚本,把 update() 放在读 matrix_world 之前(详见 docs/运动网格灯光方案.md)
