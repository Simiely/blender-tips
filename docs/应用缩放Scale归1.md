# 修改缩放：把 Scale 归 1 且保持大小不变

来源：`260827x07_主装置迁移.blend` 实战（1423 对象 / 879 静态 / 桥批量处理 / Blender 5.2）覆盖：原理 → 做法 → 注意事项（几何预放大陷阱 / 多用户网格 / 负缩放 / 大倍数副作用 / 验证与还原）

## 一、场景：想让 Scale 全是 1，但画面不能变

模型是从 3ds Max / 其它 DCC 搬进来的，大量对象带着非单位缩放（实测 0.0027 ~ 40 倍），三轴还不一致。想让所有静态对象的 `scale` 归一成 `(1,1,1)`，到驱动、对齐、导出时不再被"缩放尾巴"干扰，**但同时不能改变物体在世界里的实际大小和位置**。

## 二、原理：应用缩放 = 把缩放“烘焙”进网格顶点

对象某顶点的世界位置 = `T · R · S · v`（位置·旋转·缩放·局部坐标）。**应用缩放（Apply Scale）** 就是把缩放并入网格本身、再把 scale 置 1：

```
v' = S · v          （网格顶点局部坐标乘以缩放）
obj.scale = (1,1,1)（对象缩放归一）
```

新世界位置 = `T · R · (S·v)`，与原式**逐字节相等** → 大小、位置、形状严格不变，只是 scale 变 1。这等价于 Blender 的 `Ctrl+A → Apply Scale`。

**检验**：处理前后 `obj.dimensions`（世界尺寸）相对误差应 ≈ 0（实测 ≤ 3e-7）。

## 三、做法

### 方式 A · GUI
1. 选中对象 → `Ctrl+A` → `Apply` → 选 `Scale`
2. 想连旋转一起归正就选 `Rotation & Scale`（慎用，会动角度）

### 方式 B · 脚本批量（桥内数据层，等价）
无需 `bpy.ops`，避免 context 问题，逐对象可控：

```python
import bpy, numpy as np, os, json

EXCLUDE = {"C-DT 02.003"}   # 需要排除的特例

def is_unit(scale):
    return all(abs(getattr(scale, a)-1) < 1e-6 for a in "xyz")

targets = [o for o in bpy.data.objects
           if o.type == "MESH" and not is_unit(o.scale) and o.name not in EXCLUDE]

backup = []
for o in targets:
    sx, sy, sz = o.scale.x, o.scale.y, o.scale.z
    backup.append({"obj": o.name, "scale": [sx, sy, sz], "dims": list(o.dimensions)})
    mesh = o.data
    if mesh.users > 1:                 # 多用户网格必须独立,见注意③
        o.data = mesh.copy(); mesh = o.data
    nv = len(mesh.vertices)
    co = np.empty(nv*3, dtype=np.float32)
    mesh.vertices.foreach_get("co", co)
    co[0::3] *= sx; co[1::3] *= sy; co[2::3] *= sz   # 把缩放烘焙进顶点
    mesh.vertices.foreach_set("co", co)
    o.scale[:] = (1.0, 1.0, 1.0)
    o.update_tag()
bpy.context.view_layer.update()

# 备份落盘(便于精确还原)
os.makedirs("./backup", exist_ok=True)
json.dump(backup, open("./backup/scale_backup.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("applied:", len(targets))
```

## 四、⚠️ 注意事项（全是实战踩出来的坑）

### ① 几何预放大叠加 —— 最大的坑（翻车现场）
**现象**：对某对象 Apply 后，它"从很小变得巨大无比"，甚至怎么还原都"很大"。

**根因**：这个对象的**网格几何本身早被放大过 40 倍**（局部坐标从 ±0.39 被烤成 ±14.96），但 **scale 还留在 37.9**，于是 `世界尺寸 = 几何(大) × scale(大)` 双重叠加，一上来就是 569 的巨型，而不是它应有的 15。

**必须先核实"几何本体的自然尺寸"**，再决定基准，否则会把"已被放大过的错误状态"当成正确初始：

- 核对局部顶点范围 `min/max(v.co)` 与 `dimensions/scale` 是否自洽；
- 对比同组/同父装置里其它件的量级（本案例同装置网格最大边中位数只有 0.42，唯独它是 569，一眼巨量异常）；
- `dimensions ≈ 几何范围 × scale` 且值合理 → 正常；`dimensions` 比同类件大几十上百倍 → 高度可疑为预放大叠加。

### ② 改与验证必须分两次请求
桥 `exec` 内**改完立即验证会读到未刷新缓存值**。正确姿势：先跑执行（含备份），再用**独立的第二个脚本**重读 `scale / dimensions` 做对比。

### ③ 多用户网格必须先独立
`obj.data.users > 1`（共享同一 mesh 数据块）时，直接 apply 会 `Cannot apply to a multi user`（算子报错）或串改所有共享者。先 `o.data = o.data.copy()` 独立副本再处理；复制后原网格会成为 orphan，记得留定义不定。

### ④ 负缩放（镜像）要当心
scale 含负号（如 `(-0.805, -0.7, -0.7)`）表示镜像。Apply 后几何镜像，**法向由 depsgraph 自动重算**；Blender 5.2 已移除 `mesh.calc_normals()`，不要调它。实测负缩放对象视觉正确。数量级：本场景 697 个待处理里 48 个负缩放。

### ⑤ 大倍数 scale 的副作用
对 scale≈40 的对象 Apply，局部坐标会跟着放大 40 倍（±0.39 → ±14.96）。世界大小虽不变，但**后续局部空间操作（轴心、布尔、对齐、测量、再缩放）浮点精度会下降**。这类对象若必须 keep scale 1，可接受；否则保留其缩放特征。

### ⑥ 只处理网格，先梳理清单
批量前先"重新梳理清单"：仅筛选 `type == 'MESH'` 的静态对象（无动画/驱动/约束，且父链也无动态），再过滤 `scale != 1`。不要在未确认的基准上直接全量 apply。可疑对象（世界尺寸异常巨）先排除单灸。

### ⑦ 备份与精确还原，链路可逆
应用缩放是**可逆**的：记录原 `scale`，还原 = 网格顶点 `÷` 原 scale + `scale` 设回原值，能逐字节回到 apply 前。批量前务必把 `{name, scale, dims}` 落盘。

### ⑧ 桥只改内存，不自动存盘
远程操作全部在内存，Ctrl+S 才持久。重要批次前对 .blend 另存一份快照。

## 五、验证清单（独立脚本做）

| 项 | 期望 |
|---|---|
| 所有处理对象 `scale == (1,1,1)` | 无异常 |
| `dimensions` 相对误差 | ≤ 1e-3（实测 3e-7） |
| 排除对象（特例） | 未被改动，保留原 scale/dims |
| 负缩放对象 | 法向/朝向正确 |

## 六、Blender 5.2 API 坑速查

| API / 事实 | 说明 |
|---|---|
| `mesh.calc_normals()` | **5.2 已移除**，法向交 depsgraph 自动重算 |
| `obj.data.users > 1` | 多用户网格，先 `data.copy()` 独立 |
| apply 只做内存 | 需手动 Ctrl+S |
| 改后立即验证 | 缓存未刷新，改/验分两次请求 |