---
name: blender-volume-beam-feather
description: 让射灯(SPOT)的光柱在 Cycles/EEVEE 里可见并**边缘柔和、两端自然收尾** —— 闭合锥体当体积域 + 局部体积材质,把同一个渐变**同时接到 Density 和 Emission Strength**(只接 Density 是白费:Principled Volume 的 Emission 不受密度控制),轴向再用**端点精确到 0 的平滑渐变**避免远端被平切。当需要「光柱可见」「光束羽化」「体积光」「假体积光锥」「舞台光柱阵列」「光斑边缘太硬」「光柱远端/末端是硬的平切」时使用。含 5.2 节点引用失效坑、驱动器做参数滑块的正确姿势、ColorRamp 色标不可节点驱动、多灯共用一份材质的条件,以及**绝不在用户会话里跑换文件级 operator** 的血泪铁律。
agent_created: true
---

# 体积光柱羽化

## 何时用

- 射灯要出**可见的光柱**（舞台光、阵列光）
- 已经有锥体但**边缘太硬**，像塑料柱而不是光
- **远端（粗的那头）被平切**，像被刀切平的
- 想给光锥参数做**能手动拖的滑块**

## 为什么看不见 / 为什么硬（先想清楚再动手）

| 现象 | 原因 |
|---|---|
| 真空里看不见光柱 | 光线追踪只记录"射到相机的光"；无介质 ⇒ 光子直线穿过。实测纯黑世界下非零像素 **0** |
| 假几何锥永远硬 | 亮度来自"**锥面被照亮**"，看到的是前后两层壳，边缘就是网格边界 |
| 体积锥也还硬 | 均匀密度横向亮度 ∝ `2√(R²−d²)`，贴边处导数发散 |
| **加了径向渐变还是硬** | ★ **`Principled Volume` 的 Emission 不受 `Density` 控制** |
| **远端是一条水平硬边** | 轴向衰减底值不是 0 ⇒ 端面圆盘带残余亮度被几何**一刀切** |

**★ 决定性证据 1**（务必自己复现一次再信）：

| `Density` 接常量 | 渲染峰值 |
|---|---|
| `Value = 0.0`（零浓度） | **19.74** |
| `Value = 0.8` | **17.32** |

零浓度**依然亮**，而且**更亮**（浓度低 → 吸收少 → 自发光累积更多）。
⇒ 边缘硬度来自"**发光是均匀的**"。修法：渐变**同时接到 `Emission Strength`**。
实测过渡宽度 **6px → 18px（3 倍）**。

**★ 决定性证据 2**：轴向用线性斜坡映到 `0.05…1.0` 时，几何末端仍留 **5%** 亮度，
端面被硬切 ⇒ 正交侧视下是**一条平切水平边**。改成**精确到 0 的平滑渐变**后远端溶进黑暗。

## 铁律

1. ★★★ **绝不在用户正在用的会话里执行换文件级 operator**
   （`read_factory_settings` / `read_homefile` / `wm.open_mainfile`）。
   实测把会话卡死并崩溃，**未存盘改动全丢**。
   要空场景做实验 → 另开 `blender.exe -b --factory-startup --python x.py`。
   桥**只跑读写当前 .blend 内存**的脚本。

2. ★★★ **渐变必须同时接 `Density` 和 `Emission Strength`**。
   建完材质后**回读连线数**，`Emission Strength` 必须 = 1，否则羽化根本没生效。

3. ★★★ **轴向渐变的端点必须精确到 0**，且用**平滑**插值（`SMOOTHSTEP`）。
   线性斜坡底值留 5% ⇒ 远端被几何平切出硬边。
   想让远端"实"一点 → 调小「尾部羽化」，别去动插值类型。

4. ★★ **5.2 里 `nodes.remove()` 后旧节点引用会失效**
   —— 删完必须**重新遍历 `nt.nodes` 取输出节点**，绝不跨删除持有引用。
   症状：`out.name` 读乱码（`UnicodeDecodeError`）、`out.inputs["Volume"]` 抛 `KeyError`、
   或**链接静默丢失**（不报错但没接上）。

5. ★★ **改自定义属性后依赖图不会自动重算**，脚本里要 `id.update_tag()`。
   GUI 拖滑块 Blender 会自动打 tag ⇒ 用户手上是即时的。
   驱动器求值**有延迟**：同一次脚本内"改属性→立刻读插槽"读到的是**旧值**。

6. ★ **要"渐变终点可调"就别用 `ColorRamp` 节点**
   —— 它的色标位置 `color_ramp.elements[1].position` **没有输入插槽**，连不上 `Value` 节点。
   用 **`MapRange` 的 `From Max`（是 socket）**，可直接接滑块。

7. ★ **驱动器用 `AVERAGE`（单变量、无表达式）**，别用 `SCRIPTED`
   —— 后者在非受信任打开的 .blend 里静默不求值（见主题 45）。
   `DriverTarget` 必须先设 `id_type`，再赋 `id`。

8. ★ **材质里烘焙了 `R` / `L` 常量** ⇒ 只有 `spot_size` 与 `cutoff_distance`
   **完全一致**的灯才能共用一份材质。不一致就一灯一材质。

9. ★ **体积域必须是闭合网格**（`end_fill_type='TRIFAN'` / `'NGON'`）。

## 作业循环

```
① 探查   → probe_beam.py      灯清单 + 几何签名 + 已有锥 + 材质/驱动器
② 建材质 → build_feather_material.py   （读样板锥的 L/R；建 4 个滑块属性 + 4 条驱动器）
③ 批量建锥 → add_cones_all_lights.py   （共享材质；几何签名不一致会主动中止）
④ 核验   → verify_beam.py      （**必须另跑一次**，末尾 PASS/FAIL）
⑤ 撤销   → undo_beam.py        （DRY_RUN=True 先看清单）
```

