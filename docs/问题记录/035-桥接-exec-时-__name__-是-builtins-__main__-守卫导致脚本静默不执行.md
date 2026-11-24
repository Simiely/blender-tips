---
id: docs.issue-035
title: "桥接 exec 时 __name__ 是 builtins,__main__ 守卫导致脚本静默不执行"
summary: "经控制桥远程执行的脚本,`__name__` 为 `builtins` 而非 `__main__`,写 `if __name__=='__main__': main()` 会静默跳过,桥端只回 `OK` 无任何输出。"
type: explanation
kind: note
status: active
owner: "@simiely"
topics: [blender]
source_type: doc
source: "docs/问题记录/035-桥接-exec-时-__name__-是-builtins-__main__-守卫导致脚本静默不执行.md"
last_reviewed: 2026-11-24
related: []
---

# 问题：桥接 exec 时 __name__ 是 builtins,__main__ 守卫导致脚本静默不执行

**TL;DR**:经控制桥远程执行的脚本,`__name__` 为 `builtins` 而非 `__main__`,写 `if __name__=='__main__': main()` 会静默跳过,桥端只回 `OK` 无任何输出。

- 问题:新写 make_independent.py 带 `__main__` 守卫,桥里跑只回 `OK`,集合数据块毫无变化;改为内联 `-c` 执行同样逻辑却立即生效
- 根因:桥脚本用 `exec(code)` 在当前命名空间执行,`__name__` 是 `builtins`;`__main__` 分支永远不满足
- 解决:脚本末尾直接调用 `main()`,不写 `__main__` 守卫(Scripting 工作区 Run Script 同理可跑)
- 预防:凡"经桥远程执行"的脚本一律直接执行;若要区分导入/直跑,用 `__file__` 或环境变量,不要依赖 `__name__`
