---
name: blender-plane-procedural-material
description: 通过本地 9877 桥做「平面（flat plane）」这一路的程序化材质：平面专属的坐标/朝向处理、把平面当材质验收测试卡（test card）出客观读数，以及像素级测量（滚动方向/位移）的正确判据。当用户说「我在场景里贴了个平面试材质」「平面上是全发光/没有暗区」「平面上的噪波看不出层次」「帮我复现平面的效果」「用一块平板验证材质对不对」「测一下这个材质滚动是朝哪边走」时使用。含：平面必有零跨度轴（法线轴）导致该轴 Scale 失效、Generated 在平面上的退化轴、平面=噪声体切片（沿面内轴=滑动 / 沿法线轴=换切片）、官方手册关于 planar surface 条带与 fBm 恒 0.5 的原文、沿法线正交正视渲染（防看到一条缝）、ortho_scale 溢出取纯平面读数、AgX vs Standard 读数差异、render.dither_intensity 必须关、互相关要求位移≪相关长度、空对照（同帧渲两次）。
agent_created: true
---

# 平面（flat plane）程序化材质 + 验收测试卡

**先读 `blender-procedural-emission-material`**（母 skill）：节点链模板（`纹理坐标→Mapping→噪波4D→ColorRamp→×强度→Emission`）、
ColorRamp 才是对比度、SINGLE_PROP 驱动、刷新机制、预览渲染的坑，都在那边。
**本 skill 只讲平面独有的事**：几何/坐标的退化、平面专属的坑、以及"把平面当测试卡量材质"。

传输层（9877 桥、120s 上限）见 `blender-bridge-ops`。

---

## §0 一句话心智模型

> **平面 = 一把切进 3D 噪声体里的"扫描刀"。**
> 平面上看到的图案，就是噪声体在某个位置上的**一张横截面**。
> 沿**面内轴**平移采样点 ⇒ 图案在平面上**滑动**；
> 沿**法线轴**平移采样点 ⇒ 换一张横截面 ⇒ 图案**原地演化**（不是滑动）。

推论（很重要）：**平面在法线方向几何跨度为零，所以"滚动"只能靠 Mapping 的 Location，
不能用 Scale**（0 × 任何数 = 0，该轴缩放在平面上恒无效果）。

---

## §1 拿到平面先量三件事（别信描述，量出来）

```python
mw = obj.matrix_world
pts = [mw @ v.co for v in obj.data.vertices]
span = [max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)]
flat_axes = [i for i, s in enumerate(span) if s < 1e-5]      # ← 零跨度轴 = 平面法线方向
```

### 实测样例（本项目，2026-09-13）

| | `平面`（用户自贴的测试片） | `水晶走廊_竖向灯.001`（细丝灯带） |
|---|---|---|
| 顶点 / 面 | **4 / 1** | 45,428 / 84,208 |
| 局部范围 | `[-1,-1,0] … [1,1,0]`（**2×2 单位方片**） | 三个轴都很大 |
| scale | `4.1795` | `0.0414` |
| 旋转 | `(90°, 0, 0)` | `(-68.75°, 90°, 0)` |
| 世界尺寸 | 8.359 / **0.0** / 8.359 | 26.353 / 2.4407 / 3.088 |
| **世界零跨度轴** | **Y** | 无 |
| 世界法线 | `(0, -1, 0)` | `(0.263, -0.965, 0.000)` |
| 纹理坐标(Object) span | 8.359 / **0** / 8.359 | 三轴皆非 0 |
| Generated 局部 span | 2.0 / 2.0 / **0.0** | 74.5 / 592.7 / 230.5 |
| UV 层 | `UV贴图`，u/v 都恰好 **[0,1]** | `UVChannel_1` |

三条可以直接抄的结论：
1. **平面必有一个轴世界跨度为 0**（就是法线方向）。先把它找出来，后面所有判断都依赖它。
2. **`Generated` 坐标在平面上是退化的**：包围盒归一后，法线轴的 span 也是 0 ⇒
   "0..1 归一"在那个轴上没有意义。想改该轴只能用 **Location**，用 **Scale 无效**。
3. **平面的 Object 坐标跟随控制空物体的空间**：`tex.object = <原点空物体>` ⇒ 得到**世界坐标**；
   `tex.object = None`（默认自身）⇒ 得到**局部坐标**（本项目是 2×2，且不受 `scale` 影响）。
   两者行为完全不同，别混。

