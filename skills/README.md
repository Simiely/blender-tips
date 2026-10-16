# Agent Skills（给 AI 助手用的作业规范）

本目录收录供 AI 助手（WorkBuddy 等）加载的 **Agent Skill**：每个子目录一个 skill，
内含 `SKILL.md`（带 YAML frontmatter，描述触发条件 + 作业步骤 + 硬约束）与可选的 `scripts/`。

## 和 `../scripts/` 的区别

| 目录 | 面向 | 内容形态 |
|---|---|---|
| `../scripts/` | **人** | 可复用脚本包：README（原理 / 配置项 / 使用步骤 / 实测数据）+ 脚本 |
| `skills/` | **AI 助手** | 作业规范：怎么干、先干什么、什么绝对不能干，并把同一套脚本作为附件带上 |

两者内容**有意重叠**：`skills/` 的价值是让 AI 不必每次重新推演流程与安全闸，直接照着干。
改动脚本时**两处都要同步**（`skills/<名>/scripts/` 与 `../scripts/<名>/`）。

## 清单

| Skill | 作用 | 关联文档 / 脚本包 |
|---|---|---|
| `blender-bridge-ops` | 9877 桥的**传输层作业规范**：客户端封装、120s 上限规避、Blender 5.x Slotted Action、引用判定、删除后引用失效等硬约束 | [技巧速查 §1](../docs/技巧速查.md) / [`../scripts/blender-remote-control/`](../scripts/blender-remote-control/) |
| `blender-scene-cleanup` | 工程**清理类**改造：EMPTY 收敛清理（不动点）、孤儿数据块、空集合、缺失贴图审计与还原 | [空物体收敛清理](../docs/空物体收敛清理.md) / [`../scripts/scene-cleanup/`](../scripts/scene-cleanup/) |
| `blender-render-blackout-diagnose` | **渲染发黑 / 材质不发光**排查：材质覆盖、引擎不读材质、Holdout、输出未连线或改错节点、AgX 压暗等七条路径 | [渲染发黑与材质不发光排查](../docs/渲染发黑与材质不发光排查.md) / [`../scripts/blackout-diagnose/`](../scripts/blackout-diagnose/) |
| `blender-overlap-difference` | 让两个互相穿插的网格体「**物理上不重叠**」——**面级剔除**替代布尔差集（只删目标件伸进刀具体的面，刀具体分毫不动）；含动刀前分类着色预览、三票制内外判定、布尔干跑评估、还原点与 `__BAK__` 撤回、独立核验 | 暂无独立文档，脚本包随 skill 自带 `scripts/`（`cull_overlap.py` / `probe_overlap.py` / `render_classify.py` / `restore_from_backup.py`） |
| `blender-procedural-emission-material` | **世界空间程序化噪波滚动发光材质** + 全套数字控件：不用 UV，标准链 `纹理坐标→Mapping(滚)→噪波4D→ColorRamp(对比度)→×强度→Emission`；含 SINGLE_PROP 驱动、**看门狗定时器**自动刷新、AREA 面光灯节点树同构接入与依赖环铁律 | [渐变发光滚动材质](../docs/渐变发光滚动材质.md) / [材质参数统一控制器与实时面板](../docs/材质参数统一控制器与实时面板.md)（其 §3 刷新结论不完整，见本 skill §6） |
| `blender-plane-procedural-material` | **平面（flat plane）专项**：法线轴零跨度导致的坐标退化、**平面 = 3D 噪声体的一片切片**、把平面当**验收测试卡**出客观读数（暗区占比 / 滚动方向 / 位移的像素级测法） | 母 skill `blender-procedural-emission-material` |
| `blender-radial-pulse-material` | **世界空间径向距离场发光材质**：图案只依赖到**共享中心的距离 r**（和方向 d）⇒ 共心的 XY/XZ/YZ 平面切过去天然同心、交线连续；含五种模式、**四段循环脉冲**（`TVAL≡帧号` 关键帧技巧 + 周期/相位分离：时长类参数只进周期就是空操作）、**空物体自定义属性 + SINGLE_PROP 驱动器**（数据驱动，不写面板）；附 Math 第 3 输入口 / 未连输入默认 0.5 / 接触表行序三个静默陷阱 | 母 skill `blender-procedural-emission-material` |
| `blender-inward-pulse-material` | **径向内收多脉冲**：若干同心亮环从外往内收、无缝循环；核心是**环数恒定的有效窗口公式**（`L + 占空比 − 软边 − 2×最小可见宽度 ≈ N`，缺一项环数就会在 N±1 间跳）与**计数基准的选择**（内切圆 vs 角点，相差 √2）；含亮面裁切把发光限制在圆内、从姊妹材质读 ColorRamp 复制配色、**驱动只能挂 Value 节点**的守卫、以及**出场「出生门」**(黑场起步 + 逐圈跟上,门只乘掩码而非缩放) | [径向内收多脉冲材质](../docs/径向内收多脉冲材质.md) / [`../scripts/radial-inward-pulse/`](../scripts/radial-inward-pulse/) |
| `blender-driver-param-maintenance` | **参数化驱动系统的运维改造**（已建成系统的维护，不是新建）：① `refs` 引用体检 —— 谁在读这个参数（扫描**必须含 `物体数据 → node_tree`**，灯光 Shader Nodetree 层漏扫会双向出事：误判"假控件" / 改名后驱动静默失效）；② `health` 失效体检 —— 全库 `is_valid=False` + 悬空引用，判据 0 条；③ 关键帧 → 常量的存档纪律；④ 改名换轴六步顺序（驱动重建完才删旧键） | [驱动参数化材质维护](../docs/驱动参数化材质维护.md) / [`../scripts/driver-param-maintenance/`](../scripts/driver-param-maintenance/) |
| `blender-cylinder-spiral-material` | **圆柱面螺旋斜条纹发光材质**（滚筒）：斜纹 = 柱面坐标相位取模 `f = u×K − v×N` + `FLOORED_MODULO`；波形走 **Math 域**（`MapRange(SMOOTHSTEP)×2 + MINIMUM`），**不让 ColorRamp 兼职**（后者会参数耦合 / 色标被驱动锁死 / 拖尾被结构卡在 58%）；ColorRamp 零驱动只管颜色。**两套并列调参方案**（按条数 / 按角度，跑哪个装哪个，避免留幽灵参数）；端盖按**法线**单独分槽（否则条纹摊成扇形风车）；**方向以实测标定**（纸面推导曾推反） | [滚筒斜纹材质](../docs/滚筒斜纹材质.md) / [`../scripts/streak-material/`](../scripts/streak-material/) |
| `blender-radar-scan-material` | **雷达扫描空间材质**（不用 UV，**沿某世界轴投射**）：极坐标角度场 `u = (atan2(Z, X) + π)/2π`（只取两分量 ⇒ 天然沿第三轴投射）+ 多扫描条相位 `D = frac(条数×时刻 − 方向×条数×u)`（★ **方向只准进角项**：进时间项时 `frac(−x)` 头位置集合与正向相同 ⇒ **旋钮按了不反向**）+ `FLOORED_MODULO`（普通 `MODULO` 负值裁剪 ⇒ **跨 0° 拖尾断头**）；拖尾/头部线/网格环带走 **Math 域**（`MapRange` + `POWER`，**ColorRamp 只管颜色不兼职**）；半径 `CombineXYZ(0 填 Y)` + `LENGTH`；12 参数控制空物体 + `SINGLE_PROP` 驱动；含 5.2 **无 `ShaderNodeSceneTime`** 的时间源替代（`Value` 节点 + 驱动）与**正交正视渲染 + 像素级测转角/反向/条数 + md5 验投射**的可证伪核验 | [空间雷达扫描材质](../docs/空间雷达扫描材质.md) / [`../scripts/radar-scan-material/`](../scripts/radar-scan-material/) |
| `blender-loop-keyframe-anim` | **给自定义属性批量写「循环三角波关键帧动画」**：一个完整周期进 fcurve + CYCLES 循环修饰器铺满帧范围，贝塞尔自然缓入缓出；含 Slotted Action 正确写入路径、5.x 无 mode 属性、`is_valid=False` 判空、depsgraph 读被驱动值、关键帧值精确写入（绕开属性当前值被驱动干扰） | 传输层 `blender-bridge-ops`；[技巧速查 §3/§4/§5](../docs/技巧速查.md) |
| `blender-split-flap-flip` | **翻页牌批量翻页动画**（报刊亭/机场翻页牌整块动起来）：每张卡建一个**中缝轴 Empty** 挂几何中心（卡片轴心常在角落，直接转就绕角甩）+ **单重补偿**挂接保持世界位置；**总转角必须是 360 的整数倍**（半圈停在背面看不到字）、缓动用 **smoothstep**、相位 `((列+行)%8)×2` 出斜向波浪。★ 两大真坑：**非受信任打开的 .blend 里 SCRIPTED 驱动静默不求值**（改走 `frame_change_post` 处理器）、**驱动表达式必须返回 `radians()`**（写度数 1080 → 61879°）；★ 处理器不写进 .blend ⇒ **存盘前必须停静止帧** | [分体翻页牌驱动翻页系统](../docs/分体翻页牌驱动翻页系统.md) / [`../scripts/flip-card/`](../scripts/flip-card/) |
| `blender-spot-bloom-swing` | **射灯阵列径向摆动绽放**（像花开花合）：一圈射灯各自**锁在自己的竖直径向平面**里摆动；起始线 = 灯→中轴线对象连线（中轴抬高时是**倾斜**的）、旋转轴 = 水平切向 `ẑ × r̂`；★ **必须插一层「铰链」空物体**承载摆动（XYZ 欧拉下"X 轴水平 ⇒ Z 轴必竖直"故不能一步到位）；**拍频公式** `θ_i = 2π(t·f_i − sync·(f_i−1))/period`、`f_i = 1 + spread·i/7` ⇒ 依次展开 → **sync 帧精确同步** → 之后错位；★ 5.2 `DriverTarget.id` 必须先 `id_type='SCENE'`、★ **批量脚本中途失败会留半改造状态**、★ 定位空对象常无旋转（朝向必须问用户） | [射灯阵列径向摆动绽放系统](../docs/射灯阵列径向摆动绽放系统.md) / [`../scripts/spot-bloom-swing/`](../scripts/spot-bloom-swing/) |
| `blender-volume-beam-feather` | **射灯光柱可见 + 边缘羽化**：闭合锥体当体积域 + 局部体积材质。★ **`Principled Volume` 的 Emission 不受 `Density` 控制**（Density 接 `Value=0` 画面**依然亮**且比 0.8 浓度**更亮**）⇒ 渐变**必须同时接 `Emission Strength`**（边缘过渡宽度实测 **6px → 18px**）；★ 轴向收尾的**端点必须精确到 0**（线性底值留 5% ⇒ 远端被几何**平切**一条硬边），要调渐变终点**别用 `ColorRamp`**（色标位置连不上节点）而用 `MapRange` 的 `From Max`；★ **5.2 `nodes.remove()` 后旧节点引用失效**（`out.name` 读乱码 / **链接静默丢失**）⇒ 删完**重新遍历**取输出节点；★ 材质烘焙 R/L ⇒ 只有 `spot_size`/`cutoff_distance` 完全一致的灯才能共用一份材质；★★★ **换文件级 operator 绝不许通过桥送进用户会话**（实测崩会话、未存盘改动全丢） | [体积光柱羽化系统](../docs/体积光柱羽化系统.md) / [`../scripts/volume-beam-feather/`](../scripts/volume-beam-feather/) |
| `blender-project-prescan` | **动手整理前的只读体检**（三段扫描：结构 → 定向 → 精查）：工程画像 / 目标材质与目标件清单 / **分组口径对比**（按材质 · 按材质+父级 · 按材质+顶层祖先）/ 红线与风险项（多实例、join 丢修改器、父级摘除）/ 顺带可清项，落成一份可交付的「意见清单」。**只读，绝不改工程**；扫完直接交给 `blender-headless-batch` 执行。含三条最易被忽略的判据：`join` 只保留活动对象的修改器、**有面槽** vs 槽总数、单件组无收益 | Skill `blender-headless-batch`；前置分析脚本 [`../scripts/merge-by-material/analyze_materials.py`](../scripts/merge-by-material/analyze_materials.py) |
| `blender-headless-batch` | **不开 GUI、用命令行无头处理巨型工程**（`--background`）：按材质合并海量网格降对象数、工程结构扫描、删除集合。含**四个实测致命的坑**（共享 mesh 数据块 + 多段 join 让几何**重复计入**、一次性 join 几千对象 **Calloc 溢出崩溃**、**跨组选中状态泄漏**、excluded 集合里对象的 `matrix_world` 不被求值）、**两级 join**（大组必用）、**网格数据独立化**、活动对象必须挑带「按角度平滑」的、**风险组判定**（跨集合 / 不在视图层 / 修改器不一致 ⇔ 整组跳过）、**世界变换烘焙**（不烘焙模型会散架）、join 性能真相（开销看**对象数**而非几何量）、后台跑与 CPU 判定法、**重开复核**铁律、**性能验收四口径**（会更快、但快在操作响应而非渲染帧率）、以及「重名是假警报」的几何指纹判据（**两个工程合并另见下条 `blender-blend-append-merge`**） | [按材质合并为单个网格体](../docs/按材质合并为单个网格体.md) / [`../scripts/merge-by-material/`](../scripts/merge-by-material/) |
| `blender-blend-append-merge` | **把两个 `.blend` 追加合并成一个**：核心结论是 **append 耗时 ≈ 15 ms × 被追加的对象数**（与几何/贴图量几乎无关）⇒ **以对象少的一边为底、追加对象多的那边**（实测 458 s vs 7 s，差 **80 倍**）；含三个必踩的坑（**重名去重「按 `.NNN` 数字后缀续号」会链式挪号、3.4% 的对象被改名**、**直接挂在场景根下、不属任何集合的游离对象会整批漏掉**、**世界与场景设置不随集合追加**）与**不依赖名字的多重集（Counter）对账口径** | [追加合并两个工程](../docs/追加合并两个工程.md) / 脚本包随 skill 自带 `scripts/`（`merge_append.py` / `verify_append.py` / `dump_b_baseline.py` / `probe_append_speed.py` / `probe_missing.py` / `smoke/`） |
| `blender-region-batch-delete` | **按覆盖区框选批量删除对象**（俯视 Z 轴，走 `--background` 无头通道）：用户放好带关键字（如「Z轴覆盖范围」）的网格体当"区域标记"，**俯视 = 忽略 Z** ⇒ 世界 XY 二维矩形包含。★★ **退化矩形（EMPTY/CAMERA/LIGHT 零尺寸）走四角点分流**（面积判据对它们恒真 ⇒ 会把全工程空物体与相机全删）、★★ **并集格网分解**（不能拆成"在 R1 或 R2"）、★★ **区外子级先冻结 keep-transform**（否则被连带删除/瞬移）；含**删除方法实测选型表**（`batch_remove` 23 ms/对象 vs 逐个 `remove` 124 ms，换参数零收益）、**三重闸**（只写新文件 / 干跑数不符即退 / 冻结外部子级）+ **重开复核**（硬判据"区内残留 = 0"，对象数带容差） | [覆盖区框选批量删除对象](../docs/覆盖区框选批量删除对象.md) / [`../scripts/region-batch-delete/`](../scripts/region-batch-delete/) |
| `blender-sweep-angle-material` | **平面上的多角度扫光 + 两层渐变相乘合成**：扫过方向 = **0–360° 的 UV 平面角度**（0° 沿 +U、90° 沿 +V、180° 反向），核心是**二维方向投影** `t = (u·cosθ + v·sinθ)/(\|cosθ\|+\|sinθ\|)` —— ★ **分母是必须的**（值域宽度是 `\|cosθ\|+\|sinθ\|`，45° 时 √2；不归一化则角度一拨条纹凭空多出 1.41 倍），**θ=0° ⇒ t ≡ u，与原版逐点相同**；水平层全白 = 中性（逐像素实测最大差 **0.00392**，等于没接）；5 旋钮挂**空对象**、**ColorRamp 零驱动**留给手调。★ `ShaderNodeMix` 的 **`Factor=0` 不是纯相乘**（退化成只取 A，必须 1.0）、★ 改驱动**变量**必须**原子重建**、★ `SINGLE_PROP` 先 `id_type` 后 `id`（补充变量循环顺序反了 ⇒ **数值减半**）、★★ 核验两个**自证陷阱**：沿 t 的剖面**要先按 1.0 取模再分箱**（否则 180° 的负 t 被丢 ⇒ 条数塌成 1）、**别拿 t 剖面验镜像**（采样方向跟着 t 一起翻，再 `[::-1]` 就翻了两次）⇒ **直接比像素**（镜像差 `0.001884` vs 同向差 `0.273658`） | [渐变扫过材质 · UV 方向角](../docs/渐变扫过材质-UV方向角.md) / [`../scripts/sweep-angle-material/`](../scripts/sweep-angle-material/) |

