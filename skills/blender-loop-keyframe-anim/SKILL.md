---
name: blender-loop-keyframe-anim
description: 通过本地 9877 桥给运行中 Blender 的自定义属性批量写「循环三角波关键帧动画」——一个完整周期写进 fcurve + CYCLES 循环修饰器铺满帧范围，贝塞尔自然缓入缓出。当用户说「从第 a 帧到第 b 帧，每 n 帧一个周期，从低到高再到低，循环」「发光强度做呼吸动画，8→13→8 每 30 帧」「面光统一强度让它在 1–450 帧循环」「给这几个参数各打一套周期循环关键帧」时使用。含 Slotted Action 正确写入路径（fcurves.new）、CYCLES 循环修饰器（5.x 无 mode 属性）、is_valid=False 判空、drivers 定位、depsgraph 侧改值—验证分离、关键帧值精确写入（绕开"改属性当前值被驱动/求值干扰"的坑）。
agent_created: true
---

# 给自定义属性写「循环三角波关键帧动画」

传输层（9877 桥、客户端封装、120s 上限、Slotted Action 读取路径、删除后引用失效）见 **`blender-bridge-ops`** skill。
定位 fcurve / 打单个关键帧 / 插值机制的手册式说明另见仓库文档 `docs/技巧速查.md §3/§4/§5`。
本 skill 专讲「**用代码给一批自定义属性批量写一个周期 + 循环修饰器**」这一套完整可复用流程。
**核心结论先行**：单周期关键帧（如 `(1,8)→(16,13)→(31,8)` 三点）+ `CYCLES` 修饰器铺满范围，
比「手动把 90 个台阶逐帧打全」可靠得多 —— 既有真实循环、又可在任意帧验证。

## 铁律

1. **先只读侦察**：对象是否已有 action / layer / slot / 该属性是否已有 fcurve（见 §1）
2. **先建干跑副本再实验**：用一个临时空对象试一条周期，笔法确认正确再批量（见 §2 自检段）
3. **改动前放还原点**（`blender-bridge-ops` 的纪律；存盘 `.blend_before_*.blend` 副本文档可回滚）
4. **写入与验证分两次请求**：同一次 `exec` 内改完立即读会读到未刷新缓存（AGENTS.md 既有红字），
   验证一律**新起一次请求、重新取引用、重新读 socket 值**
5. **判据取差集 / 覆盖到整段**：循环动画要逐帧求值，抽样关键帧（周期起点/峰值/终点/末帧）确认周期 + 循环一致
6. **单次只处理一个矛盾点**，卡住就暂停

---

## §1 先只读侦察：定位动画挂在哪个 action / channelbag

要往**自定义属性**写关键帧，先确认它落在哪个 action 的哪个 slot：

```python
import bpy
obj = bpy.data.objects["竖向灯001_噪波控制"]
ad = obj.animation_data
a = ad.action
print("action:", a.name if a else None)
print("layers:", len(a.layers) if a else None)
for layer in a.layers:
    for strip in layer.strips:
        for cb in strip.channelbags:
            print("channelbag fcurves:", [fc.data_path for fc in cb.fcurves])
```

> 5.x Slotted Action 里**自定义属性的 fcurve 也住在 channelbag**（与位置/旋转同层）；
> 读已存在的：`action.layers → layer.strips → strip.channelbags → cb.fcurves → fc.keyframe_points`
> （与 `blender-bridge-ops` 一致）。`ActionSlot` 没有 `fcurves` 属性，别 `slot.fcurves`。

## §2 正确写入：`channelbags[0].fcurves.new(...)` + 单周期 + CYCLES

**要在目标 channelbag 里新建一条属性 fcurve**（不是 `action.fcurve_ensure_for_datablock`，
那个是定位/读默认通道用的；新建自定义属性的干净写入用 `channelbag` 的 fcurves collection）：

```python
cb = a.layers[0].strips[0].channelbags[0]   # 目标对象的 channelbag
fcurves = cb.fcurves

# 幂等：先删掉同路径旧 fcurve，避免残留叠加
for fc in list(fcurves):
    if fc.data_path == datapath:
        fcurves.remove(fc)

fc = fcurves.new(datapath, index=0)         # ★ 参数名是 index=0（不是 action_group）
```

**写一个完整周期 + 末帧补一遍起始值**（例：30 帧周期 8→13→8，从帧 1 起）：

```python
pts = [(1, 8.0), (16, 13.0), (31, 8.0)]     # (帧, 值)；末帧 31 重复起始值 8 做无缝
kps = fc.keyframe_points
full = pts                                   # 末帧已含起始值，无需再补
kps.add(len(full))
for i, (fr, val) in enumerate(full):
    kp = kps[i]
    kp.co = (float(fr), float(val))
    kp.interpolation = 'BEZIER'              # 贝塞尔 → 缓入缓出（天然平滑三角波）
fc.update()
```

