---
id: docs.issue-020
title: "Blender 没有\"反转关键帧\"菜单(Reverse Keyframes 不存在)"
summary: "反转关键帧的正确操作是「关键帧 → 镜像」;官方文档/API 均无 Reverse Keyframes 操作。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/020-Blender-没有-反转关键帧-菜单-Reverse-Keyframes-不存在.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：Blender 没有"反转关键帧"菜单(Reverse Keyframes 不存在)

**TL;DR**:反转关键帧的正确操作是「关键帧 → 镜像」;官方文档/API 均无 Reverse Keyframes 操作。

- 问题:用户按教程找"反转关键帧"菜单项,怎么都找不到
- 根因:"Reverse Keyframes" 是错误记忆(来自其他软件/旧版教程);Blender 官方文档(Manual Mirror 部分)与 bpy.ops.graph/bpy.ops.action 均无此操作
- 解决:反转 = 关键帧菜单 → 镜像(`Ctrl-M`)→ 沿时间轴关于当前帧(播放头放中间帧)或沿时间轴关于时间 0
- 预防:涉及 Blender 功能术语先查官方文档核实;中文界面给中文菜单名(镜像/沿时间轴关于当前帧)
