---
id: docs.issue-019
title: "同一次 exec 内修改后立即验证读到旧缓存值"
summary: "桥脚本改关键帧后在同一请求里马上重读,拿到的是未刷新值(数值错误但数据实际正确)。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/019-同一次-exec-内修改后立即验证读到旧缓存值.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：同一次 exec 内修改后立即验证读到旧缓存值

**TL;DR**:桥脚本改关键帧后在同一请求里马上重读,拿到的是未刷新值(数值错误但数据实际正确)。

- 问题:execute 脚本内"修改→验证"输出 min=2 max=47,与新请求重读的 min=1 max=106 不符
- 根因:Blender 主线程 exec 内关键帧修改后,同上下文读取走缓存/延迟路径
- 解决:修改与验证分成两次 send 请求;以新请求读取结果为准
- 预防:所有"改完验证"一律新请求;探查脚本只读不会触发
