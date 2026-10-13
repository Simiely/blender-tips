---
name: blender-radar-scan-material
description: 通过本地桥给 Blender 做「雷达扫描」**空间材质**（不用 UV）—— 一块平面/网格体上出现绕中心匀速旋转的扫描头 + 拖尾扇面 + 同心圆网格 + 中心亮点，且**沿某个世界轴投射**（图案沿该轴无变化，平移物体画面逐像素不变）。当用户说「做个雷达扫描效果」「扫描头绕圈转」「扫描线/拖尾」「像雷达那样扫」「C4D/Canvas 那个雷达效果搬到 Blender」「不是 UV，是空间材质」「沿 Y 轴投射 / 沿某轴投射」「图案不要贴图、跟物体位置无关」「扫描条数 / 拖尾长度 / 扫描速度 / 正反向」「加同心圆网格 / 中心亮点」「按原来的 HTML/JS 效果复刻」时使用。核心是**极坐标角度场** `u = (atan2(Z, X) + π) / 2π`（只取两个分量 ⇒ 天然沿第三个轴投射）+ **多扫描条相位** `D = frac(条数×时刻 − 方向×条数×u)`（★ 方向**只能进角项**，进时间项会导致旋钮按了不反向）+ `FLOORED_MODULO`（普通 MODULO 负值裁剪 ⇒ 跨 0° 拖尾断头）+ 拖尾走 **Math 域**（`MapRange` + `POWER`，别让 ColorRamp 兼职）。含 12 参数控制空物体 + `SINGLE_PROP` 驱动、Blender 5.2 无 `ShaderNodeSceneTime` 改用 Value 节点 + 驱动、正交正视渲染 + 像素测转角/数条数/md5 验投射的可证伪核验法。
agent_created: true
---

# 雷达扫描空间材质（Y 轴投射 · 极坐标角度扫掠 + 拖尾）

> 一句话：把扫描头角度写成极坐标 `u = (atan2(Z, X) + π) / 2π`，
> 让「头部」位置 `u = 方向×时刻` 随时间推进，`D = frac(条数×时刻 − 方向×条数×u)`
> 就是"到最近后方扫描头"的归一化距离 ⇒ 拖尾 / 头部亮线 / 多条扇面全部由 `D` 派生。
> **只取世界 X/Z 两个分量**（Y 被丢弃）⇒ 天然**沿世界 Y 轴投射**。

**两个前置 skill，先读：**

| 需要什么 | 去哪 |
|---|---|
| 怎么把代码送进正在运行的 Blender（桥、客户端封装、120s 上限、BOM、`__file__` 不存在） | **`blender-bridge-ops`** |
| 世界空间程序化材质的**通用机制**（`纹理坐标.Object` 锚点、SINGLE_PROP 驱动、tag 矩阵、像素级验收、Math 域波形） | **`blender-procedural-emission-material`** |

**本 skill 只讲「雷达扫描」这一路独有的东西**：极坐标角度场怎么定、**方向为什么必须只进角项**、拖尾/头部线怎么由 `D` 派生、Y 投射怎么证伪。

**脚本包**：[`../scripts/radar-scan-material/`](../scripts/radar-scan-material/)（`probe_plane.py` / `build_radar_material.py` / `verify_radar_material.py`），
配套文档 [`../docs/空间雷达扫描材质.md`](../docs/空间雷达扫描材质.md)。

**实测环境**：Blender **5.2.2 LTS** / Windows。

## 铁律

1. **先只读侦察**：量出世界中心、面内半宽、**法线朝向**（确定"屏幕上看是顺时针还是逆时针"）。
2. **"不是 UV、是空间材质" ⇒ `纹理坐标.Object` 必须指向一个空物体**，
   并把该空物体**定位到目标平面的世界中心**（此时 Object 坐标 = 世界坐标相对该中心）。
3. **必须问清「沿哪个世界轴投射」**（本例 Y）——它决定**丢弃哪一个分量**，选错整个图案行为不同。
4. **方向旋钮必须真的能反向**：`方向` 只准进**角项**，绝不准进时间项（见 §2）。
5. **改动前放还原点**；旧材质块**只换槽、不删数据块**（便于回退）。
6. **执行完另起一次请求独立核验**，且核验必须是**可证伪的读数**（像素级测转角、md5 验投射），
   不能只断言"节点连对了"（见 §5）。
7. **测量前先把发光强度调小**（默认 8 会过曝到全 1.0 ⇒ 亮度剖面被压平 ⇒ 测角度的 argmax 变成随机）。

