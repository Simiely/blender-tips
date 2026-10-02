---
name: blender-blend-append-merge
description: 把两个（或多个）.blend 工程追加合并成 1 个——最稳最快的做法与对账口径。当用户说「这两个文件要追加合并为一个工程」「把 B 并进 A」「两个 blend 合成一个」「合并两个场景」时使用。★核心实测结论：append 耗时几乎只取决于**被追加进来的对象数**（29,914 对象 = 458 s vs 137 对象 = 7 s，差 80 倍），与顶点数/贴图量几乎无关，所以底文件的选法决定成败；且必须处理三个必踩的坑：① Blender 重名去重会「按数字后缀续号」把对象名整体挪号（实测 1,026/29,914 被改名，父子链接没事但名字不可靠）② 直接挂在 Scene Collection 根下、不属于任何 bpy.data.collections 的**游离对象会被整批漏掉** ③ 世界/场景设置不会随集合追加过来。对账口径必须用**多重集（世界矩阵/几何/数据块/users）**，不能用名字。
agent_created: true
---

# 两个 .blend 追加合并为一个工程

`blender-headless-batch` 管「按材质把**一个**工程内部的对象合并」；
本 skill 管的是**两个工程并成一个** —— 是另一件事，坑也完全不同（那边怕几何重复计入，这边怕**丢件**和**名字错位**）。

传输层同样走**系统命令行无头**，不引用 `blender-bridge-ops`：

```bash
blender.exe --background --factory-startup "<底文件.blend>" --python merge_append.py
```

## 0. 一句话结论

```
以「对象少的一边」为底，用 bpy.ops.wm.append 追加另一边的顶层集合
+ 补追「游离对象」（挂在 Scene Collection 根下、不属于任何集合的那些）
+ 对账必须用多重集口径（不能靠名字）
```

追加耗时 ≈ **15 ms × 被追加的对象数**，与顶点数、贴图数量几乎无关。

## 1. 性能：底文件选错，代价是 80 倍

同一对工程，只换「以谁为底」：

| 方向 | 被追加进来的对象数 | 被追加的几何 | append 本体耗时 |
|---|---|---|---|
| **A 为底** → 追加 B 的 `SKP Imported Data` | 29,914 | 18.73 M 顶点 | **457.9 s** |
| **B 为底** → 追加 A 的 `SKP Imported Data` + `相机` | 154 | 10.20 M 顶点 | **7.0 s**（5.55 + 1.49） |
| A 为底 → 只追加 B 的 `SKP Scenes (as Cameras)`（1 相机） | 1 | 0 | 约 1.4 s（库打开固定开销） |

★ **几何量差 1.8 倍，耗时差 80 倍** —— 起决定作用的是**对象个数**，不是数据量。
A 侧 10.2 M 顶点只花 5.6 s，B 侧 18.7 M 顶点花 458 s。

> ⚠️ 本仓库早先记录的「以对象少的一边为底能省一半时间」——**严重低估**。
> 当两边对象数差两个数量级时，收益是**两个数量级**。
> 估时请直接看「被追加侧有多少个对象」，不要看文件体积或顶点数。

**推论**：如果底文件必须是「对象多的那个」（比如场景设置只有它有），那 append 就注定慢；
想快只能**先把被追加那侧的对象数降下来**（合并 / 精简），但那是另一件事且不可逆。

## 2. 选底文件的两条硬约束

| | 以 A 为底 | 以 B 为底 |
|---|---|---|
| 速度 | 458 s | 7 s |
| 场景设置（fps / 帧范围 / 输出路径 / 场景相机 / 世界 / Cycles 采样 / 色彩管理 …） | **天然全是 A 的，零风险** | 全是 B 的，需要**逐项归位**，漏一项就是隐性错 |
| A 的 excluded 集合（如 `Export`，5 个对象在视图层外） | 保持 exclude | 追加进来后 exclude 状态丢失 ⇒ 那 5 个对象会冒出来参与渲染 |

⇒ **除非两边对象数很接近，否则不要为了省 7 分钟去选「对象多的一边」当底**——
场景级设置的归位没有可枚举的边界（`scene` + `render` + `cycles` + `color_management` +
view layers + 合成树 …），是「省了 7 分钟、换来一堆隐性漏项」的典型负收益。

## 3. 三个必踩的坑

