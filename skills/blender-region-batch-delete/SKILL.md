---
name: blender-region-batch-delete
description: 在巨型 Blender 工程里按「区域标记网格体」批量删除对象 —— 用户已放好带关键字（如「Z轴覆盖范围」）的网格体，要求从 Z 轴俯视、被这些网格体包住的对象全部删掉。走 blender --background 无头通道（不是 9877 桥），干跑 → 执行 → 重开复核三段式，三重安全闸 + 另存新文件。当用户说「对象太多了」「我创建了 N 个网格体框了个范围」「被这两个网格体包含的对象都删掉」「按区域批量删除」「俯视方向看被框住的对象删掉」时使用。
agent_created: true
---

# 按覆盖区框选批量删除对象（俯视 Z 轴）

> 通道：`blender.exe --background <工程> --python <脚本>`，**不走 9877 桥** —— 桥有 120 s 上限，本任务删除阶段实测 **40 分钟**。
> 姐妹 skill：`blender-headless-batch`（同工程内整理）、`blender-project-prescan`（动手前只读体检）、`blender-blend-append-merge`（两个工程合并）。
> 脚本包：[`../scripts/region-batch-delete/`](../scripts/region-batch-delete/)（含共享几何核 `region_geom.py`）；完整原理与实测数据见 [`../docs/覆盖区框选批量删除对象.md`](../docs/覆盖区框选批量删除对象.md)。

## 铁律（顺序不可颠倒）

1. **先干跑，只读，绝不直接删** —— 出计数报告 + SVG 预览，把"待删数"落到磁盘
2. **让用户确认选区** —— 让用户看 `region_preview.svg`（青 = 标记矩形，红 = 待删，灰 = 保留）并点头
3. **只写新文件，绝不覆盖原工程** —— 脚本内硬闸：`NEW == 当前路径` 直接退出
4. **删前重算名单，与干跑数不一致就退出** —— 这是防"判据分叉"的唯一一道闸
5. **删前冻结"父级在内、自己在外"的子级**（keep-transform），否则外面的东西会跟着消失或瞬移
6. **重开新文件独立复核**，区内残留判据是 **0**（不是"变少了"）

## 一、判定（核心只有三条）

### 1. 俯视 Z 轴 = 忽略 Z

```
被删除  ⟺  对象的「世界 XY 包围矩形」完全落在标记矩形的「并集」内
```

### 2. 世界 XY 矩形：`bound_box` 必须先过 `matrix_world`

```python
# ★ bound_box 是对象局部坐标 —— 直接用它比矩形 = 假设所有对象都躺在原点
x = mw[0][0]*c[0] + mw[0][1]*c[1] + mw[0][2]*c[2] + mw[0][3]
y = mw[1][0]*c[0] + mw[1][1]*c[1] + mw[1][2]*c[2] + mw[1][3]
```

按矩阵**前两行直接展开叉乘**，不构造 `Vector`、不写 `matrix_world @ Vector(c)` —— 30 万对象 × 8 角 ≈ 256 万次变换，省掉对象分配后干跑只要几秒。

### 3. 完全包含：并集格网 + 退化矩形分流

```python
# 并集不是矩形 ⇒ 不能拆成"在 R1 里 或 在 R2 里"（会把横跨两块、中间悬空的对象误判在内）
# 正解：取所有矩形边界的 x/y 坐标切成互不重叠的格网，逐格求交面积求和
area(R ∩ 并集) == area(R)   ⇒ 完全包含
```

```python
# ★★ 退化矩形（EMPTY / CAMERA / LIGHT / 点数据对象的 bound_box 是零尺寸）
#    w*h == 0 ⇒ 面积判据两侧恒等 ⇒「任何位置都判成包含」⇒ 会把全工程空物体+相机全删
if w <= 1e-9 or h <= 1e-9:
    return 四角点各自都在并集内          # 不是面积判据！
```

> 本案例：退化矩形分支命中 **5,946 EMPTY + 14 CAMERA** —— 漏掉这条分支 = 灾难。
> 判据抽成 `region_geom.py` 共享，**三个脚本 import 同一份**，禁止各自复制（否则会出现"算 143318、删 143317"）。

> 容差用**相对量** `1e-6 × max(1, w*h)`，不要用绝对值 —— 这类工程坐标量级常到 1e6。

## 二、执行（`delete_region.py`）

顺序不可打乱：

1. `victims = [o for o in list(bpy.data.objects) if judge(wbbox(o.matrix_world, o.bound_box))]`
2. **计数硬闸**：`len(victims) != EXPECT_INSIDE` ⇒ `raise SystemExit`（不动手）
3. **冻结受害父级的外部子级**：

```python
mw = o.matrix_world.copy(); o.parent = None
o.matrix_parent_inverse.identity(); o.matrix_world = mw      # 世界变换逐位不变
```

4. **分块 `batch_remove`**（`CHUNK=10000`，每块打一行 `[DEL] removed i / N elapsed Xs`）
5. `orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=False)` 跑 2 遍
6. `bpy.ops.wm.save_as_mainfile(filepath=NEW, check_existing=False, compress=False)`

### 删除方法选型（实测，反直觉 —— 别凭直觉挑）

