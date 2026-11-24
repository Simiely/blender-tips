---
id: docs.issue-010
title: "远程脚本修改合成器节点树导致 Blender 崩溃"
summary: "Blender 5.x 的 File Output 节点有已知崩溃 bug,远程脚本(主线程 timer)新建/操作该节点会直接崩溃(无崩溃日志)。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/010-远程脚本修改合成器节点树导致-Blender-崩溃.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：远程脚本修改合成器节点树导致 Blender 崩溃

**TL;DR**:Blender 5.x 的 File Output 节点有已知崩溃 bug,远程脚本(主线程 timer)新建/操作该节点会直接崩溃(无崩溃日志)。

- 问题:通过远程桥在合成器节点树新建 `CompositorNodeOutputFile`、操作 `file_output_items` 时,Blender 进程直接消失
- 根因:Blender Artists 社区确认 —— Blender 5.x 的 file output 节点(带 vec1 输入)存在崩溃 bug,5.1 Alpha 修复;官方 devtalk 也讨论过 File Output 节点在 5.2 的行为问题
- 解决:该环节放弃脚本,改 GUI 手动添加/配置 File Output 节点
- 预防:远程桥只做只读探查;合成器节点树的写操作(新建/删除/槽操作)一律 GUI 手动