### ① 重名去重会「按数字后缀续号」，把对象名整体挪号 ★最容易误判成数据丢失

Blender 的唯一名算法在最后一个 `.NNN`（纯数字）处切分基名。所以 `G-物体.010` 的基名被视作
`G-物体`、序号 10。当 A 里已有大量 `G-物体.NNNNN` 时，追加 B 的 `G-物体.010` 会去找
**`G-物体` 这组的第一个空闲号**，于是变成 `G-物体.011`、`.008 → .009`、`.013 → .014` …
被顶掉的位置再往后挤，形成**链式挪号**。

**后果**：
- **父子链接、世界变换、几何、材质全都正确** —— Blender 内部按 ID 指针链接，改名字不影响。
  实测世界矩阵多重集**位级完全一致**（最大元素偏差 `0.000e+00`）。
- 但**名字完全不可靠** —— 任何「按对象名找回来源侧某个对象」的脚本、任何名字对账都会失败。
  极易被误判成「追加丢了东西 / 层级错乱」。
- 若确实要保名，正确做法是在 append **之前**给来源文件的对象名统一加重前缀（在副本上做），
  **不要**事后去改。

**量化它**（这个口径才是准的）：

```python
# 用「除名字外全属性结构键」配对：类型 + 顶点 + 面 + 材质槽数 + 修改器数 + 位级世界矩阵
key = lambda t, nv, np, nm, nmod, mw: (t, nv, np, nm, nmod, tuple(mw))
# 键相同的对象之间除名字外完全一样 ⇒ 键组内名字集合的差集 = 真被改名的对象数
```

实测：**1,026 / 29,914（3.4%）个对象名被改**，而**结构键 100% 可配对**（0 个键组找不到对应）。

> ⚠️ **不要用「名字集合的差集」去量它** —— 链式挪号是**置换**：`G-物体.011` 这个名字
> 在产物里和来源里都存在（只是换了主人），所以名字集合只差一个新的最大值（实测只差 3 个名），
> 会把 1,026 个被改名的对象**全部漏报**。同理，用脆弱的名字映射去校验父级名会得到
> 「2,894 处父级不匹配」这种数字——它既不是真错误，也不是改名的规模。

### ② 游离对象会被整批漏掉（只追加集合的话）

`bpy.ops.wm.append` 追加一个集合，只会带**该集合树里**的对象。
但导入工程常有几个对象**直接挂在 Scene Collection 根下**，不属于任何 `bpy.data.collections`：

```python
covered = {o.name for c in bpy.data.collections for o in c.objects}
miss = sorted({o.name for o in bpy.data.objects} - covered)
# 实测来源侧: 3 个 —— G-3d66-Edi961475.001 / Mesh1 / Mesh2
```

**它们往往不是垃圾**：实测这 3 个都在主体位置、`visible=True`、`hide_render=False`、
各有 8 K~21 K 顶点和正常材质 —— 漏掉就是**模型缺件**。

**动手前必跑这段普查**，然后对漏掉的对象逐个单独 append：

```python
bpy.ops.wm.append(filepath=os.path.join(SRC, "Object", name),
                  directory=SRC + os.sep + "Object" + os.sep, filename=name,
                  instance_collections=False, set_fake=False, use_recursive=False)
```

（实测 3 个对象 5.4 s —— 每个都重新打开一次库，固定开销 ≈ 1.4~1.8 s/次。）

### ③ 世界 / 场景设置不会随集合追加过来

追加的是**数据块**，不是场景。实测：
- 底文件 `scene.world` 引用**从不变**（追加来源侧的集合不会把它的 `World` 带进来）⇒
  同名但节点树不同的 `World`（实测 A 是 3 节点、B 是 2 节点）**不会**冲突，这个隐患自动消失。
- 底文件的 fps / 帧范围 / 输出路径 / 场景相机 / 引擎 / 分辨率**全部保持不变**（14 项逐项验过）。
- 反过来说：**以 B 为底就会丢掉 A 的这些设置**（见 §2）。

### 附带：同名材质即使内容一模一样也会被复制成 `.001`

实测 5 个同名材质（`Brain1` / `Concrete 04 [imported]` / `DefaultMaterial` / `Glass` / `石膏 (1)`）
用节点树指纹判定**内容完全相同**，append 后仍然生成 `X.001` 副本 ——
`do_reuse_local_id=True` **实测无效**（行为与 `False` 完全一致）。

