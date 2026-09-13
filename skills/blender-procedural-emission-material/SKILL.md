---
name: blender-procedural-emission-material
description: 通过本地 9877 桥给 Blender 网格体做「世界空间程序化发光材质」——不用 UV，噪波写在指定平面、按指定轴滚动，全部参数做成数字控件（自定义属性 + 节点驱动 + Register 实时面板）。当用户说「做个程序化贴图/噪波材质」「不要 UV、要按物理空间」「从 Y 轴看是个方形/长灯带，上面是噪波」「噪波沿 Z 方向移动」「我要能改噪波密度/种子/速度/对比度/发光强度」「这些参数要有个控件能改数字」「整片全发光／没有不发光暗区」「拖动滑块材质没变化／改了属性驱动不重算」时使用。**标准链 = Mapping 滚 + ColorRamp 做对比度**（噪波 Fac 实测聚在 0.5 附近，直通映射会全片发亮 ⇒ 必须用 ColorRamp 拉伸窗口才有真暗区）。含坐标空间选择、4D 噪波当连续种子、ColorRamp 色标挂驱动、驱动重算 tag 矩阵（命名空间型 vs SINGLE_PROP 型）、读驱动真值必须走求值依赖图、驱动内置 frame 变量无效、Register 文本块持久化面板、隔离场景渲预览与像素级验证。
agent_created: true
---

# 世界空间「程序化噪波 / 发光」材质 + 数字控件面板

传输层（9877 桥、客户端封装、120s 上限、Blender 5.x API 坑）见 **`blender-bridge-ops`** skill。
参数控件/面板的通用机制另见仓库文档 `材质参数统一控制器与实时面板.md`（但**其 §3 的刷新结论不完整**，见本 skill §6）。
本 skill 专讲「**世界空间** + **平面噪波** + **沿线滚动** + **5 个数字控件**」这一套。

## 铁律

1. **先只读侦察**：对象世界包围盒 + 网格量级 + 现有材质/节点/驱动。**"方形"这种描述必须量出来验证**（见 §1）
2. **先建干跑副本再做实验**：要验证 API 行为，用**临时对象/材质**试，试完删掉并校验无残留
3. **改动前放还原点**（`blender-bridge-ops` 的纪律）；原材质一律 `use_fake_user = True` 保留，别删
4. **执行完另起一次请求独立核验**（全新取引用、重新读 socket 值），不要复用同一脚本的自检
5. **判据取差集**：预览图两两做**像素级差异**，不要靠肉眼说"看起来一样/不一样"
6. **单次只处理一个矛盾点**，卡住就暂停

---

## §1 需求拆解：先把「坐标空间」和「平面」钉死

用户说「根据物理空间，不是根据 UV」→ 用 **`ShaderNodeTexCoord` 的 `Object` 输出**：

```
tex.object = <控制空物体>      # 该空物体必须：位置(0,0,0)、rotation 全 0、scale 全 1
```
只有在上述条件下 **Object 坐标 == 世界坐标**。
> 反过来这也是警告：**一旦移动/旋转这个空物体，噪波坐标系跟着变**，滚动方向也会偏。
> 要在交付文档里明确写「别动它，它只是坐标锚点」。（`AGENTS.md` 也记着「Object 坐标只跟随平移，不跟随旋转」）

**"从 X 轴看是方形" 之类必须实测**。用逐顶点世界坐标求包围盒，再按三个轴正交渲染确认：

```python
mw = obj.matrix_world
xs, ys, zs = [], [], []
for v in obj.data.vertices:
    p = mw @ v.co
    xs.append(p.x); ys.append(p.y); zs.append(p.z)
# X span = max(xs)-min(xs) 等 → 哪个轴看是"长条"、哪个是"方形"，一目了然
```

⚠️ **实战教训**：用户凭印象说"从 Y 轴看是方形"，实测 **沿 +Y 看是 26.35×3.09 的长灯带，沿 +X 看才是 2.44×3.09 的近方形**。
**必须把实测结果摆给用户让他选**（用 AskUserQuestion 给「沿 Y 看的长灯带 / 沿 X 看的方形」两个选项），别自己替他想。

**"把三维压成平面"**：**通常不需要做**。薄片物体（如 2.44 m 厚的灯带）沿厚度方向的噪波变化在正面看不到；
真想压平就用 `分离XYZ → 合并XYZ` 把该轴写成常量，或给 Mapping 的 `Scale` 该轴一个极小值。
**优先选"什么都不做"** —— v2 实测压平与否视觉上无差别，少两个节点。

**"沿某轴滚动" 的做法（标准）= Mapping 节点的 Location**：

```
纹理坐标.Object ─► 滚动映射(ShaderNodeMapping, Location.Z = 驱动 frame×速度) ─► 噪波纹理…
```

`mp.inputs['Location'].default_value`（= `inputs[1]`）的 **Z 分量（array_index 2）** 挂驱动。
这与仓库滚筒材质 `scripts/glow-scroll-material/` 同源，也是 Blender 的标准做法。

