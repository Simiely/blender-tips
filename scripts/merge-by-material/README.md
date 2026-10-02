# 按材质合并为单个网格体(可复用包)

[`separate-by-material`](../separate-by-material/) 是「一拆多」,本包是它的**反向操作:「多合一」**。

SketchUp / CAD 导入后的工程常有几万个零碎网格对象,视口和大纲树卡成幻灯片。
把**材质组合相同**的对象合并成极少数几个对象,是治本的办法。

## 一句话原理

```python
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")   # 先烘焙世界变换,否则模型会散架
bpy.ops.object.join()                                       # 再按组拼接
```

* 分组键 = **(材质列表, UV 层名列表[, 父级名])** 的组合,不是单个材质
* 合并后对象数 = **去重后的材质组合数** + 排除对象数
* UV 必须进分组键:若把带 UV 的和不带 UV 的并进同一组,UV 会被拉平丢失
* **父级进不进分组键是一道取舍**(v2 默认进,见下)——
  进了保住「装置归属」、结果更保守;不进则组数最少、但装置层级彻底消失

> ⚠️ **合并不可逆** —— 单个构件的名字和可选中性永久消失。这是默认取舍,动手前要确认粒度。

## 运行位置(和其它包不一样)

本包脚本**不用桥 `send.py`**,而是走**系统命令行无头 Blender**:

```bash
blender.exe --background --factory-startup "<源.blend>" --python <脚本>.py -- [参数...]
```

原因:合并动辄几分钟以上,桥有 **120s 超时**限制;而且巨型工程本身在 GUI 里就打不开或极卡,
无头模式绕开了这一步。

## 文件清单

| 文件 | 作用 | 运行位置 |
|---|---|---|
| `analyze_materials.py` | **前置分析**(只读):多实例检测 / UV 盘点 / 材质组合去重数。**动手前必跑** | 命令行 |
| `merge_by_material.py` | **执行**:烘焙世界变换 → 分组 → 风险判定 → 逐组合并 → 清空物体 → 守恒校验 → 另存。**v2 起大组自动走两级 join** | 命令行(**必须后台跑**) |
| `verify_merge.py` | **独立复核**:**另开一次 Blender** 打开产物,读 `merge_result.json` 逐组核对 | 命令行 |
| `perf_probe.py` | **性能体检**:对象数 / draw call 代理量 / 每帧提交顶点量 / 显存口径(单文件) | 命令行 |
| `compare_perf.py` | **性能对照**:对多个 .blend 同口径跑「加载 + 体检」计时 | 普通 Python |
| `inspect_file.py` | 结构扫描(只读):顶层集合树 + 总数统计 | 命令行 |
| `build_smoke_scene.py` | **自测台**:建一个覆盖全部代码路径的场景(第 1 步) | 命令行 |
| `verify_smoke.py` | **自测台**:比对基线与合并结果(第 3 步) | 命令行 |
| `exclude.example.txt` | 排除名单模板(改名 `exclude.txt` 后生效) | — |
| `../docs/按材质合并为单个网格体.md` | 完整原理 / 实测数据 / 坑 | 阅读 |

## 配置项

`merge_by_material.py` 顶部:

```python
HERE             = os.getcwd()                  # 工作目录:日志 / 排除名单 / 结果都在这里
LOG              = os.environ.get("MBM_LOG", <HERE>/merge_run.log)
EXCLUDE_FILE     = <HERE>/exclude.txt           # 排除名单,一行一个对象名
NAME_PREFIX      = "M_"                         # 合并后对象名前缀(取该组第一个材质名)
PURGE_EMPTY      = True                         # 是否清理合并后失去意义的空物体

# ---- v2 新增 ----
GROUP_BY_PARENT  = True    # 分组键含父级(保住装置归属;要 v1 行为设 False)
SKIP_MULTI_SLOT  = False   # True = 多材质槽对象不参与(用户口径);False = 按完整材质列表分组
SKIP_RISKY       = True    # 跨集合 / 不在视图层 / hide_viewport / 修改器不一致 ⇒ 整组跳过
ONESHOT_MAX_OBJS = 400     # 组内对象数 ≤ 此值走一次性 join;超过则独立化 + 两级 join
MAX_BATCH_OBJS   = 120     # 两级 join 的单块上限
TOL              = 1e-3    # 世界包围盒容差
```

