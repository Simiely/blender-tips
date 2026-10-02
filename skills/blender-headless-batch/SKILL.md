---
name: blender-headless-batch
description: 不打开 Blender 界面、用无头命令行批量处理巨型 .blend——按材质合并海量网格、扫描工程结构、删除集合、合并两个工程。当用户抱怨「blend 太大/对象太多导致卡」「能不能不打开就改工程」「把相同材质的网格合并」「合并后会不会更流畅」「删掉某个 collection」「合并两个 blend」时使用。含四个实测致命的坑（共享 mesh 数据块 + 多段 join 导致几何重复计入、一次性 join 几千对象 Calloc 溢出崩溃、跨组选中状态泄漏、excluded 集合里对象的 matrix_world 不被求值）、两级 join（大组必用）、网格数据独立化、活动对象必须挑带「按角度平滑」的、风险组判定（跨集合 / 不在视图层 / 修改器不一致）、世界变换烘焙（不烘焙模型会散架）、join 性能真相（开销看对象数而非几何量）、后台跑与 CPU 判定法、重开复核铁律、性能验收四口径（会更快但快在操作响应、不是渲染帧率）、以及「多线程不可能」的原因。
agent_created: true
---

# Blender 无头批处理（巨型工程）

`blender-bridge-ops` 管「怎么把代码送进**正在运行**的 Blender」；
本 skill 相反 —— **不开 GUI**，直接用系统命令行把整个工程吃进来改完另存。

适用场景：工程大到 GUI 打开就卡 / 根本不想打开 / 改动要大批量且耗时超过桥的 120s 上限。

> **先扫描再动手**：本 skill 管「怎么安全地执行 + 怎么验收」。
> 摸清工程结构、出「意见清单」与分组口径选项，交给 `blender-project-prescan`。

## 铁律（顺序不可颠倒）

1. **只读扫描先行** —— 先搞清工程结构与红线，绝不直接动手
2. **查多实例**（`mesh.users > 1`）—— 不为 0 就**注意**：小-中组走一次性 join 没问题，
   但大组一旦走多段 join 就会把几何重复计入（见 §3.2）。脚本 v2 起自动处理
3. **确认合并粒度** —— 合并不可逆，单体选择能力会永久消失，必须让用户拍板
4. **小场景冒烟测试** —— 拿 500 MB 工程调试脚本，一次几分钟，错了还得从头来
5. **后台跑 + 独立日志**（前台跑会被 SIGTERM 掐断）
6. **执行**（脚本内自带安全闸：绝不覆盖源文件）
7. **重开复核** —— 另起 Blender 加载产物，核对几何守恒
8. **告诉用户「原始工程没被动过」**

## 一、命令形态

```bash
blender.exe --background --factory-startup "<源.blend>" --python <脚本>.py -- [参数...]
```

* `--background` —— 无 GUI。**缺了就变成开界面**，对巨型工程就是灾难
* `--factory-startup` —— 跳过用户插件。批处理**一律加上**（实测可省掉加载本机
  SketchUp 插件那个 25 MB `SketchUpAPI.dll` 的开销）
* `-- <参数>` —— 双横线之后传给脚本，脚本里
  `sys.argv[sys.argv.index("--") + 1:]` 取
* 本机 Blender：`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`

脚本包：**[`../scripts/merge-by-material/`](../scripts/merge-by-material/)**
（含 `analyze_materials.py` / `merge_by_material.py` / `verify_merge.py` /
`perf_probe.py` / `compare_perf.py` / 自测台）
完整原理：**[`../docs/按材质合并为单个网格体.md`](../docs/按材质合并为单个网格体.md)**

## 二、动手前必查的四件事

跑 `analyze_materials.py`，回答：

