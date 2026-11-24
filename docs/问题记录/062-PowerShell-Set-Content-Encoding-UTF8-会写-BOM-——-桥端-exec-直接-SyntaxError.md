---
id: docs.issue-062
title: "PowerShell `Set-Content -Encoding UTF8` 会写 BOM —— 桥端 `exec` 直接 SyntaxError"
summary: "Windows PowerShell 5.1 的 `Set-Content -Encoding UTF8` / `Out-File -Encoding UTF8`"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/062-PowerShell-Set-Content-Encoding-UTF8-会写-BOM-——-桥端-exec-直接-SyntaxError.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：PowerShell `Set-Content -Encoding UTF8` 会写 BOM —— 桥端 `exec` 直接 SyntaxError

**TL;DR**:Windows PowerShell 5.1 的 `Set-Content -Encoding UTF8` / `Out-File -Encoding UTF8`
**会写入 UTF-8 BOM**(PS 7 才有 `utf8NoBOM`);送给桥的脚本第一行就被判非法字符,脚本完全跑不起来。

- 现象:用 PowerShell 拼接生成的 `_smoke.py` 发到桥,返回
  `SyntaxError: invalid non-printable character U+FEFF`,报错行是 `# -*- coding: utf-8 -*-`
- 根因:桥端是 `exec` 收到的源码文本,**不吞 BOM**;
  而 PowerShell 5.1 的 `-Encoding UTF8` 语义恰恰是"UTF-8 带 BOM"
- 解决(任选):用 Write 类工具直接落盘 / PowerShell
  `[System.IO.File]::WriteAllText($p,$s,(New-Object System.Text.UTF8Encoding($false)))` /
  Python `open(p,"w",encoding="utf-8",newline="\n")`
- 预防:凡"**生成文件 → 交给另一个程序解析**"的链路,都要核对首字节。
  注意本机 `bl.py` 落的 `.out` 是客户端写的、不受影响;**手工生成的输入脚本才是风险点**
  (详见 skills/blender-bridge-ops/SKILL.md「脚本文件绝不能带 BOM」)