输出路径由命令行第一个参数给(`--` 之后),**脚本内有安全闸**:输出路径等于源文件时直接拒绝。
`--limit N` 可只处理前 N 组(按对象数降序),用于先试跑。

`merge_by_material.py` 落盘三个文件:

| 文件 | 内容 |
|---|---|
| `merge_run.log` | 实时日志(长任务后台跑时持续 tail) |
| `merge_result.json` | 前后计数 / 每组偏差 / 跳过清单 / **每组前后世界包围盒**(复核脚本要用它) |
| `merge_names.txt` | 人读名单:哪些合成了哪些 |

`verify_merge.py` v2 起**零配置** —— 直接读上面那个 JSON,不用再手工填 `EXPECT_VERTS`。

## 使用步骤

### 0. 前置分析(不许跳过)

```bash
blender.exe --background --factory-startup "<源.blend>" --python analyze_materials.py
```

**它要回答的四个问题**:

| 看什么 | 为什么关键 |
|---|---|
| `对象共用同一网格的数量` | **红线**。不为 0 说明有多实例,合并会把一份几何复制 N 份,文件暴涨 |
| `UV_LAYER_COUNT_HIST` / `有顶点色的对象` / `有形态键的对象` | 决定会不会丢数据、分组键要不要更细 |
| `DISTINCT_MATERIAL_SETS` | 直接等于**合并后的对象数** |
| `有父级的对象` / `非单位缩放` | 不为 0 就必须做世界变换烘焙(脚本已做,但要知道为什么) |

### 1. 自测台:小场景验证逻辑

```bash
blender.exe --background --factory-startup --python build_smoke_scene.py
blender.exe --background --factory-startup smoke_scene.blend ^
            --python merge_by_material.py -- "<cwd>\smoke_out.blend" KEEP_ME
blender.exe --background --factory-startup smoke_out.blend --python verify_smoke.py
blender.exe --background --factory-startup smoke_out.blend --python verify_merge.py
```

判据:

```
==CHECK_verts== OK
==CHECK_polys== OK
==CHECK_groupcount== OK
==CHECK_position== OK
==CHECK_risky_kept_*== OK          ← 被跳过的风险组必须原样保留
==SMOKE_RESULT== PASS
==VERIFY_RESULT== PASS
```

`build_smoke_scene.py` 的场景**不是随便凑的**,它逐条覆盖代码路径:
普通组 / 多材质槽 / 带父级的层级 + 旋转缩放 / 一个应被排除的对象,
**外加 v2 的四条新路径**:共享 mesh 的大组(450 个)、独立 mesh 的大组(500 个)、
跨集合的一组、躺在 excluded 集合里的一组。

### 2. 跑真家伙(**必须后台跑**)

```bash
cd <工作目录>
copy exclude.example.txt exclude.txt        # 按需编辑排除名单
del merge_run.log
blender.exe --background --factory-startup "<源.blend>" ^
            --python merge_by_material.py -- "<输出>_合并.blend"
```

> 前台跑超过 120 s 会被 SIGTERM 掐断,之前踩过一次,跑到一半白干。
> 后台跑 + 独立日志文件,随时 `tail merge_run.log` 看进度。

判断「真在干活还是卡死」——**看 CPU 增量,不要看日志刷新频率**:

```powershell
$a = (Get-Process blender)[0].TotalProcessorTime.TotalSeconds
Start-Sleep 3
$b = (Get-Process blender)[0].TotalProcessorTime.TotalSeconds
"3秒CPU增量: {0:N2}s" -f ($b-$a)   # > 0.5s = 在干活
```

### 3. 独立复核(**必须另开一次 Blender**)

```bash
blender.exe --background --factory-startup "<输出>_合并.blend>" --python verify_merge.py
```

> 合并进程里打的 `CHECK_VERTS 一致` 只能证明**内存里**的数据对得上,
> **不能证明存出去的文件还能打开**。这一步不能省。

### 4. 性能验收(可选,回答「合并后会更流畅吗」)

```bash
python compare_perf.py "<源.blend>" "<输出>_合并.blend"
```

## v2 的四项加固(全都实测踩过)

### ① 两级 join —— 一次性 join 两千多个对象会崩

```
Calloc array aborted due to integer overflow: len=18446744072358535680x4
in from_uninitialized, total 27960300944     → Blender 直接退出,EXIT=127
```

