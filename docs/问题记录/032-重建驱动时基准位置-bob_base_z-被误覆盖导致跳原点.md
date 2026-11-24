---
id: docs.issue-032
title: "重建驱动时基准位置(bob_base_z)被误覆盖导致跳原点"
summary: "挂驱动时要记录物体静止 Z 作基准,但重建时若覆盖了被驱动\"当前值\",物体会跳到原点附近;只在首次记录、已存在则跳过。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/032-重建驱动时基准位置-bob_base_z-被误覆盖导致跳原点.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：重建驱动时基准位置(bob_base_z)被误覆盖导致跳原点

**TL;DR**:挂驱动时要记录物体静止 Z 作基准,但重建时若覆盖了被驱动"当前值",物体会跳到原点附近;只在首次记录、已存在则跳过。

- 问题:设想在已有驱动的物体上重跑构建,若直接 `o['bob_base_z'] = o.location.z`,此时 location.z 是被驱动后的偏移值,基准被污染 → 整体位移错位
- 根因:有驱动时 `obj.location.z` 返回的是驱动求值结果,不是原始静止位置
- 解决:记录基准前先判断 `if 'bob_base_z' not in o: o['bob_base_z'] = o.location.z`,只在无基准时写(首次);已有则保留
- 预防:任何"基于当前位置记基准"的脚本,都要先判存在再写,保证幂等重建不污染
