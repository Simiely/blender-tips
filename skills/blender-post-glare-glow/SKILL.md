---
name: blender-post-glare-glow
description: 通过本地 9877 桥给 Blender 的**渲染画面**加**合成器后期辉光(眩光 / Glare)**,节点组 `渲染层 → 眩光 → 合成输出` 挂在 `scene.compositing_node_group` 上,6 个中文滑块(辉光开关 / 强度 / 阈值 / 尺寸 / 饱和度 / 最大亮度)长在一个**空对象**上,`类型`/`质量`/`染色`/`阈值过渡柔度` 留在节点上不设驱动给用户手调。当用户说「加个后期辉光」「后期辉光效果」「眩光 / Glare」「光晕 / 泛光 / bloom」「灯带/霓虹/LED 的光晕」「发光溢出」「渲染完再加一层辉光」「辉光强度 / 辉光阈值 / 辉光尺寸 怎么调」「合成器里加辉光」「加了辉光没效果 / 辉光不生效 / 画面完全没变」「节点上参数拖不动 / 框是紫色 / 参数是灰的」「5.2 合成器怎么接」「辉光参数挂到空对象上」时使用。★★★ 头号坑:**终结节点必须是 `NodeGroupOutput` 且必须先用 `tree.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')` 声明组输出插座 —— 少了这步整条合成被「静默旁路」**(不报错、画面完全不变、**连 PNG 文件字节数都一模一样**);★★ 不要把 `CompositorNodeConvertToDisplay` 当终结节点(色彩管理套两遍,旁路档 max=0.4039);★★ 驱动挂在**合成器节点树**上时**脚本读插座必须手工 `ng.update_tag()`** 否则读到陈旧值(但**渲染路径会自己求值**);★★ `drivers.new()` 追加到末尾 / `remove()` 前移 ⇒ **一律按 `data_path` 匹配**、`DriverVariable` 的 `data_path`/`id` 在 **`v.targets[0]`** 上;★ `Type`/`Quality` 是 MENU 插座且取值是**标题式字符串**(`'Fog Glow'`,全大写 `TypeError`)、**没有 `.enum_items`**;★ `Size`/`Strength`/`Saturation`/`Smoothness` 的 subtype 是 `FloatFactor` ⇒ 0–1(旧配方 `Size=12` 已死);★ **大尺寸 + 低采样 = 噪点放大器**;★ 自定义属性要像滑块必须写**硬 `min`/`max`**(只写 soft 不够);★ 紫色插座 = 被驱动不是锁死,`NodeSocket.description` 有 **63 字节**上限、`label` 只读;★ 视口要另设 `shading.use_compositor='ALWAYS'`;★★ 判据陷阱:**本类工程的 Cycles 不是逐位确定的**(单像素压在 8bit 量化台阶中点,差值恰好 1/255)。
agent_created: true
---

# 合成器后期辉光(Glare)

传输层(9877 桥、`send.py`、120 s 上限、Blender 5.x API 坑、引用判定)见 **`blender-bridge-ops`**。
**材质级**发光见 `blender-procedural-emission-material` / `blender-cylinder-spiral-material` /
`blender-radar-scan-material` / `blender-sweep-angle-material` / `blender-radial-pulse-material`。
本 skill 专讲:**渲染之后的合成器那一层** + **参数外挂到空对象** + **5.x 合成器迁移的静默失效**。

- 原理与坑的完整版:[`../docs/合成器后期辉光-Glare.md`](../docs/合成器后期辉光-Glare.md)
- 脚本包:[`../scripts/post-glare-glow/`](../scripts/post-glare-glow/)(**只维护一份**,本 skill 目录下不放副本)

## 铁律

1. **先只读侦察**(`probe_glow.py`)。它回答 4 个问题:合成器现状 / **是不是旧配方** /
   空对象与旋钮在不在 / 驱动有几条、`is_valid` 如何。别对半成品盲改。
2. **★★★ 终结节点必须是 `NodeGroupOutput`,而且必须先用 `interface.new_socket(...)` 声明组输出插座。**
   少这一步整条合成被**静默旁路**。**每次构建后都要断言这两件事**,不能靠"看着有变化"。
