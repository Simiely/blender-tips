# CHANGELOG.md

## v1.24.7 · 2026-09-20

- **滚筒斜纹拆成两份【并列方案】**（原先硬塞在一套控件里，语义互相打架）：
  ① `build_streak_count.py` 按条数（K + 高度周期数 N 两个整数控件）⇒ 斜角是结果，占槽 1
  ② `build_streak_angle.py` 按角度（K + 斜角，N 经 `RADIANS→TANGENT→K×(H/P)÷tanθ` 反算），占槽 3
  两套面板/看门狗/文本块键名各自独立，可同时在线；切换脚本改面索引即时生效。
- 关键坑：**废弃键列表绝不能含对方在用的键** —— 实测 B 的 `DEPRECATED` 带了「高度条纹数」，
  跑一次 B 就把 A 的控件删了、A 的驱动一并失效。两边只清历史废弃键。
- 核验改为**并列跑两遍**（`verify_variants.py`）：49 项，含「两个材质同时存在且互不覆盖」断言。
- 说明「斜角越大屏幕上条纹越弯、间距越不均」是**柱面投影固有性质**（`x = R·sinφ` 非线性），非缺陷。
- 涉及文档：`skills/blender-cylinder-spiral-material/*`、`CHANGELOG.md`、`AGENTS.md`（基线行）

## v1.24.6 · 2026-09-20

- **新增技能 `blender-cylinder-spiral-material`（圆柱螺旋 / 滚筒斜纹发光材质）** —— 
  两条同源变体：①螺旋上升条纹（`f = u×K + v×N`）②**滚筒斜纹**（`f = u×K − v×N`，运动方向右下→左上）。
  波形走 **Math 域**（`MapRange(SMOOTHSTEP) ×2 + MINIMUM`），**不让 ColorRamp 兼职** ——
  用色标位置编码数学曲线会把参数耦合、色标被驱动锁死、拖尾长度被结构卡在 58%（旧方案实测值）。
  现在 `ColorRamp` 只负责颜色且**零驱动**，用户可以自由加色标。
- **「斜角」是独立控件**：经节点链 `RADIANS → TANGENT → K×(柱高/周长) ÷ tanθ` 实时反算高度周期数 `N`，
  改斜度不必再凑 `K:N` 比值。固定 K=3 时：20°⇒N4.75 / 41°⇒N1.99 / 65°⇒N0.81。
- 端盖按**法线**分到独立纯黑槽（端盖上 `atan2` 是极角，条纹会摊成扇形 —— 实测俯视像风车）。
- **11 条实测坑**，其中 5 条是渲染管线级的（本轮排查最耗时）：
  隔离场景渲染时**节点树驱动不被求值**（`evaluated_get()` 读到的却全对）· `bpy.data.images` **按路径缓存** ·
  `Image.pixels` 对 PNG 返回 **sRGB 编码值** · **`ortho_scale` 对应较长边**（用错让水平比例差一倍，
  把 1.59 个周期误判成 1 个）· 比对「渲染像素 vs 理论曲线」前**必须先自证 φ 空间映射**（对齐后相关系数 0.07→0.9989）。
- **方向类问题以实测标定**：纸面推导曾把「上升偏移」符号推反（实测往右下走），
  靠「固定高度一行的暗带中心跨帧比对」纠正为 `+fr * us`。
- 核验 **135 项**；技能含 21 个脚本；端到端波形验证相关系数 **0.9989**。
- **「斜角」做成派生量**：`N` 由斜角经 `RADIANS → TANGENT → K×(柱高/周长) ÷ tanθ` 实时反算，
  `K` 仍是控件、`N` 在面板实时显示 ⇒ 「条纹数」与「角度」两个信息同时可读可控。
- 涉及文档：`skills/blender-cylinder-spiral-material/*`、`CHANGELOG.md`、`AGENTS.md`（基线行）

## v1.24.5 · 2026-09-20

- **`blender-bridge-ops` 标准作业循环新增第 5 步：跑「带还原逻辑」的技能脚本前，先用自己的隔离探针验它一遍** ——
  来源同一天 `self_test.py` 的还原缺陷（见 v1.24.4）。技能脚本头部那句「跑完与基线逐字节等价」
  是**声明而非事实**：实测该脚本的旧 `restore()` 会把**全部 mesh** 的面级材质索引归零。
  做法：先建 2 槽 mesh 探针（面索引交替 0/1）并记状态 → 跑脚本 → 读探针确认它原封未动，
  再核对对象/材质总数与跑前一致。原第 5~7 步顺延为 6~8。
- 涉及文档：`skills/blender-bridge-ops/SKILL.md`、`CHANGELOG.md`、`AGENTS.md`（基线行）

## v1.24.4 · 2026-09-20