---

## §2 ★★ 平面专属的三个坑（都有官方手册原文）

### 坑 1：平面上很容易出现"整片均匀灰"（fBm 恒 0.5）

官方手册（Noise Texture 节点页）原文：

> "any discrete evaluation of noise at integer multiples of the reciprocal of the noise scale
> will always evaluate to 0.5. It also follows that evaluations closer to that will have values
> close to 0.5."

平面是**低维采样**（一个坐标被冻住），命中"接近 0.5"的概率比三维体更高。
本工程实测平面上的 Fac 分布：`min 0.11 / p50 0.497 / max 1.0`（密度 2.0）——大量像素挤在 0.5 附近。
**直通当发光强度 ⇒ 最暗处也压不到 0 ⇒ 全片发亮。** 正解是 ColorRamp 拉窗口（见母 skill §2）。

### 坑 2：平面轻微倾斜 ⇒ 条带（banding）

官方手册原文：

> "one might experience some banding patterns in the noise, where there are bands of high
> contrast areas followed by banding of low contrast areas. For instance, **planar surfaces that
> are slightly tilted along one of the axis** will have such a banding pattern. This happens
> because the slight tilt along one of the axis causes values along the perpendicular axis to
> change very slowly making the grid structure of the noise more apparent.
> The easiest way to mitigate this issue is to **rotate the coordinates by an arbitrary amount**."

⇒ 平面如果**不是严格沿轴**（法线不平行于任何世界轴），就会出现疏密相间的条带。
**要么让法线严格对齐轴，要么给 Mapping 的 Rotation 加一个小角度**把一个轴"拧"一下破坏网格结构。

### 坑 3：手册给的四条缓解里，有两条正是"控件化"的正确做法

> "Adjust the scale of the noise… **Add an arbitrary offset to the texture coordinates**…
> **Evaluate the noise at a higher dimension**…"

| 手册缓解手段 | 对应到我们的 5 个控件 |
|---|---|
| 加任意偏移（打破与采样域的对齐） | **Mapping.Location 的刷新**（滚动） |
| 提高维度（多一维当连续种子） | **噪波用 4D，`W = 种子 × 10`** |
| 调整 scale | **噪波密度** |
| 旋转坐标（破坏网格可见性） | 暂未控件化；需要时给 Mapping.Rotation 一个常量小角度 |

**所以"密度/种子/速度/对比度 + 4D 噪波"这套设计不是拍脑袋，是照着手册的缓解清单做的。**

---

## §3 坐标空间三选一（平面上尤其要选对）

| 输出 | 平面上拿到什么 | 什么时候用 |
|---|---|---|
| **Generated** | 局部包围盒归一 **0..1**（法线轴退化） | 想让图案**与平面尺寸脱钩**："整块板上大概 N 团"。换更大/更小的平面，**相对构图不变** |
| **Object → 控制空物体（原点）** | **世界坐标**（世界单位） | 想让图案**锚在物理空间**：跨多个物体图案连续、尺寸可换算（本项目用这条） |
| **Object → None（自身）** | **局部坐标**（本项目 2×2，且**不受物体 scale 影响**） | 想让图案"粘"在这个物体上，物体缩放时图案跟着变大 |
| **UV** | UV 坐标；平面通常有 UV（本项目恰好整块 0..1） | 需要精确控制贴法/非等比，或要与图片纹理对齐 |

⚠️ 用 **Object→空物体** 时，那个空物体**是世界坐标锚点，不要动它**（一动整套坐标跟着偏）。
官方手册对 Object 输出的原话也点了这件事：
*"Often used with an empty… **This object can also be animated, to move a texture around or
through a surface.**"* —— "around"=沿面移动，"through"=穿过表面（法线方向），与 §0 的模型一致。

---

## §4 ★★ 把平面当「材质验收测试卡」（本 skill 最值钱的一节）

### 为什么必须用平面做验收

| | 细丝灯带 | 实心平面 |
|---|---|---|
| 物体像素占画面 | **~8%**（直径 2mm、间距 7.5cm 的细丝网格） | **~100%** |
| 暗区占比 / 直方图 | 被 92% 背景稀释，噪声极大 | **直接可信** |
| 判定"有没有暗区" | 要换算占比，容易误判 | 一眼 + 数字 |

