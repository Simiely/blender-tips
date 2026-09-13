# CHANGELOG.md

## v1.17.0 · 2026-09-13

- **新增主题 #35「渲染发黑与材质不发光排查」** —— `docs/渲染发黑与材质不发光排查.md` + 脚本包 `scripts/blackout-diagnose/`
  - **核心结论：这类问题 90% 不在材质节点里**。七条路径按命中率降序：
    ① **View Layer 材质覆盖 `material_override`**（★最高频）② Workbench 引擎不读材质节点
    ③ Holdout / 相机可见性 / 视图层排除 ④ Material Output 未连线或**发光值改在未接输出的孤儿 BSDF 上**
    ⑤ AgX 色彩变换压暗（只解释"不够亮"，不解释"纯黑"）⑥ 透明度与背面剔除 ⑦ 材质被几十对象共享 / 挂错材质
  - **头号嫌疑的特殊性**：`material_override` 是 **View Layer 级属性、不在材质里** ⇒
    在材质节点树里永远查不到，用户极难自查。非 None 时**该视图层下全部对象**的材质被替换，改任何材质都不生效
  - **实测案例（真实工程 `260910xAx01`，Blender 5.2 / Cycles）**：用户报"给了发光材质渲染还是黑的"，排查后发现**两层原因叠加** ——
    ① `material_override` 覆盖（用户已自行清除，这是本次根因）
    ② 清除后仍偏暗：该对象材质内有**两个 Principled BSDF**，用户把 `Emission Strength=100` 设在了
    **未接输出**的 `原理化 BSDF` 上，真正接在输出上的是 `原理化 BSDF.001`（只有 **10**）
    ⇒ 看到 100 以为够亮，实际生效 1/10
    ③ 另记：`view_transform = AgX` 仍在生效，AgX 下 10 的发光强度偏弱
  - **教训**：必须**一次打全七条路径**。只盯用户提到的那一条，会漏掉第二层原因
  - 诊断脚本实测：全场景 236 个材质扫描耗时 **0.05 s**；自动输出「发光值>0 但未接到输出」的孤儿节点清单
- **新增 Skill `skills/blender-render-blackout-diagnose/`**（含 `scripts/diagnose_blackout.py`）：
  按命中率排序的七条排查路径 + 铁律（先查全局开关再查局部节点）+ 报告模板（头号结论 / 机制解释 / 逐条判定表 / 建议动作 / 顺带隐患）
- **`blender-bridge-ops` 补一条硬约束：脚本文件绝不能带 BOM**
  - 桥端 `exec` 带 BOM 的源码 → `SyntaxError: invalid non-printable character U+FEFF`
  - **Windows PowerShell 5.1 的 `Set-Content -Encoding UTF8` / `Out-File -Encoding UTF8` 会写 BOM**，用它生成送桥脚本必炸（本次实测踩到）
  - 安全做法：Write 类工具直接落盘 / Python `open(...,encoding='utf-8',newline='\n')` /
    PowerShell `[System.IO.File]::WriteAllText($p,$s,(New-Object System.Text.UTF8Encoding($false)))`
- 涉及文档：`docs/渲染发黑与材质不发光排查.md`、`scripts/blackout-diagnose/README.md`、
  `skills/blender-render-blackout-diagnose/SKILL.md`、`skills/README.md`、`skills/blender-bridge-ops/SKILL.md`、
  `README.md`(索引 #35 + Agent Skills 表)、`docs/技巧速查.md`(索引 #35)、`AGENTS.md`、`DEVELOPMENT.md`

## v1.16.0 · 2026-09-13

- **新增主题 #34「空物体收敛清理」** —— `docs/空物体收敛清理.md` + 脚本包 `scripts/scene-cleanup/`
  - **核心结论：不能只删"无子级"的 EMPTY**。实测删掉 5006 个无子级空物体后，Outliner 里**又长出 2026 个** ——
    原本挂着这些叶子的中转容器（`Group-*` / `Arc*` / `Line*`）自己变成了叶子。
    正确做法是 **引用图 + 不动点**，一次算准最终可删集（避免反复扫描撞 120s 上限）
  - 判定规则：`EMPTY 需要保留 ⟺ 它支撑某个非 EMPTY 对象`，支撑 = a) 直接挂非 EMPTY 子级 /
    b) 子级里有需保留的 EMPTY / c) 被需保留对象引用（约束·修改器·驱动）/ d) 被外部数据块引用（节点 OBJECT socket ·
    场景相机 · 相机 DOF 焦点 · 粒子）
  - **三重安全闸**：① 只删 `type=='EMPTY'` ② 删后无非 EMPTY 对象失去父级 ③ 删后无悬空引用（由引用图保证）
  - 实测（真实工程 `260910xAx01`，22315 对象 / 5867 网格）：总对象 **22315 → 14848**，EMPTY **11775 → 4308**
    （两轮共删 **7467** = 5006 + 2461 级联），**EMPTY 无子级 5006 → 2026 → 0（收敛）**；
    **非 EMPTY 10540 / MESH 10527 / CAMERA 13 / 材质 236 逐个不变**；可见几何包围盒
    `min(-1348.71, -428.05, -958.45)` / `max(1348.71, 428.05, 439.90)` **逐位一致**；
    删除耗时 **71.88 s**，引用图扫描 **12~20 s**
  - 独立核验（另起一次请求）：名单残留 0 / 悬空约束 0 / 父级丢失 0 / 位置漂移 0 / 真缺失贴图 0 / 孤儿数据块 0
- **新增 `skills/` 目录（Agent Skill，给 AI 助手用的作业规范）**
  - `skills/blender-bridge-ops/` —— 9877 桥的**传输层**规范：客户端封装、**120s 上限规避**、
    Blender 5.x Slotted Action、引用判定必须排除 `Scene.objects`/`ID.original`、
    **判贴图缺失必须带 `not img.packed_file`**、`bpy.data.objects.remove()` 后旧引用立即失效
  - `skills/blender-scene-cleanup/` —— 工程**清理**方法论：不动点算法、三重安全闸、还原点流程、9 条核验清单
  - `skills/README.md` 说明与 `scripts/` 的分工（前者面向 AI、后者面向人，同一套脚本**两处需同步**）与安装方式
  - 同步修正三处脚本里陈旧的硬编码 `OUT_DIR`（原为某次会话的绝对路径）→ 改为显式占位符 + 顶部注释，
    避免跨会话复用时报错或把报告写到不存在/不该写的目录
- **连带清理项收录**：空集合（`objects=0` 且 `children=0`，用 `bpy.data.collections.remove(col, do_unlink=True)`，
  **不是"空对象"要单独问**）、孤儿材质/图像（顺序**先材质再图像**，每个先判磁盘副本）、空 action slot（存盘自动丢弃）