---

## §1 节点链

```
纹理坐标(Object=控制空物体) → 分离XYZ                 ★ Object 坐标 = 世界坐标相对该空物体
u  = ( atan2(世界Z, 世界X) + π ) / 2π                 ★ ARCTAN2(in0=Z, in1=X) → ADD π → ×1/2π
时刻 = frame / fps × 扫描速度 / 360                    ★ Value 节点输出 + 驱动
有向条数 = 扫描条数 × 扫描方向                          ★ 两个输入都驱动
时间项 = 时刻 × 扫描条数            ┐
角项   = u × 有向条数               ┴→ D = FLOORED_MODULO(时间项 − 角项, 1.0)
拖尾 = MapRange(D, 0 .. 条数×拖尾/360 → 1..0) ^ 拖尾曲率
头部线 = MapRange( min(D, 1−D), 0 .. 头部线宽 → 1..0 )
中心点 = MapRange( length((X,0,Z)), 0 .. 中心点半径 → 1..0 )
网格   = MapRange( frac( r ÷ (亮面半径/环数) ), 0 .. 0.05 → 1..0 ) × 网格亮度
掩码 = min(拖尾 + 头部线 + 中心点 + 网格, 1) × 亮面裁切(r − 亮面半径, 0..淡出宽度 → 1..0)
掩码 × 发光强度 → Emission Strength ; RGB(白) → Emission Color ; Base Color=黑
```

- **Y 投射 = 只连 `X` / `Z` 两个输出**，`Y` 输出悬空不接 —— 这就是"投影"的全部。
- **半径用 `CombineXYZ` 把 Y 填 0** 再 `VectorMath(LENGTH)` ⇒ `r = √(X²+Z²)`，
  与投影平面内的极坐标半径一致（直接对 Object 坐标取 length 会带上 Y 分量，**半径就错了**）。
- 拖尾**越靠尾部越暗**：用 `Math POWER` 对 `MapRange` 的线性结果取幂（参考 HTML 的 `pow(fade, 1.8)`）。

## §2 ★★ 方向必须只进「角项」（本 skill 最值钱的一节）

**症状**：把 `方向` 从 `1` 拨到 `−1`，扫描头**还是朝同一方向走**，只是拖尾换了边。

**根因（数学）**：

```
错法：D = frac( 方向 × 条数 × (时刻 − u) )
      ∵ frac(−x) 与 frac(x) 的【值域】只差一个补数，
        令 t' = 1 − t 可验证其【头位置集合】与正向完全相同
      ⇒ 头位置仍是 u = +时刻（不随方向翻转）
```

**正解**：

```
正解：D = frac( 条数 × 时刻 − 方向 × 条数 × u )
      ∂D/∂u = −方向×条数  ⇒ 头位置 D=0 ⇒ u = 方向×时刻
      ⇒ 方向 = ±1 真正决定 u 的推进方向
```

**落地三条硬约束**：

1. **时间项 = `时刻 × 扫描条数`（不含方向）**；**角项 = `u × (方向 × 扫描条数)`**。
2. **`有向条数` 节点的两个输入都挂驱动**（`inputs[0] ← 扫描条数`、`inputs[1] ← 扫描方向`）。
3. **「有向条数 → 时间项」这条连线绝对不能连** —— 连线会**盖过** `时间项.inputs[1]` 上的驱动值，
   届时时间项会变成 `时刻×方向×条数`，方向又只进时间项 ⇒ 退回症状。

> **判据（机器可验）**：`时间项` 的 `inputs[1]` 上游只能是**驱动**（无连线进入），
> `角项` 的 `inputs[1]` 上游必须是 `有向条数`。核验脚本已按此断言（见 §5）。

## §3 `FLOORED_MODULO` 与跨 0° 无缝

- `D = frac(x)` 必须实现成 **`Math` 的 `FLOORED_MODULO`（取模 1.0）**。
- **普通 `MODULO` 对负值裁剪**：`x<0` 时返回负值 ⇒ 扫描头跨过 `u=0`（= 0°）那一瞬间，
  拖尾扇面的角度区间出现负值 ⇒ **拖尾断头/整块消失一帧**。
- 参考实现（HTML）：`D` 本身取 `(x % 1 + 1) % 1` 的手写环绕 —— 与 `FLOORED_MODULO` 等价。

## §4 ★★ 别让「域」混用：波形一律 Math 域，ColorRamp 只管颜色