触发场景:2405 个对象一次 join(总顶点才 36 万,却要申请 ~28 GB ⇒ 是 bug 不是真实需求)。
Blender 的 join 实现里某个数组长度计算下溢成了负数。

⇒ **按 ≤ `MAX_BATCH_OBJS`(默认 120)切块,每块做一次性 join 得中间对象,
再把这些中间对象一次性 join 成一个**。实测 2405 个对象 → 21 块 + 第 2 级,
363281 顶点与基线完全吻合,偏差 0.000021 ✅

⚠️ **绝不能**「逐批 join 到同一个 active」—— 那就是下面的坑 ②。

### ② 共享 mesh 数据块 + **多段** join = 几何被重复计入 ★最阴

导入工程里大量对象是**同一网格的实例**(SKP 组件 / Alt+D)。实测某组 137 个对象中,
136 个共用一份 `C-墙砖#1`(8 顶点):

| 做法 | 结果 |
|---|---|
| 一次性 join 137 个 | **1365 顶点,偏差 0.000003 ✅** |
| 分两批 join(120+17) | **16597 顶点,偏差 1.688313 ❌** |

第二段 join 把该 mesh 在**整个工程里**的全部实例几何都算了进来(多出 15232 = 1904×8)。
**与「选中残留」无关**(加了每批前全场景 DESELECT 后结果一模一样)。

⇒ **正解:走两级 join 前先把网格数据独立化**

```python
for o in g:
    if o.data.users > 1:
        o.data = o.data.copy()
```

独立化后同一组:块 2 → 405 顶点、合并后 1365(= 基线)✅

> 注意:独立化的**代价**是把实例展开成实体几何,文件会变大。所以 v2 只在
> 「必须走两级 join 的大组」上做;小-中组走一次性 join,共享网格在 join 后变孤儿、
> 存盘时被 Blender 丢弃,**文件不膨胀**。

### ③ 选中状态必须【跨组】维护

两级 join 走的是全局选中路径。若把 `sel = []` 写在每组内部,
**上一组的存活对象会一直保持选中**,被下一组 join 一起吞掉
(实测偏差 5013.98,67/69 组失败)。

⇒ `sel` 提到循环外;每组开头先取消它;并加安全网:

```python
leftover = list(bpy.context.selected_objects)
if leftover:
    bpy.ops.object.select_all(action='DESELECT')      # 强制清空
```

> v1 的快路径用 `temp_override(selected_editable_objects=...)`,不碰全局选中状态,
> 天然免疫这一问题 —— 但它处理不了大组(见坑 ①),所以两条路径都得留着。

### ④ 风险组判定 —— 有些组根本不该碰

| 判据 | 为什么 |
|---|---|
| **跨集合** | 组内对象分散在多个集合 ⇒ 合并会让某个集合凭空多出/失去几何,破坏 SKP 结构 |
| **有成员不在视图层** | 躺在被 exclude 的隐藏集合里 ⇒ join 拿不到它,结果不可预期 |
| `hide_viewport` | 同上 |
| **修改器配置不一致** | `join` 只保留**活动对象**的修改器,其余的全丢。若组内有「带按角度平滑」和「不带」混着,合并后着色会变 |

> ⚠️ **excluded 集合里还有一个静默陷阱**:那里的对象 `matrix_world` **不会被 depsgraph 求值**,
> 停在旧值(往往就是局部坐标)。任何「算世界包围盒/世界坐标」的校验脚本都会在这里得出错值 ——
> 两侧口径必须都限定在**视图层内**的对象(`bpy.context.view_layer.objects`)。

### ★ 活动对象要挑「带按角度平滑」的

Blender 4.1+/5.x 导入的工程常给每个网格挂 **`Smooth by Angle`(按角度平滑,NODES 型)** ——
实测某 SKP 工程 27,352 / 50,622 个对象带它。`join` 只保留活动对象的修改器栈,
所以必须**指定一个带它的对象当活动对象**:

```python
SMOOTH = re.compile(r"按角度平滑|Smooth by Angle")
A = next((o for o in g if any(SMOOTH.search(m.name) for m in o.modifiers)), g[0])
```

## 实测数据(Blender 5.2.2 LTS)

> 下面两段是**不同取舍**的两个工程,别混着用。