- 涉及文档：`docs/空物体收敛清理.md`、`scripts/scene-cleanup/README.md`、`skills/README.md`、
  `skills/blender-bridge-ops/SKILL.md`、`skills/blender-scene-cleanup/SKILL.md`、
  `README.md`（索引 #34 + Agent Skills 节）、`docs/技巧速查.md`（索引 #34）、`CHANGELOG.md`、`AGENTS.md`、`DEVELOPMENT.md`

## v1.15.2 · 2026-09-11

- **规则修正**:「按材质拆分后原对象保留哪个槽」的表述**有误**,由「最后一个材质槽」修正为
  **「面序中首次出现位置最晚的那一组」** —— 旧表述在 v1.15.0 文档里出现了 5 处,已全部修正
  - **源码依据**:`source/blender/editors/mesh/editmesh_tools.cc` · `mesh_separate_material`
    逐轮取 `BM_iter_at_index(bm_old, BM_FACES_OF_MESH, nullptr, 0)`(当前第一个面)的 `mat_nr`,
    若该材质已覆盖全部剩余面(`tot == bm_old->totface`)则 `mesh_separate_material_assign_mat_nr(...)`
    并 `break`,否则 `mesh_separate_tagged(...)` 把这组切走 ⇒ 最后剩下的那组即「首现最晚」
  - **判别实验**:7 个互相排斥的用例 × 4 种候选理论,只有「首现最晚」全用例成立,
    「最低索引」「最高索引」「最后一个面的材质」**全部被证伪**
  - **真实对象印证(累计 9/9)**:`对象9041` 各组首现面 = 槽0:1128 / 槽1:0 / 槽2:660 / 槽3:664
    ⇒ 槽0 首现最晚 ⇒ 原对象拿到**槽0**(灯光光.001) —— 与实测一致;`对象9287` 同规律
  - 推论:原对象的**名字与它拿到的材质常常对不上**,这是 Blender 既有行为、不是 bug
- **空材质槽行为**(实测 + 源码,已写入文档):
  - 循环只遍历**面的** `mat_nr`,从不遍历材质槽 ⇒ 空槽**不产生对象**、也不会被保留
  - `mesh_separate_material_assign_mat_nr` 把数据块 resize 到 **1 个槽** ⇒ 空槽**被自动清除**,无需手工清理
  - ⇒ **部件数 = 「有面的」材质槽数**,不是槽总数
  - ⇒ 只有 1 个槽有面时**完全不拆分**(仍是 1 个对象,不产生新对象)
  - ⚠️ **空槽里的材质会被「存盘」丢弃**(实测三级分辨:拆分前 users=1 → 拆分后未存盘仍存在但 users=0
    → 存盘后同进程仍 users=0 → **重新打开文件后已不存在**)。
    即：**拆分算子不删材质**，是 Blender 的**存盘孤儿清理**删的。
    若该材质只被本对象引用，「拆分 + Ctrl+S」= **永久丢失**。
  - ⚠️ 结论修正：不能说「users 合法下降、只要 ≥ 1 就不是孤儿」就完事 —— **归零就会在存盘时永久消失**。
  - 新增保命开关 `KEEP_EMPTY_SLOT_MATERIALS`(默认 False)：True 时给空槽材质打 `use_fake_user`。
    实测:material 存活、`fake=True`、验证 **24 项全绿**。
  - 真实场景印证:`对象9287` 的 2 个空槽材质另有使用者(users 3→2)，**不受影响**
- **验证器第 9 节改为分级判定**:`[有面槽]` 材质丢失 = ❌ 真问题;
  `[空槽]` 材质消失或归零 = ⚠️(预期内但确实变了数据,需知悉)，不计入 FAIL。
  新增 `WARN` 列表与汇总段的「⚠️ 需知悉 N 条」。
- **验证器口径修正**(`scripts/separate-by-material/verify_separation.py`):
  - 「部件数」判据由「材质槽总数」改为**「有面的材质槽数」**,不再对空槽对象误报
  - 「几何守恒」判据由「世界包围盒并集」改为**「逐顶点局部坐标 min/max」**。
    旧判据两侧不等价:基线用局部 AABB × `matrix_world`(**松上界**),拆分后用各部件局部 AABB 的并集
    (每部件跨度更小 ⇒ 上界更紧),并集几何上必然 ⊆ 原上界 ⇒ **必然误报漂移**。
    实测反例:`对象9287` 真实世界范围 Y `0.14~7.31`,旧口径给出 `-11.28~16.31`(差一个数量级),
    旧判据报 `1.557e-03` 的"漂移",而几何实际逐位未变
  - 新判据实测:`对象9287` `max|Δ| = 4.551e-07`、`对象9041` `max|Δ| = 4.141e-07`;
    该量级下 float32 可表示间隔约 `3.05e-05` ⇒ 差值**小于一个浮点台阶**,即逐位一致
  - 世界包围盒降级为**仅供参考、不参与判定**
- **脚本增强**(`separate_by_material.py`):基线新增 `local_extent` 字段(逐顶点局部坐标 min/max)
  与 `face_index_by_mat` 的诊断输出,供「首现最晚」规则核对与几何守恒判定使用
- **实测执行**:`对象9287`(1,160,332 面 / 4 槽含 2 空槽)→ 2 个对象;`对象9041`(3,505,328 面 / 4 槽)→ 4 个对象。
  两对象面数与顶点数**精确守恒**、世界位姿逐位重合、下游引用**均为零**
- 涉及文档:`docs/按材质拆分为多个网格体.md`、`scripts/separate-by-material/README.md`、
  `README.md` 索引 #33、`docs/技巧速查.md` 索引 #33、`AGENTS.md`

## v1.15.1 · 2026-09-11

- 文档清理:修复 2026-08-28「删除 #30 修改缩放」动作留下的残留(当时只清了索引表,正文与副本未清)
  - `docs/技巧速查.md`:删除「## 30. 修改缩放」**残留整节**(28 行,含指向已删文档的死链)
  - `docs/技巧速查.md`:删除**重复的 `## 30、粒子系统礼花喷射方案` 整节**(29 行,与保留节逐字相同)
  - `docs/技巧速查.md`:删除 **§13「时间轴标记管理」快捷键表格内误插入的索引行**(4 列塞进 2 列表格)
  - `docs/技巧速查.md`:修正 **37 处相对链接路径** —— 该文件位于 `docs/`,却写作 `[x](docs/x.md)` / `[x](scripts/x/)`,
    GitHub 解析成 `docs/docs/x.md` **全部 404**(实测 HTTP 状态码);改为同目录 `x.md` 与 `../scripts/x/`
  - `docs/技巧速查.md`:修正 §16~§17 之间**错位的结尾句**(现全文只在文末出现一次);补文件末尾缺失的换行
  - `CHANGELOG.md`:删除**重复的 v1.12.0 节**(11 行,逐字相同);并在保留节末补「后续变更」注记

## v1.15.0 · 2026-09-11