⇒ **改了材质，先用平面出一遍读数，再去看真实物体。** 平面是 4 顶点实心面片，
统计量干净、渲染秒级、可重复。

### 标准流程（脚本 `scripts/plane_testcard.py` 已封装）

1. 找出用同一材质的**平面**（顶点最少 / 有零跨度轴的那个），别拿细丝物体当基准
2. **沿法线正交正视**：相机放 `center + normal × 30`，朝向 `-normal`；
   `ortho_scale = max(跨度) × 0.98`（**溢出取景**）
   - ⚠️ 用 `×1.05` 会留一圈**黑背景**，那圈黑会被算进 `dark%`，读数被污染（实测差 5.3 个百分点）
   - ⚠️ **不沿法线看 = 只看到一条缝**。本项目那个平面 `rotation_euler=(90°,0,0)` 竖着，
     从上方俯视只看到边线，导致一整轮"平面几乎全黑"的**错误结论**
   - 相机 `local +Y` 会被 `to_track_quat('-Z','Y')` 对齐到世界 +Z ⇒ **图像竖直方向 = 世界 Z**
3. 扫一串对比度，记录 `dark% / mid% / blown% / p10-p50-p90 / 十档直方图`
4. **空对照**（见 §5）：同帧渲两次，必须完全一致
5. 输出里附带**材质真正看到的参数**（从求值依赖图读 `mapZ / scale / W / ramp / mult`），
   确认不是"图变了但其实参数没生效"

### 实测基准（本项目，平面 8.36 m，AgX，默认 密度2 / 种子0 / 强度5）

| 对比度 | ColorRamp 色标 | 平面暗区占比 `dark%(<0.05)` | 直方图形态 |
|---|---|---|---|
| 1 | 0.00 / 1.00 | **0.00 %** | 97.8% 像素挤在 0.8–0.9 ⇒ **整片灰糊，零暗区** |
| 2 | 0.25 / 0.75 | **0.00 %** | 79.6% 在 0.8–0.9 ⇒ 仍是灰糊 |
| **5（默认）** | **0.40 / 0.60** | **12.15 %** | 明显双峰：11.1% 全黑 + 38.3% 亮 |
| 10 | 0.45 / 0.55 | **27.90 %** | 26.5% 全黑，接近硬开关 |

> 这就是用户报的"**全发光、没有不发光的效果**"的定量版本：
> **对比度 ≤ 2 时平面上暗区恰好是 0%**；必须到 5 才有真暗区。

### ★ 用测试卡反推配方：「黑底 + 零星白点」

用户原话需求：*"黑底面积比较大，零零星星有白色的那种效果"*。
**噪波完全做得到**，关键认知是：**Fac 的分布不是均匀的**。

实测分布（本项目，密度 6，20 万次采样）：

| 分位 | p50 | p80 | **p90** | **p95** | p98 | p99 | max |
|---|---|---|---|---|---|---|---|
| Fac | 0.506 | 0.637 | **0.704** | **0.756** | 0.815 | 0.853 | 1.060 |

⇒ 想让"白"稀缺，**把 ColorRamp 窗口搬到分布尾部**即可，不需要换节点。

**窗口公式（母 skill v4）** —— 从「绕 0.5 对称」改成「绕阈值 T 对称」：

```python
elements[0].position = max(0.0, T - 0.5 / c)     # T = 亮区阈值，c = 对比度
elements[1].position = min(1.0, T + 0.5 / c)
```

- `T = 0.5`（默认）：窗口骑在中位数上，黑白约各半 ⇐ 就是上表那套读数
- `T ↑`：窗口整体上移到分布尾部 ⇒ 只有最高的那几个百分点变白 ⇒ **黑底白点**
- `c ↑`：窗口变窄 ⇒ 边界更硬（c=100 时 ±0.005 ≈ 硬开关，可切出极细等值线）

**实测（反色=0，对比度 20，密度 6，8.36 m 平面正交正视）**：

| 亮区阈值 T | 白点占比 |
|---|---|
| 0.70 | **1.55 %** |
| 0.75 | **0.16 %**（极稀疏星点） |

侦察阶段的窗口扫描同向印证：窗口 `0.60–0.65` → 10.3%；`0.64–0.68` → 3.5%；
`0.68–0.71` → 0.9%；`0.71–0.74` → 0.2%。

