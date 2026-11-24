---
id: docs.issue-046
title: "位移想沿\"自己的轴\"或\"世界轴\",K 出来的 `location` 却哪个都不是"
summary: "`location` 的坐标系是**父空间基底**(`parent.matrix_world @ matrix_parent_inverse`),`matrix_basis = T(location) @ R @ S` 里**平移在最左端**,所以对象自身怎么转都不影响位移方向。想沿自身轴 ⇒ 让\"承载位移的那一层\"自身旋转为 0;想沿世界轴 ⇒ 让那一层的父空间与世界对齐。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/046-位移想沿-自己的轴-或-世界轴-K-出来的-location-却哪个都不是.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：位移想沿"自己的轴"或"世界轴",K 出来的 `location` 却哪个都不是

**TL;DR**:`location` 的坐标系是**父空间基底**(`parent.matrix_world @ matrix_parent_inverse`),`matrix_basis = T(location) @ R @ S` 里**平移在最左端**,所以对象自身怎么转都不影响位移方向。想沿自身轴 ⇒ 让"承载位移的那一层"自身旋转为 0;想沿世界轴 ⇒ 让那一层的父空间与世界对齐。

- 问题:物体轴向与世界轴不一致时(被转过的父级下、或自身带旋转),在对象上 K `location[2]` 得到的世界位移方向,既不是自身轴也不是世界轴;实测(父级绕 X 转 90°、子级自转 90°)与自身 Z 偏 **90.0000°**
- 根因:`matrix_world = parent.matrix_world @ matrix_parent_inverse @ matrix_basis`,而 `matrix_basis = T @ R @ S` —— 一个点先经 `S`、`R` 再被 `T` 平移 ⇒ `T` 作用于 `parent.matrix_world @ MPI` 这个坐标系(父空间基底),与 `R` 无关。顺带:**`delta_location` 与 `location` 同坐标系**(常见误解),`delta_rotation` 也不把 `location` 带转(均实测偏 90.0000°)
- 解决(统一心法:**想沿哪个坐标系,就把承载位移那一层的父空间做成它**):
  - 沿**自身轴**: `父级 → 朝向层(放旋转,location 恒 0) → 位移层(自身旋转恒 0,K location[2])`;上层旋转即使是动画也逐帧精确(实测逐帧 0.000000°)
  - 沿**世界轴**: 中间插一层"抵消旋转"的**世界对齐层**(静态父级填固定逆角 · 实测 0.000000;动态单轴父级挂 `Copy Rotation` invert · 0.000000),或直接用**世界空间约束**(无父级空对象 K 动画 + `Copy Location` with `owner_space/target_space='WORLD'`+`use_offset` · 实测含复合旋转也是 0.000000)
  - 不想改结构:`loc = d·(R_own @ AXIS)`(自身轴)/ `loc = d·(P_basis_rot⁻¹ @ AXIS)`(世界轴),**父级朝向是动画时必须逐帧 bake**(只 K 两端实测偏 7.07 单位)
- 预防:凡"位移方向不对"的问题,先跑 `scripts/axis-space-motion/axis_report.py` 量三个夹角(父空间基底 vs 自身轴 / vs 世界轴,以及坐标基底是否随时间变),夹角为 0 的那一项就是"现状已经对"的方向,别瞎试(详见 docs/轴向位移-自身轴与世界轴.md)