代价可忽略（341 个材质里多 5 个，外观一致）。
真要收干净，事后按指纹把 `X.001` 的材质槽重映射到 `X` 再删即可。

## 4. 对账口径：必须用多重集，不能靠名字

```python
import collections
mset = collections.Counter

new = set(OBJ_AFTER) - set(OBJ_BEFORE)          # 新增对象名（A 侧不变性另验）

# ★ 世界矩阵多重集 —— 一条判据同时覆盖「层级正确 + 变换正确」
# ① 位级：raw 16-float 元组的多重集逐一相等（最强判据，通过了就什么都不用再说）
exact = mset(tuple(v) for v in mw_B) == mset(tuple(v) for v in mw_new)
# ② 容差：逐列排序后逐点比 —— 免疫 float32 末位抖动（|v|≈5000 时 ULP≈6e-4）
for j in range(16):
    for x, y in zip(sorted(v[j] for v in mw_B), sorted(v[j] for v in mw_new)):
        assert abs(x - y) <= 2e-3 + 1e-6 * abs(x)

# 逐对象签名（类型 / 顶点 / 面 / 材质槽数 / 修改器节点组）
assert mset(sig_B) == mset(sig_for(n) for n in new)

# 数据块与资源
assert mset((m.users, len(m.vertices), len(m.polygons)) for m in NEW_MESHES) == mset(...)
assert mset(mat.users for mat in NEW_MATERIALS) == mset(base mats)
assert mset(img_names) == mset(base images 去掉 source == "VIEWER")   # Render Result / Viewer Node 不会进来
assert mset(cam.users for cam in NEW_CAMERAS) == mset(base cameras)
```

**为什么世界矩阵多重集是「层级 + 变换」的总账**：`matrix_world` 已经是绝对世界坐标，
父级链只要有一环错了，世界坐标就错，多重集立刻不等 ⇒ 不需要（也无法）靠名字去校验父子。

**为什么「逐列排序后比较」而不是靠名字配对**：同一列上若有两个对象值相同，谁配谁都不影响
排序后的标量序列 —— 这既是多重集语义，又天然容忍 ULP 抖动。真有一个对象变换错了，
排序序列会出现 O(1) 的错位，立刻被抓到。

**A 侧不变性**要单独验（名字在 A 侧是可靠的，A 的对象不会被改名）：
逐对象比 `type / data / parent / users_collection / 材质槽 / 修改器 / 世界矩阵 / hide_*`，
外加「A 原有的材质/图像/网格/节点组/相机/集合**条目仍在且值不变**」。

**几何总量**：`新增顶点和 == 来源侧顶点和`、`总顶点 == A + B`。两条都要验。

### 别犯的两个自带 bug（都实测踩过）

- 基线用 `round(v, 6)` 存、产物用 `round(v, 5)` 比 ⇒ 双重取整，29,914 个对象会**全部**报不匹配。
  两侧取整位数必须一致，或干脆都用容差口径。
- A 侧不变性的判据写成「前后**总数**相等」⇒ 追加必然让总数变大，5 项全红。
  正确判据是「A 原有的**每个条目仍在且值不变**」。

### ★ 顺序铁律：存盘必须排在对账【之前】

实测踩过：对账里一个 `%` 格式化 bug（把 tuple 当格式串）让脚本在存盘前崩溃，
**8 分钟 append 全部白跑**。存盘先做，报告出问题也不丢产物。

## 5. 冒烟台（先跑，别拿大工程试错）

本 skill 的 `scripts/smoke/` 是一对合成场景生成 + 语义测试，8 个对象、**0.007 s**
就能把 append 的全部语义验一遍：

```bash
SMK_TAG=A blender.exe --background --factory-startup --python build_smoke_ab.py
SMK_TAG=B blender.exe --background --factory-startup --python build_smoke_ab.py
SMK_ROUTE=op blender.exe --background --factory-startup smoke_A.blend --python append_test.py
```

实测结果（可直接当「append 到底做了什么」的参考基准）：

```
集合    SKP Imported Data -> SKP Imported Data.001（并行子树，原树分毫不动）
对象    G-物体 -> G-物体.001（原对象不动）
材质    M_shared -> M_shared.001（内容相同也复制，do_reuse_local_id 无效）
网格    3 个对象共用一份 mesh -> 仍共用，users 仍为 3（★文件不会因实例展开而膨胀）
修改器  NODES 修改器引用的 NodeGroup 自动跟随带入
贴图    打包图像自动跟随带入
世界    底文件 scene.world 不变，来源文件的 World 不进来
```