| 看什么 | 红线 / 影响 |
|---|---|
| `对象共用同一网格的数量` | **红线**。不为 0 ⇒ 有多实例。小-中组合并会把一份几何复制 N 份、**文件反而变大**；大组若走多段 join 还会把几何**重复计入**（偏差 ~1.7）。v2 脚本自动独立化，但你要知道为什么 |
| `UV_LAYER_COUNT_HIST` / `有顶点色/形态键的对象` | 决定会不会丢数据、分组键要不要更细 |
| `DISTINCT_MATERIAL_SETS` | 直接等于**合并后的对象数**（按材质+UV 分组时） |
| `有父级的对象` / `非单位缩放` | 不为 0 ⇒ 必须烘焙世界变换（脚本已做，但要知道为什么） |

## 三、必须懂的机制

### ① 世界变换烘焙 —— 不做的后果是模型散架

对象最终位置由三段矩阵连乘决定，而 `join()` 只取**自己的 `matrix_world`**，
**父级的贡献会被丢掉**。所以必须先解开父子关系、同时把世界变换烧进对象自身：

```python
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
```

`CLEAR_KEEP_TRANSFORM` 是关键 —— 用默认的 `CLEAR` 对象会"跳回"局部原点，立刻散架。

> ⚠️ **别用 `transform_apply()` 替代**，多层父级下同样算错，且破坏原始形状定义。
>
> 等价写法（逐组处理时更顺手，不必碰全局 context）：
> ```python
> world = {o.name: o.matrix_world.copy() for o in g}
> for o in g:
>     if o.parent is not None:
>         o.parent = None
>         o.matrix_world = world[o.name]
> ```
> 顺序不能反 —— 先摘父级再赋世界矩阵。

### ② 分组键必须带 UV，**要不要带父级是一道取舍**

```python
key = (tuple(m.name if m else "<空>" for m in o.data.materials),  # 完整材质列表
       tuple(l.name for l in o.data.uv_layers))                   # UV 层名列表
```

只按"第一个材质名"分组不够（多材质槽对象会混）。
UV 必须进 key —— 带 UV 的和不带 UV 的并进同一组，**UV 会被拉平丢失**。

**父级**（`+ (o.parent.name if o.parent else None,)`）进不进 key，是**取舍不是对错**：
导入工程的"同类件"往往**按装置分组**（实测 83 个铜件分布在 19 个不同父级下）：

```
① 只按材质        → 83 → 7    装置归属彻底消失
② 材质 + 父级     → 70 → 11   每组恰好一个装置，还能挂回原父级   ← v2 默认
③ 材质 + 顶层祖先 → 62 → 21
```

v2 默认 ②（`GROUP_BY_PARENT = True`）；要旧行为设 `False`，但**必须同步改自测台的期望值**。

### ③ 大组必须两级 join —— 一次性 join 几千个对象会崩

```
Calloc array aborted due to integer overflow: len=18446744072358535680x4
in from_uninitialized, total 27960300944      → Blender 直接退出，EXIT=127
```

触发：2405 个对象一次 join（总顶点仅 36 万，却要申请 ~28 GB ⇒ 是 bug 不是真实需求）。
某个数组长度计算下溢成了负数。

⇒ **按 ≤ `MAX_BATCH_OBJS`（默认 120）切块，每块做一次性 join 得中间对象，
再把这些中间对象一次性 join 成一个**。实测 2405 个对象 → 21 块 + 第 2 级，
363281 顶点与基线完全吻合，偏差 0.000021 ✅

⚠️ **绝不能**「逐批 join 到同一个 active」—— 那会踩上下一个坑。

### ④ 共享 mesh 数据块 + **多段** join = 几何被重复计入 ★最阴

| 做法 | 结果 |
|---|---|
| 一次性 join 137 个（含 136 个共用 `C-墙砖#1`） | **1365 顶点，偏差 0.000003 ✅** |
| 分两批 join（120+17） | **16597 顶点，偏差 1.688313 ❌** |

第二段 join 把该 mesh 在**整个工程里**的全部实例几何都算了进来（多出 15232 = 1904×8）。
**与「选中残留」无关**（加了每批前全场景 DESELECT 后结果一模一样）。

⇒ **正解：走两级 join 前先把网格数据独立化**

```python
for o in g:
    if o.data.users > 1:
        o.data = o.data.copy()
```

独立化后同一组：块 2 → 405 顶点、合并后 1365（= 基线）✅

