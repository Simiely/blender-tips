---
name: blender-headless-batch
description: 不打开 Blender 界面、用无头命令行批量处理巨型 .blend——按材质合并海量网格、扫描工程结构、删除集合、合并两个工程。当用户抱怨「blend 太大/对象太多导致卡」「能不能不打开就改工程」「按材质合并网格」「删掉某个 collection」「合并两个 blend」时使用。含多实例红线、世界变换烘焙（不烘焙模型会散架）、join 性能真相（开销看对象数而非几何量）、后台跑与 CPU 判定法、重开复核铁律、以及「多线程不可能」的原因。
agent_created: true
---

# Blender 无头批处理（巨型工程）

`blender-bridge-ops` 管「怎么把代码送进**正在运行**的 Blender」；
本 skill 相反 —— **不开 GUI**，直接用系统命令行把整个工程吃进来改完另存。

适用场景：工程大到 GUI 打开就卡 / 根本不想打开 / 改动要大批量且耗时超过桥的 120s 上限。

## 铁律（顺序不可颠倒）

1. **只读扫描先行** —— 先搞清工程结构与红线，绝不直接动手
2. **查多实例**（`mesh.users > 1`）—— 不为 0 就**停止**，先做数据独立化
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
（含 `analyze_materials.py` / `merge_by_material.py` / `verify_merge.py` / 自测台）
完整原理：**[`../docs/按材质合并为单个网格体.md`](../docs/按材质合并为单个网格体.md)**

## 二、动手前必查的四件事

跑 `analyze_materials.py`，回答：

| 看什么 | 红线 / 影响 |
|---|---|
| `对象共用同一网格的数量` | **红线**。不为 0 ⇒ 有多实例，合并会把一份几何复制 N 份，**文件反而变大**。先独立化再合并 |
| `UV_LAYER_COUNT_HIST` / `有顶点色/形态键的对象` | 决定会不会丢数据、分组键要不要更细 |
| `DISTINCT_MATERIAL_SETS` | 直接等于**合并后的对象数** |
| `有父级的对象` / `非单位缩放` | 不为 0 ⇒ 必须烘焙世界变换（脚本已做，但要知道为什么） |

## 三、两条必须懂的机制

### ① 世界变换烘焙 —— 不做的后果是模型散架

对象最终位置由三段矩阵连乘决定，而 `join()` 只取**自己的 `matrix_world`**，
**父级的贡献会被丢掉**。所以必须先解开父子关系、同时把世界变换烧进对象自身：

```python
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
```

`CLEAR_KEEP_TRANSFORM` 是关键 —— 用默认的 `CLEAR` 对象会"跳回"局部原点，立刻散架。

> ⚠️ **别用 `transform_apply()` 替代**，多层父级下同样算错，且破坏原始形状定义。

### ② 分组键必须带 UV

```python
key = (tuple(m.name if m else "<空>" for m in o.data.materials),  # 完整材质列表
       tuple(l.name for l in o.data.uv_layers))                   # UV 层名列表
```

只按"第一个材质名"分组不够（多材质槽对象会混）。
UV 必须进 key —— 带 UV 的和不带 UV 的并进同一组，**UV 会被拉平丢失**。

## 四、执行纪律

### 必须后台跑

前台跑超过 120 s 会被 SIGTERM 掐断 —— **踩过一次，几分钟白等**，
而且日志是空的、磁盘上没留半成品，很难判断发生了什么。

```bash
cd <工作目录> && del merge_run.log
blender.exe --background --factory-startup "<源>.blend" --python merge_by_material.py -- "<输出>_合并.blend"
```

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

3. **自测台**（改脚本逻辑时用）：`build_smoke_scene.py` → `merge_by_material.py` → `verify_smoke.py`，
   核心判据是**世界包围盒最大偏差 = 0.000000**，证明父子/旋转/缩放都处理对了。

## 六、性能真相（用于估时，别搞反）

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
（我第一次就是这么估，得出"还要几十分钟"，实际两分钟后就跑完了。）

### 多线程为什么不可能

`bpy.data` 不是线程安全的，`join` / `append` 是**硬性单线程**。
实测开了 32 线程，3 秒 CPU 增量只有 2.95 秒。`--threads` 只管渲染和物理，**对数据块操作无效**。

「切块并行再拼接」也不省：那些数据块终究要一个个灌进同一个 `bpy.data`，工作量一分不少。

## 七、合并两个工程时的两个陷阱

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

## 八、忙中出错清单

| 现象 | 优先怀疑 | 处理 |
|---|---|---|
| 前台任务跑了 2 分钟就没了 | 被 SIGTERM 掐断 | 改后台跑 + 独立日志；别用 `sleep` 长命令轮询 |
| 日志长时间不更新 | 未必卡死 | 看 3 秒 CPU 增量，> 0.5 s 就是还在算 |
| 合并后模型散架 / 坐标错 | 没烘焙世界变换 | `parent_clear(type="CLEAR_KEEP_TRANSFORM")` |
| 合并后文件反而变大 | 多实例被复制 N 份 | 回第二步查 `mesh.users > 1` |
| UV 丢了 | 分组键没带 UV 配置 | `(材质tuple, uv层名tuple)` 一起做 key |
| 顶点/面数对不上 | 排除名单写错 / 非网格对象被误并 | 名单不存在会告警，别忽略 |
| 脚本 `NameError` | 编辑漏行 | `ast.parse` 通过 ≠ 能跑，必须实跑小场景 |
| GUI 删集合后文件没变小 | 孤立数据还在 | 需做 orphan purge |

## 九、姐妹操作

[`../scripts/separate-by-material/`](../scripts/separate-by-material/) 是「一拆多」，
本 skill 是「多合一」，两者判据与算子都不相同 —— 别混用：

| | separate | merge |
|---|---|---|
| 算子 | `bpy.ops.mesh.separate(type='MATERIAL')` | `bpy.ops.object.join()` |
| 依据 | 材质**槽**，对整网格生效、与选择无关 | 材质**列表 + UV 配置** |
| 判据 | 几何守恒 + 属性层无损失 | 几何守恒 + **世界包围盒偏差 ≈ 0** |