二十个是**分层**关系：`blender-bridge-ops` 管「怎么把代码送进正在运行的 Blender」，
其余十五个各管一件事（都走桥）：`blender-scene-cleanup` 清理、`blender-render-blackout-diagnose` 查画面不对、
`blender-overlap-difference` 去重叠、`blender-procedural-emission-material` 做程序化发光材质与控件、
`blender-plane-procedural-material` 用平面验收材质、`blender-radial-pulse-material` 做径向距离场脉冲材质、
`blender-inward-pulse-material` 做径向**内收多脉冲**材质（环数恒定的约束解算）、
`blender-sweep-angle-material` 做**平面多角度扫光**（0–360° UV 角度 + 两层渐变相乘合成）、
`blender-cylinder-spiral-material` 做圆柱面螺旋斜纹发光材质（滚筒）、
`blender-radar-scan-material` 做**雷达扫描空间材质**（极坐标角度场 + 拖尾，沿某世界轴投射）、
`blender-split-flap-flip` 做**翻页牌批量翻页动画**（中缝轴 + 单重补偿，绕开非受信任文件的 SCRIPTED 限制）、
`blender-spot-bloom-swing` 做**环形射灯径向摆动绽放**（铰链层 + 拍频同步）、
`blender-volume-beam-feather` 让**射灯光柱可见且边缘羽化**（体积域 + 径向/轴向两层衰减）、
`blender-driver-param-maintenance` 给**已建成**的参数化系统做维护（引用体检 / 关键帧收敛 / 改名换轴）、
`blender-loop-keyframe-anim` 给自定义属性批量写**循环三角波关键帧动画**（Slotted Action + CYCLES）。
其中 `blender-plane-procedural-material` / `blender-radial-pulse-material` / `blender-inward-pulse-material`
三者的**母 skill 是 `blender-procedural-emission-material`**（通用机制在那边）；
`blender-cylinder-spiral-material` / `blender-radar-scan-material` / `blender-sweep-angle-material`
是**同类并列的专项材质**（各自独立、开头互相索引）；
`blender-driver-param-maintenance` 与之并列，管的是同一套系统的**运维**而非新建；
`blender-loop-keyframe-anim` 是**动画写入类**（继承 bridge 传输层，管关键帧而非材质）；
各 skill 开头均引用 `blender-bridge-ops`。

