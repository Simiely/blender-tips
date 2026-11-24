---
id: docs.issue-033
title: "Blender 5.2 视口录制(opengl + FFMPEG)输出配置顺序"
summary: "配置视频输出必须先 `image_settings.media_type='VIDEO'`,再 `file_format='FFMPEG'`;顺序反了报枚举找不到。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/033-Blender-5.2-视口录制-opengl-+-FFMPEG-输出配置顺序.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：Blender 5.2 视口录制(opengl + FFMPEG)输出配置顺序

**TL;DR**:配置视频输出必须先 `image_settings.media_type='VIDEO'`,再 `file_format='FFMPEG'`;顺序反了报枚举找不到。

- 问题:`bpy.ops.render.opengl` 想导出 mp4,脚本先设 `file_format='FFMPEG'` 再设 `media_type='VIDEO'`(或只设 file_format),报 `'FFMPEG' not found in enum` / 配置无效,输出全空
- 根因:Blender 5.2 把渲染输出拆成 media_type(IMAGE/VIDEO/MULTILAYER)与 file_format 两层;在 media_type 还不是 VIDEO 时,file_format 枚举里还没有 FFMPEG 项
- 解决:严格顺序——`isx.media_type='VIDEO'` → `isx.file_format='FFMPEG'` → 再设 `ffmpeg.format/codec`
- 预防:任何"视口录屏/视频输出"脚本,把 media_type 写在 file_format 之前;录屏用 `render.opengl(animation=True, view_context=False)`(False=从场景相机出画面)
