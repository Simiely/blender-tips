---
id: docs.issue-028
title: "Blender 5.2 驱动变量类型无 SELF(use_self 替代)"
summary: "给物体挂驱动想引用\"自身属性\"时,旧教程 `vf.type='SELF'` 报非法变量类型;正确做法是 `driver.use_self=True`,表达式里 `self` 即可用。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/028-Blender-5.2-驱动变量类型无-SELF-use_self-替代.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：Blender 5.2 驱动变量类型无 SELF(use_self 替代)

**TL;DR**:给物体挂驱动想引用"自身属性"时,旧教程 `vf.type='SELF'` 报非法变量类型;正确做法是 `driver.use_self=True`,表达式里 `self` 即可用。

- 问题:想在每个网格物体的 `location.z` 驱动里读它自己的 `bob_base_z` / `bob_seed`,按旧方法加 `SELF` 变量时报错
- 根因:Blender 5.x 驱动变量合法类型里没有 `SELF`(旧版有但已移除)
- 解决:`d.use_self = True`,表达式写成 `bob(fr, self)`,函数签名 `def bob(frame, self)` 里 `self` 即当前物体
- 预防:任何"驱动引用自身数据"的需求统一走 use_self,不碰 SELF 变量类型