3. **★ 判"效果生效"绝不能靠 md5 / 文件大小。** PNG 有时间戳块 ⇒ md5 不同而字节数相同。
   **必须比像素**,而且先跑自证(同设置渲两次)。
4. **不要把 `CompositorNodeConvertToDisplay` 当终结节点**(色彩管理套两遍)。
5. **参数挂空对象 ⇒ 必须把该对象设为 `view_layer.objects.active`**(属性面板只显示活动对象)。
6. **不设驱动的插座留给用户手调**(`类型`/`质量`/`染色`/`阈值过渡柔度`),
   与"ColorRamp 零驱动、颜色归用户"同一约定。
7. **读插座值前必须强刷新**(`ctrl.update_tag()` + `ng.update_tag()` + 依赖图更新),
   否则拿到**陈旧值**并得出**完全错误的结论**。★ 但**别把这当成"用户改了没用"的理由** ——
   渲染路径会自己求值。
8. **改驱动器的变量必须原子重建**;规格比对按 `data_path`,变量字段读 `v.targets[0]`。
9. **`build` 与 `maintain` 分工**:`build` 会重建链条/恢复默认值;`maintain` 只动驱动与旋钮 UI。
   **用户手调过后只想修驱动 ⇒ 跑 `maintain`。**
10. **执行完另起一次请求独立核验**,核验脚本自己也要**自证不自证**(见 §5)。
11. **桥只改内存**:收尾必须提醒用户 **Ctrl+S**。
12. **超出本主题范围的事先问**:比如"顺手修掉仓库里别的失效配方" —— 那是别人的脚本。

---

## §1 目标结构

```
scene.compositing_node_group  ──>  节点组「后期辉光」(CompositorNodeTree)
                                    渲染层(RLayers) ──Image──> 眩光(Glare) ──Image──> 合成输出(NodeGroupOutput)
                                    interface: 必须有一个 OUTPUT 插座(SOCKET / 'OUTPUT')
空对象「辉光控制」  6 个自定义属性  ──5 条 SCRIPTED 驱动──>  眩光节点的 5 个输入插座
```

| 驱动 `data_path` | 表达式 | 变量 |
|---|---|---|
| `…["Threshold"].default_value` | `th` | `th ← 辉光阈值` |
| `…["Size"].default_value` | `sz` | `sz ← 辉光尺寸` |
| `…["Saturation"].default_value` | `sa` | `sa ← 辉光饱和度` |
| `…["Maximum"].default_value` | `mx` | `mx ← 辉光最大亮度` |
| `…["Strength"].default_value` | `(sw * st)` | `sw ← 辉光开关`,`st ← 辉光强度` |

`辉光开关` 不单独占插座,乘进 `Strength` ⇒ `开关=0` 时 `Strength=0` ⇒ **真旁路**。

## §2 5.x 合成器事实(全部实测)

| 事实 | 说明 |
|---|---|
| 树的位置 | `scene.compositing_node_group`(`CompositorNodeTree`) |
| `scene.node_tree` | **5.0 已移除** |
| `scene.use_nodes` | 恒 `True`,**设了没用** |
| 总闸 | `render.use_compositing` |
| 终结节点 | **必须 `NodeGroupOutput` + 先声明 OUTPUT 插座** |
| 视口可见 | 需 `space.shading.use_compositor='ALWAYS'`(默认 `DISABLED`)+ `shading.type='RENDERED'` |
| 路线图 | 5.0 上 CPU 实时合成器(RTR);5.2 移除旧 CPU 合成器 ⇒ 老教程不能直接套 |

**眩光节点插座清单(5.2 实测 22 输入 / 3 输出)**:

```
输入: Image, Type, Quality, Threshold, Smoothness, Clamp, Maximum, Strength, Saturation,
      Tint, Size, Streaks, Streaks Angle, Iterations, Fade, Color Modulation, Diagonal,
      Sun Position, Jitter, Kernel Data Type, Kernel(Float), Kernel(Color)
输出: Image, Glare, Highlights
```