- 新增 `scripts/separate-by-material/` 可复用脚本包:**按材质拆分为多个网格体**
  - `separate_by_material.py`(执行: 前置自检 → 录拆分前基线 → `separate(type='MATERIAL')` → 结果盘点;状态**逐阶段写盘**,防桥 120s 超时丢结果;含 `RENAME_BY_MATERIAL` 按材质重命名新部件)
  - `verify_separation.py`(验证: 读磁盘基线逐项比对,输出 **11 组判定** —— 部件数 / 面·顶点守恒 / 每部件槽面映射 / 父级·MPI·世界矩阵 / 属性层 / **逐组锐边** / 包围盒并集 / 集合归属 / 材质 users / 动画·修改器·形态键 / 场景统计与孤儿)
  - `refs_scan.py`(收尾: 扫修改器·约束·粒子·顶点父级·驱动·材质节点·几何节点里对本组对象的引用)
  - `README.md`(原理 / 配置项 / 四步用法 / 11 组判据表 / 属性层判定逻辑 / 实测数据 / 自测台 / 11 条坑)
- 新增 `docs/按材质拆分为多个网格体.md`: 权威依据 + 机制细节 + 前置条件 + 操作方式 + 验证表 + 属性层判定 + 自测台 + 10 条坑
- **权威依据(先查再做)**: Blender 5.2 LTS 官方手册原文 —— By Material *"Splits the mesh into an object per **material slot** … **This is done for the whole mesh regardless of the selection.**"*(按**材质槽**、对**整网格**生效、**与选择无关**)
- **核心结论 1(算子不存在)**: **没有** `bpy.ops.mesh.separate_by_material`;`hasattr(bpy.ops.mesh, "separate_by_material")` 会**假阳性返回 `True`**,而 `get_rna_type()` 直接 `KeyError` ⇒ **判 `bpy.ops` 算子存在性必须用 `get_rna_type()` 包 `try`**
- **核心结论 2(保留哪个槽)**: 原对象保留**最后一个**材质槽的几何(名字不变)  ⚠️ **此项表述已被 v1.15.2 修正为「面序中首次出现最晚的那一组」**,其余槽各生成 `原名.001/.002/.003`,**每个新网格只留自己那一个材质槽**;所有部件沿用原对象的局部变换与 `matrix_parent_inverse` ⇒ 世界位姿**逐位重合**
- **核心结论 3(属性层消失的判定)**: 拆分后某部件的 `sharp_edge` 属性层可能**消失** —— Blender 丢弃结果网格上**全为默认值**的属性层。判定必须靠基线记录的 **`sharp_by_mat`(每个材质组内的锐边数)**:该组为 `0` ⇒ 无信息损失;`> 0` ⇒ 真数据丢失
- **决定性证据(真实项目)**: 只读打开改前的存盘文件实测 —— 材质 3 组锐边数 = **0**(所以拿到该槽的原对象属性层消失),另外三组 = **68,142 / 2,461,210 / 80,886**,与拆分后对应部件**逐组精确吻合** ⇒ 无信息损失
- **实测数据(真实场景 3,505,328 面 / 2,020,266 顶点 / 4 材质槽)**: 耗时 **10.5 s**;面数**精确守恒**;顶点数**精确守恒**(跨材质边界共享边 = 0,材质组拓扑独立);4 个部件父级·MPI·世界矩阵 `max|Δ|` = **0.000e+00**;包围盒并集 Δ = **1.788e-07**(float32 精度);UV 与自定义拆分法线全保留;下游引用扫描(20788 对象 / 213 材质 / 驱动 / 节点)**零引用**
- **关键坑 1**: 桥 `exec` 在**主线程**跑、客户端 **120s 超时**后结果即丢,且主线程忙时新请求**只排队不执行** ⇒ 长耗时算子**无法轮询**,必须**逐阶段写盘**并从磁盘回捞
- **关键坑 2**: 桥的 `_env()` 命名空间里**没有 `__name__`** ⇒ 脚本结尾写 `if __name__ == "__main__"` 会直接 `NameError`,必须**无条件**调用 `main()`
- **关键坑 3**: `Material.use_nodes` 在 Blender 5.2 起抛 `DeprecationWarning`(预计 6.0 移除) ⇒ 判"材质有无节点"用 `mat.node_tree is not None`
- **关键坑 4**: **Empty 不支持修改器** —— 引用测试的修改器必须挂在网格对象上(`ref.modifiers.new()` 在 Empty 上返回 `None`)
- **关键坑 5**: 顶点数**可能增加**(材质边界处共享顶点被各组复制,合成自测 52 → 64)⇒ 这是**正常现象**而非损坏,验证器按提示(ℹ️)报出而非失败(❌);`material_index` 与 `.select_*` 掩码的消失也属正常
- **自测台(跨进程三段式,可复现)**: 造同构合成场景(4 材质槽 + 带动画父级 151 帧挂父级 + UV + 自定义拆分法线 + Array 修改器引用) ⇒ `islands` 变体 **36 项全绿**(面/顶点精确守恒,2 个零锐边组属性层被丢弃 → 判定无信息损失);`shared` 变体 **35 项全绿**(走"顶点 +12 属正常"提示分支);`RENAME_BY_MATERIAL=True` 分支与 `refs_scan` 报出真实引用亦验证通过

## v1.14.0 · 2026-09-11

- 新增 `scripts/axis-space-motion/` 可复用脚本包:**位移坐标系 —— 沿自身轴 / 沿世界轴运动**
  - `axis_report.py`(诊断: 打印父空间基底与对象自身轴在世界中的方向、三项夹角、坐标基底是否随时间变,并自动给出方案建议)
  - `key_axis_motion.py`(写入: `SPACE=SELF/WORLD/PARENT` + `ENGINE=auto/direct/bake`,自动换算并写 `location` 关键帧;`PRESERVE` 可叠加在原有位移之上)
  - `verify_axis_motion.py`(验证: 静音 `location` 曲线先采基准轨迹 → 逐帧比"实际 vs 理想",输出 **位置 / 沿轴投影 / 垂轴分量** 三项偏差)
  - `README.md`(原理 / 配置项 / 换算公式表 / 三步用法 / 判读阈值 / 四条路对照 / 11 条坑)