> ⚠️ v1 曾错误地手搓 `分离XYZ → Math(ADD) → 合并XYZ` 来做滚动：
> 能用，但多 3 个节点、多一条易错路径，**没有任何好处**。要滚动就用 Mapping。

---

## §2 节点链模板（标准写法，7 节点 / 7 连线，v3 起含反色）

```
纹理坐标(Object→ctrl)
   ─Vector─► 滚动映射 Mapping（Location.Z = 驱动 fr×速度）
      ─Vector─► 噪波纹理 Noise（4D；W = 种子×10；Scale = 密度）
         ─Fac─► 对比度 ColorRamp（elements[0]/[1].position = 驱动 [T−0.5/c, T+0.5/c]）
            ─Color─► 反色 MapRange（To Min/To Max = 驱动 iv / 1−iv；不需要可整体去掉）
               ─Result─► 发光强度 Math MULTIPLY（× 驱动强度）
                  ─Value─► 原理化BSDF.Emission Strength
```

> ★ v4 窗口公式带**亮区阈值 T**：窗口从「绕 0.5 对称」改成「绕 T 对称」，T=0.5 与旧公式完全等价。
> **T 调高 = 窗口搬到噪波分布顶部 = 黑底零星白点**（实测 密度6/c=20：T=0.70 → 1.55% 白点，
> T=0.75 → 0.16%；Fac 分布 p90=0.70 / p95=0.76，20 万点采样）。
> 分布本身近似密度不变（fBm 自相似），所以阈值语义稳定。
> 调阈值/对比度上限都可给到 100（c=100 → 窗口 ±0.005 ≈ 硬开关）。
> **反色开着时效果翻转成白底黑点** —— 两个控件组合出四种黑白布局。

### 反色控件（v3 新增；可选环节）

在 **对比度 与 发光强度 之间** 插一个 **MapRange**（命名 `反色`）做黑白翻转：

| 反色 iv | To Min / To Max | 效果 |
|---|---|---|
| 0 | 0 / 1 | 恒等映射（什么都不做，默认） |
| 1 | 1 / 0 | **黑白互换**：噪波亮处不发光、暗处发光 |
| 0.5 | 0.5 / 0.5 | 输出恒定 0.5 灰（全部中等亮度） |
| 中间值 | 部分互换 | 黑白按比例混合，可做渐变过渡 |

- 驱动写法（SINGLE_PROP，变量 `iv` = `ctrl["反色"]`）：
  `反色.inputs['To Min']` 表达式 `iv`；`反色.inputs['To Max']` 表达式 `1.0 - iv`。
- `From Min/From Max` 固定 0/1 不动 —— **只动 To 端**。
- ⚠️ **别和 §2 的核心坑搞混**：v1 的错误是「拿 MapRange 做对比度窗口拉伸」（应该 ColorRamp）；
  这里是拿 MapRange 做 0↔1 线性翻转，是它的本职用法。核验时应断言**全材质只有这一个 MapRange**。
- **像素级验收**（`dither=0` + 16-bit + 零控）：反色0 ↔ 反色1 逐像素相关系数实测 **−1.000**
  （完美互补），零控 1.0000，iv=0.5 输出 std=0（恒定灰）。见 `scripts/render_invert_check.py`。

### ★★ 对比度必须用 ColorRamp —— 这是本 skill 的核心坑

**现象**：材质做出来**整片全发光，没有"不发光"的暗区**（用户原话："全发光，没有不发光的效果"）。

**根因**：Noise Texture 的 **Fac 是 fBm，取值死死聚在 0.5 附近**。
Blender 官方手册（Noise Texture 节点页）原话：噪声在"噪声尺度的整数倍"处**恒等于 0.5**，
"evaluations closer to that will have values close to 0.5"；并提醒 **planar surfaces** 会出现条带/低对比。
本工程实测：`min 0.242 / p50 0.497 / max 0.738` —— 总共只有 0.24~0.74 这么窄。
把它**直通**当发光强度（或 `From 0..1 → To 0..1` 的 MapRange）⇒ 最暗处也是 `0.24 × 强度`，
**永远压不到 0**，于是全片都亮。

**正解 = 用 ColorRamp 把这段窄范围拉伸开**（官方手册与多处教程一致的标准做法：
*"It's common to interrupt a Noise Texture signal chain with a Colour Ramp…
dragging the handles left and right changes the contrast"*）：

```
窗口 = [0.5 - 0.5/c , 0.5 + 0.5/c]        # c = 对比度
elements[0].position = clamp(0.5 - 0.5/c)  # 黑（= 不发光）
elements[1].position = clamp(0.5 + 0.5/c)  # 白（= 满亮）
```

| c | 色标 | 效果 | 实测不发光像素占比（8.36 m 平面） |
|---|---|---|---|
| 1 | 0.00 / 1.00 | 等于直通 ⇒ 灰糊、无暗区 | 0 % |
| 2 | 0.25 / 0.75 | 全范围拉伸但仍多中间灰 | 8.5 % |
| **5（推荐默认）** | 0.40 / 0.60 | **黑白分明** | **17.9 %** |
| 10 | 0.45 / 0.55 | 接近断续硬开关 | 31.7 % |

