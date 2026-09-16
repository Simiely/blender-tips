# 参数化驱动维护脚本包

给**已经建好的**「空物体自定义属性 + `SINGLE_PROP` 驱动器」参数化材质系统做运维改造:

- 查清**谁在读**某个参数(引用体检)
- 把某个参数的**关键帧动画收敛成常量**
- 改名/换轴时**不留失效驱动**(见配套文档 §3)

配套文档:[`docs/驱动参数化材质维护.md`](../../docs/驱动参数化材质维护.md) ·
作业规范:[`skills/blender-driver-param-maintenance/`](../../skills/blender-driver-param-maintenance/)

## 文件清单

| 文件 | 作用 |
|---|---|
| `param_ref_scan.py` | **引用体检**(只读):`MODE='refs'` 列出谁在读指定属性;`MODE='health'` 列出全库失效驱动 + 悬空引用 |
| `strip_keys_to_constant.py` | **关键帧 → 常量**:`MODE='report'` 导出曲线存档(回滚依据);`MODE='apply'` 删曲线并写回常量 |

两个脚本都是**幂等**的,可以反复跑;`MODE='report'` / `health` 全程只读。

## 为什么需要引用体检(本包的核心)

驱动器的**宿主**不止一处。除了控制物体与材质节点树,Blender 5.x 的**灯光/网格数据块自带
`node_tree`**,面光灯的同构接入驱动全都挂在那里:

```python
o.animation_data                      # 对象级
o.data.animation_data                 # 数据块级
o.data.node_tree.animation_data       # ★ 最常漏的一层
o.modifiers[i].node_group.animation_data
```

漏扫这一层会**两个方向都出事**(实测):

1. **误判**:某个属性明明被 7 盏灯的节点树读着,却报告"全库零引用 ⇒ 假控件";
2. **事故**:把 `Z向速度` 改名为 `X向速度` 后,那 7 条漏扫到的驱动变成 `is_valid=False`
   (**静默失效**),面光灯的噪波滚动整片停摆 —— UI 上完全看不出来,只有体检能发现。

所以标准动作是:**改前 `refs` 看消费者清单,改后 `health` 复验 0 条失效**。

## 使用步骤

```python
# 1) 送桥执行(Blender 里先 Run Script 起桥)
python send.py param_ref_scan.py
```

改 `param_ref_scan.py` 顶部 CONFIG:

```python
MODE = 'refs'          # 'refs' | 'health' | 'both'
TARGET_ID = ""         # 目标 ID 名;空串 = 全库
PROPS = []             # 要查的键;空 = 全部自定义属性
OUT_DIR = r""          # 报告输出目录(留空 = 只打印)
```

```python
# 2) 关键帧收敛:先 report 留档,再 apply
MODE = 'report'        # 先看 (帧,值) 全表 + 当前帧求值
OWNER_KIND = 'OBJECT'  # 'OBJECT' | 'OBJECT_DATA_NT' | 'MATERIAL_NT'
OWNER = "竖向灯001_噪波控制"
DATA_PATH = '["噪波种子"]'
CONSTANT = None        # None = 当前帧所见值(画面不跳变);或给具体数值
```

```python
# 3) 改完必须【另起一次请求】复核
MODE = 'health'        # 判据: 失效 0 条 + 悬空 0 条
```

## 写回节点插槽

`DATA_PATH` 为空串以外的节点插槽路径时(如 `nodes["噪波纹理"].inputs[1].default_value`),
写回需要 `NODE_NAME` / `SOCKET_INDEX`:

```python
DATA_PATH = 'nodes["噪波纹理"].inputs[1].default_value'
NODE_NAME = "噪波纹理"
SOCKET_INDEX = 1
```

## 可复用结论(实测)

- **`driver_add()` 会把表达式自动填成"当时的数值"** ⇒ 装完必须显式覆盖 `d.expression`,
  否则等于装了个常量驱动,参数纹丝不动。
- **顺序铁律**:驱动重建完成**之后**才删旧属性键,否则留下悬空引用。
- **`drivers.find(path, index)`** 的 `index` 必须**关键字传参**(位置传参报 `TypeError`)。
- **`id_properties_ui(k)`** 要 `.as_dict()`,不能下标;`update()` **不接受 `name`**——
  自定义属性的显示名就是键名。
- 脚本改 IDProperty 后驱动不会自动重算 ⇒ `ctrl.update_tag()` + `bpy.context.view_layer.update()`。
- **验收要读下游插槽的动态读数**:例如把速度设 0.5,`frame_set(100)` 后主材质 + 7 盏灯的
  `滚动映射` X 分量都应精确等于 50.0(一次覆盖全部消费者);测完还原参数与帧号。
