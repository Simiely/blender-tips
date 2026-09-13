---
name: blender-render-blackout-diagnose
description: 通过本地 9877 桥排查 Blender「材质不生效 / 渲染发黑 / 发光没效果 / 自发光不亮」类问题。当用户说「我给了发光材质渲染还是黑的」「材质不亮」「自发光没反应」「对象渲染出来是黑的」「材质覆盖导致不显示」「改了节点没效果」时使用。提供按命中率排序的七条排查路径（View Layer 材质覆盖 / 引擎不读材质 / Holdout 与相机可见性 / Material Output 未连线或改错节点 / AgX 色彩变换压暗 / 透明度与半透明 / 材质数据块被共享覆盖）与一次打全的诊断脚本。
agent_created: true
---

# Blender 渲染发黑 / 材质不发光 排查

传输层（9877 桥、客户端封装、120s 上限、Blender 5.x API 坑）见 **`blender-bridge-ops`** skill。

**核心原则**：这类问题 90% 不在材质节点里。**先查"材质有没有被顶掉 / 有没有被排除"，再查节点连线，最后才怀疑数值**。顺序反了会在节点树里白折腾半天。

## 铁律

1. **先跑一次全景诊断**（`scripts/diagnose_blackout.py`），一条请求打全七条路径 —— 不要把七条拆成七次往返
2. **先看全局开关，再看局部节点** —— 材质覆盖 / 引擎 / Holdout 是"一刀切"级别的，命中率远高于节点连线
3. **报告要带上"为什么"** —— 光说"是覆盖材质"不够，要说清"覆盖材质会让全场景 N 个材质全部被替换，所以你改的任何材质都不生效"
4. 改之前**出差异预览**；改材质节点前先快照原连线（可回溯）

---

## 一、七大排查路径（按命中率降序）

### ① View Layer 材质覆盖 `material_override` ★最高频

**症状**：给任何对象配任何材质都没反应；全场景渲染成同一种观感（常常是黑/灰）。

```python
for vl in scene.view_layers:
    print(vl.name, vl.material_override)   # 非 None 就是它
```

- 这是 **View Layer 级属性，不在材质里**，查材质树永远查不到 —— 所以极难自查到
- 一个 `material_override` 会把**该视图层下全部对象**的材质统统替换成它
- 用户常见来源：从别的工程/教程文件继承、同事调试图省事、Max/C4D 转换流程留下的
- **清除**：`vl.material_override = None`（在 `Properties → View Layer → Material Override`，或渲染属性里）
- 注意 **Workbench 另有** `scene.display.shading.color_type == 'SINGLE'` + `single_color`，效果类似（整场景单色），排查时两条都要看

### ② 渲染引擎不读材质节点

- `scene.render.engine == 'BLENDER_WORKBENCH'` → **完全忽略材质节点树**，只看 `shading.color_type`（`MATERIAL` 用 `diffuse_color`、`SINGLE` 用单色）。发光材质在 Workbench 下**永远不发光**
- 要出材质/发光效果必须是 **`BLENDER_EEVEE_NEXT`**（4.2+ / 5.x 的 EEVEE 名）或 **`CYCLES`**
- 实测案例：某分镜工程一直是 `BLENDER_WORKBENCH`，用户配完发光渲染全黑，切到 Cycles 才有效

### ③ Holdout / 相机可见性 / 视图层排除

对象级"一刀切"，任一条命中都会让对象在渲染里消失或变黑：

| 属性 | 含义 |
|---|---|
| `ob.is_holdout` | **Holdout**：渲染时被抠掉（输出黑/透明），最像"材质没用" |
| `ob.indirect_only` | 只参与间接光，相机直看不到 |
| `ob.visible_camera` | 相机可见性，False = 相机拍不到 |
| `ob.visible_diffuse/glossy/transmission/shadow` | 各类光线可见性 |
| `ob.is_shadow_catcher` | 阴影捕捉器（本身不显示） |
| `ob.hide_render` | 渲染隐藏 |
| `view_layer.objects.get(name) is None` | 被视图层排除（Exclude），跟 `hide_viewport` 不是一回事 |

排查时**逐条打出来**，别只看 `hide_render`。

### ④ Material Output 未连线 / 改错节点 ★本 skill 最"隐蔽"的坑

**症状**：确实改了发光强度，但没效果；或者"我明明设了 100 却是暗的"。

```python
out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
print(out.inputs['Surface'].is_linked)              # False = 整棵树没接输出
for l in nt.links:
    if l.to_node == out:
        print(l.from_node.type, l.from_node.name)   # 真正生效的是这个节点
```

三个高频子情形：

