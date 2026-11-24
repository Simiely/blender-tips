---
id: docs.issue-039
title: "send.py 不支持端口参数,多 Blender 并存连不上"
summary: "仓库 send.py 硬编码 9877,AGENTS.md 却声称\"第二参数指定端口\";多 Blender 并存(如 9877+9897)时无法用仓库客户端连第二实例。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/039-send.py-不支持端口参数-多-Blender-并存连不上.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：send.py 不支持端口参数,多 Blender 并存连不上

**TL;DR**:仓库 send.py 硬编码 9877,AGENTS.md 却声称"第二参数指定端口";多 Blender 并存(如 9877+9897)时无法用仓库客户端连第二实例。

- 问题:新开工程在 9897,仓库 send.py 只能连 9877,AGENTS.md 文档与代码不符
- 根因:send.py 写死 `PORT=9877`,没解析命令行端口参数
- 解决:send.py 加 `-p/--port` 参数解析(默认仍 9877);顺带把超时从 120s 提到 300s(playblast 等长任务)
- 预防:AGENTS.md 声称的能力必须与 send.py 代码一致;多 Blender 工作流统一用 `python send.py -p PORT script.py`
