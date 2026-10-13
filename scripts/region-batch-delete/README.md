# 覆盖区框选批量删除对象（可复用包）

导入型工程对象数爆炸（本案例 **320,474** 个），只想保留某个区域、其余清掉。
用户已经在工程里放好**两个网格体当"区域标记"**（名字里带「Z轴覆盖范围」）。

**"俯视 Z 轴"= 忽略 Z 轴** ⇒ 判定退化成**世界 XY 平面上的矩形包含**。本包给出确定做法：

**① 干跑（只读）→ ② 执行（另存新文件）→ ③ 重开复核**

> ⚠️ 本包不在 9877 桥里跑，走**系统命令行无头通道**：
> `blender.exe --background <工程> --python <脚本>.py -- [参数]`
> （与 [主题 43](../../docs/按材质合并为单个网格体.md) / [主题 44](../../docs/追加合并两个工程.md) 同一通道 —— 桥有 120 s 上限，本任务实测删除阶段 **40 分钟**。）

## 一句话原理

```
对象被删除  ⟺  它的「世界 XY 包围矩形」完全落在两个标记矩形的「并集」内

并集不是矩形 ⇒ area(R ∩ 并集) 用格网分解精确求（等价于两块的容斥式）
退化矩形（EMPTY / CAMERA / LIGHT，bound_box 零尺寸）⇒ 面积判据恒真，必须改四角点判定
```

## 文件清单

| 文件 | 作用 | 何时跑 |
|---|---|---|
| `region_geom.py` | **共享几何核**：世界 XY 矩形、标记提取、`make_judge()` 完全包含判据 | 被下面三个脚本 import，**不单独跑** |
| `analyze_region.py` | **① 干跑（只读，绝不改工程）**：计数 + 落 `region_analysis.json` / `inside_names.txt` / `region_preview.svg` | 先跑，拿到"待删数" |
| `delete_region.py` | **② 执行**：冻结受害父级 → 分块 `batch_remove` → 孤儿清理 → **另存新文件** | 干跑数确认后 |
| `verify_region.py` | **③ 复核**：**重开新文件**，用同一套判据复算残留（判据 **0**） | 执行完必跑 |
| `progress_dashboard/` | 长任务实时进度看板（局部 HTTP 服务 + 网页，**只读日志**） | 执行时另开一个窗口 |
| [`../../docs/覆盖区框选批量删除对象.md`](../../docs/覆盖区框选批量删除对象.md) | 完整原理 / 实测数据 / 坑 | 阅读 |
| [`../../skills/blender-region-batch-delete/`](../../skills/blender-region-batch-delete/) | 同一套脚本的 AI 作业规范版 | AI 加载 |

## 配置项

三个脚本顶部各有 `CONFIG`。**不需要一致的项**：`analyze` 写 `OUT_DIR`（报告落盘目录）、`delete` 写 `NEW`（输出路径）、`verify` 写 `OUT_DIR`。**必须一致**的只有一项：

```python
MARKER_KEY = r"Z轴覆盖范围"      # 三个脚本必须一模一样，否则判据会分叉
```

路径也可以走 `--` 之后的命令行参数覆盖（优先级高于 `CONFIG`），两个约定都支持：

```powershell
blender.exe --background "D:\proj\a.blend" --python delete_region.py -- "D:\proj\a_已删除覆盖区对象.blend"
```

> 其余脚本相关的硬约束见 [skills/README.md](../../skills/README.md)：
> 跑之前记得改顶部 `CONFIG`，别把 `OUT_DIR` 留在占位路径上。

## 使用步骤

### 0. 先确认标记体

在 Blender 里确认那两个"覆盖范围"网格体存在、名字里带 `MARKER_KEY`（`分析` 阶段找不到会直接 `[FATAL]` 退出）。
标记体的**世界 XY 包围矩形**就是选区 —— 所以它**不能有旋转过的零厚度**之类的退化形状，否则 XY 投影会变成一个非常细的长条。

### 1. 干跑（只读）

```python
# analyze_region.py
CONFIG = dict(MARKER_KEY=r"Z轴覆盖范围", OUT_DIR=r"C:\path\to\workdir", ...)
```

```powershell
blender.exe --background "D:\proj\a.blend" --python analyze_region.py
```

输出（本案例真实结果）：

```
[RUN] loaded 320474 objects
[RUN] marker rects (2): [(795.738, 618.579, 1090.355, 913.196), (917.452, 407.940, 1224.741, 715.229)]
...
[RUN] DONE 4.36s
```

`region_analysis.json` 关键字段：

| 字段 | 本案例值 | 说明 |
|---|---|---|
| `n_total_objects` | 320474 | 工程总量 |
| `n_fully_inside_total` | **143318** | **这个数是后面 `EXPECT_INSIDE` 的取值** |
| `n_fully_inside_by_type` | MESH 137358 / EMPTY 5946 / CAMERA 14 | 逐类型核对（能看到退化矩形那条分支有没有生效） |
| `n_overlap_total` | 343 | 只部分重叠，**不删** |
| `n_origin_inside_total` | 143471 | 原点在内 ≠ 完全在内，**不能当判据** |
| `n_deleted_parents_of_outside_objects` | 256 | 受害父级数 |
| `n_outside_children_to_freeze` | **485** | 将被 keep-transform 冻结的外部子级数 |

`region_preview.svg` 用浏览器打开即可**肉眼验收选区**：青 = 标记矩形、红 = 待删、灰 = 保留。

### 2. 执行（另存新文件）

```python
# delete_region.py
CONFIG = dict(MARKER_KEY=r"Z轴覆盖范围", EXPECT_INSIDE=143318, CHUNK=10000, PURGE_PASSES=2)
```