| 类别 | 插座 | 类型 |
|---|---|---|
| MENU | `Type` / `Quality` / `Kernel Data Type` | 标题式字符串,无 `.enum_items` |
| 0–1 量程 | `Strength` / `Saturation` / `Size` / `Smoothness` / `Fade` / `Color Modulation` / `Jitter` | `NodeSocketFloatFactor` |
| 不受 0–1 限 | `Threshold` / `Maximum` | `NodeSocketFloat` |
| 整数 | `Streaks` / `Iterations` | `NodeSocketInt` |

`Type` 候选:`'Fog Glow'` / `'Bloom'` / `'Streaks'` / `'Ghosts'` / `'Simple Star'` / `'Kernel'`。
`Quality` 候选:`'Low'` / `'Medium'` / `'High'`。

## §3 参数表(6 旋钮,键在空对象上)

| 旋钮 | 默认 | 硬 | 软 | 目标 |
|---|---|---|---|---|
| `辉光开关` | 1.0 | 0–1 | 0–1 | `Strength`(乘子) |
| `辉光强度` | 1.0 | 0–4 | 0–2 | `Strength` |
| `辉光阈值` | 1.0 | 0–50 | 0–20 | `Threshold` |
| `辉光尺寸` | 0.5 | 0–1 | 0–1 | `Size` |
| `辉光饱和度` | 1.0 | 0–4 | 0–2 | `Saturation` |
| `辉光最大亮度` | 10.0 | 0–500 | 0–100 | `Maximum` |

★ 要像滑块必须写**硬 `min`/`max`** + `step=0.01`;只写 `soft_*` 会留成普通数值框。

## §4 陷阱清单(按杀伤力排序)

**A. ★★★ 静默旁路 —— 本主题唯一"全无信号"的失效**
终结节点不是 `NodeGroupOutput`,或组没声明 OUTPUT 插座 ⇒ 不报错、画面完全不变、
**连 PNG 字节数都一模一样**。识别信号只有:"所有变体的出图字节数完全相同"。
⇒ 构建后**必须断言** `终结节点.bl_idname == 'NodeGroupOutput'` 且存在 `OUTPUT` 插座。

**B. ★★ 拿 md5 / 文件大小判"两张图一样"**
PNG 含时间戳块 ⇒ md5 不同、字节数可完全相同。**必须比像素。**

**C. ★★ `CompositorNodeConvertToDisplay` 不能当终结节点**
色彩管理套两遍;旁路档实测 `max=0.4039` / `90944/129600` 分量被改。

**D. ★★ 驱动挂合成器树上:脚本要 tag,渲染不用**
只更新依赖图 ⇒ 读到**陈旧值**(实测属性 1.0→3.5、插座停在 1.0)。
但渲染路径全程不 tag 也会自己求值(实测差 `120817/230400` 分量)。
⇒ **别把"脚本读到旧值"当成"用户改了没用"**。

**E. ★★ 驱动维护三件事**
`drivers.new()` **追加到末尾**、`remove()` 让后续前移 ⇒ **按 `data_path` 匹配,不按下标**;
`DriverVariable` 没有 `.data_path` / `.id`(在 `v.targets[0]` 上,读错就每跑必重建);
改**变量**必须**原子重建**整条驱动。

**F. ★ MENU 插座是标题式字符串,且没有 `.enum_items`** ⇒ 全大写 `TypeError`,枚举只能试写。

**G. ★ subtype 决定量程** ⇒ `FloatFactor` 的 0–1;**旧配方 `Size=12` 已失效**。

**H. ★★ 大尺寸 + 低采样 = 噪点放大器** ⇒ 12 samples 不降噪 + `尺寸=1.0` 会炸成雪花;
**先把渲染弄干净再调大尺寸**。

**I. ★ 紫色插座 = 被驱动,不是锁死。**
Blender 每次求值都把它重算回驱动结果 ⇒ 手输立刻被覆盖。
**要改的是驱动源,不是显示值。** 顺手做可发现性:节点 `label` 指路 +
被驱动插座 `description` 写 `被驱动 →「<空对象>」的<旋钮名>`;
★ `description` 硬上限 **63 字节**(超了静默截断)、**`NodeSocket.label` 只读**。

**J. ★ 视口看不见辉光** ⇒ `shading.use_compositor` 默认 `DISABLED`,要设 `'ALWAYS'`。