- **拖尾 / 头部线 / 网格环带** 的亮度掩码全部是 `MapRange(LINEAR, clamp)`
  （+ `POWER` 调曲率），**不经过 ColorRamp**。
- 让 ColorRamp 兼职做波形会：参数耦合（一个滑块同时改亮度和形状）、色标被驱动锁死、
  拖尾长度被结构卡死（此法在姊妹 skill `blender-cylinder-spiral-material` 已被实测打回）。
- 本例只有一个颜色（白），**直接用 RGB 节点**，节点树里**一个 ColorRamp 都没有**。

**★「亮面面积」与「拖尾长度」是两个正交旋钮**：

| 用户说的 | 该动哪个 |
|---|---|
| 拖尾太长/太短 | `拖尾长度`（度） |
| 发光范围收紧 / 四角要黑 | `亮面半径` + `淡出宽度` |

（同 `blender-inward-pulse-material` 的裁切 vs 占空比，别混成一个。）

## §5 ★★ 可证伪核验：正交正视渲染 + 像素级读数

**只有"结构断言"是不够的** —— 本例中一个**数学建模错误**（方向进错项，§2）
在纯结构断言下完全隐形。核验必须把材质**渲染出来**、**量像素**：

1. **沿法线正交正视**：临时相机 `center + normal*30`、`type='ORTHO'`、
   `ortho_scale = 最大边span × 0.98`、`to_track_quat('-Z','Y')`；`film_transparent=True`、
   `view_transform='Standard'`（**别用 AgX，会把对比压平**）、`dither_intensity=0`、
   其余对象 `hide_render=True`。
2. **采样一圈亮度**：按 `u = i/N` 反演 `X = r·cos(2πu−π)`、`Z = r·sin(2πu−π)`
   （与材质 `u=(atan2(Z,X)+π)/2π` 严格互逆），取该像素亮度 ⇒ 得到 `(u, lum)` 剖面。
3. **测转角**：`count=1` 时剖面只有一个亮峰，取 `argmax(u)`；帧 1→31 的角度差 = 转速，
   与期望 `30/fps × 速度` 比对（实测 **+109° vs 期望 +110°，误差 1°**）。
4. **测反向**：`方向=−1` 重跑，应得相反符号（实测 **−110°**）。
5. **数条数**：`count=5` 时数剖面里的亮峰个数（实测 **5**）。
6. **证 Y 投射**：平面**沿世界 Y 平移 2m**，正交投影下画面应**逐像素不变**
   ⇒ 比两张渲染 PNG 的 **md5**（实测同值 `5a72afe178`）。这是"图案与 Y 无关"的**机器可判据**。
7. **读驱动真值**：**别用 `fcurve.evaluate(frame)`**（读到的是帧号本身，实测打印 1.0/31.0）；
   要在**渲染后读被驱动插槽的 `default_value`**（实测 `0.01019 / 0.31574` 与期望逐位一致）。
8. **先调低发光强度**：默认 8 会过曝到全 1.0 ⇒ 剖面被压平 ⇒ `argmax` 随机、测角无意义。
   核验里用 `CHECK_GAIN = 1.0`。
9. **收尾必须还原**：快照引擎/分辨率/`film_transparent`/`view_transform`/`dither`/帧号/
   各对象 `hide_render`/被改的参数，临时相机用完 `remove`。

## §6 Blender 5.2 环境事实（实测）

| 事实 | 说明 |
|---|---|
| **`ShaderNodeSceneTime` 不存在** | `bpy.types` 全量探查：5.2 无任何 `ShaderNode*Time*`（只有 `CompositorNodeSceneTime` / `GeometryNodeInputSceneTime`）⇒ 时间源 = **`ShaderNodeValue` 输出 + 驱动** `fr / fps * sp / 360.0` |
| **`nt.driver_add(path)` 标量属性不能传 index** | 传 `0` 报 `driver_add(): index 0 was given while property ... is not an array`（本路首轮就踩到） |
| **`MapRange` 有 VALUE / VECTOR 两套同名插槽** | 一律用**索引**取：VALUE = `0..5`（Value / From Min / From Max / To Min / To Max / Steps）；按名字会撞 |
| **`ShaderNodeMath` 支持 `ARCTAN2` / `FLOORED_MODULO`** | `ARCTAN2` 的 `in0` = y、`in1` = x ⇒ **`in0 ← Z`、`in1 ← X`**（顺序反了图案镜像） |
| **`VectorMath` 节点 `type` 是 `'VECT_MATH'`** | `operation='LENGTH'`，长度在 `outputs[1]` |
| **改自定义属性后脚本里画面不刷新** | 必须 `ctl.update_tag()` + `bpy.context.view_layer.update()`；GUI 拖滑块 Blender 自动打 tag |

