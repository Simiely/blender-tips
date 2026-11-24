---
id: docs.issue-022
title: "send.py 发送大任务报超时,但桥实际执行完了"
summary: "桥内任务耗时 >120s 时 send.py 的 socket 先超时抛错(误报失败),但桥的 timer 线程会继续把任务执行完。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/022-send.py-发送大任务报超时-但桥实际执行完了.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：send.py 发送大任务报超时,但桥实际执行完了

**TL;DR**:桥内任务耗时 >120s 时 send.py 的 socket 先超时抛错(误报失败),但桥的 timer 线程会继续把任务执行完。

- 问题:发送"全量网格指纹计算+合并"(9,079 数据块)时,send.py 报 `TimeoutError: timed out`(exit 1),看起来失败了
- 根因:桥端 `_handle` 等待 res 的 deadline 与 send.py 的 socket timeout 都是 120s,几乎同时到点;send.py 在收到桥的 ERR 前先抛超时;桥端 timer 仍在主线程跑完该任务(exec 不中断)
- 解决:超时后**重跑一次同样的脚本**——若输出"冗余 0 / 已完成"说明第一次实际执行完了;写操作先备份、幂等设计(合并脚本重跑无副作用)
- 预防:大任务(全量遍历 5 万+ 对象)拆分批次或接受超时重跑验证;只读探查超时同样用重跑确认