**加 CYCLES 循环修饰器铺满帧范围**（Blender 5.x）：

```python
m = fc.modifiers.new('CYCLES')
# ★ 5.x 的 FModifierCycles 没有 mode 属性（旧 REPEAT/REVERSE 枚举已移除），默认即正向循环
m.frame_start = 1.0
m.frame_end = 450.0
fc.update()
```

> ⚠️ **CYCLES 修饰器的 `mode` 在 5.x 不存在**：`m.mode = 'REPEAT'` 会 `AttributeError` —— 直接跳过，默认为正向重复。
> ⚠️ `fcurves.new(data_path, index=0)` 的第一个参数名是 `index`，不是 `action_group`/`group`；写成后者直接 `TypeError`。
> ⚠️ 保存前确认 `scene.frame_start/end` 覆盖动画区间；若目标帧范围不是从 1 起，`frame_start` 用周期首帧。

**关键帧值精确写入（绕坑）**：不要用「`obj[prop] = 值` 然后 `keyframe_insert`」——当该属性**同时被节点驱动引用**
（如材质发光强度被 `SINGLE_PROP` 驱动当 `st`）时，属性当前值会被驱动求值干扰，插出来的帧值错乱。
**正解 = 直接构造 fcurve 的关键帧坐标**（上面写法），不依赖属性当前值。

## §3 验证（独立请求，覆盖整段）

逐帧求值 + 关键帧到位检查，两问缺一不可：

```python
# 1) 关键帧是否精确落在预期帧/值（BEZIER 时峰值帧后的实际值≈峰值）
for fc in cb.fcurves:
    if fc.data_path == datapath:
        print("keys:", [(int(k.co[0]), k.co[1]) for k in fc.keyframe_points])
        print("mods:", [m.type for m in fc.modifiers])
        # 抽查若干帧的循环求值
        for fr in (1, 峰值帧, 末帧, 450):
            print(fr, "->", round(fc.evaluate(fr), 2))
# 2) 驱动的联动（若有）：改属性→depegraph 刷新后读被驱动节点
for val in (0.0, 30.0, 100.0):
    obj[NEW] = val
    dg = bpy.context.evaluated_depsgraph_get(); dg.update()
    # 读被驱动节点/目标 —— 必须经 depsgraph 求值，不能直读 default_value
```

> ⚠️ **读被驱动节点值必须走 depsgraph，且要先 update_tag 并全量更新**：
> 直读 `nodes[...].inputs[...].default_value` 或 `evaluated_depsgraph_get().id_eval_get(...)` 后若不强制
> `dg.update()`，会读到**静态默认/未重算缓存**（常见恒为 1.0 / 0.0），误以为"驱动没生效"。
> 正解：对相关对象 `obj.update_tag()` + `dg.update()` 后**再**读 target 求值结果。
> （`FModifierCycles`/fcurve `evaluate(frame)` 返回恒定值也常见 —— 那是 API 对循环外插的处理，不代表失败。）

## §4 驱动 is_valid=False 的快速排查（与本次同源）

现象：驱动面板引用齐全（变量名、target 都对）、手动求值也正确，但 `d.is_valid == False`、
depsgraph 求值恒回基准值。按优先级查：

1. **驱动挂在了「output 悬空」的节点上**：本 skill 最常踩 —— 树里有两个同名节点，
   一个真的接到输出、一个 output 没接线；驱动加在这个哑节点上，is_valid 恒 False 且不影响画面。
   → 先打印「要驱动的这个 input 最终连到哪」，确认它**真的通向输出**（如 `自发光.Strength`）再动。
2. **直接改了 `t.data_path` 刷新失败**：重建驱动（删旧 fcurve + `driver_add` 重新整）比修补稳妥。
3. **脚本内改 `obj[prop]` 后驱动不重算**：`obj.update_tag()` + `view_layer.update()`。

## 脚本

- `scripts/write_loop_anim.py` — 给一批自定义属性批量写「周期(帧,值)表 + CYCLES 循环修饰器」的参考实现
- `scripts/verify_loop_anim.py` — 独立核验：关键帧帧号/值、插值类型、CYCLES 修饰器、逐帧循环求值抽样

> 脚本顶部 `TARGET_OBJ`、`ANIMS`(周期表)、`FRAME_END_GLOBAL` 需按场景改（写入/验证两脚本的 `ANIMS` 字段要勾稽一致）；同一 skill 下口径一致。