---
id: docs.issue-047
title: "循环采样时 `matrix_world` 没 `.copy()`,所有样本都变成最后一帧的值"
summary: "`evaluated_get(dg).matrix_world` 返回的是**活引用**,存进列表前必须 `.copy()`,否则遍历结束后读到的全是末帧值;`to_3x3()` / `to_translation()` 返回新对象,天然安全。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/047-循环采样时-matrix_world-没-.copy-所有样本都变成最后一帧的值.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：循环采样时 `matrix_world` 没 `.copy()`,所有样本都变成最后一帧的值

**TL;DR**:`evaluated_get(dg).matrix_world` 返回的是**活引用**,存进列表前必须 `.copy()`,否则遍历结束后读到的全是末帧值;`to_3x3()` / `to_translation()` 返回新对象,天然安全。

- 问题:诊断脚本按 `for f in frames: scene.frame_set(f); mw = obj.evaluated_get(dg).matrix_world; rows.append((f, mw, ...))` 收集采样,随后打印表里 **f=151 / f=315 / f=480 三行的"自身Z→世界"完全一样**,且恰好等于最后一帧(f=480)的值 → 由此算出"自身Z vs 世界Z = 0.0000 度"的**假结论**(真实应为 101.53°)
- 根因:`evaluated_get()` 拿到的是**求值代理对象**,其 `matrix_world` 暴露的是内部内存的引用/视图;下一次 `frame_set` 重新求值后该内存被改写,先前存下的 3 个对象**指向同一处**,于是全部反映末帧。同一循环里 `(pw @ mpi).to_3x3()` 因为 `to_3x3()` 生产了新矩阵,所以没有这个症状 —— 这也解释了为什么只有"直接存的 `matrix_world`"那一列坏了
- 解决:`mw = ev.matrix_world.copy()` 后再存;或只取需要的数值(`to_translation().copy()` / `to_3x3()`)
- 预防:任何"多帧采样后统一比对"的脚本,凡把矩阵/向量**存进容器**的,一律显式 `.copy()`;写完先打印首末两帧做自检(两帧完全相同 = 踩了这个坑)(详见 docs/轴向位移-自身轴与世界轴.md、脚本 scripts/axis-space-motion/axis_report.py)