剩下四个 —— `blender-project-prescan`、`blender-headless-batch`、
`blender-blend-append-merge` 与 `blender-region-batch-delete` —— 走**另一条通道**，
按「**先扫描 → 后执行 → 两个工程合并另起一条 → 覆盖区批量删除**」配成一组，且都不引用 `blender-bridge-ops`：

> ⚠️ 它们用的是 `blender.exe --background --python <脚本>` 的**系统命令行**，不是 9877 桥。
> 区别在于：桥有 **120s 超时**且要求 Blender 正在运行；合并这类改动动辄几分钟，
> 而且目标工程往往大到 GUI 里打不开 —— 这两件事桥都干不了。
> 分工是：`blender-project-prescan` 只读出「意见清单」与分组口径选项（**只读，绝不改工程**），
> `blender-headless-batch` 拿着清单动手改（含「按材质合并」这类**同工程内**的整理，两边共用脚本包
> [`../scripts/merge-by-material/`](../scripts/merge-by-material/)）；`blender-blend-append-merge` 专管
> **把两个工程并成一个**（对象数以万计、耗时以分钟计，必须选对「以谁为底」）。

## 安装

⚠️ **只拷 `skills/` 会留下断链** —— 多数 SKILL.md 用 `../scripts/<包>/` 与 `../docs/<文>.md` 引用同级目录，
所以必须**连同 `scripts/` 与 `docs/` 一起**拷到同一个父目录下（相对路径才成立）。