- 新增 `docs/轴向位移-自身轴与世界轴.md`: 原理推导 + 统一心法 + 两条对称做法 + 视口手动操作 + 诊断读法 + 验收指标 + 实测数据总表 + 11 条坑
- **核心结论**: `matrix_basis = T(location) @ R @ S` 中**平移在最左端** ⇒ `location` 的坐标系 = `父级世界矩阵 @ matrix_parent_inverse`("父空间基底"),**既不是世界空间、也不是对象自身空间**,且**对象自身的 `rotation` / `delta_rotation` 都改变不了它**
- **统一心法**: 想让位移沿哪个坐标系,就把"承载位移那一层"的父空间做成那个坐标系 —— 沿**自身轴**(朝向放上层、位移层自身旋转恒 0)、沿**世界轴**(中间插一层"抵消旋转"的世界对齐层);两种情况都**只需 K `location`,不做任何换算**
- **实测证伪的两条高频误解**: `delta_location` **不是**"对象局部位移"(与 `location` 同一坐标系,实测偏 **90.0000°**);`delta_rotation` 也**不会**把 `location` 带转(实测偏 **90.0000°**)
- **沿世界轴实测数据**: 静态父级换算 **0.000000** ✅ / 逐帧 bake(动态父级) **0.000000** ✅ / **世界空间空对象 + `Copy Location`(WORLD + `use_offset`)任意父级旋转(含复合) **0.000000** ✅(最通用) / 抵消层 + `Copy Rotation`(invert, `owner_space='LOCAL'`) 单轴 **0.000000** ✅、复合旋转偏 **3.83 单位** ❌ / 静态换算用在动态父级上偏 **7.07 单位** ❌
- **沿自身轴实测数据**: 两层结构(上层承载旋转)静态 **0.0000°**、上层旋转是动画**逐帧 0.000000°** ✅;单对象换算 `loc = R_own @ AXIS` **0.0000°** ✅(朝向须静态);driver 单通道 **0.0000°** ✅
- **关键坑 1**: `evaluated_get(dg).matrix_world` 返回**活引用**(不 `.copy()` 直接存进列表,循环结束后所有样本都变成**最后一帧**的值),实测导致诊断脚本输出"自身Z vs 世界Z = 0.0000°"的**假结论**;`to_3x3()` / `to_translation()` 天然安全
- **关键坑 2**: 验收**不要用"逐帧步进方向 vs 目标轴"** —— 目标轴随时间旋转时位移向量本身就在转、基准轨迹也在动,该指标必然误报(实测真实偏差 8.1e-06 单位却报出 **112° / 163.86°**),正确判据是"**垂轴分量 ≈ 0**"
- **关键坑 3**: `Copy Rotation` 的 `owner_space` 只有 `WORLD`/`CUSTOM`/`LOCAL`(无 `LOCAL_WITH_PARENT`),用来"抵消父级旋转"必须 `owner_space='LOCAL'` + `target_space='WORLD'`(实测 `WORLD`/`CUSTOM` 均无效,仍偏 90°);且其逐分量 invert **≠ 矩阵求逆**,复合旋转不成立
- **关键坑 4**: driver 表达式里**不能直接写自定义属性名**(`restricted access` / `NameError`),必须走驱动变量 `type='SINGLE_PROP'`;测 driver 值要把属性 K 成动画再逐帧取(直接改属性 + `view_layer.update()` 在后台模式不重算,会得到 Δ=0 的假象)
- **真实项目闭环**(合成同构场景 = 旋转父级 + 带动画转移空对象 + 位移层 + 相机,151→480 共 330 帧): `SPACE="SELF"` 自动选 direct → 位置 **8.09e-06** / 沿轴 **5.46e-06** / 垂轴 **6.20e-06(0.0005%)**;`SPACE="WORLD"` 自动选 bake → **4.29e-06 / 5.23e-06 / 3.82e-06(0.0001%)**

## v1.13.0 · 2026-09-11

- 新增 `scripts/anim-transfer-to-empty/` 可复用脚本包:**动画转移到父级空对象(动态转移)**
  - `transfer_anim.py`(执行转移: 建"动态"空对象复刻目标世界运动 → 复制 action(独立副本+绑 slot)→ 目标改挂并摘掉自身动画 → 可选插"基点"空对象把本体本地变换归零;含前置自检/对齐断言/后置粗检/幂等保护)
  - `verify_transfer.py`(验证器: `MODE='record'` 转移前录逐帧世界矩阵基线 → `MODE='check'` 转移后逐帧对比,输出位置/旋转块/良态角度三项最大偏差与判定)
  - `README.md`(原理 / 最终层级 / 三步用法 / 判读阈值 / 10 条坑)
- 新增 `docs/动画转移到父级空对象.md`:完整原理(世界变换恒等式 + 四步构造 + 恒等证明)+ 最终层级 + 做法 + 验证实测表 + 8 条逐条实测坑
- **核心结论 1(通用解)**:目标改挂新父级时,`matrix_parent_inverse` 的通用解是 **`B(F)⁻¹`(局部 basis 的逆)**,不是 `M(F)⁻¹`(世界矩阵的逆) —— 只有参考帧处"局部==世界"时两者才相等。自测构造 `M(F)` 与 `B(F)` 相差 6.35 单位的场景,用 `B(F)⁻¹` 得 0 偏差,用 `M(F)⁻¹` 会把对象挪偏 6.35 单位
- **核心结论 2(精度)**:在"D 与目标之间插一个无动画基点空对象、三段全用单位 MPI+单位 basis"时,`M'(t) = D.world(t) @ I @ I` **乘单位矩阵是精确的**(无大数相消),实测对原始基线偏差 **0.000e+00**(比 `B(F)⁻¹@B(F)` 路径的 1.19e-07 / 7.63e-06 更准)
- **关键坑**:`obj.parent` 赋值会**静默重置 `matrix_parent_inverse` 为单位矩阵** → 必须"先设 parent、后设 MPI"(隔离实验逐项验证: parent_type / animation_data_clear / 写变换 / frame_set 均不重置,只有 parent 赋值重置)
- **验收坑**:算角度偏差**不要用 `2*acos(dot)`**(`dot≈1` 时病态放大,实测把 3.8e-06 的矩阵差虚报成 0.0396°,放大 100+ 倍);改用旋转矩阵元素最大差或良态式 `2*asin(sqrt(x²+y²+z²))`(注意 `mathutils.Quaternion` 无 `.vector` 属性)
- 自测: 用 headless Blender 造"带 Z 旋转动画父级 + 自带 Z 抬升相机"的同构场景,跨进程跑 record→transfer→check 两个变体(`ZERO_TARGET=True/False`)全部通过
- 文档: `README.md` 索引新增 #31 / `docs/技巧速查.md` 索引新增 #28~#31(补齐此前 28~30 缺行) / `AGENTS.md` 补关键坑 + 基线行 / `DEVELOPMENT.md` 新增 2 篇问题记录
- 实战来源: `260910xBx01.blend`(11,891 对象)相机 x02 —— 由父级空对象 `旋转对象`(Z 匀速 0°→-423°)带动公转,相机自带 `location[2]` 抬升动画;转移后层级 `旋转对象 → 转移对象 → 相机基点 → 摄像机x02`(相机本地全零)

