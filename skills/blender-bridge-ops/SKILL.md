---
name: blender-bridge-ops
description: 通过本地 9877 socket 桥远程操控正在运行的 Blender（读取/体检/改动场景）。当用户要求「连接 Blender」「跟 Blender 联调」「清理工程里的空物体/孤儿数据块」「批量改场景」等需要把 Python 脚本送进运行中的 Blender 主线程执行的任务时使用。包含客户端封装、120s 上限规避、Blender 4.4+/5.x Slotted Action 与引用/删除的正确写法，以及本机踩过的具体坑。
agent_created: true
---

# Blender 远程联调（9877 桥）

## 环境事实（本机）

- 桥服务端：`scripts/blender-remote-control/blender_bridge.py`（来源 `Simiely/blender-tips`），在 Blender 的 **Scripting 工作区 Run Script** 启动，监听 `127.0.0.1:9877`
- 协议：客户端发 `code + <END>`，桥用 `bpy.app.timers` 每 0.05s 把代码调度到**主线程**执行，回 `OK\n<输出>` 或 `ERR\n<traceback>`
- **服务端硬超时 120s** —— 超时只断开回包，脚本仍在 Blender 主线程继续跑，期间桥对外表现为无响应
- 本机 **PowerShell 不回传 stdout**，所有结果必须落盘再用 Read 读
- 本机 **bash 环境已损坏**（`ls`/`dirname` not found），文件操作一律用 PowerShell 或 Read/Glob/Grep 工具
- 后台 PowerShell 任务约 **120s 会被杀掉**，长等待改用前台短轮询（每次 sleep 循环 < 90s）

## 客户端封装

工作目录下自备 `bl.py`：

```
python bl.py <code.py>        # 结果打印到 stdout 并写入 <code.py>.out
```

要点：客户端 socket timeout 设 300s；结果文件命名为 `<脚本名>.out`，**每次都要 Read 这个文件**而不是读 shell 输出。

### ⚠️ 脚本文件绝不能带 BOM

桥端是直接 `exec` 收到的源码，**带 UTF-8 BOM 会在第一行就炸**：

```
ERR
  File "<remote>", line 1
    ﻿# -*- coding: utf-8 -*-
    ^
SyntaxError: invalid non-printable character U+FEFF
```

- **Windows PowerShell 5.1 的 `Set-Content -Encoding UTF8` / `Out-File -Encoding UTF8` 会写入 BOM** ——
  用它们生成送给桥的脚本必炸（本机已实测踩过一次）
- 安全做法，任选：
  - 用 Write 类工具直接落盘（无 BOM）
  - Python：`open(path, "w", encoding="utf-8", newline="\n")`
  - PowerShell：`[System.IO.File]::WriteAllText($p, $s, (New-Object System.Text.UTF8Encoding($false)))`
- 只落**日志/报告**（不送桥）的文本文件不受影响，但读回来时注意首行可能带 `﻿`

## 标准作业循环

1. 侦察：确认 9877 在听、Blender PID、当前活动文件、`bpy.data.is_dirty`
2. **只读体检**（probe_*.py）→ 出报告
3. 报告呈给用户 → 确认范围（尤其是删除类操作）
4. **建还原点**：复制 `.blend` 到 `_backup\<名>.before-<动作>.blend`，比对字节数
5. 执行改动（脚本内做「三重闸 + 反向复核」）
6. **独立核验**（verify_*.py，全部用新取的引用）
7. 提醒用户：桥只改内存不存盘，满意 Ctrl+S，不满意 `File > Revert`

## 硬性技术约束

### 性能
- **禁止** `bl_rna.properties` 全属性遍历上万对象。22315 个对象全属性遍历 ≈ 7 分钟，必超 120s。
- 改用**打靶式扫描**：约束 `c.target` / 修改器指针属性 / 几何节点与材质节点的 OBJECT socket `default_value` / 驱动 `variable.targets[*].id` / `Scene.camera` / 相机 `dof.focus_object` / 粒子 `dupli_object|instance_object`。全场景 2 万对象约 12~20s。
- 少量对象（约束/修改器/节点组）才可以用 bl_rna 细扫。