1. **一个材质里有多个 BSDF，只有其中一个接在输出上** —— 用户改了**没接线的那个**。实测案例：`Material #18526fds.001` 里 `原理化 BSDF` 的 `Emission Strength = 100`（**孤儿节点，未连输出**），而真正接在输出上的是 `原理化 BSDF.001`（`Emission Strength = 10`）。用户看到 100 以为够亮，实际生效的是 10
2. **存在多个 `OUTPUT_MATERIAL`**，只有 `is_active_output == True` 那个生效 —— 改了另一个
3. **`mat.use_nodes == False`** —— 节点树被整个旁路，只用 `diffuse_color`，谈不上发光

> 诊断脚本会专门输出「**发光值 > 0 但未接到输出**的节点清单」——这类节点是"假发光"，几乎必然对应一个迷惑中的用户。

### ⑤ 色彩变换（View Transform）把发光压暗

- Blender 4.x/5.x 默认 **AgX**，对高亮有强烈滚降（highlight roll-off）+ 高亮去饱和。**曾经在 Filmic/Standard 下 `Emission Strength = 5` 就很亮，AgX 下 10 也像哑光**
- 排查：`scene.view_settings.view_transform` / `look` / `exposure` / `gamma`
- 对策（按推荐度）：
  1. **提高发光强度**（AgX 下常见量级要到 50~500+，视场景）
  2. 临时切 `Standard` 验证是否只是色调映射问题（**验证手段，别当最终交付**）
  3. 用 `look` = `AgX - Punchy` 之类提升对比
- **注意**：这是"看起来不够亮"，不会让材质变**纯黑**。纯黑要往 ①②③④ 找

### ⑥ 透明度 / 半透明 / 背面剔除

- `mat.blend_method`（EEVEE）= `BLEND`/`HASHED`/`DITHERED` + Principled 的 `Alpha` 接了贴图 alpha → 透明区域看着像"黑"或"没渲染出来"
- `mat.surface_render_method`、`mat.use_backface_culling = True` → 法线反的面直接消失
- 贴图 alpha 全 0、或 Base Color 接了空图像 → 黑
- 顺带：`mat.diffuse_color`（视口颜色）与节点树结果无关，不要拿它当判断依据

### ⑦ 材质数据块被共享 / 被覆盖后又被改回

- 材质可能是**多对象共享**（`mat.users` 很大）。实测案例 `Material #18526fds.001` 有 **61 个使用者** —— 改它会**同时改掉 61 个对象**，容易被当成"改了没反应"（其实改了别处也在变）或"改错了对象"
- 用户可能在**别的对象**上配的发光材质，当前对象挂的是另一个（先 `print` 出 `ob.material_slots[i].material`，别凭记忆）
- `.001` 后缀的材质是**复制残留**，容易与无后缀原版混淆

---

## 二、一次打全的诊断脚本

`scripts/diagnose_blackout.py` —— 通过桥发送即可（默认全场景扫描，顶部 `TARGET` 可填对象名做对象级体检）：

```
python bl.py diagnose_blackout.py
```

输出分区：

| 区 | 内容 |
|---|---|
| A | 引擎 / view_transform / look / exposure / film_transparent |
| B | **所有 view layer 的 `material_override`** + Workbench `color_type`/`single_color` |
| C | 全场景材质健康度：输出未连线数、**"假发光"节点清单**（发光>0 但未接输出）、多 BSDF 只连一个的材质、`Transparent BSDF` 直连输出、`use_nodes=False` |
| D | 对象级（填了 `TARGET` 时）：类型/父子/可见性全套开关/Holdout/slots/材质树连线 |
| E | **结论区**：按本次扫描结果直接给出"头号嫌疑 + 建议动作" |

因为要遍历材质树，**材质多时耗时上升**（200+ 材质实测 0.1s 级，很快；切勿在脚本里遍历 Action 的 fcurve，那才是慢的来源，见 `blender-bridge-ops`）。

## 三、排查报告模板

给用户的结论按这个结构写：

1. **头号结论一句话**（如"是 View Layer 材质覆盖，不是你的材质有问题"）
2. **机制解释**（为什么覆盖材质会让发光失效）
3. **其余嫌疑项的实测值与判定**（用表格，逐条给"命中/不命中"）
4. **建议动作**（改什么、在哪改、改完怎么验证）
5. **顺带发现的隐患**（如"该材质有 61 个使用者，改动会波及 61 个对象"、"存在一个发光 100 的孤儿节点"）

## 本机路径约定

- 工程：以桥探查的 `bpy.data.filepath` 为准（本工程曾从 `260910xAx01.blend` 另存为 `260912xAx02.blend`，**别凭记忆写死**）
- 工作目录：`C:\Users\wandou\WorkBuddy\<时间戳>\blender_control\`
- 客户端：`bl.py`（`python bl.py <脚本.py>`，结果落 `<脚本.py>.out`）