- **默认值别给 1.x** —— 那是直通，用户第一眼就是"全发光"。
- `c < 1` 会被 0~1 夹住（不能比直通更软），所以范围给 `1 – 20`。
- **对比度色标位置可以挂驱动**：路径 `nodes["对比度"].color_ramp.elements[0].position`
  （`color_ramp.elements[i]` 不是 socket，**只能**用 `nt.driver_add(路径)`，不能用 `socket.driver_add()`）。
  实测通过（`probe_50` / `probe_52`）。
- 也可以不挂驱动、把色标写死 —— 但那就没有"数字控件"了。

> 等价替代：`MapRange(clamp, From=窗口, To=0..1)` 语义相同（v1 用过），
> 但 **ColorRamp 更贴仓库规范**（`docs/材质与驱动规范.md` §2 的条纹方案就是 `ColorRamp(f) → 灰度 → ×强度 → Emission`），
> 且能在节点编辑器里直接看见/手调色标。**优先 ColorRamp**。

### 其余要点

| 要点 | 做法 | 为什么 |
|---|---|---|
| 噪波用 **4D** | `noise.noise_dimensions = '4D'` | 第 4 维 **W 是"连续种子"**：给 W 不同值 = 换一整张图案，且平滑可控（比换 seed 更适合做动画） |
| **种子用 W 承载** | `W = 种子 × 10.0`（`SEED_SPAN`） | 每 +1 就跳 10 个噪波单位 ⇒ 保证"真的换了一张图"，不是细微差别 |
| 密度 = **Scale** | `noise.inputs['Scale']` | 世界单位频率 |
| 对比度 = **ColorRamp 两色标位置** | 见上 | 把 0.24~0.74 的窄范围拉成 0~1，低端压到 0 才有真暗区 |
| 发光 | `ColorRamp.Color × glow_strength` → `原理化BSDF.Emission Strength` | 基础色给纯黑，就只有发光；**暗区 = 0，乘任何强度都还是 0**，不会被拉亮 |
| 节点**命名** | 全部起中文名（`纹理坐标 / 滚动映射 / 噪波纹理 / 对比度 / 发光强度`） | 面板/文档/驱动 data_path 都要引用 |

⚠️ **原理化BSDF 不要按名字找**：默认节点名是**本地化中文**「原理化 BSDF」，
`nt.nodes["Principled BSDF"]` 会 `KeyError`。一律：
```python
bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
```
⚠️ **同理，新建 World 的 `Background` 节点名也是本地化的**，用
`next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')`。
（`probe_50` 第一版就是被这个 `KeyError` 打断。）

⚠️ **Noise 的插槽顺序**（5.2）：`[0]Vector [1]W [2]Scale [3]Detail [4]Roughness [5]Lacunarity [6]Offset [7]Gain [8]Distortion`。
（注意是 **Offset**，不是旧文档写的 Distortion 在前。）
⚠️ **Mapping 的插槽**：`[0]Vector [1]Location [2]Rotation [3]Scale` —— 滚动挂在 `inputs[1]` 的 index 2。

---

## §3 驱动：数值控件 → 节点 socket

**驱动必须挂在材质节点树上**：`nt.animation_data_create()` 之后用 `socket.driver_add('default_value')`。

```python
fc = node.inputs['Scale'].driver_add('default_value')
d = fc.driver
d.type = 'SCRIPTED'
d.expression = 'nz_density()'          # 调 driver_namespace 里的函数
fc.update()                            # 立即算一次
```

- **表达式读属性**用 `bpy.app.driver_namespace` 里的函数（`nz_*`），函数内部去 `ctrl.get(key, default)`。
  这样属性改了只改一处，节点侧不用重连。
- ★★ **需要当前帧时，必须用 `SINGLE_PROP` 变量指向 `scene.frame_current`，不要用驱动内置的 `frame`**：

  | 写法 | 实测（Blender 5.2.0 LTS） |
  |---|---|
  | `frame * nz_z_speed()`（内置变量） | **❌ 解析不到**，取值恒停在默认 0，**画面零变化**（像素差 0.00%） |
  | `fr * nz_z_speed()`，`fr` = `SINGLE_PROP → SCENE.frame_current` | ✅ 正常（帧1→0.02、帧60→1.2） |

  仓库滚筒材质用的也是 SINGLE_PROP。**别信"内置 frame 能用"的旧笔记**。
  `probe_51` 两轮都栽在这上面：对比度/种子/密度都变了，唯独滚动 0% 变化 —— 差别就在这一条。
- **socket 路径必须用数字索引**：`nodes["噪波纹理"].inputs[1].default_value`。
  用 socket **名字**在某些版本会 `not found`（仓库 `AGENTS.md` 有记）。