拷到用户级 skill 目录（Windows，三件套一起拷）：

```powershell
$dst = "$env:USERPROFILE\.workbuddy\skills"
# 1) 17 个技能本体
Copy-Item .\skills\* $dst -Recurse -Force
# 2) 共享脚本包 —— 供 SKILL.md 里的 ../scripts/<包>/ 解析
Copy-Item .\scripts   $dst -Recurse -Force
# 3) 配套文档 —— 供 SKILL.md 里的 ../docs/<文>.md 解析
Copy-Item .\docs      $dst -Recurse -Force
```

装完**务必跑一次断链校验**（下面的脚本会把每个带路径的引用逐一解析）：

```bash
python - <<'PY'
import os, re
SK = os.path.expanduser("~/.workbuddy/skills")
ref = re.compile(r'((?:\.\./)*[A-Za-z0-9_\u4e00-\u9fff-]+(?:/[A-Za-z0-9_\u4e00-\u9fff.-]+)+\.(?:py|md))')
bad = 0
for d in sorted(os.listdir(SK)):
    p = os.path.join(SK, d, "SKILL.md")
    if not os.path.isfile(p): continue
    for r in sorted(set(ref.findall(open(p, encoding="utf-8").read()))):
        if r.startswith("http") or r.startswith("_bridge/"): continue
        if not (os.path.exists(os.path.normpath(os.path.join(os.path.dirname(p), r)))
                or os.path.exists(os.path.normpath(os.path.join(SK, r)))):
            print("MISS", d, "->", r); bad += 1
print("断链:", bad)
PY
```