> **代价**：独立化把实例展开成实体，文件会变大。所以 v2 **只在必须走两级 join 的大组**上做；
> 小-中组走一次性 join，共享网格在 join 后变孤儿、存盘时被 Blender 丢弃，**文件不膨胀**。

### ⑤ 活动对象必须挑「带按角度平滑」的

`join()` 只保留**活动对象**的修改器栈，其余成员的修改器全丢。
Blender 4.1+/5.x 导入的工程常给每个网格挂 **`Smooth by Angle`（按角度平滑，NODES 型）**——
实测某 SKP 工程 **27,352 / 50,622** 个对象带它。丢了着色（锐边）就变。

```python
SMOOTH = re.compile(r"按角度平滑|Smooth by Angle")
A = next((o for o in g if any(SMOOTH.search(m.name) for m in o.modifiers)), g[0])
# 用 A 当 active_object，join 后结果对象就有平滑
```

## 四、执行纪律

### 必须后台跑

前台跑超过 120 s 会被 SIGTERM 掐断 —— **踩过一次，几分钟白等**，
而且日志是空的、磁盘上没留半成品，很难判断发生了什么。

```bash
cd <工作目录> && del merge_run.log
blender.exe --background --factory-startup "<源>.blend" --python merge_by_material.py -- "<输出>_合并.blend"
```

### 日志要能「崩之前看到进度」

stdout 重定向到文件时是**块缓冲** —— 进程崩掉就什么都看不到。
脚本必须**同时**写日志文件（`buffering=1` 或每次 flush）并打印。
每条日志注明**当前在第几组 / 共几组**，这样挂掉时能定位到具体组。

### 判断「在干活还是卡死」—— 看 CPU，不看日志

慢的大组可能几分钟**一行新日志都不打**，但它确实在算。

```powershell
$a = (Get-Process blender)[0].TotalProcessorTime.TotalSeconds
Start-Sleep 3
$b = (Get-Process blender)[0].TotalProcessorTime.TotalSeconds
"3秒CPU增量: {0:N2}s" -f ($b-$a)   # > 0.5s = 在干活
```

内存：单个进程峰值约 2.7 GB（双工程同时在内存时到过 5.15 GB）。先量机器内存。

### 文件系统

* 输出一律**另存**，脚本内置安全闸 —— 输出路径等于源文件时直接 `SystemExit`
* 排除名单写在工作目录 `exclude.txt`，一行一个名字，`#` 开头为注释
* 名单里的名字**若不存在会被告警**（故意不静默跳过 —— 手抖写错必须暴露）

## 五、验证：三层，最后一層不能省

1. **进程内**：脚本自比顶点/面数
2. **重开复核**（**必做，另起 Blender**）：

```bash
blender.exe --background --factory-startup "<输出>_合并.blend>" --python verify_merge.py
```

> 「①」只证明**内存里**数据对得上，**不证明存出去的文件还能打开**。这一步不能省。
>
> v2 的 `verify_merge.py` 是**零配置**的：它读 `merge_by_material.py` 落盘的
> `merge_result.json`，逐组核对 顶点数 / 面数 / **父级** / **世界包围盒偏差**，
> 外加四项收尾检查（见 §六）。

3. **自测台**（改脚本逻辑时用）：`build_smoke_scene.py` → `merge_by_material.py` → `verify_smoke.py` → `verify_merge.py`。
   核心判据是**世界包围盒最大偏差 ≈ 0**，证明父子/旋转/缩放都处理对了。
   场景本身覆盖每条代码路径（普通组 / 多材质槽 / 带父级 + 旋转缩放 / 应排除对象 /
   **共享 mesh 的大组 / 独立 mesh 的大组 / 跨集合组 / excluded 集合里的一组**）。

### ⚠️ 世界包围盒必须逐顶点算，不能用 `bound_box`

```python
co = np.empty(n * 3, dtype=np.float32); me.vertices.foreach_get('co', co)
w = co.reshape(n, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]   # M = matrix_world
```

`obj.bound_box` 是「物体局部包围盒再变换」，是**松上界**，与合并后的口径不等价，必然误报。

