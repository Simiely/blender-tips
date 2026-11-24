---
id: docs.issue-037
title: "恢复驱动命名空间函数后,驱动仍 is_valid=False,物体停在 Z=0 错位"
summary: "重开 .blend 后 exec 文本块把 bob/spin_speed 重新注册进命名空间,但驱动仍不求值(物体掉 Z=0);必须对每条 SCRIPTED 驱动**重新赋值同值表达式**(`d.expression = d.expression`)强制重新编译才恢复。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/037-恢复驱动命名空间函数后-驱动仍-is_valid=False-物体停在-Z=0-错位.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：恢复驱动命名空间函数后,驱动仍 is_valid=False,物体停在 Z=0 错位

**TL;DR**:重开 .blend 后 exec 文本块把 bob/spin_speed 重新注册进命名空间,但驱动仍不求值(物体掉 Z=0);必须对每条 SCRIPTED 驱动**重新赋值同值表达式**(`d.expression = d.expression`)强制重新编译才恢复。

- 问题:9877 工程重开后 bob/spin 函数丢失(5.2 文本块不自动执行),主装置01-05 全部物体 Z 掉到 0 错位。exec 文本块后 `driver.is_valid` 仍 False,物体不动
- 根因:函数注册只是把符号放回命名空间;depsgraph 对驱动的失败状态有缓存,不会自动重算。驱动求值失败时 Blender 返回 0(不是保持基础值)→ 物体全落 Z=0
- 解决:恢复函数后,遍历全场景 SCRIPTED 驱动,若表达式含恢复的函数名,执行 `d.expression = d.expression`(同值重赋值触发重新编译),再 view_layer.update()
- 预防:restore_drivers.py 已内置该步骤(EXPR_MAP 声明 文本块→函数 映射);任何"恢复驱动函数"脚本都要带强制重编译,否则看似恢复实则物体停 0 位