- **ColorRamp 色标不是 socket**：只能 `nt.driver_add('nodes["对比度"].color_ramp.elements[0].position', -1)`。
- **幂等**：重跑建脚本前先 `nt.animation_data_clear()` 再 `create()`，否则驱动会叠加。
- ★★ **向量插槽分量驱动**：给 `Mapping.Location` 的 Z 挂驱动要传 array_index：
  ```python
  fc = mp.inputs['Location'].driver_add('default_value', 2)   # 2 = Z
  ```

---

## §4 控件：自定义属性 + 中文 UI 元数据

属性存在**控制空物体**上，并用 `id_properties_ui` 注入范围/步进/描述 → `prop()` 直接就是数字框 + 滑杆：

```python
ctrl["噪波密度"] = 2.0
ctrl.id_properties_ui("噪波密度").update(
    description="噪波频率(世界单位)　| 默认 2", min=0.05, max=20.0,
    soft_min=0.2, soft_max=6.0, step=1, precision=2)
```
（读回元数据要用 `ctrl.id_properties_ui(k).as_dict()`；直接 access `.description` 会抛异常。）

### ★★ 键名决定「物体属性 → 自定义属性」列表显示什么（必看）

用户反馈"这几个控件的 UI 是全英文的"，指的就是**物体属性 → 自定义属性**那张列表。
它显示的字面量**就是 ID 属性的键名本身**，而且**无法本地化** ——
`layout.prop(..., text="中文")` 只能改**你自己面板**里的行标签，改不了那张列表。

**正解：键名直接写中文。**

```python
ctrl["噪波密度"] = 2.0                              # 中文键名，列表里就显示中文
box.prop(ctrl, '["噪波密度"]', text="噪波密度")      # RNA 路径带中文同样合法
```

- 任意 UTF-8 键名合法（含中文）；存盘 / 读回 / 驱动表达式 / RNA 路径全部正常
- **必须做迁移**：老版本用过英文键的话，重跑建脚本时 `del ctrl[老键]`，
  否则列表里中英两种键混着更难看。同时给取值函数留老英文键兜底
  （`v = c.get(中文键)`，没有再 `c.get(英文键)`），防止半迁移状态读到 0
- 面板 `Panel.draw()` 的 `cls._last` 缓存要用**同一个中文键**当 key
- 驱动表达式**不受影响**（它只调 `nz_*()` 函数名，不引用属性键），改键名不用重建驱动
- 重跑建脚本把中文键按"新键"创建时，值是默认值 —— 若用户已调过参，先读旧键再回填

### 定位"英文 UI 到底在哪"的方法

不确定用户说的英文在哪个面板时，直接抓窗口截图，别猜：

```python
bpy.ops.screen.screenshot(filepath=r"...\ui_shot.png")     # 全窗口截图，一步到位
```
⚠️ **必须在另起一次请求里抓**：同一个请求内改完数据立刻截图，拿到的是**重绘前的旧帧**
（实测踩过：新加的属性没出现在截图里，差点误判成"中文键名不显示"）。
先发一个只做数据改动的请求，隔一次再发一个只截图的请求即可。

---

## §5 面板持久化：Register 文本块（关键）

面板只在运行期注册，**重启就丢**。正解：

1. 把面板源码写进一个 **文本块**（`bpy.data.texts.new()` + `write()`）
2. `txt.use_module = True`（= UI 上那个 **Register** 勾）
3. 工程需开启 **偏好设置 → Save & Load → Auto Run Python Scripts**
4. 文本块里 `register()` 要**同时**注册 `bpy.app.driver_namespace` 函数**和** Panel 类

⇒ 保存 .blend 后重开，面板与命名空间函数自动恢复，不用重跑脚本。
（文本块里的源码要**自包含**：不能 import 你本地的脚本。）
若面板要同时重算多个材质的驱动，把材质名做成 `MAT_NAMES = ["..."]` 列表遍历。

---

## §6 ★★ 让"改控件"真正生效 —— 三层机制（本 skill 最值钱的一节）

**现象**（用户实际报的 bug）："*控件似乎没有正确设置，所有的控件都没有效果*" ——
5 个控件全改了没反应；或者只有从 N 面板改才生效，在
「物体属性 → 自定义属性」里改数字没反应。

### 第 1 层：改自定义属性【本身】不会让驱动重算（实测）

只赋值、不 tag，立刻从求值依赖图读回的是**旧值**：

| 操作 | mapZ | Scale | W | ramp | mult |
|---|---|---|---|---|---|
| 改成 `0.05 / 3.7 / 4.2 / 7.5 / 23.0`（只赋值，不 tag） | 0.02 | 2.0 | 0.0 | 0.4 / 0.6 | 5.0 |
| **等 4 秒（看门狗跑过）** | **0.05** | **3.7** | **42.0** | **0.4333 / 0.5667** | **23.0** |

（脚本 `blender-plane-procedural-material/scripts/autorefresh_{A_set,B_read}.py`）

### 第 2 层：驱动必须带【已声明的依赖边】

依赖图只认**已声明的依赖边**。所以**控件值不要靠"表达式调命名空间函数"去读** ——
那样没有任何边指向控制物体，只能靠外部 tag，而外部 tag 极易漏。
**正解：用 `SINGLE_PROP` 变量直接指向 ctrl 的 ID 属性，表达式的值就来自变量。**

