---
id: docs.issue-003
title: "SCRIPTED 驱动\"变量声明了但没进表达式\"导致参数失效"
summary: "问题:控制器 `动态缩放` 循环三角波动画不改变星芒大小"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/003-SCRIPTED-驱动-变量声明了但没进表达式-导致参数失效.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：SCRIPTED 驱动"变量声明了但没进表达式"导致参数失效

- 问题:控制器 `动态缩放` 循环三角波动画不改变星芒大小
- 根因:驱动表达式只用了 `a`,漏写 `+ b/1000`;声明变量不等于使用变量,求值只看表达式文本
- 解决:完整式 `a/1000 + b/1000`;脚本一键改写三条 scale 驱动(见 `scripts/starburst-scatter/fix_star_scale.py`,幂等、先打印旧式)
- 预防:探测脚本打印**驱动表达式全文**,别只列变量表;核验用 depsgraph 评估 scale