判据：**断链 = 0**。非 0 说明漏拷了 `scripts/` 或 `docs/`，或 SKILL.md 里的相对层级写错（见下）。

> **相对层级约定（易错）**：从 `skills/<名>/` 出发，正确写法是 **`../scripts/`** 与 **`../docs/`**（一级）。
> 写成 `../../scripts/`（两级）会落到安装根之外，静默断链 —— 本文件早期版本与
> `blender-driver-param-maintenance` / `blender-inward-pulse-material` 两个 SKILL.md 都踩过，已于 2026-09-20 修正。


拷完目录结构应为：

```
~/.workbuddy/skills/
├── blender-bridge-ops/SKILL.md
├── blender-scene-cleanup/
│   ├── SKILL.md
│   └── scripts/{purge_empties.py, verify_purge.py, snapshot_baseline.py}
├── blender-render-blackout-diagnose/
│   ├── SKILL.md
│   └── scripts/diagnose_blackout.py
├── blender-overlap-difference/
│   ├── SKILL.md
│   └── scripts/{cull_overlap.py, probe_overlap.py, render_classify.py, restore_from_backup.py}
├── blender-procedural-emission-material/
│   ├── SKILL.md
│   └── scripts/{build_noise_scroll.py, verify_noise_scroll.py, verify_lights.py, restore_lights.py, ...}
├── blender-plane-procedural-material/
│   ├── SKILL.md
│   └── scripts/{plane_testcard.py, probe_plane.py, probe_threshold_e2e.py, ...}
└── blender-radial-pulse-material/
    ├── SKILL.md
    └── scripts/{radial_field.py, cycle_pulse.py, verify_field.py, self_test.py, shoot_modes.py}
└── blender-inward-pulse-material/
    ├── SKILL.md                  # 脚本包在 ../scripts/radial-inward-pulse/(与本目录不重复)
    └── (无自带 scripts —— 引用 ../scripts/radial-inward-pulse/)
└── blender-driver-param-maintenance/
    ├── SKILL.md                  # 脚本包在 ../scripts/driver-param-maintenance/(与本目录不重复)
    └── (无自带 scripts —— 引用 ../scripts/driver-param-maintenance/)
└── blender-loop-keyframe-anim/
    ├── SKILL.md
    └── scripts/{write_loop_anim.py, verify_loop_anim.py}
└── blender-blend-append-merge/
    ├── SKILL.md
    └── scripts/{merge_append.py, verify_append.py, dump_b_baseline.py, probe_append_speed.py, probe_missing.py, smoke/}
└── blender-headless-batch/
    └── SKILL.md                  # 脚本包在 ../scripts/merge-by-material/(与本目录不重复)
└── blender-project-prescan/
    ├── SKILL.md
    └── scripts/{scan_project.py, scan2.py, scan3.py}
└── blender-radar-scan-material/
    └── SKILL.md                  # 脚本包在 ../scripts/radar-scan-material/(与本目录不重复)
└── blender-region-batch-delete/
    └── SKILL.md                  # 脚本包在 ../scripts/region-batch-delete/(与本目录不重复)
└── blender-sweep-angle-material/
    └── SKILL.md                  # 脚本包在 ../scripts/sweep-angle-material/(与本目录不重复)
```