| 目标 | 表达式 | 变量（`SINGLE_PROP` → ctrl 的 ID 属性） |
|---|---|---|
| `滚动映射.inputs[1]` idx 2 | `fr * sp` | `fr` = SCENE.frame_current；`sp` = `ctrl["Z向速度"]` |
| `噪波纹理.inputs[2]`（Scale） | `dn` | `dn` = `ctrl["噪波密度"]` |
| `噪波纹理.inputs[1]`（W） | `sd * 10.0` | `sd` = `ctrl["噪波种子"]` |
| `对比度.color_ramp.elements[0].position` | `max(0.0, 0.5 - 0.5 / ct)` | `ct` = `ctrl["噪波对比度"]` |
| `对比度.color_ramp.elements[1].position` | `min(1.0, 0.5 + 0.5 / ct)` | `ct` |
| `发光强度.inputs[1]` | `st` | `st` = `ctrl["发光强度"]` |

```python
v = d.variables.new(); v.name = 'ct'; v.type = 'SINGLE_PROP'
t = v.targets[0]; t.id_type = 'OBJECT'; t.id = ctrl; t.data_path = '["噪波对比度"]'
```

- 驱动表达式里 **`max` / `min` / `abs` 实测都可用**（`probe_57`）⇒ 窗口夹取可以直接写在表达式里
- `data_path` 用 `'["中文键"]'` 一样合法
- **变量绑好再写 `d.expression`**

### 第 3 层：看门狗（不依赖任何 UI）

★ **绝不要**把刷新放在面板 `draw()` 里。`draw()` 只在「N 面板显示本分类、且被重绘」时执行；
用户在「物体属性 → 自定义属性」里改数字时它**不执行** ⇒ 不 tag ⇒ **控件全哑**。
（上一版本就是这么写的，正是用户踩的坑。）

正解 = Register 文本块里注册一个**定时看门狗**，与 UI 完全解耦：

```python
_TICK = 0.25
_WATCH_LAST = {}


def _touch():                       # 强制重算挂在材质/节点树上的驱动
    c = bpy.data.objects.get(CTRL_NAME)
    if c:
        c.update_tag()
    for mn in MAT_NAMES:
        m = bpy.data.materials.get(mn)
        if m is None:
            continue
        m.update_tag()
        if m.use_nodes and m.node_tree:
            m.node_tree.update_tag()
    bpy.context.view_layer.update()


def _watch():
    try:
        c = bpy.data.objects.get(CTRL_NAME)
        if c is not None:
            dirty = False
            for k, _lbl in PROPS:
                v = c.get(k)
                if _WATCH_LAST.get(k) != v:
                    _WATCH_LAST[k] = v
                    dirty = True
            if dirty:
                _touch()
    except Exception:
        pass
    return _TICK


def register():
    # ... 注册命名空间 / Panel 类 ...
    try:
        bpy.app.timers.unregister(_watch)
    except Exception:
        pass
    bpy.app.timers.register(_watch, first_interval=0.5, persistent=True)
```

只有值**真的变了**才 tag ⇒ 无空转、无递归。

### 附：tag 策略参考表（仅兜底，别当主手段）

万一有驱动没法改成变量（例如色标位置的历史遗留）才需要手动 tag：

| tag 策略 | 命名空间函数型（表达式只调 `nz_x()`，无变量） | `SINGLE_PROP` 变量型 |
|---|---|---|
| 不 tag | ❌ | ❌ |
| `ctl.update_tag()` | **❌** | ✅ |
| `mat.update_tag()` / `mat.node_tree.update_tag()` | ✅ | ❌ |
| **ctl + mat + node_tree 三个都 tag** | **✅** | **✅** |
| `depsgraph.update()` | ❌ | ❌ |
| `frame_set(当前帧)` | ✅ | ❌ |

> 仓库 `材质参数统一控制器与实时面板.md` §3 / `ring_control_panel.py` 只写了 `ctl.update_tag()`——
> 那对 `SINGLE_PROP` 型成立，对命名空间函数型不成立。**不是错，是不完整**。
> `depsgraph.update()` 两种场景都无效。
> ⚠️ `frame_set()` 会**强制全量重算**，用它"证明生效"是**假阳性**，别拿来当证据。
>
> 上表数据来自 **`scripts/probe_driver_tag_matrix.py`**（`probe_58`）—— 干净版实验。
> 更早的 `probe_57` 有**脏读陷阱**：它反复用同一个材质 datablock 换驱动，
> 换完没强制重算 ⇒ 读到的 evaluated 副本还停在**上一个驱动**的结果，
> 于是 `SINGLE_PROP` 那几行全读出同一个值、等于没测。
> **教训：测 tag 矩阵时，每种驱动类型用独立的新材质，且每个采样点只施加一种 tag。**

### 怎么确认看门狗**真的在跑**（而不是以为注册了就完事）

`bpy.app.timers` 没有"列出所有定时器"的 API，但可以用 **`is_registered()` 按函数对象反查**：