## v1.12.0 · 2026-08-27
- 新增 `docs/应用缩放Scale归1.md`:**把 Scale 归 1 且保持世界大小不变**(= Apply Scale),完整原理 + 注意事项
  - 场景:导入/迁移模型带非单位、倍数巨大的缩放,想 scale 全归1 又不动视觉;
  - 原理:顶点×scale + scale=1 → 世界位 `T·R·(S·v)` 逐字节不变(dims 相对误差实测≤3e-7);桥内数据层与算子 `transform_apply(scale=True)` 等价;
  - 核心坑(翻车现场):**几何预放大叠加**——顶点早被放大而 scale 仍在,世界=几何×scale 双重放大(实战 C-DT 02.003,569 vs 应 15);务必先核实几何自然尺寸 + 重梳理清单;
  - 附坑:多用户网格先 copy 独立 / 负缩放法向由 depsgraph 自动重算(5.2 无 mesh.calc_normals) / 大倍数 scale 副作用 / 改验分两次 / 备份可逆;
- `README.md` 索引新增 #30;`docs/技巧速查.md` 新增 §30
- 实战来源:260827x07_主装置迁移.blend(697 静态网格 scale 归1、含 48 负缩放;特例 C-DT 02.003 按几何自然尺寸还原)
- ⚠️ **后续变更**:`docs/应用缩放Scale归1.md` 已于 2026-08-28 按用户要求删除(commit `9ed89ed`),该主题不再维护;本节为历史记录,保留不改

## v1.11.0 · 2026-08-23

- 新增 `scripts/frame-window-time-switch/` 可复用脚本包:**帧窗口驱动时间开关**
  - 核心:命名空间函数 `grad_window(fr)`(帧 `[lo,hi]` 内=1,外=0)+ SCRIPTED 驱动(`fr` 读 `scene.frame_current`)挂到 Value 节点输出;
  - `build_frame_window_switch.py` 一键:注册+持久化 Register 文本块(`grad_window_driver.py`)→ 挂驱动并强制重编译 → 用 depsgraph 评估值逐帧验证;
  - 记录并复述关键坑(Blender 5.2 实测):**Value 节点用 `keyframe_insert` 打动画在 Slotted Action 下不生效(原始与评估值恒为默认)**;验证必须读 `deps.id_eval_get(mat)` 评估值而非原始 socket;5.2 Action 为 Slotted,`action.fcurves`/`slots[].fcurves` 均不存在,读关键帧走 `layers[].strips[].channelbag.fcurves`
- 新增 `docs/帧窗口驱动时间开关.md`;`README.md` 索引新增 #29
- 实战来源:发光材质_005 / 发光灯 两材质渐变开关按 517–657 帧窗口开启、区间外纯色;用户换机后因开错文件疑为失效,实为方案有效

## v1.10.0 · 2026-08-23

- 新增 `scripts/ring-control-panel/` 可复用脚本包:**材质参数统一控制器 + 实时面板**
  - `ring_control_panel.py`(核心:3D 视口贴近栏实时面板,draw 里检测自定义属性变化 → `update_tag()` + `view_layer.update()`,拖滑块即时重算材质驱动;作为 Register 文本块可随 .blend 持久化)
  - `build_ring_controls.py`(一键:建控制空物体 + 重建材质为 XZ 径向同心圆扩展灯管线 + 注入 Register 面板文本块)
  - `README.md`(方案要点 / 复用配置 / 踩坑)
- 新增 `docs/材质参数统一控制器与实时面板.md`;**多材质共用同一圆心 + 一套参数**;`README.md` 索引新增 #28
- 记录并复述关键坑:**Blender 5.2 自定义属性改动不自动触发材质驱动重算**,须 `ctl.update_tag()` + `view_layer.update()`(ABLE §24 已有,本文档给"面板实时刷新"落地)
- 实战来源:主装置_发光材质 / 发光材质_005 / 发光灯 三块面板共用 主装置_圆环控制 控制器(圆心=控制空物体,speed=0.05,density=1,gain=25,solid=20,gradient_on 开关),Register 面板随工程自恢复

## v1.9.0 · 2026-08-23

- 新增 `scripts/speed-light/` 可复用脚本包:**速度驱动灯光亮度**通用方案
  - `speed_light_driver.py`(核心:注册 `speed_energy(target, frame)`,按目标 Z 高度分档配系数/上限,前向差分求速,clamp 安全范围)
  - `build_speed_light_drivers.py`(给灯的 energy 挂 SCRIPTED 驱动,幂等)
  - `README.md`(方案要点 / 参数表 / 踩坑)
- 新增 `docs/速度驱动灯光亮度.md`;`README.md` / `docs/技巧速查.md` 索引新增 #27
- 实战来源:主装置 01~05 灯光亮度随柱子 Z 轴运动速度变化(上移 6+3400v / 下移 6−2·3400|v|,短柱 0~20、长柱 0~100,灯位置固定于轴心)

## v1.8.3 · 2026-08-22

- 用户重启实测通过:天空太阳控制重启后自愈,不再断开
- **修正不准确说法**:命名空间函数**源码随 .blend 保存**(文本块 Register),不落盘的只是运行期 `driver_namespace` 映射—靠 Register 文本块载入重注册;依据 Blender 手册 Scripting & Security(Registered Text-Blocks will load on start,受 Auto Run / Trusted Source 控制)
- `docs/天空太阳高度驱动.md` 新增「核心逻辑与要点(官方机制, 重启自愈)」:三前置 = 文本块当前双函数版 + Register + Auto Run
- `scripts/driver-sky/README.md` 顶部加核心逻辑说明
- `AGENTS.md` 修正 bob/spin 命名空间函数持久化两处措辞(源码落盘,映射不落盘)

## v1.8.2 · 2026-08-22

- 实战修复「重启后天空控制断开」:**根因 = .blend 内嵌的 `sky_driver.py` 文本块是旧版**,只注册 `sky_sun_angle`、缺 `sky_sun_elev` → 高度驱动红(Auto Run 正常)。用仓库权威版覆盖文本块 + 保持 Register + 强刷驱动 + Ctrl+S 后,高度/角度均 1:1 恢复
- `scripts/driver-sky/README.md` 排查新增「重启后断开优先看这个」:先核对文本块是否含两个函数,再查命名空间/驱动有效性/Auto Run
- `AGENTS.md` 补坑:重启断开多为内嵌文本块旧版;Scripted 驱动 5.2 无 `d.update()`,强刷用 `d.expression=d.expression`(try/except 兜底)

## v1.8.1 · 2026-08-22

- `docs/天空太阳高度驱动.md` 重构优先序:**命名空间函数版提到最前(默认方案)**,原「数字驱动版」降级为「旧做法,有已知坑」附后;标题改为「天空太阳控制驱动」
- 新增 `scripts/driver-sky/README.md`:**权威脚本目录说明**——`sky_driver.py` 为唯一推荐脚本,旧 `build_sky_sun_driver.py` 标记禁用(会写回常量覆盖 sun 驱动)
- `AGENTS.md` 精简 SINGLE_PROP / sun 驱动那条坑说明,附推荐脚本路径

## v1.8.0 · 2026-08-22