### 引用判定必须排除
- `Scene.objects`、`Collection.objects`、`ViewLayer.objects` —— 是**成员关系**，不是引用，否则全场景对象都会被标成"被引用"
- `ID.original` —— 副本来源指针，同样不是逻辑引用
- 判断"空物体能不能删"：`ob.type == 'EMPTY'` **且** `len(ob.children) == 0` **且** 无任何逻辑引用
- 迭代剪枝（删完无子级的会"长出"新的无子级）：某 EMPTY 是否"必须保留" = 其**后代里存在非 EMPTY 对象**。这样自动保护所有撑着网格/相机的链条，且已删叶子不会让 MESH 失去父级。

### Blender 4.4+/5.x API
- **没有 `action.fcurves`**。取 fcurve 走 Slotted Action：
  ```python
  for layer in a.layers:
      for strip in layer.strips:
          for cb in strip.channelbags:   # ActionKeyframeStrip 无 .name
              for fc in cb.fcurves: ...
  ```
- 一个 Action 可能被上千对象共享（每对象一个 slot），`frame_range` 对无关键帧的 slot 返回 `(0.0, 0.0)`

### 删除与核验
- `bpy.data.objects.remove(o, do_unlink=True)`
- **删除后旧引用立即失效**：被删对象的 Python 包装器**连 `o.name` 都会抛** `ReferenceError: StructRNA of type Object has been removed`
  - **所有后续要用的字段（name / users_collection / parent / animation_data / 子级数）必须在 `remove()` 之前冻结成纯 Python 值**（str/int/tuple）
  - 遍历删除时只在循环内使用当前元素，不要留到循环外再访问
  - 核验必须重新 `list(bpy.data.objects)`，绝不复用删除前的列表
  - 本机这个坑踩了两次，务必**先冻结、再删除**
- 删除脚本要把「被删名单」先落盘（`NAME/tp/COLLECTIONS/PARENT/HAS_ANIM/ACTION`），便于回溯。
- 删除前**反向复核**：遍历"将保留"的对象，收集其约束/修改器/驱动/节点 socket 引用，若命中待删集合则把该对象移出待删集并报警。
- **不要在循环里用 `ob.children` / `ob.all_objects`** —— 每个都是 O(n) 重算，17k 对象量级会卡死。自己建 `parent.name -> [child, ...]` 映射，一次 O(n)。

### 判定"贴图缺失"
- 必须带 `not img.packed_file` 条件：
  ```python
  if img.source == 'FILE' and img.filepath and not img.packed_file \
     and not os.path.exists(bpy.path.abspath(img.filepath)): ...
  ```
- 否则会把大量"路径失效但已打包"的贴图误报为缺失（本机某工程有 105 个这种）。

### 孤儿数据块
- Blender 存盘时 `users == 0` 的数据块**不会写进 .blend**，所以「显式删除」与「存盘自动丢弃」结果等价
- 反向风险：**只打包在 .blend 里、磁盘无副本**的数据块一旦变孤儿，存盘即永久丢失 → 删孤儿前必须先判磁盘有没有同名副本（或 `packed_file`）

## 相关 skill

- **`blender-scene-cleanup`** —— 基于本 skill 传输层的「工程清理」方法论：空物体收敛清理（不动点算法）、孤儿数据块、缺失贴图审计与还原，含可直接复用的脚本。
- **`blender-render-blackout-diagnose`** —— 基于本 skill 传输层的「画面不对」诊断：渲染发黑 / 材质不发光（材质覆盖、引擎不读材质、Holdout、输出未连线或改错节点、AgX 压暗）。

## 本机路径约定

- 工程：`E:\Downloads\260910\260910xAx01\260912xAx02.blend`
- 还原点目录：`E:\Downloads\260910\260910xAx01\_backup\`
- 工作目录：`C:\Users\wandou\WorkBuddy\<时间戳>\blender_control\`
- 桥脚本在桌面另有一份副本：`E:\Desktop\blender_bridge.py`
