---
id: docs.issue-042
title: "Blender 5.2 DriverTarget 没有 array_index 属性"
summary: "SINGLE_PROP 驱动变量要读数组的某个分量(如 location 的 X),不能设 `target.array_index`(5.2 无此属性,报 AttributeError);改在 `data_path` 里带下标 `'location[0]'`。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/042-Blender-5.2-DriverTarget-没有-array_index-属性.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：Blender 5.2 DriverTarget 没有 array_index 属性

**TL;DR**:SINGLE_PROP 驱动变量要读数组的某个分量(如 location 的 X),不能设 `target.array_index`(5.2 无此属性,报 AttributeError);改在 `data_path` 里带下标 `'location[0]'`。

- 问题:`v.targets[0].array_index = 0` 报 `AttributeError: 'DriverTarget' object has no attribute 'array_index'`
- 根因:Blender 5.2 移除了 DriverTarget.array_index,数组分量索引并入 data_path
- 解决:`v.targets[0].data_path = 'location[0]'`(或 `'rotation_euler[2]'` 等)
- 预防:任何挂"读对象数组属性分量"驱动的脚本,data_path 直接带下标(详见 docs/运动网格灯光方案.md)
