---
id: docs.issue-049
title: "`hasattr(bpy.ops.xxx, \"yyy\")` 会假阳性,判算子存在性必须用 `get_rna_type()`"
summary: "`hasattr(bpy.ops.mesh, \"separate_by_material\")` 返回 **`True`**,但这个算子**根本不存在**;真调 `get_rna_type()` 直接 `KeyError`。判 `bpy.ops` 算子是否存在,一律用 `get_rna_type()` 包 `try`。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/049-hasattr-bpy.ops.xxx-yyy-会假阳性-判算子存在性必须用-get_rna_type.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：`hasattr(bpy.ops.xxx, "yyy")` 会假阳性,判算子存在性必须用 `get_rna_type()`

**TL;DR**:`hasattr(bpy.ops.mesh, "separate_by_material")` 返回 **`True`**,但这个算子**根本不存在**;真调 `get_rna_type()` 直接 `KeyError`。判 `bpy.ops` 算子是否存在,一律用 `get_rna_type()` 包 `try`。

- 问题:要按材质拆分网格,顺手写了 `hasattr(bpy.ops.mesh, "separate_by_material")` 做能力探测,得到 `True` 就照着这个"更语义化"的算子去写方案;后来在真实网格上跑才发现路径不对,回头做运行时自省才确认它并不存在
- 根因:`bpy.ops` 是**动态命名空间**,`__getattr__` 对任意属性名都返回一个 `BPyOpsSubModOp` 包装对象(真正的解析推迟到调用时),所以 `hasattr` 对它几乎恒为真 —— 只能证明"名字能被包装",不能证明"算子存在"。唯一权威判据是 `op.get_rna_type()`:存在才有 RNA 类型,不存在则 `KeyError`
- 解决:能力探测统一写成
  ```python
  try:
      t = getattr(bpy.ops.mesh, name).get_rna_type()
      print("exists:", t.identifier, t.description)
  except Exception:
      print("NOT exists:", name)
  ```
  同时用 `bpy.ops.mesh.separate.get_rna_type()` 把 `type` 的枚举打出来核对(实测只有 `SELECTED / MATERIAL / LOOSE`)
- 预防:本项目里"探测 Blender 能力"一律**读运行时 RNA**(`get_rna_type()` / `bl_rna.properties[...].enum_items`),不要凭记忆或 `hasattr`。查文档也以**官方手册原文 + 运行时自省**双向交叉验证为准(本次官方手册确认 By Material 是"按材质槽、对整网格生效、与选择无关")(详见 docs/按材质拆分为多个网格体.md、脚本 scripts/separate-by-material/)