```python
mod = bpy.data.texts["<面板文本块名>.py"].as_module()   # Register 过的文本块
fn  = getattr(mod, "_watch", None)
assert fn is not None
print(bpy.app.timers.is_registered(fn))                  # True = 定时器在线
```

**活体验收（最有说服力的一招）**：不要用脚本造的值自证，而是拿
**用户在 UI 里拖出来的真实值当输入**，核对「控制器属性值」是否等于「驱动求值真值」。
若逐项吻合 ⇒ 看门狗确实在把用户的每次改动喂给驱动。
（本项目实测：用户在 UI 侧把 5 个控件拖到 6 / 11.34 / -0.1 / 10 / 5 后，
驱动真值读出 6.0 / 113.4 / -0.1 / 0.45-0.55 / 5.0，逐项吻合 ⇒ 通过。）

---

## §7 渲染预览的坑（★★ 含一次整轮测量作废的教训）

1. **`bpy.ops.render.render(write_still=True)` 不认你算好的路径**。
   必须先 `sc.render.filepath = <绝对路径>`，否则**静默不写盘**，而 `os.path.exists(p)`
   还会因为**旧文件**而误判成功。⇒ 千万别用"文件存在"当成功判据；
   或把 job 名带序号、跑前先清目录，并核对 **mtime**。

2. ★★ **隔离临时场景时，材质必须仍落在"会被求值"的场景里**。

   依赖图**只求值当前活动场景**里的东西。所以：

   ```python
   sc = bpy.data.scenes.new("__PREVIEW__")
   sc.collection.objects.link(obj)        # ✅ 额外 link 进临时场景（obj 本来就在主场景里）
   # ❌ 不要 unlink 主场景；❌ 更不要"新建一个只属于临时场景的物体"
   ```

   **换帧要调主场景**（因为 `fr` 变量指向主场景）：
   ```python
   main.frame_set(frame)                  # ✅ 注意是 main，不是 sc
   bpy.context.view_layer.update()
   bpy.ops.render.render(write_still=True, scene=sc.name)
   ```

   **反例（v1 踩的坑）**：当时新建了一个只挂在临时场景里的测试物体，
   那个临时场景又不是活动场景 ⇒ 材质从未参与求值 ⇒
   **驱动全程没生效，整轮 8 张图的测量全是垃圾**，白跑两轮才发现。
   判定征兆：所有图统计值几乎一模一样、换帧像素差 **0.00%**。

   ★ **补充（probe_56 实测，很重要）**：临时场景的**渲染**会正确跟随主场景的帧
   （f1 vs f96 像素变化 81%），但**手动读值会读到陈旧值** ——
   活动场景 = 临时场景时改 `main.frame_set()`，从临时场景依赖图读出来仍是旧值。
   ⇒ **验收读数一律在主场景读**（`bpy.context.window.scene` 指回主场景），
   或者在临时场景渲完之后靠**像素差**判断，不要用"临时场景依赖图读回的值"当证据。

3. **临时场景想彻底删掉，得先确保它不是活动场景**（`bpy.context.window.scene` 要指回主场景）。
   `bpy.data.scenes.remove()` 对活动场景会失败。
   另外**先取 `s.name` 再 remove**，remove 之后那个引用就失效（`ReferenceError: StructRNA of type Scene has been removed`）。

**让预览图自带标签**：用自带 stamp，不用建文字物体（省事且不用清理）：
```python
sc.render.use_stamp = True
for f in ("use_stamp_date","use_stamp_time","use_stamp_frame","use_stamp_camera",
          "use_stamp_scene","use_stamp_filename","use_stamp_render_time","...") :
    setattr(sc.render, f, False)         # 只留 note
sc.render.use_stamp_note = True
sc.render.stamp_note_text = "BASE f1 dens2 seed0 ..."   # ⚠️ 用 ASCII，默认字体无中文
sc.render.stamp_font_size = 22
```
stamp 渲染出来在画面**左上角**。

**拼对照图**：把 N 张同尺寸 PNG 拼成网格 —— **优先用 Blender 自带 `Image.scale(w,h)`** 归一尺寸，
再 `pixels.foreach_get/set` 拼接、`bpy.data.images.new()` + `save()`。
比 numpy 路径更省事（`img.scale()` 直接做重采样）。
⚠️ Blender 图像 **行 0 = 最底行**，放置 tile 时行号要按 `(ROWS-1-row)` 换算，否则上下翻。

**渲染用户实际看到的那个对象**：用户说"我贴了个平面用同样的材质"时，
**别猜**，直接把**所有引用该材质的对象**列出来（遍历 `material_slots`），
按各自**面积加权平均法线**摆相机做正面正交渲染：
```python
n = Vector((0,0,0)); mw3 = o.matrix_world.to_3x3()
for p in o.data.polygons:
    n += (mw3 @ p.normal) * p.area
cam.location = center + n.normalized() * 30
```
（v1 曾因为不知道用户那个"平面"是 `rotation_euler=(90°,0,0)` 竖着的，
从上方俯视只看到一条缝，得出"平面几乎全黑"的错误结论、整轮数据作废。）