### ⚠️ 校验口径别踩「孤儿数据块被 prune」

存盘时 Blender 会**丢弃 `users == 0` 的孤儿数据块**（材质、图像，旧工程里很常见）。
拿「数据块总数」比对前后必然误报「丢了材质 / 丢了贴图」。
**复核要用「被引用的数量」**：

```python
sum(1 for m in bpy.data.materials if m.users > 0)
```

## 六、风险组判定 —— 有些组根本不该碰

导入工程里总有一批组是「碰了会出事」的。v2 起脚本会**整组跳过**并在报告里列出原因：

| 判据 | 为什么 |
|---|---|
| **跨集合** | 组内对象分散在多个集合 ⇒ 合并会让某个集合凭空多出/失去几何，破坏 SKP 结构 |
| **有成员不在视图层** | 躺在被 exclude 的隐藏集合里 ⇒ join 拿不到它，结果不可预期 |
| `hide_viewport` | 同上 |
| **修改器配置不一致** | 各成员的修改器栈不同 ⇒ join 后只剩活动对象那份，其余成员的着色/细分会变 |

实测某工程：可合并 393 组里**跳过 24 组（约 1,188 个对象）**，
原因**全部是「有成员不在视图层」** —— 躺在 SketchUp 导入时被 exclude 的隐藏集合
（`组件#89_*66` / `Component#127` 等）。要合并需**先在 Outliner 里取消那些集合的排除**。

### ⚠️ excluded 集合还有个静默陷阱

那里的对象 **`matrix_world` 不会被 depsgraph 求值**，停在旧值（往往就是局部坐标）。
任何「算世界包围盒 / 世界坐标」的脚本都会在这里拿到错值 ——
**两侧口径都必须限定在视图层内的对象**：

```python
vl_names = {o.name for o in bpy.context.view_layer.objects}
```

顺带：判断「在不在视图层」**必须先物化成 set** —— `o.name not in VL.objects` 是 O(n)，
在 5 万对象的视图层上被调用上万次会让脚本卡死几分钟。

## 七、性能真相（用于估时与回答「会更流畅吗」）

### 耗时：开销看「对象数」，不看几何量

实测 510 MB / 24,481 对象工程，总耗时 **5.5 分钟**：

| 阶段 | 耗时 |
|---|---|
| 加载工程 | ~30 s |
| 世界变换烘焙 | 2.4 s |
| **第 1 组 `Color M02]1`（24,137 个对象）** | **321.8 s** ← 98% |
| 其余 54 组合计（343 个对象） | 2.7 s |
| 存盘 505 MB | 0.6 s |

**`bpy.ops.object.join` 的开销集中在「对象个数」，跟几何体量关系不大。**
`Am176_048_001` 只有 20 个对象却含 3,326,200 顶点，用了 0.1 秒。

⇒ **估时看最大那组有多少对象**，别用"总对象数 ÷ 当前进度"的平均速率外推。

### 「会更流畅吗」—— 用四个指标回答，别笼统说「更快」

`compare_perf.py <源> <产物>` 同口径跑 `perf_probe.py`：

| 指标 | 含义 | 合并后 |
|---|---|---|
| `mesh_objects` | **draw call 代理量** | ↓ 24%（实测 28,571 → 21,678） |
| `objects_with_mod` | **依赖图求值负担** | ↓ 25%（27,352 → 20,454） |
| `objsum_verts` | **每帧真正提交的顶点量** | **完全不变**（19,871,278） |
| `uniq_verts` | 显存 / 内存口径 | ↑ 32.5%（1228 万 → 1627 万） |

⇒ **正确结论**：会更快，但**快在「操作响应」**（选择、移动、改材质、Outliner 浏览、
依赖图重算），**不是「渲染帧率」** —— 每帧真正提交的顶点数一模一样。
副作用：实例被展开成实体（文件 / 显存变大），且大对象的**视锥剔除会变差**
（原来能被剔除的小对象，合并后跨越大范围反而剔不掉）。

### 多线程为什么不可能

