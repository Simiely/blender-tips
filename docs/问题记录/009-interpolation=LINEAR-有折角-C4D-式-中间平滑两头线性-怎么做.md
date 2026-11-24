---
id: docs.issue-009
title: "interpolation=LINEAR 有折角,C4D 式\"中间平滑两头线性\"怎么做"
summary: "两头关键帧 handle 改 FREE,手动对齐线段方向;中间保持平滑。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/009-interpolation=LINEAR-有折角-C4D-式-中间平滑两头线性-怎么做.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：interpolation=LINEAR 有折角,C4D 式"中间平滑两头线性"怎么做

**TL;DR**:两头关键帧 handle 改 FREE,手动对齐线段方向;中间保持平滑。

- 问题:改 LINEAR 段是直线但关键帧处折角;VECTOR handle 自动拉直不满足
- 根因:Blender 段插值线性化必然在段交界产生尖角;C4D 的切线控制更细
- 解决:中间帧保持 BEZIER/AUTO;两头帧 handle 改 FREE 并手动拖到与线段平行
- 预防:涉及"线性+平滑混合"需求优先 Free handle 方案,别先改 interpolation
