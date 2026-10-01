# 按材质合并为单个网格体(可复用包)

[`separate-by-material`](../separate-by-material/) 是「一拆多」,本包是它的**反向操作:「多合一」**。

SketchUp / CAD 导入后的工程常有几万个零碎网格对象,视口和大纲树卡成幻灯片。
把**材质组合相同**的对象合并成极少数几个对象,是治本的办法。

## 一句话原理

```python
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")   # 先烘焙世界变换,否则模型会散架
bpy.ops.object.join()                                       # 再按组拼接
```

* 分组键 = **(材质列表, UV 层名列表)** 的组合,不是单个材质
* 合并后对象数 = **去重后的材质组合数** + 排除对象数
* UV 必须进分组键:若把带 UV 的和不带 UV 的并进同一组,UV 会被拉平丢失

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
| `merge_by_material.py` | **执行**:烘焙世界变换 → 分组 → 逐组合并 → 清空物体 → 守恒校验 → 另存 | 命令行(**必须后台跑**) |
| `verify_merge.py` | **独立复核**:**另开一次 Blender** 打开产物,核对顶点/面/排除对象/顶层集合 | 命令行 |
| `inspect_file.py` | 结构扫描(只读):顶层集合树 + 总数统计 | 命令行 |
| `build_smoke_scene.py` | **自测台**:建一个 ~20 对象的小场景做冒烟测试(第 1 步) | 命令行 |
| `verify_smoke.py` | **自测台**:比对基线与合并结果(第 3 步) | 命令行 |
| `exclude.example.txt` | 排除名单模板(改名 `exclude.txt` 后生效) | — |
| `../docs/按材质合并为单个网格体.md` | 完整原理 / 实测数据 / 坑 | 阅读 |

## 配置项

`merge_by_material.py` 顶部:

```python
HERE         = os.getcwd()                      # 工作目录:日志 / 排除名单都在这里
LOG          = os.environ.get("MBM_LOG", <HERE>/merge_run.log)
EXCLUDE_FILE = <HERE>/exclude.txt               # 排除名单,一行一个对象名
NAME_PREFIX  = "M_"                             # 合并后对象名前缀(取该组第一个材质名)
PURGE_EMPTY  = True                             # 是否清理合并后失去意义的空物体
```

输出路径由命令行第一个参数给(`--` 之后),**脚本内有安全闸**:输出路径等于源文件时直接拒绝。

`verify_merge.py` 顶部要填这次的实测值:

```python
EXPECT_VERTS = 10197620      # 取自 analyze_materials.py 的 TOTAL_VERTS
EXPECT_POLYS = 7957765       # 取自 TOTAL_POLYS
EXPECT_KEPT  = ["G-物体.24146"]
EXPECT_TOP_COLLECTIONS = ["Collection", "SKP Imported Data", "相机", "Export"]
```

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
```

判据:

```
==CHECK_verts== OK
==CHECK_polys== OK
==CHECK_GROUPCOUNT== OK
==CHECK_POSITION== OK 最大偏差 0.000000
==SMOKE_RESULT== PASS
```

**最大偏差 0.000000** 是核心 —— 它证明父子 / 旋转 / 缩放全都正确处理了。

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

## 实测数据(Blender 5.2.2 LTS)

工程:`261001x02x环境.blend`,SketchUp 导入,510 MB,zstd 压缩。

| 指标 | 合并前 | 合并后 |
|---|---|---|
| 网格对象 | 24,481 | **56**(55 个材质组合 + 1 个排除对象) |
| 顶点 | 10,197,620 | 10,197,620(**完全一致**) |
| 面 | 7,957,765 | 7,957,765(**完全一致**) |
| 空物体 | 470 | 1 |
| 材质 / 图片 | 64 / 42 | 64 / 42(未丢) |
| 文件体积 | 510.7 MB | 505.2 MB |
| 总耗时 | — | **5.5 分钟** |

### 耗时分布 —— 这里反直觉

```
第 1 组  Color M02]1(24,137 个对象)  → 321.8 秒   ← 占 98%
其余 54 组合计(343 个对象)            →   2.7 秒
存盘 505 MB                            →   0.6 秒
```

**`bpy.ops.object.join` 的开销集中在「对象个数」,跟几何体量关系不大。**
`Am176_048_001` 这组只有 20 个对象却有 3,326,200 顶点,用了 0.1 秒;
反倒是挂着 24,137 个零散对象的 `Color M02]1` 吃掉了几乎全部时间。

所以**给用户估时,先看最大组有多少对象**,别用平均速率外推(我曾按平均速率估成几十分钟,实际 5.5 分钟)。

## 姊妹操作对照

| | [`separate-by-material`](../separate-by-material/) | 本包 |
|---|---|---|
| 方向 | 一个对象(多材质槽)→ 多个对象 | 多个对象 → 一个对象 |
| 算子 | `bpy.ops.mesh.separate(type='MATERIAL')` | `bpy.ops.object.join()` |
| 按什么分/合 | 材质**槽**,对整网格生效、与选择无关 | 材质**列表 + UV 配置**的组合 |
| 判据 | 几何守恒 + 属性层无信息损失 | 几何守恒 + **世界包围盒偏差 ≈ 0** |
| 适用时机 | 要单独隐藏 / 换材质 / 导出 / 做 LOD | 对象太多导致 GUI 卡死 |

## 相关

- 完整原理与坑:[`docs/按材质合并为单个网格体.md`](../docs/按材质合并为单个网格体.md)
- Skill:[`skills/blender-headless-batch/`](../skills/blender-headless-batch/)
