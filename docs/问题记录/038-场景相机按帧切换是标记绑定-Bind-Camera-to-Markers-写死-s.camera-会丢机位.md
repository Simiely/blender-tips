---
id: docs.issue-038
title: "场景相机按帧切换是标记绑定(Bind Camera to Markers),写死 s.camera 会丢机位"
summary: "相机切换常用时间轴标记绑定实现(非 action 动画);录屏脚本若写死 `s.camera=某相机` 会覆盖标记绑定,整段锁死一个机位;直接 `render.opengl(view_context=False)` 即自动跟随标记切换。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/038-场景相机按帧切换是标记绑定-Bind-Camera-to-Markers-写死-s.camera-会丢机位.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：场景相机按帧切换是标记绑定(Bind Camera to Markers),写死 s.camera 会丢机位

**TL;DR**:相机切换常用时间轴标记绑定实现(非 action 动画);录屏脚本若写死 `s.camera=某相机` 会覆盖标记绑定,整段锁死一个机位;直接 `render.opengl(view_context=False)` 即自动跟随标记切换。

- 问题:playblast 录屏前在工程里写死 `s.camera=摄像机006`,导出整段视频都是中景机位,丢了开头/结尾的广角机位
- 根因:工程相机切换靠 9 个时间轴标记绑定(如 F1→摄像机001 … F1043→摄像机009),`scene.camera` 在各帧被标记驱动;直接赋值 s.camera 覆盖了这个绑定
- 解决:录屏脚本不写死相机,`bpy.ops.render.opengl(animation=True, view_context=False)` 自动跟随标记切换机位;排查用 `scene.timeline_markers` 看 `m.camera`
- 预防:任何"相机动画"相关脚本,先确认相机切换机制(标记绑定 vs action 动画)再动 s.camera
