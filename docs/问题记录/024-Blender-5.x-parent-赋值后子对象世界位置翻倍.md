---
id: docs.issue-024
title: "Blender 5.x parent 赋值后子对象世界位置翻倍"
summary: "`child.parent = empty` 后 matrix_parent_inverse 不自动设置(保持单位矩阵),空对象不在原点时子对象世界位置 = 空对象位置 + 局部坐标(如 743+743=1486)。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/024-Blender-5.x-parent-赋值后子对象世界位置翻倍.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：Blender 5.x parent 赋值后子对象世界位置翻倍

**TL;DR**:`child.parent = empty` 后 matrix_parent_inverse 不自动设置(保持单位矩阵),空对象不在原点时子对象世界位置 = 空对象位置 + 局部坐标(如 743+743=1486)。

- 问题:把 (743,380,0.5) 处对象挂到空对象,世界位置变成 (1486,760,1.9)(翻倍);撤销/再移动时偏移叠加,局部坐标被反复重写(743 大数 ↔ 小数)
- 根因:Blender 5.x 中 parent 赋值**不自动更新 matrix_parent_inverse**;世界 = parent.world @ mpi @ local,mpi=Identity 时 = parent.world @ local;空对象与物体距离越远越明显
- 解决:挂载后手动 `child.matrix_parent_inverse = parent.matrix_world.inverted()`;世界位置立即恢复,局部坐标变为相对父级的小数
- 预防:远程 parent 一律手动设 mpi;**空对象先定位到目标位置再挂载**;设置 location 后 `bpy.context.view_layer.update()` 刷新;同 exec 内读取 matrix_world 是缓存值,用新请求验证