- 新增 `scripts/driver-sky/sky_driver.py`:命名空间函数版天空驱动(`sky_sun_angle` / `sky_sun_elev`),实时读属性,脚本/UI 改值均立即生效
- `docs/天空太阳高度驱动.md` 补充「命名空间函数版(推荐)」小节:含太阳旋转 `sun_rotation`;并记录坑——旧 `build_sky_sun_driver.py` 会把 `sun_elevation` 驱动写回常量导致高度无反应
- `AGENTS.md` 补坑:SINGLE_PROP 读自定义属性脚本内改值不重算、旧重构脚本覆盖驱动 → 用命名空间函数实时读
- `README.md` / `docs/技巧速查.md` #23 更新为「天空太阳控制驱动」
- 来源:9877 工程 260821x05,天空控制 自定义属性(太阳角度/太阳高度)驱动天空纹理

## v1.7.0 · 2026-08-21

- 新增 `docs/输出路径与序列帧输出规范.md`:**输出序列帧路径规范**——相对路径 `//`(工程目录)+ `output/<批次>/` + `#` 帧号占位命名;正确设置顺序 `media_type='IMAGE' → file_format='PNG' → filepath`;`use_file_extension` 自动扩展名;`bpy.path.abspath()` 复核落盘路径
- `README.md` 索引新增 #26 入口
- `AGENTS.md` 补关键坑:media_type 先于 file_format 决定枚举域(镜像 5.2 视口录制 VIDEO 顺序)+ 相对路径规范
- 来源:9877 工程 260821x05 修复主装置,输出改为相对路径 `//output/260821x01/260821x01####.png` 并实测 PNG 序列可行

## v1.6.1 · 2026-08-21

- 新增 `scripts/driver-lights/light_driver.py`、`scripts/glow-scroll-material/scroll_driver.py`:**命名空间函数文本块模板**(勾 Register + Auto Run → 重开文件自动恢复)
- `scripts/driver-restore/restore_drivers.py` EXPR_MAP 补充 light_off / scroll_speed(一键恢复含新函数)
- **实测确认 Register 自动恢复 100% 生效**:light_off/scroll_speed 文本块勾 Register + Auto Run → 重启后函数自动进命名空间、全部驱动 is_valid=True(843 驱动 INVALID 0),无需手动操作
- `AGENTS.md` 更新"恢复后必须强制重编译"适用范围(仅运行中 exec 注册场景;正常重启 Register 自动恢复连带驱动)
- 来源:9877 工程重启验证(打开自动就对)

## v1.6.0 · 2026-08-21

- 新增 `scripts/driver-lights/` 可复用脚本包:**运动网格灯光方案**
  - `build_light_system.py`(给驱动浮动网格轴心加向上/向下双 AREA 灯,分组+跟随驱动+偏移属性+旋转绑定,一键全套,幂等)
  - `README.md`(参数表 / 手动微调 / 5 条实战坑)
- 新增 `scripts/glow-scroll-material/` 可复用脚本包:**渐变发光滚动材质**
  - `build_glow_scroll_material.py`(竖图渐变自发光 + Mapping 放大2倍只显示一半 + Location Y 驱动竖直滚动 + 速度滑块)
  - `README.md`
- 新增 `docs/运动网格灯光方案.md` / `docs/渐变发光滚动材质.md`
- `README.md` / `docs/技巧速查.md` 索引新增 #24 / #25
- `AGENTS.md` 补 3 条关键坑(新建空物体需先 update 再读 matrix_world / 5.2 DriverTarget 无 array_index / 驱动单向主从)
- `DEVELOPMENT.md` 新增 3 篇问题记录(翻倍偏移 / array_index / 循环依赖)
- 来源:9877 工程 5 个主装置 168 灯灯光方案 + 渐变发光滚动材质实战

## v1.5.0 · 2026-08-21

- 新增 `scripts/driver-sky/` 可复用脚本包:**天空太阳高度数字驱动**
  - `build_sky_sun_driver.py`(建「天空控制」空物体 + `太阳高度` 滑块(度),给 `sun_elevation` 挂 SCRIPTED 驱动 度→弧度;幂等可重跑)
  - `README.md`(原理 / 用法 / 坑)
- 新增 `docs/天空太阳高度驱动.md`:5.2 天空纹理参数是节点属性(非 socket) / 节点驱动在 node_tree.animation_data / 打关键帧做太阳升降
- `README.md` 索引新增 #23 / `docs/技巧速查.md` 补 #23
- `AGENTS.md` 补 2 条关键坑(5.2 TEX_SKY 属性驱动 / 节点驱动存 node_tree.animation_data)
- 来源:9877 工程天空纹理(天空控制.太阳高度 滑块, 悬停按 I 打关键帧)

## v1.4.2 · 2026-08-21

- **修正 send.py 不支持端口参数**:`scripts/blender-remote-control/send.py` 新增 `-p/--port`(多 Blender 并存连接非默认端口;AGENTS.md 早已声称支持但代码缺失,现已补上);超时从 120s 提到 300s(长任务如 playblast 更稳)
- **去掉经桥执行脚本的 `__main__` 守卫**:`build_bob_drivers.py` / `build_spin_drivers.py` / `restore_drivers.py` 改为直接调用 `main()`——桥接 exec 时 `__name__='builtins'`,守卫会让脚本静默不执行(只回 OK 无输出)
- **修正 AGENTS.md 过时结论**:5.2 文本块 Register 持久化**实测有效**——`use_module=True`(UI 的 Register 复选框)+ Auto Run Python Scripts → 重开文件自动恢复命名空间函数,无需手动 Run Script(`use_register` 是旧 API 名已移除,但 use_module 仍在)
- **docs/视口预览录制录屏式.md 补坑**:场景相机按帧切换 = 时间轴标记绑定(Bind Camera to Markers),**不要写死 `s.camera`** 否则覆盖标记绑定丢机位切换
- 来源:9877 工程重开验证(Register 自动恢复成功)+ 录屏 v2/v3 实战(写死相机丢机位切换的坑)

## v1.4.1 · 2026-08-21

- `scripts/driver-restore/restore_drivers.py` 增强:恢复命名空间函数后,**强制重新赋值驱动表达式**触发驱动重新编译
  - 修复:只 exec 文本块注册函数不够——depsgraph 缓存旧失败状态(`driver.is_valid=False`,求值失败返回 0 → 物体掉到 Z=0 错位);必须重赋值同值表达式强制重算
  - 机制:`EXPR_MAP` 声明 文本块名→函数名,扫描全场景 SCRIPTED 驱动,表达式含该函数的即重赋值
- `AGENTS.md` 补关键坑:恢复函数后必须强制驱动重编译(否则 is_valid 仍 False、物体停 0 位)
- 来源:9877 工程重开后 bob/spin 函数丢失导致主装置01-05 全部错位(Z 掉 0),按此流程修复

## v1.4.0 · 2026-08-21

