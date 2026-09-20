---
name: blender-driver-param-maintenance
description: 给**已经建好的**「空物体自定义属性 + SINGLE_PROP 驱动器」参数化材质系统做运维改造——查清「这个参数到底谁在读」、把某个参数的**关键帧动画收敛成常量**、给参数**改名/换轴**而不留失效驱动。当用户说「这个参数改了没效果」「检查一下参数是不是没接上」「把 XX 的关键帧去掉，改成常量」「XX 速度改成 YY 速度」「参数改个名」「把驱动从 Z 轴挪到 X 轴」「检查有没有坏掉的驱动」时使用。核心是两张体检表：改前 `refs`（消费者清单，**必须扫到 `物体数据 → node_tree` 层**，灯光/网格自带节点树、驱动都挂在那里，漏扫会双向出事：误判"假控件"或改名后驱动 `is_valid=False` 静默失效）；改后 `health`（全库失效驱动 + 悬空引用，判据 0 条）。另含关键帧收敛的存档纪律、驱动换轴的六步顺序、三个容易混淆的「index」。
agent_created: true
---

# 参数化驱动的引用体检 · 关键帧收敛 · 改名换轴

> 一句话：**改参数前先做引用体检，改完必须做失效体检。**
> 两张体检表对应两个脚本(`param_ref_scan.py` 的 `refs` / `health` 模式),
> 判据是**消费者看得全**、**失效 0 条**。

**先读这两个前置 skill：**

| 需要什么 | 去哪 |
|---|---|
| 怎么把代码送进正在运行的 Blender(桥、客户端封装、120s 上限、5.x Slotted Action) | **`blender-bridge-ops`** |
| 这套参数化系统的**建法**(SINGLE_PROP 驱动、空物体中文属性 + `id_properties_ui`、tag 矩阵、看门狗刷新) | **`blender-procedural-emission-material`** / **`blender-radial-pulse-material`** |
| 拆曲线 / 建曲线 / 分层 Action 的读写细节 | **`blender-bridge-ops`** |

配套文档:[`docs/驱动参数化材质维护.md`](../docs/驱动参数化材质维护.md) ·
脚本包:[`scripts/driver-param-maintenance/`](../scripts/driver-param-maintenance/)

**实测环境**：Blender **5.2.0 LTS** / Windows / 9877 桥。

## 铁律

1. **先体检再动手**。跨 data-block 的改名/删键,必须先拿到"消费者清单";数量对不上就别改
2. **改完必跑失效体检**——`is_valid=False` 与悬空引用**都必须是 0**;做不到就别收工
3. **顺序铁律**:驱动**重建完成之后**才删旧属性键(反了会留悬空引用)
4. **删关键帧前先留档**:把 `(帧, 值)` 全表 + 插值 + 外插 + 当前帧求值打印/落盘,那是唯一的回滚依据
5. **改与验分两次请求**(同一次 exec 内读的是未刷新缓存值)
6. **验收读下游插槽的动态读数**,不要只读控制物体上的属性值
7. **桥不存盘** → 收尾必须提醒用户 `Ctrl+S`

## §1 引用体检:`refs` 模式(改前)

扫描必须覆盖(一条都不能少):

```python
o.animation_data                        # 对象级(自定义属性/变换)
o.data.animation_data                   # 数据块级
o.data.node_tree.animation_data         # ★ 最常漏:灯光/网格/世界自带节点树
o.modifiers[i].node_group.animation_data
# 全局: materials(+.node_tree) / node_groups / scenes / worlds(+.node_tree)
```

**漏这一层会双向出事(都实测过)：**

| 方向 | 症状 | 案例 |
|---|---|---|
| 误判 | 明明接了线的参数被报告成"假控件(零引用)" | `面光统一强度` 的消费者在 7 盏灯的 `AreaLight → Shader Nodetree`(节点 `发光强度.001`,`expr='st * k'`) |
| 事故 | 改名/删键后驱动**静默失效**,画面不动但 UI 无异常 | `Z向速度→X向速度` 改名后,7 盏灯各 1 条驱动 `is_valid=False`,噪波滚动整片停摆 |