```powershell
blender.exe --background "D:\proj\a.blend" --python delete_region.py
```

典型输出：

```
[DEL] loaded 320474 objects
[DEL] region rects: [...]
[DEL] victims: 143318
[DEL] count verified == 143318
[DEL] frozen (keep-transform) outside children: 485 2.6 s
[DEL] removed 10000 / 143318 elapsed 207.2s
...（每 10000 打点一次）
[DEL] removed 143318 / 143318 elapsed 2401.6s
[DEL] all removed. objects remaining: 177156 2401.6 s
[DEL] orphans_purge pass 1 -> 822 2401.9 s
[DEL] orphans_purge pass 2 -> 64 2402.2 s
[DEL] after purge -> objects: 177156 meshes: 7243 materials: 503 images: 280
[DEL] saved -> D:\proj\a_已删除覆盖区对象.blend 135.9 MB 2409.2 s
[DEL] DONE
```

**三重安全闸**（脚本内实现）：

| 闸 | 内容 | 触发后果 |
|---|---|---|
| 1 | 只写新文件，**绝不覆盖当前文件** | `NEW == 当前路径` ⇒ 直接退出 |
| 2 | 删前重算名单，与 `EXPECT_INSIDE` 不一致 | 退出，**不动手** |
| 3 | 删前把"父级在内、自己在外"的子级 keep-transform 冻结 | 世界坐标逐位不变 |

### 3. 重开复核（**必须另起一次 blender 进程**）

```powershell
blender.exe --background "D:\proj\a_已删除覆盖区对象.blend" --python verify_region.py
```

```
[VER] {"objects": 177155, "region_objects_left": 0, ...}
[VER] [1] 区内残留 = 0  (判据 0)      OK
[VER] [2] 对象数 177155 vs 预期 177156 (容差 10, 实测差 1)  OK
[VER] FAILS=0  6.71s
```

> **重开数 ≠ 内存数**：内存 177156 → 重开 **177155**。少掉的是 `users==0` 且无 fake user 的数据块
> （Blender 存盘本就不写它）。所以复核脚本里对象数判定带**容差**（默认 ±10），而"区内残留"是**硬判据 0**。

## 性能真相（本案例实测，反直觉）

| 方法 | 单对象耗时 | 143,318 推算 |
|---|---|---|
| `bpy.data.objects.remove(o, do_unlink=True)` | 123.6 ms | 4.9 小时 |
| `o.unlink(...)` | 26.6 ms | 1.06 小时 |
| `bpy.ops.object.delete()` | 44.2 ms | 1.76 小时 |
| **`bpy.data.batch_remove(list)`** ← 终选 | **23.0 ms** | **0.92 小时**（实测 40 分钟，随块内推进加速） |
| `remove(do_id_user=False, do_ui_user=False)` | 135.6 ms | 无收益 |

- 换参数、缩小视图层、缩小集合 **都不改变单对象成本** —— 成本来自每次"写"触发的 ID 记账 / 视图层同步。
- **循环里绝不要 `bpy.data.objects.get(name)`**（32 万规模下病态慢，早期版本因此挂死 >10 分钟）。
- `orphans_purge(do_recursive=True)` 全量一遍 **42.7 s / 2214 个**；改 `do_recursive=False` 连跑两遍共 **0.6 s**。

## 附：长任务实时进度看板

删除阶段实测 **40 分钟**，终端每 10,000 个才一行字 —— 很容易误判"卡死了"。

```powershell
$env:PROGRESS_JOB_DIR = "C:\Temp\...\jobs\job-xxxx"
python progress_dashboard\serve_progress.py 8765
# 浏览器打开 http://127.0.0.1:8765/
```

- **只读日志，对 Blender 进程零干扰**（不注入、不桥接、Blender 侧零配合）。
- 认 `delete_region.py` 的 `[DEL]` 前缀；**换个前缀看板可直接复用到别的长任务**。
- 画**实测采样点** + 按当前速率画**预计终点虚线**；日志超 10 分钟不更新会提示（区分"正在另存大文件（正常）"与"真卡死"）。
- 实测节拍：`30,000/143,318 · 50.2 个/秒 · 预计剩余 38 分钟`。

## 注意事项（踩过的坑）

1. **★ `bound_box` 永远是局部坐标** —— 必须过 `matrix_world`。用局部 AABB 比矩形 = 假设所有对象都躺在原点。
2. **★ 退化矩形必须走四角点判定** —— `EMPTY` / `CAMERA` / `LIGHT` 的 `bound_box` 零尺寸，面积判据对它们**恒真**，会把全工程所有空物体与相机删掉。
3. **★ 父级塌陷** —— 删掉的父级会带走外面的子级（本案例 256 个父级 / 485 个子级）。必须先 keep-transform 冻结。
4. **★ 干跑 / 执行 / 复核三份判据必须同源** —— 本包直接抽成 `region_geom.py` 共用，杜绝"算 143318、删 143317"。
5. **★ 删除后不能碰旧引用** —— `batch_remove` 之后残留的 `o.name` 会抛 `ReferenceError: StructRNA of type Object has been removed`。要用的字段删除**前**冻结成纯值。
6. **★ 另存后对象数会少几个** —— `users==0` 无 fake user 的数据块存盘不写（本案例少 1 个对象 / 1 个 mesh / 35 个 image）。不是逻辑错，复核要按容差判。
7. **只删"完全在内"的** —— 只部分重叠的（本案例 343 个）**不删**；判据拆成"在 R1 或 R2"会把跨块悬空的对象误判在内。
8. **`--background` 存盘不做压缩**（`compress=False`）—— 30 万对象下压缩会额外吃几分钟，收益不值。
9. **先看一眼 `region_preview.svg`** —— 4.36 s 就能出图，比删完再后悔便宜得多。