⚠️ **两个必须提醒的点**：

1. **反色 = 1 会把它整个翻转成"白底黑点"**（同一组参数下实测亮区占比 99.97 %）。
   阈值 × 反色 两个控件组合出 4 种黑白布局，别在反色还开着的时候调阈值。
2. **白点占比随密度变化**。上面的分位数是密度 6 测的；改密度后尾部会动
   （fBm 中位数恒 0.5，但尾部不守恒）。要精确控制占比就**重跑一次分位数扫描**，别硬套表。

> 交付前上限记得放开：密度 / 对比度 上限 20 → **100**，否则 T 调到 0.9 时窗口被
> `c ≤ 20` 卡住变不窄，出不来"零星"感。

### 视图变换：暗区占比稳，亮部完全不同

| 视图变换（对比度 5） | dark% | blown%(>0.95) | p50 |
|---|---|---|---|
| AgX | 12.15 % | **0.00 %** | 0.730 |
| Standard | 12.01 % | **74.71 %** | 1.000 |

- **`dark%` 对视图变换不敏感**（0 → 0 保真）⇒ 判"有没有暗区"可以用它，跨变换可比
- **亮部读数完全不可比**：AgX 把 74.7% 的过曝像素压进 0.72–0.85 的窄带
  ⇒ 想读"亮到什么程度"必须切 **Standard**（社区对"渲贴图/测试卡"的标准建议也是切 Standard，
  因为 AgX/Filmic 会改变颜色）
- 本 skill 的脚本默认两个都出，并标注用的是哪个

---

## §5 ★★ 像素级测量的三个硬性前提（不满足就得出假结论）

这一节是**血的教训**，三次误判都出在这里。

### 前提 1：关掉输出抖动（`render.dither_intensity`）

**`bpy.types.RenderSettings.dither_intensity` 默认为 1.0** —— PNG 落盘时给每个像素加 ±1/255 随机抖动。

- 后果：**同一帧渲两次，像素级也不同**（只在最低位）。肉眼、直方图都看不出来，
  但**相位相关/互相关会彻底失效**：峰值从 1.0 崩到 **0.376**，位移估计变成纯噪声。
- 正解：`sc.render.dither_intensity = 0.0` + `image_settings.color_depth = '16'`

### 前提 2：位移必须 ≪ 噪声相关长度

fBm 的**所有倍频同幅位移** —— 基频失相关时，高频也一起失相关。所以：

| 密度 | 特征尺寸 | 位移 0.6 世界单位 = ? | 互相关 |
|---|---|---|---|
| 2.0 | ≈0.5 m | **1.2 个特征** | ❌ 峰值 1.0 → 0.15，方向测不出 |
| 0.4 | ≈2.5 m | 0.24 个特征 | ✅ 可测（实测 −112 px vs 几何预期 −105 px） |

⇒ **想用互相关测位移：降密度（放大特征）+ 控制位移在 0.2–0.5 个特征之间。**
粗暴"把位移调大让它更明显"是反的。

### 前提 3：空对照（同帧渲两次）

永远先渲两张**同一帧**的图，确认估计器给出 **位移 = 0、峰值 ≈ 1.0**。
它证明"渲染 → 像素 → 相关"这条链路没有引入假位移。
**没有空对照的位移数字一律不可信**（本项目前两轮就是缺了这一步，白跑）。

### 测量方法的选择

| 方法 | 适用 | 注意 |
|---|---|---|
| **二维相位相关**（`np.fft.rfft2` + 归一化） | 位移小、图干净 | 对噪声/量化极敏感；必须满足前提 1–3 |
| **粗尺度峰值追踪**（块平均降采样后 argmax + 邻域搜索） | 有大块结构、位移较大 | 更鲁棒；块尺度 = 定位精度（8 px） |
| ❌ 行/列投影一维互相关 | 不推荐 | 沿另一轴平均会把信息洗掉，峰值展宽 ⇒ argmax 不稳（实测给出假的 0） |

**两个方法都跑、符号一致才下结论。** 脚本里已经这么做了。

---

## §6 平面滚动的方向：正速度到底朝哪边