---

## §8 核验清单（另起一次请求跑）

### ★★ 读驱动真值必须走"求值后的依赖图"

**这是最容易误判的一环**：直接读原 datablock 的 `socket.default_value`，
拿到的是**未求值的旧值**（表现为"永远停在工厂默认"，于是误判成"驱动没生效"）。

```python
dg = bpy.context.evaluated_depsgraph_get()
nt_eval = mat.evaluated_get(dg).node_tree          # ← 真值在这里
val = nt_eval.nodes["滚动映射"].inputs[1].default_value[2]
```

（`probe_51` 就吃了这个亏：真实渲染明明受对比度影响，读回却显示色标一直在 0/1。）

### 结构

对象/材质/控制器存在、slot 指派、`tex.object is ctrl`、噪波 4D、
**ColorRamp 存在且色标为黑(0)/白(1)**、`发光强度` 是 MULTIPLY、
**无 MapRange 残留**、**无 Separate/Combine XYZ 残留**、
**无残留指向已删节点的驱动**（重写后老节点没了，老驱动却可能还挂着）、
连线**逐条断言**（别只数总数）、驱动路径齐全、滚动驱动绑定 `fr=SINGLE_PROP(scene.frame_current)`、
命名空间函数齐全、Panel 类 `hasattr(bpy.types, ...)`、文本块存在且 `use_module==True`、
**原材质存在 + fake_user + 节点树未被动过**、目标面数不变、兄弟对象不变、
**控件键名全为中文且老英文键已清除**、控制器仍在原点

### 行为（每个控件都要动一次，**从求值依赖图读回**）

| 控件 | 改什么 | 期望读回 |
|---|---|---|
| 密度 | 2 → 3 | `噪波纹理.inputs[2] == 3.0` |
| 种子 | 0 → 7 | `噪波纹理.inputs[1] == 70.0`（×10） |
| 对比度 | 5 | `color_ramp.elements[0/1].position == 0.4 / 0.6` |
| 对比度 | 5 → 10 | `0.45 / 0.55`（窗口变窄 ⇒ 暗区变多） |
| 对比度 | → 0.5 | `0.0 / 1.0`（**被夹住**，不能比直通更软） |
| 发光强度 | 5 → 12 | `发光强度.inputs[1] == 12.0` |
| 滚动 | `frame_set(60)` @速度0.02 | `Location.Z == 1.2` |
| 速度负值 | -0.05 @帧60 | `== -3.0`（反向） |

最后**还原默认值**并断言还原成功。

⚠️ **别用 `bpy.context.scene.frame_current = 1` 直接赋值**（不触发重算）→ 用 `frame_set(1)`。
⚠️ **别断言 `bsdf.inputs['Emission Strength'].default_value == 强度`** ——
该插槽已被连线，`default_value` 本来就该被忽略（读回来是 0 是正常的）。
改成断言 `bsdf.inputs['Emission Strength'].is_linked is True`。
（`verify_noise_scroll.py` v2 第一版就写了这条错测试，虚报 1 项失败。）

**效果**：`render_nz_preview.py` 出 N 张 → 读像素算平均绝对差 / 变化像素占比。
⚠️ **算占小是正常的**：本项目发光灯丝只占画面 **~8%**（直径 2mm、间距 7.5cm 的细丝网格），
「变化像素占比 8.3%」≈ **灯丝像素几乎全变** ⇒ 判定生效。
不同物体的占比不一样（细丝灯带 ~8%，实心平面会是几十 %），**判据要对得上物体占比**，别拿固定阈值。

---

## §9 干跑实验的坑

- **材质必须挂到真实物体上**才能做驱动实验：挂在**无用户材质**上的驱动**根本不会被求值**
  （材质不在依赖图里），会得到"所有策略都 ❌"的假结论。
- ★★ **光挂上还不够 —— 那个物体得在"会被求值的场景"（= 活动场景）里**。
  新建一个只属于临时场景的物体 = 材质不在任何被求值的依赖图里 ⇒ 驱动全程不生效。
  **正确做法是复用工程里已有的物体（它本来就在主场景），额外 link 进临时场景**（见 §7-2）。
- 看到"所有变体统计值几乎一样 / 换帧像素差 0.00%"时，**先怀疑驱动压根没求值**，
  而不是怀疑材质逻辑。用求值依赖图直接读一次节点 socket 就能一眼确认（见 §8）。