**K. ★ 报告串位:别复用循环残留变量**(在分支里用上一个 `for` 的 `d` ⇒ 打印的是隔壁驱动,
**数据是对的、报告是错的**)。

**L. ★ 桥的既有约束**:无 `__file__` ⇒ 路径写绝对常量;脚本不能带 BOM;
**异常会让前面所有 print 全丢**;硬超时 120 s(出图脚本要控制分辨率/张数)。

## §5 核验与"自证不自证"

`verify_glow_render.py` 三层 8 项:**先证工具可靠,再证效果成立**。

| # | 断言 | 能怎么失败 |
|---|---|---|
| [0] | 同设置渲两次逐位相同 | 不成立则后面比对都不作数 |
| [1] | `开关=0` ≡ 完全不加合成器 | 接错终结节点 / 色彩管理多套一层 ⇒ 掉 |
| [2] | 增益 >0.02 的像素 >500;最大变暗 >−0.02 | 没生效 ⇒ 掉;"把高光搬走" ⇒ 掉 |
| [3] | 暗部增益占比 >10%;暗部最大单点 >0.02;高光也被加强 | "整体提亮" ⇒ 掉 |
| [4] | 尺寸↑⇒暗部增益↑;**阈值↑⇒总增益↓**;**强度↓⇒总增益↓** | 阈值/强度接反 ⇒ 掉 |

★★ **判据陷阱(实测)**:本类工程(对象上万、大量高光)的 **Cycles 不是逐位确定的** ——
`[0]` 会报 `max=0.00392157 / 差异分量 1/360000`,而**差值恰好 1 个 8bit 台阶、
两侧中点正好是 `x.5/255`**;再跑一次**抖动的像素换成另一个**。
⇒ 真实浮点值压在**量化台阶中点**,是**度量比介质更严**,不是辉光坏了。
本包的分层处理:`[0]` 工具自检保持严格 **+ 自动打印差异诊断**(坐标 / 台阶数 / 中点);
`[1]` 物理结论给 1 个量化步容差(真不等价会让**成千上万**个分量一起变)。
要硬结论就**改渲 32 位浮点 EXR 再比**。**先怀疑度量,再怀疑被测对象。**

`maintain_glow.py` 的行为验收法(不看 `is_valid`,看插座跟不跟):
改旋钮 → 强刷新 → 读插座 → 还原;并单独验 `开关=0 ⇒ Strength=0`。

## §6 与相邻 skill 的边界

| 想要什么 | 用哪个 |
|---|---|
| 渲染**之后**整幅画面的光晕/泛光 | **本 skill**(合成器) |
| 某个**材质**自己发光(噪波滚动 / 径向脉冲 / 圆柱螺旋 / 平面扫光) | `blender-procedural-emission-material` 及其专项姊妹 |
| **灯柱**可见且边缘羽化(体积) | `blender-volume-beam-feather` |
| 渲染发黑 / 材质不发光(排查) | `blender-render-blackout-diagnose` |
| 怎么把代码送进正在运行的 Blender | `blender-bridge-ops` |

★ 交叉点:`render.use_compositing` / 视图层材质覆盖这类"画面为什么不对"的问题,
先看 `blender-render-blackout-diagnose`(它列的七条路径里就有材质覆盖与 AgX)。

## §7 换工程时要改什么

四个脚本顶部都有 `═══ 配置(换工程改这里) ═══` 段落,通常只需改:

* `CTRL_NAME`(空对象名)、`NODE_GLARE`(眩光节点名)、`GROUP_NAME`(节点组名)
* `verify_glow_render.py` 另有 `OUT`(出图目录)、`VW/VH/SAMPLES`(控制 120 s 超时风险)、
  `DET_MAX_*` / `EQ_MAX_*`(判据容差,见 §5)
* `probe_glow.py` 另有 `LEGACY_NODE_NAMES` / `LEGACY_TERMINAL_TYPES`(旧配方判定)

★ **驱动地址里用的是 `node.name`,不是 `label`** ⇒ 改 label 安全,改 name 会让驱动失效
(此时跑 `maintain_glow.py` 原子重建即可修复)。