- 新增 `scripts/make-independent/` 可复用脚本包:**集合内对象数据独立化**
  - `make_independent.py`(遍历指定集合 MESH 对象,`users>1` 的共享网格数据块 `copy()` 成独立副本;材质独立可选;幂等可重跑;无 `__main__` 守卫——桥接 exec `__name__` 为 builtins)
  - `README.md`(场景 / 用法 / 效果示例 / 幂等安全 / 注意)
- 新增 `docs/集合内对象数据独立化.md`:原理(对象与数据块多对一)+ 排查方法 + 做法 + 4 条实战坑
- `README.md` 索引新增 #22(数据独立化)入口
- `docs/技巧速查.md` 索引补 #22
- `AGENTS.md` 补关键坑(桥接 exec `__name__`=builtins / 判断共享用 `users>1` 勿看数据块名)
- `DEVELOPMENT.md` 新增 2 篇问题记录:`__main__` 守卫静默不执行 / linked duplicate 共享数据块联动
- 来源:新工程「补充」集合 43 网格只共享 21 数据块(组7912/7913_GeomAdjust 共引 Mesh.537),独立化后 43/43 各自独立,可安全复制出去

## v1.3.0 · 2026-08-21

- 新增 `scripts/driver-spin/` 可复用脚本包:**驱动式 Z 轴匀速旋转系统**
  - `spin_driver.py`(核心函数 `spin_speed()`,实时读 `旋转速度` 滑块,注册进驱动命名空间;勾 Register 持久化)
  - `build_spin_drivers.py`(通用构建器:建 `旋转控制` 面板 + 给指定目标挂 Z 旋转驱动,可独立设正/反向;幂等可重复运行)
  - `README.md`(原理 / 文件清单 / 使用步骤 / 踩坑 / 调参)
- 新增 `scripts/playblast/` 可复用脚本包:**视口预览录制(录屏式,非全渲染)**
  - `playblast_export.py`(`render.opengl` 从场景相机抓视口画面导出 mp4;顶部可调输出路径/分辨率;含 5.2 输出配置顺序坑)
  - `README.md`
- 新增 `scripts/driver-restore/restore_drivers.py`:重开 .blend 后一键重跑 `bob_driver.py` / `spin_driver.py` 文本块,恢复驱动依赖的命名空间函数(解决 5.2 无 use_register 导致驱动变红)
- 新增 `docs/驱动式Z轴匀速旋转系统.md`(原理 / 与 bob 对比 / 做法 / 6 条实战坑 / 验证)
- 新增 `docs/视口预览录制录屏式.md`(原理 / 用法 / 5 条实战坑 / 调试)
- `README.md` 索引新增 #20(旋转)/ #21(录屏)入口
- `docs/技巧速查.md` 索引补 #20 / #21
- `AGENTS.md` 补关键坑(Z 轴旋转用 rotation_euler[2] / 5.2 视口录制 media_type 顺序 / spin 命名空间函数持久化)
- `DEVELOPMENT.md` 新增 2 篇问题记录:视口录制输出配置顺序 / Z 轴旋转用 rotation_euler + 基准角复位
- 来源:活力之丘点位模型 主装置实战(空物体.006 正向 / 007 反向匀速转 + 相机视角预览导出)

## v1.2.0 · 2026-08-21

- 新增 `scripts/driver-bob/` 可复用脚本包:一组独立网格物体的**丝滑阻尼感上下浮动驱动系统**
  - `bob_driver.py`(核心噪波函数 `bob()`,两层加权混合 Perlin 噪波:全局大波 + 局部错动;注册进驱动命名空间,可勾 Register 持久化)
  - `build_bob_drivers.py`(通用构建器:给指定集合挂 Z 驱动、建独立控制面板空物体、按名排除不动区;幂等可重复运行)
  - `README.md`(原理 / 文件清单 / 使用步骤 / 踩坑 / 调参)
- 新增 `docs/驱动式上下浮动噪声系统.md`:完整原理(连续信号映射 → 丝滑/阻尼感来源)+ 两层结构 + 做法代码 + 7 条实战坑
- `README.md` 索引新增 #19 入口
- `docs/技巧速查.md` 索引补 #18(3ds Max 独立文档)+ #19(驱动浮动独立文档)
- `AGENTS.md` 更新文档基线 + 补充关键坑(5.2 驱动无 SELF 类型 → use_self / 自定义属性显示名即键 / 改名后旧驱动陈旧需 driver.update / 命名空间函数不随文件保存 / 基准位置幂等)
- `DEVELOPMENT.md` 新增 5 篇问题记录:驱动变量类型无 SELF / 自定义属性显示名即键 / 改名后旧驱动陈旧 / bob 不随文件保存 / 基准位置误覆盖
- 来源:活力之丘点位模型 主装置01~05 实战(84 个运动网格,各集合独立控制面板,控件默认参数已调好)

## v1.1.0 · 2026-08-21

- 新增 `docs/3dsmax导入场景清理与轴心修复.md`:3ds Max 导入场景完整清理工作流——缺失数据诊断(五查,fbm 贴图路径失效)/ 空物体清理(孤立 + MaxHandle 元数据残留)/ **轴心安全修复(先 transform_apply 烘焙旋转缩放再 origin_set,multi-user 网格先 copy,负缩放翻车教训)** / 动画清理(静态化防跳位,保留相机对象 + camera data 动画) / 5.2 API 坑速记(apply_transform→ops、fcurve_find 不存在、user_map 返回 set、undo 栈限制)
- `README.md` 索引新增 #18 入口
- `AGENTS.md` 更新文档基线 + 补充关键坑(轴心安全流程 / 5.2 API 变化 / 清动画先静态化)
- 来源:260820x03.blend 实战(11,961 对象 3ds Max 导入,缺贴图警告 + 4165 空物体 + 轴心偏移 + 4083 动画对象)

## v1.0.0 · 2026-08-20

- 新增 `docs/材质与驱动规范.md`:灯光材质系统**完整操作手册**——材质命名规范(灯组前缀独立块) / 圆柱投影公式 / 按位置适配(TexCoord+VNorm 必改) / 驱动速度控制(对象级+材质节点级) / 三大坑(Object坐标不旋转, inputs[N], FLOORED_MODULO) / 三分法灰度 / 打组挂载规范 / 快速复用清单
- `README.md` 索引新增"材质与驱动规范"入口
- 来源:灯1/灯4/灯6 多灯组实战(滚筒材质复制 + 按位置修正 + 命名隔离)

## v0.9.0 · 2026-08-19

- `docs/技巧速查.md` 新增 §17:圆柱贴图与理发店滚筒——圆柱投影(u=atan2角度, v=高度归一化) + 螺旋条纹 f=u×K+v×N + FLOORED_MODULO 无缝循环 + 条纹角度公式 + **Object 坐标只跟随平移不跟随旋转** + **材质 driver 路径必须 inputs[N] 数字索引**
- `DEVELOPMENT.md` 新增 2 篇:Object 坐标不跟随旋转+材质 driver 路径 / 条纹底部裁剪(FLOORED_MODULO)
- `AGENTS.md` 更新基线 + 关键坑
- 来源:灯1 理发店滚筒实战(圆柱条纹 + 驱动速度控制 rot_speed/up_speed)