| 方法 | 单对象 | 143,318 推算 |
|---|---|---|
| `bpy.data.objects.remove(o, do_unlink=True)` | 123.6 ms | 4.9 小时 |
| `o.unlink()` | 26.6 ms | 1.06 小时 |
| `bpy.ops.object.delete()` | 44.2 ms | 1.76 小时 |
| **`bpy.data.batch_remove(list)`** | **23.0 ms** | **0.92 小时**（实测跑到 40 分钟） |
| `remove(do_id_user=False, do_ui_user=False)` | 135.6 ms | **无收益** |

**成本与"用哪个 API""视图层多大""集合多大"几乎无关** —— 每次"写"都触发 ID 记账 / 视图层同步。逐个删与 `batch_remove` 的差别只在**每对象触发一次还是每批触发一次**。

### 性能红线

- **循环里绝不要 `bpy.data.objects.get(name)`**（32 万规模下病态慢，实测因此挂死 > 10 分钟）。判成员关系**自己建 `set`**；遍历先 `list(bpy.data.objects)` 拿快照。
- **`orphans_purge(do_recursive=True)` 全量一遍 42.7 s / 2214 个**；`do_recursive=False` 连跑两遍共 **0.6 s**。
- 不要 `bl_rna.properties` 全属性遍历。

## 三、独立核验（`verify_region.py`，**必须另起一次 blender 进程**）

1. **区内残留 == 0** —— 用同一套判据在**新文件**上重算。**硬判据**。
2. **对象数** —— 与"干跑总量 − 待删数"比对，带**容差**（默认 ±10）。
   ★ 内存数 ≠ 重开数：本案例 177,156 → **177,155**（少 1 个 `users==0` 无 fake user 的数据块，Blender 存盘本就不写它；同批还丢 1 个 mesh / 35 个 image）。
3. **类型分布 + 数据块计数**（meshes / materials / images / collections / cameras / lights）全量列出。
4. **区内残留按类型分组** —— 非零时一眼看出是哪条判据写错（只剩 EMPTY ⇒ 退化矩形分支漏了）。
5. **场景包围盒**逐位读一遍，确认没有异常收缩。

## 四、坑表

| # | 坑 | 后果 / 判据 |
|---|---|---|
| 1 | ★ `bound_box` 是**局部**坐标 | 不过 `matrix_world` ⇒ 结果毫无意义 |
| 2 | ★ **退化矩形**用面积判据 | 面积判据对零尺寸对象**恒真** ⇒ 全工程 EMPTY + CAMERA 被删 |
| 3 | ★ **父级塌陷** | 256 个受害父级带走 485 个外部子级 ⇒ 外面的东西也少了 |
| 4 | ★ 干跑 / 执行判据**分叉** | "算 143318、删 143317"最难查；抽 `region_geom.py` 共用 |
| 5 | ★ 删除后碰**旧引用** | `ReferenceError: StructRNA of type Object has been removed` |
| 6 | ★ 另存后计数**少几个** | 存盘丢弃 `users==0` 数据块；复核按容差判 |
| 7 | 判据写成"在 R1 **或** R2 内" | 跨块悬空的对象被误判为在内 |
| 8 | 用**原点在内**当判据 | 143,471 ≠ 143,318（"完全在内"），多删 153 个 |
| 9 | **遍历中删 / 边删边取引用** | 几乎必然踩 #5；清单要一次性建好 |
| 10 | `EXPECT_INSIDE` 留空 | 唯一的安全闸失效 —— 必填干跑数 |

## 五、汇报模板

给用户的交付必须包含：

1. **干跑三数**：工程总量 / 待删 / 类型分布
2. **选区预览图**（`region_preview.svg`，青色标记矩形 + 红色待删 + 灰色保留）
3. **执行日志**（`[DEL]` 打点，含冻结数、耗时、另存路径与体积）
4. **复核结果**：区内残留 **0**（硬判据）+ 对象数对比（含容差说明）+ 类型分布 + 数据块计数
5. **方法选型依据**（为什么用 `batch_remove`，含实测毫秒表）
6. **遗留项**：只部分重叠的 343 个没删（说明"只删完全在内"是刻意口径，问用户要不要一并处理）

## 六、长任务进度可视化

40 分钟的删除阶段，终端每 10,000 个才一行 —— 用户会怀疑卡死。脚本包自带零依赖看板：

```powershell
$env:PROGRESS_JOB_DIR = "<任务的 output.log / state.json 所在目录>"
python progress_dashboard\serve_progress.py 8765     # 浏览器开 http://127.0.0.1:8765/
```

**只读日志，对 Blender 零干扰**；认 `[DEL]` 前缀（换前缀即可复用到别的长任务）；画实测采样点 + 预计终点虚线；日志 >10 分钟不更新会区分"正在另存大文件（正常）"与"真卡死"。

## 本机路径约定

- 工程：`E:\Desktop\261012\SU模型231212--龙岗大运--合模-9.3_blender_优化版R1.blend`
- 输出：同目录 `..._已删除覆盖区对象.blend`
- 工作目录 / 报告：`C:\Users\wandou\Documents\Trae-CN\temp_20261014_01\`
- 参考实现：`analyze_region.py` / `delete_region.py` / `verify_region.py` / `region_geom.py`