- 本项目 `Mapping.vector_type = 'POINT'`（从文件读出来的，不是猜的）
- 官方手册对 `POINT` 的定义：*"translating the texture coordinates along the positive X axis
  would result in the evaluated texture to move in the negative X axis"*，且变换顺序是
  **Scale → Rotate → Translate**（`TEXTURE` 类型才是 Translate → Rotate → Scale 且同向）
- 推导：POINT 下 `out = in + L` ⇒ 特征在表面上的位置 `in = p - L` ⇒ **L 增 ⇒ 图案朝 −L 方向移动**

**实测确认**（`scripts/plane_testcard.py`）：
`Location.Z` 从 0.02（f1）增到 1.22（f61），图案位移 **−112 px ≈ −1.27 世界单位**
（几何预期 −105 px / −1.2），**朝 −Z** ⇒ 与手册一致。

⇒ **交付文档里要写明：正速度 = 图案朝 −Z；想反向就填负值**（别让用户试半天）。
⇒ 若换了材质、`vector_type` 变成 `TEXTURE`，方向会**反过来**。

---

## §7 与母 skill 共享的坑（这里只列，细节见母 skill）

- **改自定义属性本身不会让驱动重算**（实测：改完立刻读仍是旧值）。
  ⇒ 控件要生效必须有 ①`SINGLE_PROP` 声明依赖边 ②不依赖 UI 的看门狗定时器。
  **只在面板 `draw()` 里 tag 是错的** —— 用户在「物体属性 → 自定义属性」里改数字时
  面板不重绘 ⇒ 5 个控件全哑。
- **读驱动真值一律在主场景读**。非活动临时场景的依赖图读出来可能是**陈旧值**；
  但那个场景的**渲染**会正确跟随主场景帧（实测 f1 vs f96 变化 81%）。
- 驱动表达式里 **`max` / `min` / `abs` 可用**（`ColorRamp` 下界夹 0 就靠 `max`）。
- `bpy.ops.render.render(write_still=True)` **必须先设 `scene.render.filepath`**。
- 临时场景用完要清，输出 `leftover_*: []` 自证。

---

## §8 脚本

| 脚本 | 作用 |
|---|---|
| `scripts/probe_plane.py` | 【只读】平面专项侦察：零跨度轴、法线、纹理坐标三轴 span、Generated 退化、节点链、驱动、求值真值 |
| `scripts/plane_testcard.py` | **平面验收测试卡**：对比度扫描 + AgX/Standard 对照 + 滚动方向（双判据 + 空对照）+ 干净性自证 |
| `scripts/autorefresh_A_set.py` / `autorefresh_B_read.py` | 两段式验证"改属性不 tag 能否自动生效"（中间靠看门狗） |
| `scripts/probe_temp_scene_eval.py` | 钉死"临时场景下帧驱动的求值/读值行为" |
| `scripts/probe_driver_autotrigger.py` | 驱动自触发写法矩阵 + `max/min/abs` 可用性 |
| `scripts/probe_sparse_white_recon.py` | 【侦察】黑底白点可行性：Fac 分布分位数 + 顶部窗口试渲（§4 白点配方的数据来源） |
| `scripts/probe_threshold_e2e.py` | 【端到端】亮区阈值走**真实驱动链**渲染 + `try/finally` 恢复用户值 |

所有脚本顶部的 `WORKDIR` / `OUTDIR` 是**占位路径**，用前改成你本机的目录。

---

## §9 出处

- Blender 5.2 手册 · Texture Coordinate 节点（`Object` 输出可动画以"move a texture
  **around or through** a surface"；`Generated` 是包围盒归一 0..1）
- Blender 5.2 手册 · Noise Texture 节点（fBm 在 scale 倒数整数倍处恒 0.5、
  "evaluations closer to that will have values close to 0.5"、
  planar surface 轻微倾斜产生条带、四条缓解手段）
- Blender 5.2 手册 · Mapping 节点（Point / Texture 两种语义的变换顺序与方向差异）
- 社区标准做法（BlenderArtists）：渲"贴图/测试卡"用**正交相机 + 沿法线正视 +
  color management 切 Standard**，并注意 film filter size 影响锐度
- 社区/官方共识：渲染输出**优先图片序列、视频编码单独做**（对应 §7 的
  `file_format` 动态枚举坑 —— 别在视频格式的场景里硬写 PNG）
- 本项目实测（2026-09-13）：Fac 分布分位数、四组顶部窗口试渲、阈值 0.70/0.75 端到端白点占比
