---
id: docs.issue-025
title: "ColorRamp 渐变\"抖\"(EASE 插值 + 过渡区多余色标)"
summary: "循环渐变色显示不平滑 = 两个原因叠加:插值类型被改成 EASE(非线性)+ 过渡区中间残留色标(打断线性)。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/025-ColorRamp-渐变-抖-EASE-插值-+-过渡区多余色标.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：ColorRamp 渐变"抖"(EASE 插值 + 过渡区多余色标)

**TL;DR**:循环渐变色显示不平滑 = 两个原因叠加:插值类型被改成 EASE(非线性)+ 过渡区中间残留色标(打断线性)。

- 问题:黑白渐变波播放时过渡区"抖",不是平滑线性;用户手动调色标后出现
- 根因:ColorRamp 默认 LINEAR,但**手动拖动色标时插值类型可能被切到 EASE**(缓动,过渡在两端加速减速 → 视觉上"抖");且过渡区中间若留色标,插值被钉住形成台阶
- 解决:`cr.color_ramp.interpolation = 'LINEAR'`;删掉两平台之间的色标,让过渡由两侧平台色标线性决定
- 预防:任何 ColorRamp 做完后检查 interpolation;循环渐变按"平台(同色连标)+ 过渡(无中间色标)+ 首尾同色"布局(见 docs §16)