## 节点链

```
u      = MapRange(z, zmin … zmax → 0 … 1)                    0=远端粗端, 1=近灯细端
轴向项  = MapRange(u, 0 … 尾部羽化 → 0 … 1, SMOOTHSTEP)       ★ 端点精确到 0
径向项  = 1 − ρ^p

fall = 轴向项 × 径向项

ρ = √(x²+y²) / radius(z),   radius(z) = R/2 − R·z/L
（锥体局部坐标：apex 在 z=+L/2 半径 0，底面 z=−L/2 半径 R）

Density           ← fall × 浓度
Emission Strength ← fall × 亮度      ★ 关键
```

实现细节：

- 分母 `MAXIMUM(radius(z), 0.0001)` 防锥尖 `0/0`
- `分离XYZ → 合并XYZ(x,y,0) → 向量数学 LENGTH` 取 `r`
- `POWER` 与 `SUBTRACT` 都勾 **Clamp**，结果压在 `[0,1]`
- 轴向那级 `MapRange` 要设 `interpolation_type = 'SMOOTHSTEP'`（默认 `LINEAR`）

## 参数滑块（场景自定义属性 + 驱动器）

材质节点**不上属性面板**，所以：**场景自定义属性 → 驱动器 → 节点里的 Value**。

```python
sc["光锥羽化"] = 1.0
sc.id_properties_ui("光锥羽化").update(
    description="...", min=0.1, max=8.0, soft_min=0.5, soft_max=4.0)   # 设 min/max 才变滑块

fc = value_node.outputs[0].driver_add("default_value")
d = fc.driver; d.type = 'AVERAGE'
var = d.variables.new(); var.name = "v"; var.type = 'SINGLE_PROP'
tgt = var.targets[0]
tgt.id_type = 'SCENE'                    # ★ 先 id_type 后 id
tgt.id = sc
tgt.data_path = '["光锥羽化"]'
```

**自定义属性的键名就是显示名** —— 要中文标签，键本身就得是中文。

位置：`Scene → 属性编辑器 → 「场景」标签 → 最底下的「自定义属性」`。

## 参数速查

| 参数 | 默认 | 范围 | 说明 |
|---|---|---|---|
| 光锥羽化（径向） | 1.0 | 0.1 ~ 8 | 越小越柔，同时越暗 |
| **光锥尾部羽化（轴向）** | **1.0** | 0.15 ~ 1.0 | **越大 → 渐变越长 → 远端越柔**；1.0 是数学极限 |
| 光锥浓度 | 0.8 | 0 ~ 3 | **不影响自发光亮度**，别指望它调亮 |
| 光锥亮度 | 2.5 | 0 ~ 20 | 主要亮度旋钮；羽化变柔后用它补 |
| Anisotropy | 0.40 | — | 轻微前向散射 |
| 渲染成本 | 400×400 / 64 samples ≈ 1.6 s | — | 体积域小，并不慢 |

档位实测：
- 径向（过渡宽度，越大越柔）：`0.1→297px / 0.5→277px / 1.0→260px / 2.5→239px / 4.0→230px`
- 轴向（远端 80% 处亮度）：`1.0→0.533 / 0.70→0.645 / 0.40→0.825`（越小越"实"）

**羽化越强越暗**，用亮度补偿。

## 核验判据

| 项 | 判据 |
|---|---|
| 可见性 | 纯黑世界：只有灯 vs 灯+锥 → 比**非零像素数**；锥体 `hide_render=True` 应归零 |
| 边缘软硬 | 扫描线上 **50% / 10% 阈值之间跨度**（越大越柔）—— **别靠肉眼** |
| **远端收尾** | **沿轴向取样**（正交侧视最方便，整根入画）：末端必须**单调趋 0、无台阶** |
| 轴对齐 | `axis_dot` = 1.000000 |
| 落点 | `apex_offset` ≈ 0 |
| 材质共享 | `mat.users` = 锥体数 |
| 连线 | `Density` / `Emission Strength` / `Volume` / **`尾部羽化→FromMax`** 各 **1** 条 |
| 驱动器 | **跨事件**验证：改属性 + `update_tag()`，下一次独立执行再读插槽 |

## 5.2 实测 API 差异

| 想做的事 | 5.2 的正确写法 |
|---|---|
| 查插槽有没有被驱动 | **`NodeSocketFloat` 没有 `.is_driven`** → 翻 `nt.animation_data.drivers` 的 `data_path` |
| 自定义属性变滑块 | `id_properties_ui(key).update(min=…, max=…)` |
| 让渐变终点可调 | **`ColorRamp` 的色标位置连不上节点** → 用 `MapRange` 的 `From Max` socket |
| 检查驱动器有效性 | `driver.is_valid`；`FCURVE.evaluate()` 对驱动器**不返回驱动值**，别用它验证 |

## 常见误报

- **按名字筛对象**别用 `endswith` 拼中文名：`endswith("_光锥")` 会漏掉 `射灯_光_锥`（是 `光_锥`），
  实测因此向用户误报"那个对象已不存在"。宁可放宽成 `"锥" in name`。
- **别靠肉眼判断边缘软硬**：渲染出来都"看着差不多"，必须量阈值跨度/轴向剖面。
- 桥的 exec 是**整段代码**：任何一行抛异常，**前面所有 print 全丢** ⇒ 脚本整体 `try/except` 打 traceback。
