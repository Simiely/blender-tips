---
id: docs.issue-016
title: "File Output 与渲染属性双份输出(文件名/大小不同)"
summary: "File Output 节点与 render.filepath 同目录时各输出一份;位深不同导致大小差约 2.7 倍。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/016-File-Output-与渲染属性双份输出-文件名-大小不同.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：File Output 与渲染属性双份输出(文件名/大小不同)

**TL;DR**:File Output 节点与 render.filepath 同目录时各输出一份;位深不同导致大小差约 2.7 倍。

- 问题:输出目录出现 frame_0001.png(8-bit,3.6MB)与 frame_0001Image.png(16-bit,9.9MB)两份
- 根因:File Output 节点(文件名 = file_name+槽名+帧号)与渲染属性(render.filepath)同时生效;File Output 槽可 16-bit
- 解决:只留一条输出 —— 删 File Output 节点(保渲染属性)或清空渲染属性路径(保 File Output)
- 预防:配置输出前明确"合成器节点输出"还是"渲染属性输出",避免双份