- 临时实验对象/材质/场景/世界/**文本块**用完必须删，并在输出里校验 `leftover_*: []` 与对象总数回到原值。
- **本机历史残留**：早期探针会留下 `__P*SCENE` 之类的临时场景，每次干跑开头顺手扫一遍清掉。
- 别用"肉眼看起来一样"当判据 —— 用像素哈希/差异。

---

## §10 交付物模板

1. **建脚本**（幂等、可重跑、配置区置顶：`TARGET_OBJ / OLD_MAT / NEW_MAT / CTRL_NAME / PROPS`）
2. **核验脚本**（结构 + 行为，60+ 项；驱动真值走求值依赖图）
3. **预览渲染 + 像素差异脚本 + 拼图**（务必渲染**用户实际看到的那几个对象**，见 §7）
4. **使用说明 .md**：效果概述表 / 节点链 / 五个控件表（含范围与公式）/ 数据驱动原理 /
   **§6 刷新矩阵** / **把"整片全发光"的根因与修法写清楚** / 验证结论 / 用法 /
   「关于运动还能怎么玩」/ 文件清单
5. 用户习惯：**结论类交付物另存一份到 `E:\Desktop`**（含预览图）
6. 提醒 **Ctrl+S**（桥只改内存），不满意 `File > Revert`
7. **重写前先给旧脚本留还原点**（`_backup/xxx.v1_<日期>.py`）——
   用户说"直接重写更快吧"时也要留，否则回不去。

### 常见后续需求（"运动还有什么玩法"）

| 想要 | 做法（不改进材质） |
|---|---|
| 减速 / 停顿 / 加速 | 给控制空物体的 `z_speed` **打关键帧**（缓入缓出） |
| 呼吸感 | 给 `glow_strength` 打关键帧做正弦涨落 |
| 反向 | `z_speed` 设负值 |
| 分段相位差 / 行波 | 需要新节点（按 X 坐标加相位偏置），**当前 5 参数版没有**，要单独立项 |

> ⚠️ 别建议"移动空物体来做位移"—— 那会改掉噪波坐标系（见 §1）。

---

## 附：可直接改用的脚本

所有脚本顶部的 `WORKDIR` / `OUTDIR` 是**占位路径**，用前改成你本机的目录。

| 脚本 | 作用 |
|---|---|
| `scripts/build_noise_scroll.py` | **主建脚本（v4）**：建材质 + 7 控件（含反色/亮区阈值）+ 8 条驱动 + Register 面板（配置区在顶部）；重跑**保留用户已调的值**，只给新控件补默认 |
| `scripts/verify_noise_scroll.py` | **核验模板**（94 项；驱动真值走求值依赖图；含反色/亮区阈值断言） |
| `scripts/render_nz_preview.py` | 灯带预览渲染（隔离临时场景，用完清理还原帧） |
| `scripts/find_material_users_and_render.py` | 列出**所有**引用该材质的对象并按各自法线做正面渲染 |
| `scripts/compose_sheet.py` | 拼 N×M 对照图（`Image.scale()` 归一尺寸） |
| `scripts/compare_previews.py` | 两两像素级差异比对 |
| `scripts/probe_driver_recalc_matrix.py` | 【干跑】驱动写法 × tag 策略矩阵（**早期版**） |
| `scripts/probe_driver_recalc_real.py` | 在真实材质上复测 tag 策略 |
| `scripts/probe_driver_autotrigger.py` | 【干跑】驱动自触发写法矩阵 + `max/min/abs` 可用性（**有脏读陷阱，已被下表矩阵版取代**） |
| **`scripts/probe_driver_tag_matrix.py`** | **★ 干净版 tag 矩阵**（每种驱动类型独立新材质，每点只施加一种 tag）；跑完记得用下面的 cleanup |
| `scripts/probe_driver_tag_matrix_cleanup.py` | 配套收尾：清理临时物体/材质 + 确认真实材质未被污染 |
| **`scripts/probe_watchdog_liveness.py`** | **★ 看门狗活体核验**：`timers.is_registered()` + 用**用户在 UI 里拖的真实值**核对驱动真值 |
| `scripts/probe_temp_scene_eval.py` | 钉死"临时场景下的求值/读值行为"（§7-2 补充结论的来源） |
| `scripts/autorefresh_A_set.py` / `autorefresh_B_read.py` | 两段式验证"改属性不 tag"能否自动生效（§6 第 1/3 层） |
| **`scripts/render_invert_check.py`** | **★ 反色像素级验收**：相关系数 −1.0 判明暗颠倒 + 零控 + 驱动真值（§2 反色小节的数据来源） |
| `scripts/probe_invert_recon.py` | 【只读】加反色控件前的节点/连线/驱动/MapRange API 侦察 |
| `scripts/probe_restore_user_vals.py` | 【收尾】恢复被实验顶掉的用户调参值（验证脚本务必"先存原值"，这是兜底） |
| `scripts/probe_sparse_white_recon.py` | 【侦察】黑底白点可行性：Fac 分布分位数（20 万点）+ 顶部窗口试渲；**隔离临时场景渲染**（5.2 视频/图片格式 RNA 二选一，别动主场景格式） |
| `scripts/probe_threshold_e2e.py` | 【端到端】亮区阈值真实驱动链渲染 + 恢复用户值 |

> 参考探针（留在工程 `blender_control/` 下，未收进 skill）：`probe_50`（ColorRamp 色标可否挂驱动）、
> `probe_51`（对比度扫描 + 暴露内置 `frame` 无效）、`probe_52`（切活动场景 + 求值依赖图定位滚动驱动）。
