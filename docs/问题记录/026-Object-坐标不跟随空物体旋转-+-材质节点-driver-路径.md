---
id: docs.issue-026
title: "Object 坐标不跟随空物体旋转 + 材质节点 driver 路径"
summary: "Texture Coordinate 的 Object 输出只跟随平移;材质节点 driver/keyframe 路径必须用 inputs[N] 数字索引。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/026-Object-坐标不跟随空物体旋转-+-材质节点-driver-路径.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：Object 坐标不跟随空物体旋转 + 材质节点 driver 路径

**TL;DR**:Texture Coordinate 的 Object 输出只跟随平移;材质节点 driver/keyframe 路径必须用 inputs[N] 数字索引。

- 问题1:旋转控制空物体 90°,条纹毫无变化——Blender 的 Object 坐标仅用空物体原点做平移参考,旋转/缩放不影响采样坐标
- 解决1:条纹旋转用材质节点内偏移(节点 ADD + driver/keyframe),不要转空物体;空物体只用于平移类控制
- 问题2:材质 driver `nodes["UOffset"].inputs["Location"].default_value` 报 not found(5.2 slotted action 路径解析 bug)
- 解决2:路径改用数字索引 `inputs[1]`(与 keyframe 经验一致,见 §16);对象级 driver(rotation/location)不受影响
- 预防:涉及材质节点动画一律用 inputs[N];旋转类动画走节点偏移;文档 §17
