---
id: docs.issue-012
title: "File Output 输出是 EXR 而不是 PNG"
summary: "节点 Media Type 默认 Multi-Layer EXR,槽需勾 Override Node Format 才能用 PNG。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/012-File-Output-输出是-EXR-而不是-PNG.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：File Output 输出是 EXR 而不是 PNG

**TL;DR**:节点 Media Type 默认 Multi-Layer EXR,槽需勾 Override Node Format 才能用 PNG。

- 问题:明明槽里选了 PNG,输出却是 .exr
- 根因:节点级 format 在 Multi-Layer EXR 模式锁定 OPEN_EXR_MULTILAYER(设置 PNG 报 enum 错);槽 override_node_format=False → 用节点级格式
- 解决:Media Type 改 Image;或槽勾 Override Node Format 选 PNG
- 预防:File Output 节点优先检查 Media Type,再检查槽的 Override