> 跑 `scripts/` 里的脚本前记得改顶部的 `OUT_DIR`（报告 / 名单 / 基线都写那里），同一 skill 下的脚本要一致。
> 脚本位置有两种约定（**不要混用**）：① **自带** `skills/<名>/scripts/`（如 plane / radius-pulse / blend-append-merge）；
> ② **引用** `../scripts/<名>/`、skill 目录下不放副本（如 `blender-inward-pulse-material` 与
> `blender-driver-param-maintenance`、`blender-radar-scan-material`、`blender-headless-batch`、
> `blender-region-batch-delete`、`blender-sweep-angle-material`）—— 后者的脚本**只维护一份**，无需两处同步。

> **例外：`blender-headless-batch`、`blender-blend-append-merge` 与 `blender-region-batch-delete` 的脚本不在桥里跑。**
> 它不用 `send.py`，而是 `blender.exe --background --factory-startup <blend> --python <脚本>.py`，
> 输出路径由 `--` 之后的命令行参数给（不是改顶部 `OUT_DIR`），日志与排除名单写在**当前工作目录**。
> `blender-blend-append-merge` 的脚本走**环境变量**传参（`AMB_WORK` / `AMB_SRC_A` / `AMB_SRC_B` /
> `MERGE_OUT` / `MERGE_STRAYS`），不设变量直接跑会 `raise SystemExit` 报「请先设环境变量」，
> **不会误改工程**。