- **`blender-radial-pulse-material/self_test.py` 还原逻辑修复（实测驱动，两处真缺陷）** ——
  - **残留**：`radial_field.py` 会自建共享坐标空物体 `CONFIG["ctrl"]`（默认 `FB_ctrl`），
    而 `restore()` 只删 `_SKILLTEST` 材质、**不删这个对象** → 每次试跑都在用户工程里留下
    1 个无主 EMPTY，还原判据也随之一直报 FAIL。实测：跑前 12635 对象 → 跑后 12636；
    残留物带 `assign=false` 与全套 CONFIG 数值属性（铁证）。已改为删除「基线中不存在的新增对象」。
  - **数据破坏（严重）**：`restore()` 对**全部 6699 个 mesh** 无条件执行
    `me.materials.clear()` + `poly.material_index = 0`。`clear()` 会把该 mesh 所有面的
    `material_index` 归零 —— 等于清掉用户的面级材质分配。
    - 反向对照：隔离探针（2 槽、6 面交替 `{0:3,1:3}`）跑完变 `{0:6}`；修复后保持 `{0:3,1:3}`
    - 真实损失：磁盘原文件里 152 个多槽 mesh 有 **141 个带非零面索引**；跑完后内存中
      **152 个全部为 0**。其中 `Group-5334926-1-728.001` 有 1657812 面、**1401528 面（85%）
      用槽 1**，`Group-5334926-1-728/.729/.730` 各有 156380 面用槽 1 → 材质整体错乱
    - 已改为「槽位未变则 `continue`，绝不触碰」；确需还原槽位时只把**越界**索引归 0
  - **误导性报告**：还原失败时打印的是**全量材质表/对象表**（实测刷出 445 KB 噪声），
    还把用户原有材质标成「残留材质」，把排查方向带向「材质没删干净」—— 而真残留其实是对象。
    已改为只输出**差异**（新增/消失的对象与材质、变化的槽位、帧）。
- **联调实测（Blender 5.2.0 LTS / `2609190xBx02.blend` / CYCLES / 12635 对象 / 12 场景）** —— 经 9877 桥做**写入闭环**：
  - `blender-loop-keyframe-anim`：建隔离临时对象 → `write_loop_anim.py` 写周期三角波 + CYCLES →
    另起请求 `verify_loop_anim.py` 独立核验，峰值精确命中 `13.00` / `50.00`，BEZIER 与 CYCLES 修饰器均在 →
    回滚后 `12635 / 78 actions / 帧 365-720` 与基线逐项一致
  - `blender-radial-pulse-material/self_test.py`：4/4 模式（spot / ring / spike / pulse）`FAILS=0` 全通过
  - 附带发现：这批技能的目标对象名（`竖向灯001_噪波控制`、`水晶走廊_竖向灯.001`）在当前文件里
    **一个都不存在**（模糊搜索「竖向灯」「水晶走廊」命中 0），说明它们是给另一个工程文件写的；
    运行前必须先改 `TARGET_OBJ` / `A_NAME` 等配置项
- 涉及文档：`CHANGELOG.md`、`skills/blender-radial-pulse-material/SKILL.md`、`scripts/self_test.py`、`AGENTS.md`（基线行）

## v1.24.3 · 2026-09-20

- **接入联调修复：技能安装链路的相对路径断链** —— 按 `skills/README.md` 只拷 `skills/` 到 `~/.workbuddy/skills/` 后，
  所有 `../scripts/<包>/` 与 `../docs/<文>.md` 引用全部解析失败。本次修复三处：
  - `skills/README.md` 安装章节：改为**三件套一起拷**（`skills/` + `scripts/` + `docs/`），并附**断链校验脚本**（判据「断链 = 0」）+ 相对层级约定说明
  - `skills/blender-driver-param-maintenance/SKILL.md`：`../../docs/` → `../docs/`、`../../scripts/` → `../scripts/`（2 处）
  - `skills/blender-inward-pulse-material/SKILL.md`：同上（4 处）
  - **根因**：从 `skills/<名>/` 出发正确层级是**一级** `../`；写成两级 `../../` 会落到安装根之外
- **`blender-bridge-ops` 环境事实订正（实测）** ——
  - 删除错误条目「本机 bash 环境已损坏（`ls`/`dirname` not found）」：2026-09-20 复测 `ls`/`dirname`/`grep`/`find`/`diff`/`cp` **全部可用**，文件操作应优先用 bash
  - 「PowerShell 不回传 stdout」**经复测仍然成立**，保留
  - 新增坑：**bash heredoc 会吃掉成对反斜杠** —— `python - <<'PY'` 里写 `'C:\\path\\to'`，Python 实际收到 `C:\path<TAB>o`（`\t` 变制表符），字符串匹配**静默失败**；构造含反斜杠的路径必须用 `chr(92)` 拼接
- **联调实测（Blender 5.2.0 LTS / `2609190xBx02.blend` / CYCLES / 12635 对象 / 12 场景）** —— 经 9877 桥实跑两个只读技能脚本，全链路通：
  - `blender-scene-cleanup` → `snapshot_baseline.py`：读数 `total 12635 / empty 5916 / empty_no_child 1941 / materials 279 / actions 78`，落盘 `cleanup_baseline.json` 成功
  - `blender-render-blackout-diagnose` → `diagnose_blackout.py`：一次打全七条路径，命中「AgX 会压暗发光」「1 个假发光节点（`3d66-VRayMtl-22674063-024` 的孤儿原理化 BSDF，发 Strength 改了没用）」「4 个材质多 BSDF 只接 1 个」
  - 附带校验：48 个自带脚本 `ast.parse` 语法全通过；10 个 SKILL.md 路径引用**断链 0**
- 涉及文档：`CHANGELOG.md`、`skills/README.md`、`skills/blender-bridge-ops/SKILL.md`、`skills/blender-driver-param-maintenance/SKILL.md`、`skills/blender-inward-pulse-material/SKILL.md`

## v1.24.2 · 2026-09-19

