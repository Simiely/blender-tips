---
id: docs.issue-034
title: "Z 轴匀速旋转驱动用 rotation_euler 而非 rotation / 基准角被污染"
summary: "想让物体绕 Z 轴匀速转,驱动必须挂在 `rotation_euler[2]`;挂之前把基准角复位为 0,否则从被污染角度累加。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/034-Z-轴匀速旋转驱动用-rotation_euler-而非-rotation-基准角被污染.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：Z 轴匀速旋转驱动用 rotation_euler 而非 rotation / 基准角被污染

**TL;DR**:想让物体绕 Z 轴匀速转,驱动必须挂在 `rotation_euler[2]`;挂之前把基准角复位为 0,否则从被污染角度累加。

- 问题1:直接 `driver_add('rotation', 2)` 或读 `rotation`(四元数)做 Z 旋转,角度结果错乱、不直观
- 解决1:统一用欧拉角 Z 分量 `driver_add('rotation_euler', 2)`,`rotation_mode='XYZ'`,表达式 `0 + fr * spin_speed() * DEG2RAD * sign`
- 问题2:目标物体此前被驱动污染过 Z 角(实测残留 100°),重挂驱动时若不复位,角度从 100° 起累加 → 起始姿态错
- 解决2:挂驱动前显式 `o.rotation_euler.z = 0.0`(原始基准即 0°);幂等重建:先移除旧 Z 驱动再重建
- 预防:任何"复位基准"的旋转脚本,挂驱动前强制写 0,不要依赖"当前值";速度用 `SINGLE_PROP` 读 `scene.frame_current`,保证每帧重算、调速即时生效