### A. 510 MB / 2.4 万对象工程(材质列表 + UV 分组,465 组)

工程:`261001x02x环境.blend`,SketchUp 导入,zstd 压缩。

| 指标 | 合并前 | 合并后 |
|---|---|---|
| 网格对象 | 24,481 | **56**(55 个材质组合 + 1 个排除对象) |
| 顶点 | 10,197,620 | 10,197,620(**完全一致**) |
| 面 | 7,957,765 | 7,957,765(**完全一致**) |
| 空物体 | 470 | 1 |
| 材质 / 图片 | 64 / 42 | 64 / 42(未丢) |
| 文件体积 | 510.7 MB | 505.2 MB |
| 总耗时 | — | **5.5 分钟** |

耗时分布 —— 这里反直觉:

```
第 1 组  Color M02]1(24,137 个对象)  → 321.8 秒   ← 占 98%
其余 54 组合计(343 个对象)            →   2.7 秒
存盘 505 MB                            →   0.6 秒
```

**`bpy.ops.object.join` 的开销集中在「对象个数」,跟几何体量关系不大。**
`Am176_048_001` 这组只有 20 个对象却有 3,326,200 顶点,用了 0.1 秒;
反倒是挂着 24,137 个零散对象的 `Color M02]1` 吃掉了几乎全部时间。

所以**给用户估时,先看最大组有多少对象**,别用平均速率外推。

### B. 541 MB / 5 万对象 SKP 工程(材质 + 父级分组,v2 默认口径)

| 指标 | 源 | 产物 | 说明 |
|---|---|---|---|
| 对象数 | 50,622 | 43,713 | −13.7% |
| 网格对象 | 28,571 | 21,678 | −24.1% ⇒ **draw call 少 24%** |
| 带修改器对象 | 27,352 | 20,454 | −25.2% ⇒ 依赖图求值负担减轻 |
| **按对象累加顶点** | 19,871,278 | 19,871,278 | **完全相同** ⇒ 渲染帧率不变 |
| 唯一网格顶点 | 1228 万 | 1627 万 | **+32.5%** ⇒ 显存/内存上升 |
| 文件体积 | 541 MB | 655 MB | +114 MB |
| 冷启动加载 | 9.0 s | 8.0 s | **反而更快**(受对象数影响 > 文件大小) |
| `select_all` | 0.215 s | 0.180 s | −16% |

执行结果:可合并 393 组 / **369 组成功 0 失败**,最大世界包围盒偏差 **0.000183**(容差 1e-3),
几何完全守恒(顶点数、面数一个不差)。跳过 24 组(约 1,188 对象),
原因**全部是「有成员不在视图层」**—— 躺在 SKP 导入时被 exclude 的隐藏集合里,
要合并需先在 Outliner 里取消那些集合的排除。

> **结论口径(重要)**:合并**会更快,但快在「操作响应」**——
> 选择、移动、改材质、Outliner 浏览、依赖图重算;
> **不是「渲染帧率」** —— 每帧真正提交的顶点数一模一样。
> 副作用是实例被展开成实体(文件/显存变大),且大对象的**视锥剔除会变差**
> (原来能被剔除的小对象,合并后跨越大范围反而剔不掉)。

## 姊妹操作对照

| | [`separate-by-material`](../separate-by-material/) | 本包 |
|---|---|---|
| 方向 | 一个对象(多材质槽)→ 多个对象 | 多个对象 → 一个对象 |
| 算子 | `bpy.ops.mesh.separate(type='MATERIAL')` | `bpy.ops.object.join()` |
| 按什么分/合 | 材质**槽**,对整网格生效、与选择无关 | 材质**列表 + UV 配置(+ 父级)**的组合 |
| 判据 | 几何守恒 + 属性层无信息损失 | 几何守恒 + **世界包围盒偏差 ≈ 0** |
| 适用时机 | 要单独隐藏 / 换材质 / 导出 / 做 LOD | 对象太多导致 GUI 卡死 |

## 相关

- 完整原理与坑:[`docs/按材质合并为单个网格体.md`](../docs/按材质合并为单个网格体.md)
- Skill:[`skills/blender-headless-batch/`](../skills/blender-headless-batch/)
- 动手前的只读体检:[`skills/blender-project-prescan/`](../skills/blender-project-prescan/)