- **双径向 Skill 铁律统一补「三平面」备注** —— 两个径向发光材质 Skill（四段循环脉冲 / 内收多脉冲）都明确：**效果必须在「三块两两正交且共心的平面」下做才准确**，目标不是三平面时必须先提示用户补齐；三面同场交线连续、任意角度环都同心，**效果对不对一眼可验**。
  - `skills/blender-radial-pulse-material/SKILL.md`：铁律 #7 补「便于检验」句
  - `skills/blender-inward-pulse-material/SKILL.md`：铁律新增 #6（同口径）
  - 来源：2026-09-19 实战（`260918xAx06` 烟花灯三平面试验台，径向脉冲_位6 / 内收脉冲_位7 两次部署）
- 涉及文档：`skills/blender-radial-pulse-material/SKILL.md`、`skills/blender-inward-pulse-material/SKILL.md`、`AGENTS.md`（基线行）

## v1.24.1 · 2026-09-19

- **Skill `blender-radial-pulse-material` 铁律补充（#7）** —— 部署/复制本材质到新目标时，若目标**不是「三块两两正交且共心的平面」**，必须先停下提示用户「要增加/补齐三块平面，做出来才准确」，确认后再动手；少于三块得不到完整的立体（球形）观感。
  来源：2026-09-19 实战部署（`260918xAx06` 烟花灯集合三平面 `_位6`，四段呼吸径向脉冲）。
- 涉及文档：`skills/blender-radial-pulse-material/SKILL.md`（铁律新增 #7）、`AGENTS.md`（基线行）

## v1.24.0 · 2026-09-16

- **新增主题 #41「雪花下落系统」** —— `docs/雪花下落系统.md` + 脚本包 `scripts/snowfall-scatter/`
  - **系统**：参数化连续下雪。一个隐藏低模雪花源 `花瓣雪花_低模`(26 顶点, 浅蓝材质) + 一个 **EMPTY 宿主** `下雪_宿主` 上的单个几何节点组 `下雪_GN`，按**真实雪速(~0.5 m/s)**下落 **50000**(250×200) 片
    - 下落核心：`SceneTime → ×1/CYCLE → +随机相位 → FLOORED_MODULO 1 → prog`，`Z = GROUND + (1-prog)*FALL_SPAN`；**触地(prog→1)取模回卷到天空**，无半空消失、无顶部堆积
    - 落点：`RandomValue(ID←Index, 独立种子)` 生成 X/Y(取地平面世界包围盒中心±半宽)与相位，防共线/堆积
    - 顶部入场：`MapRange(prog 0~2% → scale 0→满)` → 实例化 Scale；朝向 = 倾角RandomValue(90°±15°, 平行地面) + 自旋RandomValue(0~360°)
    - `ObjectInfo(花瓣雪花_低模)` **RELATIVE** 继承源几何；源三连隐藏(render/viewport/camera)
  - **实测数据(本地桥 9878，`probe_snow.py`)**：frame 1/75/150 均 n=50000，`Z[-1.30, 28.70]` 精确贴地(地面=-1.3, 天空=+30)
  - **关键坑(写入文档 §七 + AGENTS)**：
    - **宿主变换必须清零**(loc=0/rot=0/scale=1)——落雪区高度锚定地面参考平面；宿主被移(Z=-1.47)会使雪区整体下移、雪埋进地面
    - **`'%s' % (tuple)` 陷阱**：单个 `%s` 对三元组右操作数会按「多参数解包」报 `TypeError: not all arguments converted`，需包 `(xxx,)` 成单元素元组
    - 触地回卷用 FLOORED_MODULO，**别加贴地淡出**(否则半空消失)；位置偏移经 `设置位置` 施加在实例化前
    - RandomValue 必须显式接 Index 作 ID 且各维度独立种子，否则共线/同时落
  - 脚本包：`build_snowfall.py`(构建, 幂等, 顶部参数可改)/ `probe_snow.py`(只读探查, 3 帧实例数+贴地范围)/ `verify_snow.py`(独立核验 10 项)/ `pack_snow_collection.py`(归拢到 `下雪_系统` 集合用于迁移)；经 `send.py -p 9878` 实况验证 50000 实例贴地，四脚本 py_compile 通过、无 BOM、无 `__main__` 守卫