## v0.8.1 · 2026-08-19

- `docs/技巧速查.md` §16 更新为**最小色标结构**:每平台只留 2 端点色标,边界 0/1 删除靠外推,色标数从 13 → 6(三色);通用公式补"最少色标数 = 颜色数 × 2"
- 来源:灯1 三色循环渐变实战精简(6 色标与 13 色标效果等价)

## v0.8.0 · 2026-08-19

- `docs/技巧速查.md` 新增 §16:循环渐变色(ColorRamp 三色自然循环)——4 层逻辑(N 等分对称/同色连标平台/删过渡中点/首尾同色无缝)+ 共享材质 Mapping 偏移驱动 + 换色通用公式(等分数=颜色数×4)
- `DEVELOPMENT.md` 新增 1 篇问题记录:ColorRamp 渐变"抖"(EASE 插值 + 过渡区多余色标)
- `AGENTS.md` 更新文档基线 + 补充关键坑
- 来源:灯1_灯光变化 150 灯体三色渐变波实战(#7F4800/#E5BF91/#E5A145 循环)

## v0.7.0 · 2026-08-19

- `docs/技巧速查.md` 新增 §15:挂载(parent)/轴心(origin)操作的位置保持——**Blender 5.x parent 后 matrix_parent_inverse 不自动设置导致世界位置翻倍**,正确流程(空对象先定位→挂载→手动 mpi),轴心/原点操作注意事项
- `DEVELOPMENT.md` 新增 1 篇问题记录:parent 赋值后子对象世界位置翻倍(743+743=1486,mpi 不自动设置)
- `AGENTS.md` 更新文档基线 + 补充关键坑
- 来源:灯1 集合 385 对象按材质打组(可搭鸭134530→灯1_可搭鸭 150,其他→灯1_其他 235)+ 渐变空对象 107,手动 mpi 后全部位置保持

## v0.6.0 · 2026-08-18

- `docs/技巧速查.md` 新增 §14:大场景去重优化(重复网格合并为实例)——检测(类型分布/同基础名/完整指纹/抽检) + 合并(对象重定向→删冗余块) + 实测效果(9,079→3,803 数据块,-58%)
- `DEVELOPMENT.md` 新增 2 篇问题记录:send.py 大任务超时误报(桥实际执行完,重跑验证) / 重复网格合并指纹陷阱(材质+UV 必须纳入指纹,抽检真几何)
- `AGENTS.md` 更新文档基线 + 补充关键坑
- 来源:里巷点位模型 260818.blend(63,233 对象)优化实战,合并后对象数不变、材质 100% 保留

## v0.5.0 · 2026-08-18

- `docs/技巧速查.md` 新增 §10~§13:
  - §10 时间轴整体前移(关键帧+标记+frame_end 批量平移,负帧保护,先备份)
  - §11 关键帧小数帧(.5帧)检测与修复(round() 掩盖问题 + 吸附到整数帧,段间距校验)
  - §12 首尾帧交换与反转关键帧真相(**Blender 没有"反转关键帧"菜单,用关键帧→镜像→沿时间轴关于当前帧**;附官方文档链接)
  - §13 时间轴标记管理(增删移 + 中文菜单 + 远程操作)
- `DEVELOPMENT.md` 新增 4 篇问题记录:round() 掩盖小数帧 / 同 exec 缓存旧值 / Reverse Keyframes 不存在 / 平移负帧
- `AGENTS.md` 更新文档基线 + 补充关键坑(反转=镜像、小数帧检测、slotted action 读取路径)
- 来源:活力之丘点位模型 260815x02.blend 时间轴前移 + 小数帧修复 + 标记清理实战(10 相机、13,542 对象)

## v0.4.0 · 2026-08-17

- `docs/技巧速查.md` §9 新增:渲染白膜(材质覆盖,非破坏性)——View Layer `material_override` + 白膜材质 + 天空光补连;索引表补全 §7/§8/§9
- `DEVELOPMENT.md` 新增 1 篇问题记录:0 灯光场景白膜渲染靠天空光 / Sky Texture 未连接 Background
- 来源:CAD 大场景(50186 对象)白膜渲染实战(材质覆盖 + Cycles GPU + 天空纹理;Base Color 0.6 防过亮)

## v0.1.0 · 2026-08-16

- 初始版本:按 knowledge-base 单项目规范创建四件套(README/AGENTS/DEVELOPMENT/CHANGELOG)
- `docs/技巧速查.md`:沉淀 6 大主题(远程控制桥 / 自定义属性驱动 / 打关键帧 / Slotted Action API / 插值机制 / C4D 式 Free handle 法)
- 实战来源:活力之丘点位模型项目(相机002 关键帧、空物体 vis 驱动)

## v0.2.0 · 2026-08-17

- 追加合成器与渲染输出专题(Blender 5.2 变化):
  - `docs/技巧速查.md` §7:合成器输出 PNG 序列正确配置、查看器不自动显示的处理、RGBA 透明问题
  - `DEVELOPMENT.md` 新增 5 篇问题记录:合成器节点脚本崩溃 / 查看器不显示 / EXR 非 PNG / F12 不写序列 / PNG 透明
- 来源:活力之丘点位模型 720 帧渲染输出实战(File Output 节点 + Cycles)

## v0.2.1 · 2026-08-17

- 更正并补充 §7:use_nodes 5.x 恒 True 无法关闭;合成器节点组=输出开关(空节点组=幽灵状态不输出);移除节点组的 GUI/脚本方法;双份输出与位深差异
- `DEVELOPMENT.md` 新增 2 篇问题记录:空节点组导致不输出 / File Output 与渲染属性双份输出

## v0.2.2 · 2026-08-17

- `docs/技巧速查.md` §8 新增:Cycles 渲染提速技巧(GPU/OptiX、降噪+降采样、分辨率/光程、断点续渲、每帧用时查看)
- 来源:活力之丘 720 帧 Cycles 渲染提速实战

## v0.2.3 · 2026-08-17

- §8 扩充"查看每帧渲染用时"详细版:中文菜单路径、输出格式解读(累计时间/单帧换算)、命令行日志统计、F12 vs Ctrl+F12 差异

## v0.3.0 · 2026-08-17

- 新增 `scripts/blender-remote-control/` 可复用脚本包(跨机器):
  - `blender_bridge.py`(桥 v2,端口 9877,主线程执行)
  - `send.py`(发送客户端,纯标准库无依赖)
  - `example_probe.py`(通用示例:探查相机及关键帧,兼容 4.x/5.x Slotted Action API)
  - `README.md`(原理 / 环境核对清单 / 使用步骤 / 踩坑 / 常见问题)
- `docs/技巧速查.md` §1 更新:脚本位置改为指向仓库内可复用包