`bpy.data` 不是线程安全的，`join` / `append` 是**硬性单线程**。
实测开了 32 线程，3 秒 CPU 增量只有 2.95 秒。`--threads` 只管渲染和物理，**对数据块操作无效**。

「切块并行再拼接」也不省：那些数据块终究要一个个灌进同一个 `bpy.data`，工作量一分不少。
（但**切块串行**是必要的 —— 见 §3.3，两级 join 防溢出。）

## 八、合并两个工程时的两个陷阱

### ① 「重名」是假警报 —— 别凭名字去重

两个工程的顶层集合名完全撞车（`Collection` / `SKP Imported Data` / `SKP Mesh Objects`），
对象名也大面积撞。这是 SketchUp 导入器按序号生成（`G-物体.00001`、`.00002`…）造成的，
**不代表内容重复**。

用**几何指纹**比对：

```python
fp[name] = (tuple(obj.matrix_world.translation), len(me.vertices),
            len(me.polygons), tuple(obj.dimensions))
```

实测 22,550 个同名对象中 **22,549 个指纹不同** ⇒ 是两套东西，应走**全量并集**不去重。

### ② 以谁为底影响很大

追加快慢取决于**拉进来多少数据块**，跟底子多大关系不大。
所以以**对象少的那一边**为底、追加对象多的那边，能省一半时间。

## 九、忙中出错清单

| 现象 | 优先怀疑 | 处理 |
|---|---|---|
| 前台任务跑了 2 分钟就没了 | 被 SIGTERM 掐断 | 改后台跑 + 独立日志；别用 `sleep` 长命令轮询 |
| 日志长时间不更新 | 未必卡死 | 看 3 秒 CPU 增量，> 0.5 s 就是还在算 |
| **进程崩了，`Calloc ... integer overflow`，`total` 是个巨大的数** | 组太大，一次性 join 溢出 | 两级 join（§3.3） |
| **合并后顶点数比基线多** | 共享 mesh + 多段 join | join 前独立化网格（§3.4） |
| 合并后模型散架 / 坐标错 | 没烘焙世界变换 | `parent_clear(type="CLEAR_KEEP_TRANSFORM")` |
| 合并后文件反而变大 | 多实例被复制 N 份 | 大组独立化必然展开；小-中组应走一次性 join |
| **某些组的结果莫名错了 / 偏差大** | 组里有对象不在视图层 | 风险组判定（§六）；或先在 Outliner 取消排除 |
| **有的对象丢了「按角度平滑」** | 活动对象没挑带修改器的 | 见 §3.5 |
| **跨越 20 组之后结果全错** | 选中状态跨组泄漏 | `sel` 提到循环外 + 每轮开头强制清空（§3.3 注） |
| UV 丢了 | 分组键没带 UV 配置 | `(材质tuple, uv层名tuple)` 一起做 key |
| **复核报「丢了材质 / 丢了贴图」** | 拿总数比，孤儿数据块被 prune | 改用「被引用的数量」（§五） |
| **复核的世界包围盒偏差很大** | 算到了 excluded 集合里的对象 | 两侧都限定视图层内（§六） |
| 顶点/面数对不上 | 排除名单写错 / 非网格对象被误并 | 名单不存在会告警，别忽略 |
| 脚本 `NameError` | 编辑漏行 | `ast.parse` 通过 ≠ 能跑，必须实跑小场景 |
| GUI 删集合后文件没变小 | 孤立数据还在 | 需做 orphan purge |

## 十、姐妹操作

[`../scripts/separate-by-material/`](../scripts/separate-by-material/) 是「一拆多」，
本 skill 是「多合一」，两者判据与算子都不相同 —— 别混用：

| | separate | merge |
|---|---|---|
| 算子 | `bpy.ops.mesh.separate(type='MATERIAL')` | `bpy.ops.object.join()` |
| 依据 | 材质**槽**，对整网格生效、与选择无关 | 材质**列表 + UV 配置（+ 父级）** |
| 判据 | 几何守恒 + 属性层无损失 | 几何守恒 + **世界包围盒偏差 ≈ 0** |