## 6. 完整执行配方

```bash
# ① 只读普查（两边都跑）：场景上下文 + 游离对象
blender.exe --background --factory-startup "<A.blend>" --python probe_merge_ctx.py
blender.exe --background --factory-startup "<B.blend>" --python probe_missing.py

# ② 导出「被追加侧」的逐对象基线
BL_TAG=B blender.exe --background --factory-startup "<B.blend>" --python dump_b_baseline.py

# ③ dry run（MERGE_OUT 留空 —— 只对账、不落盘）
AMB_SRC_A=<A> AMB_SRC_B=<B> blender.exe --background --factory-startup "<A.blend>" --python merge_append.py

# ④ 正式执行（必须后台跑；实测总时长 ≈ 9 min，其中 append 458 s）
AMB_SRC_A=<A> AMB_SRC_B=<B> MERGE_OUT="<输出>.blend" \
  blender.exe --background --factory-startup "<A.blend>" --python merge_append.py

# ⑤ 独立复核（另开一次 Blender 打开产物）
blender.exe --background --factory-startup "<输出>.blend" --python verify_append.py
```

环境变量：`AMB_WORK`（报告/基线落盘目录，默认当前目录）、`AMB_SRC_A` / `AMB_SRC_B`（两个源文件）、
`MERGE_OUT`（产物路径，**留空 = dry run**）、`MERGE_STRAYS=0|1`（是否补追游离对象，默认 1）。

`--factory-startup` 别漏（省掉本机 SketchUp 插件的 25 MB DLL 加载）。
`append` 是硬性单线程，`--threads` 对数据块操作无效。

## 7. 实测产物形态

```
对象 164 -> 30,078 （MESH 27,472 / EMPTY 2,584 / CAMERA 22）
顶点 10,197,620 -> 28,931,688 = A + B（逐位相等）
面    7,957,765 -> 28,094,181 = A + B（逐位相等）
材质 64 -> 341   图像 42 -> 180   网格块 80 -> 2,860
节点组 0 -> 1    相机 21 -> 22    集合 5 -> 8
体积 257.9 MiB + 363.5 MiB -> 620.8 MiB
场景顶层：Export / SKP Imported Data / SKP Imported Data.001 / 相机
多实例 25,091 保持共享（未展开）★ 文件不因实例膨胀
```

**耗时拆解**：载入底文件 1.5 s　|　append 集合 457.9 s　|　append 3 个游离对象 5.4 s　|
快照 30,078 对象 33 s　|　存盘 620 MB **0.9 s**（zstd，出乎意料地快）　|　对账 0.3 s

**验收**：同进程对账 `PASS 33 / FAIL 0`；独立复核（另开 Blender）`PASS 28 / FAIL 0` + `REOPEN_OK`。

**注意产物是「两个并行子树」**（A 的 `SKP Imported Data` 与 B 的 `SKP Imported Data.001` 并列）——
这是最安全、可区分来源、可回退的形态；若要求结构统一，事后改名 / 挪集合即可
（**不要**把来源侧的名字改回原名，会再次触发 §3① 的挪号）。

## 8. 与「按材质合并」的关系

**不要**为了「让 append 快一点」而先对来源侧做按材质合并：
导入工程里大量对象共享同一 mesh 数据块（实测 2,780 个数据块服务 27,348 个对象，
单块最多服务上千个对象），按材质合并必须**独立化**这些实例 ⇒ 几何被展开 ⇒ 文件暴涨。
实测同一个来源工程：`按材质合并` 产物 **654.7 MiB > 源 540.8 MiB**，纯负收益且不可逆。

## 相关

- 姊妹通道：`blender-headless-batch`（一个工程**内部**按材质合并）/ `blender-project-prescan`（动手前只读体检）
- 完整原理 / 实测数据：[`../docs/追加合并两个工程.md`](../docs/追加合并两个工程.md)
- 反向取舍：[`../docs/按材质合并为单个网格体.md`](../docs/按材质合并为单个网格体.md)
- 整理后的清理：[`blender-scene-cleanup`](../blender-scene-cleanup/SKILL.md)
