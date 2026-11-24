---
id: docs.issue-036
title: "linked duplicate 共享网格数据块导致复制出去联动"
summary: "外部导入的对象常多个共用一个网格数据块(43 网格只 21 唯一块),复制/导出后改一个全跟着变;用 `users>1` 判断 + `data.copy()` 逐对象独立化。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/036-linked-duplicate-共享网格数据块导致复制出去联动.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：linked duplicate 共享网格数据块导致复制出去联动

**TL;DR**:外部导入的对象常多个共用一个网格数据块(43 网格只 21 唯一块),复制/导出后改一个全跟着变;用 `users>1` 判断 + `data.copy()` 逐对象独立化。

- 问题:新工程「补充」集合 43 个网格对象只有 21 个唯一数据块(`组7912/7913_GeomAdjust` 共引 `Mesh.537` 等),复制出去后联动编辑
- 根因:导入/复制产生的 linked duplicate,对象与数据块是"多对一"引用关系
- 解决:遍历集合内 MESH,`if o.data.users>1: o.data = o.data.copy()`;材质可选独立;幂等可重跑
- 预防:排查共享用 `users>1`(勿看数据块名);只处理目标集合,集合外共享不受影响(详见 docs/集合内对象数据独立化.md)