- 涉及文档：`docs/雪花下落系统.md`、`scripts/snowfall-scatter/README.md`、`README.md`(索引 #41)、`docs/技巧速查.md`(索引 #41)、`AGENTS.md`、`DEVELOPMENT.md`

## v1.22.0 · 2026-09-16

- **新增主题 #39「星芒散射光效系统」** —— `docs/星芒散射光效系统.md` + 脚本包 `scripts/starburst-scatter/`
  - **系统**：参数化星芒（6 尖角 + 中央圆盘）沿相机朝向散布到三个点云宿主。核心机制是「**隐藏的单面源对象 + 几何节点**」：
    - 源 `星芒`（单面平面 + NODES 修改器 `星芒_GN` 生成星芒形状，4 形状参数 socket）`hide_render=True` 隐藏本尊，散布实例不受影响照常渲染
    - 三宿主 (`球心_点云/2/3`) 各挂独立散布组 `星芒_散布_GN 系列`：随机筛选→`设置位置`(偏移,实例化前施加)→`实例化于点上`(源几何,`ObjectInfo RELATIVE` 继承源缩放;`对齐欧拉至矢量←空物体` billboard;SceneTime→运算链错相缩放)→实现实例
    - `星芒_控制器` 6 中文滑块统一驱动：`尖角长度/圆盘半径/基部半角/内凹程度`→修改器 Socket_0..3（expr `x`）；`实际大小`→源 scale（expr `实际大小/1000`）；`动态缩放`→源 scale（正确式应 `实际大小/1000 + 动态缩放/1000`）+ 30 帧循环三角波 Action（CYCLES）
  - **实测数据（Blender 5.2 / Eevee / AgX）**：三组散布 ObjectInfo 均 RELATIVE；位置偏移 `(-0.0065,+/-0.0076,0)` / `(-0.0065,0,-0.0076)`；评估顶点数 96652/96652/68766；`material_override=None`
  - **可复用坑（写入文档 §七 + AGENTS）**：
    - 几何散布「源隐藏渲染实例照常」——`ObjectInfo(RELATIVE)` 继承源缩放/动画；换 ORIGINAL 会忽略源缩放
    - **位置偏移要经 `设置位置` 施加在实例化前的点上**，别直接改 IOP Position/Scale（否则被实例基缩放放大）
    - **SCRIPTED scale 驱动把 `b` 变量丢掉只剩 `a/1000`** ⇒ 控制器 `动态缩放` 循环动画对整体大小失效；完整式 `a/1000 + b/1000`（`fix_star_scale.py` 一键恢复、幂等、先打印旧式）
    - 5.2 `mod.properties.inputs` 不可迭代（`GeometryNodesInterfaceInputs`），用 `.get(名)`/属性访问；`enumerate` 抛异常
    - EMPTY 自定义属性驱动几何 socket 不稳（读缓存值）→ `生成数量` 走节点组接口/修改器面板
  - 脚本包：`probe_star.py`（只读探查）/ `verify_star.py`（独立核验 20 项全绿）/ `fix_star_scale.py`（修复 scale 驱动）；经 `send.py -p 9878` 实况验证 ALL_PASS，三脚本 py_compile 通过、无 BOM、无 `__main__` 守卫
- 涉及文档：`docs/星芒散射光效系统.md`、`scripts/starburst-scatter/README.md`、`README.md`(索引 #39)、
  `docs/技巧速查.md`(索引 #39)、`AGENTS.md`、`DEVELOPMENT.md`
  - 注：本主题在两端分叉后并入主线，故版本号较主题编号后置（星芒→v1.22.0/#39，见 DEVELOPMENT 分叉记录）

## v1.23.0 · 2026-09-16

- **新增 Skill `skills/blender-loop-keyframe-anim/`** —— 给自定义属性批量写「循环三角波关键帧动画」
  - 场景：用户要求 `面光统一强度`（1–450 帧，每 30 帧 8→13→8 缓入缓出）、`发光强度`
    （每 20 帧 5→50→5）等属性做**循环三角波动画**，一个完整周期进 fcurve + **CYCLES 循环修饰器**铺满帧范围
  - 关键写法定型（Blender 5.x Slotted Action）：
    - 正确写入路径 `obj.animation_data.action.layers[0].strips[0].channelbags[0].fcurves`
      （5.x 起不再用 `action.fcurves`）
    - `FModifierCycles` **无 `mode` 属性**（5.x 移除），默认即为正向循环（CYCLES）
    - **关键帧值精确写入** `kp.co=(fr,val)` 绕开「属性当前值被驱动干扰」——被驱动属性再用 fcurve 补关键帧时，
      直接读表达式会拿到被驱动后的值，写进去会错位，必须用具名周期点显式覆盖
    - **is_valid=False 判空**：5.x 中引用/驱动判空靠 `is_valid` 而非 `is None`
    - 验证时读「被驱动值」必须走 **depsgraph**（`dg = bpy.context.evaluated_depsgraph_get()`），
      不能读内存对象属性
  - 配套脚本：`scripts/write_loop_anim.py`（写入器，顶部 `TARGET_OBJ`/`ANIMS` 配置）+
    `scripts/verify_loop_anim.py`（独立核验器：关键帧、BEZIER 插值、CYCLES 修饰器、depsgraph 抽样求值）
  - 传输层依赖 `skills/blender-bridge-ops`；写入/验证铁律同各 skill（先侦察、干跑副本、还原点、独立核验、判据取差集）
- 涉及文档：`skills/blender-loop-keyframe-anim/{SKILL.md,scripts/*}`、`skills/README.md`（清单 + 安装段）
  - 注：本 Skill 与远端 v1.18.0 撞号，随本条主线并线重编为 v1.23.0（见 DEVELOPMENT 分叉记录）

## v1.21.0 · 2026-09-16

- **新增主题 #38「驱动参数化材质维护:引用体检 / 关键帧收敛 / 改名换轴」** ——
  给**已经建成**的「空物体自定义属性 + SINGLE_PROP 驱动器」系统做运维改造(不是新建),
  来源:水晶长廊工程把 `噪波种子`/`发光强度`/`面光统一强度` 的关键帧收敛成常量、
  并把 `Z向速度` 改名为 `X向速度`、`X向速度` 改名为 `Y向速度` 的实战
  - **★ 引用体检的扫描清单必须含 `物体数据 → node_tree`**:Blender 5.x 的**灯光/网格数据块自带节点树**,
    面光灯的同构接入驱动全部挂在 `o.data.node_tree.animation_data` 上。
    **漏扫这一层会双向出事**(都实测到):
    ① **误判** —— `面光统一强度` 实为 7 盏灯节点树 `发光强度.001` 在读(`expr='st * k'`),
       却得出"全库零引用 ⇒ 假控件"的**相反结论**;
    ② **事故** —— `Z向速度 → X向速度` 改名时,7 盏灯节点树各有 1 条驱动指向旧键,
       改名+删键后**全部 `is_valid=False` 静默失效**,面光灯噪波滚动整片停摆而 UI 无任何异常
  - **★ 改完必跑失效体检**:全库 `dr.driver.is_valid == False` 计 0 条 +
    「变量 `data_path` 指向已不存在的属性」计 0 条(正则 `^\["(.+)"\]$` 比对 `id.keys()`)
  - **关键帧 → 常量(收敛)的固定顺序**:读(`(帧,值)` 全表 + 插值/外插 + **当前帧求值**,
    即回滚依据)→ 定常量(**当前帧所见值**不跳变 / 用户指定值)→ **只删目标 `data_path`+`array_index`
    那一条 fcurve**(同 action 其它曲线原样保留)→ 写回 → `update_tag` → **另起请求**验证
  - **改名 + 换轴六步(顺序不能乱)**:体检拿清单 → 新属性+UI 元数据全量复制(`as_dict`/`update`,
    描述文案同步改轴向)→ `driver_remove(旧分量)` + `driver_add(新分量)`+重建变量 →
    **显式覆盖 `d.expression`** → 旧分量归零 → **驱动全部重建完才删旧属性键**
  - **跨节点树必须同步搬轴**:同名参数被主材质 + 若干面光灯同构接入,只搬主材质会导致
    两边滚动方向不一致;判据是「主材质与全部灯在同帧读数逐位相等」(实测 8 个插槽同时 5.0/50.0)
  - **三个容易混淆的「index」**:① 驱动 FCurve 分量索引(`drivers.find(path, index=...)`,
    **index 必须关键字传参**)② DriverTarget 数组分量(5.2 已无 `.array_index`,写进 `data_path`)
    ③ `ActionSlot` 标识(`.identifier` / **`.name_display`**,既没有 `.name` 也没有 `.display_name`)
  - 脚本包 `scripts/driver-param-maintenance/`:`param_ref_scan.py`(`refs` 消费者清单 / `health` 失效体检)、
    `strip_keys_to_constant.py`(`report` 留档 / `apply` 收敛)—— 两个脚本均在真实工程上跑过
    (health: 78 驱动 0 失效;refs: 命中 21 条引用)
  - 配套文档 `docs/驱动参数化材质维护.md`、Skill `skills/blender-driver-param-maintenance/`

## v1.20.0 · 2026-09-15

- **新增主题 #37「径向材质多位置部署与播放时差」** —— 同一套径向材质部署到多个位置、
  各处播放错开一段时间,以及「改一个材质/参数其它地方跟着变」的排查与独立化
  - **位置副本**：动态定位(从材质槽读材质、顺 `纹理坐标.object` 找控制器,**不猜名字**)⇒
    `copy()` 材质与控制器(**节点树/全部驱动/全部自定义属性自动带过来**)⇒ 只改三处指向
    (纹理坐标.object / 材质驱动变量 / 控制器自身只读驱动),新控制器放**实测的网格并集中心**
  - **★ 带关键帧的材质复制后 action 必须重建**：`nt.animation_data.action` 会与原件共用;
    `action.copy()`+按名字重绑 `action_slot` **不生效**(评估值冻结)⇒ `ad.action=None` + 原地重建
  - **命名防叠**：新名字前先剥掉历史后缀(`_位N/_副本/_面N`),否则叠成 `_位3_面1_位4`
  - **★ 三层共享判别**(改一个其它跟着变的三种成因,判据都是 `users > 1`):
    ① 网格数据(改材质槽一起变) ② 材质(改节点/参数一起变) ③ 控制器(拖参数一起变) —— 三者正交
  - **★ 快照式独立化**：先按数据块分组做快照,被共享组里的每个对象都无条件复制;
    不能一边遍历一边判 `users>1`(复制一个 users 掉 1,兄弟对象被跳过,实测漏 28 个);
    **匹配关键词要向用户要全**(「收缩射灯效果」不是「收缩灯」的子串,整组漏掉)
  - **★ 播放时差 ≡ 相位偏移**：`相位 = 帧号÷循环周期 + 相位偏移`,
    令 `相位偏移 = 错位帧数×k ÷ 循环周期` 即等价于用 `帧号+错位×k`(周期相同严格等价);
    内收类零节点改动(注意 mod 1),四段循环类改 TVAL 两个关键帧的【值】(斜率不变);
    ⚠ 相位偏移存的是圈数不是帧数,改循环周期等效帧错位会变
  - **材质丢失防护**：`users==0` 且无 fake ⇒ 存盘被清;未挂载的材质不进依赖图(读值是原始存值);
    全部径向材质已上 `use_fake_user=True`
  - 脚本包 `scripts/radial-inward-pulse/` 新增:`copy_to_position.py`(自动编号) /
    `make_effect_independent.py`(快照式) / `diag_sharing.py`(三层共享诊断)
  - 配套文档 `docs/径向材质多位置部署与时差.md`
- **勘误补漏**：`skills/blender-procedural-emission-material/scripts/build_noise_scroll.py`
  的 `_bind_frame_var` 注释仍写着「内置 frame 在 5.2 里实测解析不到」—— v1.18.0 勘误只改了
  SKILL.md 没改配套脚本,本次补上(改法与 `docs/驱动式Z轴匀速旋转系统.md:84` 一致)
- **修正**：`scripts/radial-inward-pulse/probe_target_size.py` 的角点半径原本相对
  【旧控制器位置】计算 —— 网格一挪动就得出垃圾值(比值 3.31 而非 √2);
  改为相对**网格并集中心**计算,并在比值偏离 √2 时给出警告

## v1.19.0 · 2026-09-15

- **新增主题 #36「径向内收多脉冲材质」** —— 共心的多个平面/球面上,若干同心亮环**从外往内收**、
  无缝循环、黑边很细,且**环数恒定**(不是「最多 N 条」)
  - 节点链:`纹理坐标(Object=控制器) → Mapping → VectorMath(LENGTH) → r`,`r ÷ 间距 + 相位 → FRACT`,
    梯形剖面(`上升沿 × 下降沿` 两个 Map Range 相乘)⇒ 亮带 + 黑间隔;
    **相位随时间增大 ⇒ 带位 `r = 间距×(k − 相位)` 减小 ⇒ 往中心收**;`FRACT` 天然环绕 ⇒ 无缝循环
  - **★ 环数恒定的有效窗口公式**(本文最值钱的一节):
    `可见带窗口 = L + 占空比 − 软边占比 − 2×最小可见宽度` 必须 ≈ N
    —— **三项缺一不可**,每一项都是被实测打回来的:只写 `L + 占空比 ≤ N` 会多出第 N+1 条;
    补了「− 软边」没扣 `2×最小可见宽度` 则仍有约 **2%** 的相位只显示 N−1 条;
    全扣干净后 **N 条占比 99.83%**,永不出现 N+1(实测数据见脚本包 README)
  - **★★ 计数基准必须问清**:非圆网格上**内切圆半径**与**角点半径**相差 **√2 ≈ 1.414** ——
    按角点定 3 条,圆上只剩 1.55 个周期 ⇒ **只看到 2 条**(实测返工)。
    基准做成开关 `REF_FOR_COUNT = 'CIRCLE' | 'CORNER'`,扫描**同时报告两处**的环数分布
  - **亮面裁切**:`MapRange(r − 亮面半径, 0..淡出宽度, 1..0)` 乘进掩码 ⇒ 发光限制在圆内,
    四角不再多出环;「亮面面积」与「黑边粗细」是**两个正交旋钮**(混成一个必然返工)
  - **配色复用**:从姊妹材质**实时读 ColorRamp 色标**逐项复制(不能读 `Emission Color.default_value`
    —— 插槽已连线时那只是残留值);色标要按 `r / 色相半径` 归一化后再喂
  - **时间参数用「循环周期(帧/圈)」**:`= 1 ÷ 每帧推进的周期数`,实现是一句 `帧号 ÷ 循环周期`,
    用户直接填帧数(帧数越小转得越快),负值 = 向外扩
  - **★ 新坑:驱动只能挂在 `Value` 节点输出上** —— 挂在 `Math`/`MapRange` 这类**计算节点**的输出插槽上
    会被节点自身运算覆盖 = **等于没写** ⇒ 相位恒 0 ⇒ **拖时间轴画面完全静止**。
    构建与核验都加了守卫(逐条驱动检查目标节点 `type == 'VALUE'`)+「帧号响应自检」
  - 脚本包 `scripts/radial-inward-pulse/`:`probe_target_size.py`(只读量中心/半宽/角点半径,
    输出两种基准的比值)/ `build_inward_pulse.py`(幂等;含连线自检与解析扫描)/
    `verify_inward_pulse.py`(独立核验:结构 + 驱动 + 配色跨材质对拍 + 裁切链 + 环数独立复算)
  - Agent Skill `skills/blender-inward-pulse-material/`;配套文档 `docs/径向内收多脉冲材质.md`
- **顺带补齐 v1.18.0 在 `skills/README.md` 的登记遗漏**:`blender-radial-pulse-material`
  当时加了 skill 但清单表与安装命令都没带(目录树里有),本次一并补上

## v1.18.0 · 2026-09-14

- **新增 Agent Skill `blender-radial-pulse-material`** —— 世界空间**径向距离场**发光材质 + 空物体属性驱动
  - 定位：与 `blender-procedural-emission-material` 并列（同属世界空间程序化材质），母 skill = 后者
    （通用机制在那边：SINGLE_PROP 驱动、tag 矩阵、读求值依赖图、像素级验收）；本 skill 只讲径向这一路
  - 核心认知：图案只依赖到**共享中心的距离 r**（和方向 d）⇒ 共心的 XY/XZ/YZ 平面切过去天然同心、
    交线连续。「从中心向外发散」是几何必然，不是技巧
  - 五种模式：`spot` / `ring` / `spike` / `pulse` / **`cycle`（四段循环脉冲）**
  - **`cycle` 的两个关键技巧**：
    - **`TVAL ≡ 帧号`**：Value 节点只打两个关键帧（1→1.0 / 250→250.0）+ 全 LINEAR +
      F-Curve `extrapolation='LINEAR'` ⇒ 任意帧 TVAL 精确等于帧号（实测外推到 1000 帧仍准）。
      **不用驱动、不用脚本**，也不受"表达式里有东西解析不了"影响
    - **周期与相位必须分离**：`周期 = 四段之和`（自动求和）、`v = u − 变亮前等待`、`prog = v / 活动`。
      **时长类参数必须进【相位】** —— 只进"周期"的参数在 `f < 周期` 时是**数学恒等变换**，
      两种设置画面逐像素相同（实测改黑场停留 26→120：帧 30/150/199 diff **0.0/255**；帧 250/300/350 才 255/255）
  - **控制面 = 空物体自定义属性 + 驱动器**（数据驱动，用户明确不要面板）：9 个中文属性
    （带 `min/max/soft_min/soft_max/description`）→ 9 条 `SINGLE_PROP` 驱动 → 材质节点插槽；
    `周期帧数` 另挂一条 **IDProperty 驱动**做自动读数（拖任一时长它立刻跟随 —— 死数字会被误判成"逻辑没理顺"）
  - 三个静默陷阱（都实测踩过）：**`Math` 第 3 个输入只有 `MULTIPLY_ADD` 会读**（三路相加必须串两个 ADD，
    否则静默丢第三路）；**未连接的输入默认 0.5 不是 0**；**`driver_add()` 会把表达式自动填成当时的数值**
    （不覆盖 `d.expression` 就等于装了个常量驱动）
  - 脚本包随 skill 自带：`radial_field.py`（4 模式）/ `cycle_pulse.py`（循环版 + 驱动自检）/
    `verify_field.py`（T1 对称性 / T2 多物体一致性 / T3 时间推进）/ `self_test.py`（隔离试跑）/
    `shoot_modes.py`（出参考图）。`self_test.py` 改为**改脚本后必跑**的一步
- **勘误：驱动表达式里的内建 `frame` 变量【是可用的】—— 旧结论错了**
  - 症状：仓库里这条**自相矛盾**。4 处写"不可用"（`AGENTS.md:41`、`docs/驱动式Z轴匀速旋转系统.md`、
    `scripts/driver-spin/README.md`、`skills/blender-procedural-emission-material/SKILL.md` §3 + description），
    另 4 处写"可用"（`AGENTS.md` 自己的另一行、`docs/材质参数统一控制器与实时面板.md`、
    `docs/技巧速查.md` §29 与其 §17）
  - 定论（`_bridge/a_frame_probe.py`，5 组对照，Blender 5.2.0 LTS）：
    | 写法 | 结果 |
    |---|---|
    | `frame`（节点插槽驱动） | ✅ 帧 7→7.0、30→30.0，`is_valid=True` |
    | `frame`（**对象级**驱动 `location.z`） | ✅ 帧 10→1.0、40→4.0 |
    | `frame * <未注册的命名空间函数>()` | ❌ **`is_valid=False`、值恒为 0、画面零变化** |
    | `frame * <已注册的命名空间函数>()` | ✅ 帧 30→90.0、60→180.0 |
    | `fr` = `SINGLE_PROP → SCENE.frame_current` | ✅ 帧 30→60.0、60→120.0 |
  - **真凶**：`probe_51` 用的表达式是 `frame * nz_z_speed()`，是 **`nz_z_speed` 没进命名空间**
    （文本块没 Register / Auto Run 没开）导致整条表达式求值失败 ⇒ 取默认值 0。**`frame` 是被连累的**
  - **范畴纠正**：`frame` 是驱动求值器注入的**内建变量**，与 `bpy.app.driver_namespace` **无关**
    —— "5.x 驱动命名空间默认无 `frame` 键"是把内建变量当成了命名空间键
  - **新增最快判据：读 `driver.is_valid`**（变红 = 表达式里有东西解析不了，与 `frame` 无关），
    比原先写的"渲染像素差 0.00%"快得多
  - 修正文件：`AGENTS.md`、`docs/驱动式Z轴匀速旋转系统.md`、`scripts/driver-spin/README.md`、
    `skills/blender-procedural-emission-material/SKILL.md`（§3 加勘误块 + description + 出处三处）
- **修正 `skills/README.md` 一处过时说明**：原文"后三个 skill 的脚本只随 skill 自带
  （`../scripts/` 下暂无对应脚本包）"—— 实际 `scripts/scene-cleanup/`、`scripts/blackout-diagnose/` **都存在**，
  只有 4 个 skill 是纯自带。已改成分项说明（**有对应包的必须两处同步**）
- **勘误：把「UI 里改数字 ⇒ 控件全哑」这条推断降级为「未隔离实测」**
  - 现状：`emission-material` §6 第 3 层、`plane-procedural-material` §7、`材质参数统一控制器与实时面板.md`
    都曾把「用户在 UI 数值框里改 ⇒ 不 tag ⇒ 全哑」当**结论**写；但唯一证据脚本
    `probe_driver_autotrigger.py` / `autorefresh_*` 用的全是 `ctl["x"] = 21.0`（**Python 赋值**），
    从没测过 UI 编辑
  - 复核还确认**无法从脚本侧旁证**（2026-09-14 实测）：① 自定义属性**不在 `bl_rna`**
    （`prop_in_rna=False`）⇒ `setattr` 走不到，直接 `AttributeError`；② `wm.properties_edit`
    是 INVOKE-only 元数据弹窗（脚本调用报"不支持直接执行"），不是数值框
  - 处理：三处统一改成「脚本侧不 tag 是**实测**铁证；UI 侧**未隔离实测**，只能真去 UI 里拖」。
    **做法不变**——看门狗对"会 tag / 不会 tag"两种情况都成立，照旧用
  - 新增可复现配方（随 `blender-radial-pulse-material` 带上）：
    `probe_ui_tag_arm.py`（装 depsgraph 观察器）+ 人在 UI 里拖 + `probe_ui_tag_read.py`（只读回采），
    以及 `probe_tag_path_matrix.py`（脚本侧写入路径对照矩阵，自证了上面①②两条）
- 涉及文档：`README.md`、`skills/README.md`、`AGENTS.md`、`CHANGELOG.md`、
  `skills/blender-radial-pulse-material/`（新增）、
  `skills/blender-procedural-emission-material/SKILL.md`、
  `skills/blender-plane-procedural-material/SKILL.md`、
  `docs/材质参数统一控制器与实时面板.md`、
  `docs/驱动式Z轴匀速旋转系统.md`、`scripts/driver-spin/README.md`

## v1.17.1 · 2026-09-13

- **修正 `scripts/separate-by-material/` 验证器的一处必然误报：孤儿 mesh 判据从「绝对判无」改为「基线差集」**
  - 症状：对象 `水晶走廊_纵向灯2`（3,505,328 面 / 2,020,266 顶点 / 4 个材质槽）拆分后，
    面数·顶点数·世界矩阵·UV·自定义法线·逐组锐边·材质 users 等 **35 项全绿**，
    却因工程里 10 个**拆分前就存在**的历史遗留孤儿 mesh 被判 **❌ 不通过**
  - 那 10 个孤儿（`Mesh.5301/5302/5625/5626/5627/5652/5653/5654/5657/5658`）实测：`users=0`、
    每个仅 26~78 面、统一用材质 `std_8twe.002`、编号远早于本次新增的 `Mesh.6209~6211`
    ⇒ 早期删对象留下的数据块，**与本次拆分无关**
  - 根因：`verify_separation.py` 第 11 节写的是 `orphan_mesh = [m.name for m in D.meshes if m.users == 0]`
    后"有则报错" —— **绝对判据**，从未与基线比对 ⇒ 只要工程不是"零孤儿"的干净初始态，
    **干净拆分也必然报不通过**（本次实测 1 项假异常 / 35 项真通过）
  - 修正：
    - `separate_by_material.py` 基线新增 `orphan_mesh_before`（孤儿 mesh 名单）与 `orphan_mesh_count_before`
    - `verify_separation.py` 第 11 节改为差集判定：`orphan_now - orphan_before` = **本次新增孤儿** ⇒ ❌；
      `orphan_now & orphan_before` = **拆分前既有** ⇒ ℹ️ 提示（与本次操作无关，存盘时 Blender 本就会按孤儿丢弃）
    - **兼容旧基线**：无 `orphan_mesh_before` 字段时本项降级为 ⚠️ 提示、**不计入失败**，并明确提示重录基线
  - 复验：同一工程重跑 → **36 项全绿**；结论由「❌ 不通过（1 项异常 / 35 项通过）」变为
    「✅ 全部通过 —— 36 项检查全绿」，另附 1 条历史遗留孤儿提示
  - **同一病根的第二例：第 11 节「新增对象数」用了全场景口径 ⇒ 多对象连做时串扰**
    - 症状：先拆 `水晶走廊_纵向灯`、再拆 `水晶走廊_竖向灯`，回头复验前者时看到
      「ℹ️ 新增对象数 **4** != 材质槽数-1 (1)」—— 它自己只该新增 1 个（把后拆的 `竖向灯.001~003` 也数进去了）
    - 根因：`new_objs = set(D.objects) - before_objs` 是**全场景**差集；基线录完之后场景里只要
      还发生过别的结构改动，口径就串了
    - 修正：只统计「以 `TARGET + "."` 为前缀的新增对象」= **本组新增**；全场景多出的部分降为附注
      （"另有 N 个新增对象，属其它操作"），并把本项由 note 升级为**真判据**（本组数不对 ⇒ ❌）。
      `TARGET + "."` 的前缀写法对"名字互为前缀"的对象是安全的
      （`纵向灯` 是 `纵向灯2` 的前缀，但 `纵向灯2.001` 不匹配 `纵向灯.`）
    - 复验：`纵向灯` 23 项 → **24 项全绿**，误导性提示消失
  - **通用心法（已写入 AGENTS.md）**：凡"存在性 / 计数"检查（`users==0` 孤儿 / 空集合 / 缺贴图 /
    新增对象数 / 游离数据块），判据都必须**取差集、且精确到本次操作的对象集合** ——
    真实工程状态往往不是干净的初始态，而且操作**是连着做的**，用全场景绝对值必然误报或串扰
- **本次实战沉淀的可复用包装（落在工作区 `blender_control/`，暂未入仓库）**：
  `sep_multi.py`（批量拆分）/ `run_multi.py`（批量验证 + 引用扫描）——
  用**正则注入配置行**的方式驱动技能包脚本、循环处理多个对象，**不改技能包本体**；
  每个对象的 `BASE_JSON` / `STATUS_JSON` 带对象名后缀，互不覆盖
- 涉及文档：`scripts/separate-by-material/{separate_by_material.py,verify_separation.py,README.md}`、
  `docs/按材质拆分为多个网格体.md`、`docs/技巧速查.md`、`AGENTS.md`、`DEVELOPMENT.md`

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