## §7 坑表（本路实测）

| # | 坑 | 正解 |
|---|---|---|
| 1 | `方向` 拨 −1 扫描头**不反向** | 方向**只进角项**：`D = frac(条数×时刻 − 方向×条数×u)`（§2） |
| 2 | 连线「有向条数 → 时间项」把驱动值**盖掉** | 该线一律不连，时间项 `inputs[1]` 只挂驱动 |
| 3 | 用普通 `MODULO` ⇒ 跨 0° 拖尾断头 | 用 `FLOORED_MODULO`（§3） |
| 4 | `ARCTAN2` 的 y/x 接反 ⇒ 图案镜像 | `in0 ← Z`、`in1 ← X` |
| 5 | 半径算错（直接对 Object 坐标取 length 带上 Y） | `CombineXYZ` 填 `(X, 0, Z)` 再 `LENGTH` |
| 6 | 时间源找 `ShaderNodeSceneTime`（5.2 不存在） | `ShaderNodeValue` 输出 + 驱动 |
| 7 | `driver_add(path, 0)` 报 not an array | 标量属性**不传 index** |
| 8 | `MapRange` 按名字取插槽撞 VALUE/VECTOR | 用索引 `0..5` |
| 9 | 核验只断言结构 ⇒ **方向 bug 隐形** | 渲染 + 像素级测转角/反向/条数（§5） |
| 10 | 测量时发光强度 8 ⇒ 过曝、argmax 随机 | 测量前 `CHECK_GAIN=1.0`（§5.8） |
| 11 | 用 `fcurve.evaluate(frame)` 读驱动真值 ⇒ 读到帧号 | 渲染后读被驱动插槽 `default_value`（§5.7） |
| 12 | 核验没还原就结束 ⇒ 用户场景被改 | `try/finally` 快照还原（引擎/相机/渲染/参数/帧号） |
| 13 | 直接对平面**换材质**会丢旧材质块 | 只换 `slot.material`/`link`，**不删旧数据块**（便于回退） |
| 14 | 送桥脚本带 BOM ⇒ SyntaxError | 用 `[System.IO.File]::WriteAllText(..., UTF8Encoding($false))`（`blender-bridge-ops`） |
| 15 | 桥 exec 里 `__file__` 不存在 | 脚本内路径写**绝对常量**（`verify` 顶部 `OUT_DIR`） |

## §8 交付物

1. **只读侦察脚本**（`probe_plane.py`）：中心 / 面内半宽 / 朝向（法线）/ 材质槽
2. **幂等建脚本**（`build_radar_material.py`，配置区置顶：`PLANE` / `MAT` / `CTRL` / `COLL` / `DEFAULTS`）
3. **独立核验脚本**（`verify_radar_material.py`，另起请求；结构 + 驱动真值 + 像素测转角/反向/条数 + md5 验 Y 投射 + 快照还原）
4. **说明文档**：效果 / 公式推导（含方向 bug 的纠错）/ 参数表 / 实测数据 / 文件清单
5. **撤回路径**：删材质 + 控制器 + 槽 0 换回旧材质（本路**无面板、无文本块**，撤回干净）
6. 提醒 **Ctrl+S**（桥只改内存）；**别用 `File > Revert`**（会丢所有未保存改动）
7. 如果用户要**实时拖滑块面板**或**网格十字线**：明确告知**本路未做**，别默默省略

## §9 出处

- 来源：用户提供的一份 **Canvas/HTML 雷达扫描动画**（速度 110°/s、5 条、拖尾 129°、
  顺时针/逆时针、同心圆网格、白色），要求**复刻成 Blender 空间材质、沿 Y 轴投射**，2026-10-14 实战
  （Blender 5.2.2 LTS；目标网格「平面」，法线朝 −Y，世界中心 `(0.03, 0.14, −1.66)`，面内半宽 ≈1.77）。
- 同族 skill：`blender-radial-pulse-material`（径向距离场 + 时间链）、
  `blender-inward-pulse-material`（径向距离场 + 周期环带）、
  `blender-cylinder-spiral-material`（柱面角度扫掠 —— 「Math 域波形」的出处），
  母 skill 均为 `blender-procedural-emission-material`。