**下"假控件"结论之前的最后一道闸**：把参数改成一个可辨识的值,读**下游插槽**是否跟着变。
跟着变 ⇒ 不是假控件,是你没扫全。

## §2 关键帧 → 常量(收敛)

```
读(留档) → 定常量 → 只删目标那条 fcurve → 写回 → update_tag → 另起请求验证
```

- 定常量的两种口径:**当前帧所见值**(`fc.evaluate(frame_current)`,画面不跳变)
  或**用户指定值**(如"改成 200")。用哪种要让用户知道结果值是多少
- **只删 `目标 data_path + array_index`** 那一条,同一 action 的其它曲线原样保留;
  删完打印"动作剩余 fcurves"作证据
- 自定义属性关键帧走分层 Action:`action.layers[].strips[].channelbags[].fcurves`
- 变量被驱动器读取时,删关键帧**不影响驱动** —— 驱动自动读到新常量

## §3 改名 + 换轴(六步,顺序不能乱)

```
① 体检拿消费者清单  →  ② 新属性 = 旧值 + UI 元数据全量复制(as_dict/update,描述文案同步改轴向)
→ ③ driver_remove(path, 旧分量) → driver_add(path, 新分量) → 重建变量(id_type 先于 id)
     → ★ 显式覆盖 d.expression   ④ 旧分量归零
→ ⑤ 全部驱动重建完 → 才删旧属性键   ⑥ update_tag + 失效体检 + 动态验证
```

- `driver_add()` 会把表达式**自动填成当时的数值** ⇒ 不覆盖 `d.expression` 就等于装了个常量驱动
- 同名参数常被**多处同构接入**(主材质 + 若干面光灯节点树):换轴时**全都要搬**,
  否则两边滚动方向不一致、且漏搬的那批直接失效
- `id_properties_ui(k)` 必须 `.as_dict()`(不能下标);`update()` **不接受 `name`** ——
  自定义属性的显示名就是键名,换标签只能换键,逻辑读键处(驱动变量 `targets[0].data_path`)同步改

## §4 三个「index」别混

| 概念 | 长什么样 | 说明 |
|---|---|---|
| 驱动 FCurve 分量索引 | `drivers.find(path, index=2)` / `driver_remove(path, 2)` / `driver_add(path, 2)` | 向量插槽 X/Y/Z;`find()` 的 index **必须关键字传参** |
| DriverTarget 数组分量 | 5.2 **无 `.array_index`** | 写进 `data_path='location[0]'` |
| ActionSlot 标识 | `.identifier` / `.name_display` | **没有 `.name`/`.display_name`** |

## §5 验收口径(`health` 模式)

1. **失效驱动 0 条**(`driver.is_valid == False`)
2. **悬空引用 0 条**(变量 `data_path` 形如 `["X"]` 但该 ID 已无 `X` 键)
3. **动态读数**:参数设 0.5 → `frame_set(100)` → 主材质 + 全部同构灯插槽都应 **= 50.0**(逐位一致);
   测完还原参数与帧号
4. 关键帧收敛看"动作剩余 fcurves"清单

## §6 常见误报与真 bug 的分界

- **"拖了没反应"** 先问三句:① 它进相位了吗(时长类参数只进周期 = 数学恒等变换)?
  ② 当前帧在它的定义域内吗? ③ 用户拖的是哪个 data-block(真控件还是镜像)?
- **"改了没效果"** 若属性确实被读,再查:值是否被 `min/max` 静默钳位、是否读的是未刷新缓存
- 反过来,**真 bug 的典型长相**:`is_valid=False`(驱动表达式/变量解析失败)、
  变量的 `data_path` 指向不存在的键 —— 这两类都能被 `health` 一次打全
