---
id: docs.issue-011
title: "Blender 5.2 渲染后查看器不显示结果(透明/需手动切)"
summary: "5.2 移除 `CompositorNodeComposite`,合成器开启时渲染结果不再自动显示在图像查看器。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/011-Blender-5.2-渲染后查看器不显示结果-透明-需手动切.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：Blender 5.2 渲染后查看器不显示结果(透明/需手动切)

**TL;DR**:5.2 移除 `CompositorNodeComposite`,合成器开启时渲染结果不再自动显示在图像查看器。

- 问题:F12 渲染后,图像查看器显示透明/空白,要手动选择 Viewer 等才能看到
- 根因:4.x 靠 Composite 节点把结果送进 Render Result;5.2 该节点被移除(官方 API 文档 404、bpy.types 无此类)
- 解决:方式 A 加 Viewer 节点预览;方式 B 取消 Use Nodes 直接渲染(结果自动显示)
- 预防:开启合成器=必须自己安排预览节点或接受查看器无自动显示
