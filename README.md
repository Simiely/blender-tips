# Blender 5.x 技巧速查

> 日常 Blender 踩坑与可复用技巧的速查手册,按主题索引。
> 遵循 knowledge-base [单项目规范](https://github.com/Simiely/knowledge-base/tree/main/模板库/单项目规范)。

## 这是什么

记录在 Blender(当前环境 5.2)实战中验证过的技巧,每个主题含**场景 → 做法 → 坑**。覆盖:

| # | 主题 | 一句话 |
|---|---|---|
| — | **材质与驱动规范** | 灯光材质系统完整手册(命名/圆柱投影/驱动/坑),[独立文档](docs/材质与驱动规范.md) |
| 1 | 远程控制运行中的 Blender | Socket 桥,无需插件,一次配置反复用 |
| 2 | 自定义属性 + 驱动控显隐 | 空物体开关 → 批量子对象显示/渲染 |
| 3 | 给自定义属性打关键帧 | 鼠标悬停属性值按 I |
| 4 | Blender 5.2 动画数据 API | Slotted Action,不再用 action.fcurves |
| 5 | 关键帧插值机制 | 插值=从该帧到下一帧;末帧不生效 |
| 6 | C4D 式"中间平滑+两头线性" | Free handle 手动对齐线段 |
| 7 | 合成器与渲染输出(5.2) | 节点组=输出开关;PNG 序列配置 |
| 8 | Cycles 渲染提速 | GPU/OptiX、降噪、降采样 |
| 9 | 渲染白膜(材质覆盖) | 视图层 Material Override,非破坏性 |
| 10 | 时间轴整体前移 | 关键帧+标记+渲染范围批量平移,负帧保护 |
| 11 | 关键帧小数帧(.5帧) | 拖动未吸附产生;round() 会掩盖,需精确检测 |
| 12 | 首尾帧交换/反转 | 没有"反转关键帧",用镜像沿时间轴关于当前帧 |
| 13 | 时间轴标记管理 | 增删移 + 中文菜单路径 |
| 14 | 大场景去重优化 | 重复网格合并共享数据(实例化),省 58% 数据块 |
| 15 | 打组/轴心位置保持 | parent 后手动 mpi,避免世界位置翻倍 |
| 16 | 循环渐变色 | ColorRamp 三色自然循环(平台+过渡+首尾同色) |
| 17 | 圆柱贴图/理发店滚筒 | atan2+高度+FLOORED_MODULO;Object坐标不跟随旋转 |
| 18 | 3ds Max 导入场景清理与轴心修复 | 缺失数据诊断/空物体清理/轴心安全流程(先 Apply 再设原点)/动画清理,[独立文档](docs/3dsmax导入场景清理与轴心修复.md) |
| 19 | 驱动式上下浮动噪声系统 | 一组物体丝滑阻尼感上下浮动,全局大波+局部错动,滑块实时调,[独立文档](docs/驱动式上下浮动噪声系统.md) / [脚本包](scripts/driver-bob/) |
| 20 | 驱动式 Z 轴匀速旋转系统 | 空物体绕 Z 轴匀速转,一个速度滑块共用,可各自正/反向,实时调速,[独立文档](docs/驱动式Z轴匀速旋转系统.md) / [脚本包](scripts/driver-spin/) |
| 21 | 视口预览录制(录屏式) | 从场景相机抓视口画面导出 mp4,非全渲染,快速看效果,[独立文档](docs/视口预览录制录屏式.md) / [脚本包](scripts/playblast/) |
| 22 | 集合内对象数据独立化 | linked duplicate 共享数据块 → 每对象独立副本,复制/导出不再联动,[独立文档](docs/集合内对象数据独立化.md) / [脚本包](scripts/make-independent/) |
| 23 | 天空太阳控制驱动 | 天空 sun_elevation/sun_rotation 接「太阳高度/太阳角度」滑块(度);数字驱动版 + 命名空间函数版(实时读属性),[独立文档](docs/天空太阳高度驱动.md) / [脚本包](scripts/driver-sky/) |
| 24 | 运动网格灯光方案 | 驱动浮动网格轴心加向上/向下双灯,跟随运动+偏移微调+旋转联动,[独立文档](docs/运动网格灯光方案.md) / [脚本包](scripts/driver-lights/) |
| 25 | 渐变发光滚动材质 | 竖图渐变自发光+竖直匀速滚动,速度滑块驱动,[独立文档](docs/渐变发光滚动材质.md) / [脚本包](scripts/glow-scroll-material/) |
| 26 | 输出路径与序列帧输出规范 | 相对路径 `//`+`output/<批次>`+`#` 帧序号命名;`media_type→file_format` 顺序,[独立文档](docs/输出路径与序列帧输出规范.md) |
| 27 | 速度驱动灯光亮度 | 灯亮度随目标Z轴运动速度增强/衰减,前向差分求速+按高度分档,[独立文档](docs/速度驱动灯光亮度.md) / [脚本包](scripts/speed-light/) |
| 28 | 材质参数统一控制器与实时面板 | 多材质共用一圆心+一套参数(同心圆扩展灯),控制空物体驱动 + Register 文本块实时面板,重开自恢复,[独立文档](docs/材质参数统一控制器与实时面板.md) / [脚本包](scripts/ring-control-panel/) |
| 29 | 帧窗口驱动时间开关 | 让节点参数按帧区间开/关(如渐变效果 517–657 有效),命名空间函数 + SCRIPTED 驱动读 frame;避开 5.2 Value 节点关键帧在 Slotted Action 下不生效的坑,[独立文档](docs/帧窗口驱动时间开关.md) / [脚本包](scripts/frame-window-time-switch/) |
| 30 | 粒子系统礼花喷射方案 | 粒子系统 + 碰撞杀死 + 湍流场实现持续向上喷射金色纸片,[独立文档](docs/粒子系统礼花喷射方案.md) / [脚本包](scripts/firework-confetti/) |
| 31 | 动画转移到父级空对象(动态转移) | 把对象自身关键帧动画整份搬到新建父级空对象,本体退化为纯被驱动(本地全零);世界运动逐帧恒等,附「录基线→转移→逐帧对基线」验证器,[独立文档](docs/动画转移到父级空对象.md) / [脚本包](scripts/anim-transfer-to-empty/) |
| 32 | 位移坐标系:沿自身轴 / 沿世界轴运动 | 物体轴向与世界轴不一致时,K 出来的 `location` 两者都不是(它属于"父空间基底",`delta_location` 同坐标系);两条对称做法 —— 朝向/位移分层→沿自身轴,世界对齐层/世界空间约束→沿世界轴,附诊断器与逐帧验证器,[独立文档](docs/轴向位移-自身轴与世界轴.md) / [脚本包](scripts/axis-space-motion/) |
| 33 | 按材质拆分为多个网格体 | 一个对象多材质槽 → 「**有面的**」槽各一个独立对象(整网格生效、与选择无关);原对象保留**「面序中首现最晚」**那组(不是"最后一个槽");附拆分前基线(含逐组锐边数)、11 组逐项验证(孤儿 mesh 判据取**基线差集**,工程原有的历史孤儿不算失败)、下游引用扫描。[独立文档](docs/按材质拆分为多个网格体.md) / [脚本包](scripts/separate-by-material/) |
| 34 | 空物体收敛清理 | 不支撑任何几何的 EMPTY 全清 —— 不能只删"无子级"的(删完会"长出"新的),要用**引用图 + 不动点**一次算准最终可删集;三重安全闸 + 独立核验(非 EMPTY 对象数 / 可见几何包围盒逐位不变)。附空集合、孤儿数据块连带处理。[独立文档](docs/空物体收敛清理.md) / [脚本包](scripts/scene-cleanup/) / [Skill](skills/blender-scene-cleanup/) |
| 35 | 渲染发黑与材质不发光排查 | "配了发光材质渲染还是黑的" —— 七条按命中率排序的排查路径:头号嫌疑是 **View Layer 材质覆盖**(它是视图层属性、不在材质里,在材质树里永远查不到);其次是 Workbench 引擎不读材质节点、Holdout/相机可见性、**发光值改在了未接输出的孤儿 BSDF 上**(实测第二层原因)、AgX 色彩变换压暗。附一次打全的诊断脚本(236 材质 0.05s)。[独立文档](docs/渲染发黑与材质不发光排查.md) / [脚本包](scripts/blackout-diagnose/) / [Skill](skills/blender-render-blackout-diagnose/) |
| 36 | 径向内收多脉冲材质 | 若干个同心亮环**从外往内收**、无缝循环、黑边很细;核心是**环数恒定**的约束解算 —— 可见带窗口 `L + 占空比 − 软边 − 2×最小可见宽度 ≈ N`(**三项缺一,环数就在 N±1 之间跳**),以及**计数基准**的选择(内切圆 vs 角点,相差 √2 倍);另含亮面裁切(把发光限制在圆内)、从姊妹材质读 ColorRamp 复制配色、**驱动只能挂 Value 节点**的守卫。[独立文档](docs/径向内收多脉冲材质.md) / [脚本包](scripts/radial-inward-pulse/) / [Skill](skills/blender-inward-pulse-material/) |
| 37 | 径向材质多位置部署与播放时差 | 同一套径向材质部署到多个位置:动态定位 + 复制材质与控制器到新圆心(**`_位N` 自动编号、防叠名**);**三层共享判别**(网格数据/材质/控制器——「改一个其它跟着变」的三种成因)与**快照式独立化**(不能一边遍历一边判 `users>1`,会漏一整批);**播放时差 = 相位偏移**(时间错位 ≡ 相位偏移,脉冲类改 TVAL 关键帧值);材质 `users=0` 无 fake 会被存盘清掉、未挂载的材质不进依赖图。[独立文档](docs/径向材质多位置部署与时差.md) / [脚本包](scripts/radial-inward-pulse/) |
| 38 | 驱动参数化材质维护:引用体检 / 关键帧收敛 / 改名换轴 | 给**已建成**的「空物体属性 + 驱动器」系统做运维改造:**改前**跑引用体检(扫描必须含 `物体数据 → node_tree` 层 —— 灯光/网格自带节点树、驱动都挂那里;漏扫会**双向出事**:误判"假控件" 或 改名后 7 条驱动 `is_valid=False` 静默失效),**改后**跑失效体检(`is_valid` + 悬空引用,判据 **0 条**);含「关键帧 → 常量」的存档纪律(先留 `(帧,值)` 全表再删)与驱动换轴六步顺序(`driver_add` 会把表达式自动填成常量、**驱动重建完才准删旧属性键`)、三个容易混淆的「index」对照。[独立文档](docs/驱动参数化材质维护.md) / [脚本包](scripts/driver-param-maintenance/) / [Skill](skills/blender-driver-param-maintenance/) |
| 39 | 星芒散射光效系统 | 参数化星芒 + 沿相机朝向的亮片散射:一个被隐藏的单面"源"平面借 `星芒_GN` 几何节点生成星芒形状,三个点云宿主各挂一份 `星芒_散布_GN` 把它实例化到每个点,并经 `ObjectInfo(RELATIVE)` 继承源缩放 + `对齐欧拉至矢量(空物体)` 做 billboard + SceneTime 错相缩放动画 + 设置位置偏移;`星芒_控制器` 6 个中文滑块统一控形状/大小/循环脉冲。源隐藏渲染不影响散布实例。[独立文档](docs/星芒散射光效系统.md) / [脚本包](scripts/starburst-scatter/) |
| 40 | 循环三角波关键帧动画 (Skill) | 给自定义属性批量写「循环三角波关键帧动画」:一个完整周期进 fcurve + CYCLES 循环修饰器铺满帧范围;沉淀 5.x Slotted Action 正确写入路径、FModifierCycles 无 mode 属性、关键帧值精确写入绕被驱动干扰、is_valid 判空、depsgraph 读被驱动值。[Skill](skills/blender-loop-keyframe-anim/) |
| 41 | 雪花下落系统 | 参数化连续下雪:一个隐藏的低模雪花源 + 一个 EMPTY 宿主上的 `下雪_GN` 节点组,按真实雪速(~0.5 m/s)下落 50000 片;`SceneTime→FLOORED_MODULO` 触地回卷(贴地消失无半空消失)、`RandomValue(ID←Index)` 独立相位/落点/朝向防堆积、顶部 `MapRange` 入场缩放;宿主变换必须清零锚定地面参考平面。[独立文档](docs/雪花下落系统.md) / [脚本包](scripts/snowfall-scatter/) |
| 42 | 空物体父级整体挪动集合 | 新建 Empty + 选中集合对象 + Ctrl+P 挂父级:以后只动 Empty,整个集合整体偏移,对象自身关键帧动画不受影响;核心机制 = 三段矩阵链与 Parent Inverse 快照;只挂顶层防断链;含 Ctrl+P 三选项对照、实测坑与集合实例化对比,[独立文档](docs/空物体父级整体挪动集合.md) |
| 43 | 按材质合并为单个网格体 | 对象太多导致 GUI 卡死的**治本办法**(是 [主题 33](docs/按材质拆分为多个网格体.md) 的反向操作):**不开 GUI** 用 `blender --background` 命令行无头处理,把材质组合相同的对象合并掉 —— 实测 24,481 → **56** 个对象、顶点/面(10,197,620 / 7,957,765)**严格守恒**、模型包围盒偏差 0;三大要点:**join 前必须烘焙世界变换**(否则模型散架)、join 开销看**对象数**不看几何量(24,137 个对象的组吃掉 98% 时间,332 万顶点的组只用 0.1s)、进程内守恒 ≠ 文件能打开所以**必须重开复核**。附多实例红线(`mesh.users>1` 会让文件反而变大)、排除名单、小场景自测台。[独立文档](docs/按材质合并为单个网格体.md) / [脚本包](scripts/merge-by-material/) / [Skill](skills/blender-headless-batch/) |
| 44 | 追加合并两个工程 | 把两个 `.blend` **追加合并成一个**（`bpy.ops.wm.append`）：核心是 **append 耗时 ≈ 15 ms × 被追加的对象数**（与几何/贴图量几乎无关）⇒ **以对象少的一边为底**（实测 458 s vs 7 s，**差 80 倍**）。三个必踩的坑：**重名去重「按 `.NNN` 后缀续号」会链式挪号、3.4% 对象被改名**（链接/变换/几何全对，只是名字不可靠）、**挂在场景根下、不属任何集合的游离对象整批漏追**、**世界与场景设置不随集合追加**。对账口径用**多重集**而非名字。[独立文档](docs/追加合并两个工程.md) / [Skill](skills/blender-blend-append-merge/) |
| 45 | 分体翻页牌驱动翻页系统 | 报刊亭/机场翻页牌整块动起来：每张卡建一个**中缝轴 Empty** 挂在几何中心（卡片轴心常在角落，直接转就绕角甩），**单重补偿**挂接保持世界位置；**总转角必须是 360 的整数倍**（3 圈 = 1080°）才能落回初始朝向——半圈结束是背面朝外、看不到字；缓动用 **smoothstep**（二次曲线会急停）；相位 `((列+行)%8)×2` 出**斜向波浪**。★ 两大真坑：**非受信任打开的 .blend 里 SCRIPTED 驱动静默不求值**（运行时开偏好也救不活，改用 `frame_change_post` 处理器）、**驱动表达式必须返回 `radians()`**（写度数 1080 → 61879°，35 张卡全歪）；★ 处理器不写进 .blend，**存盘前必须停静止帧**否则重开僵在半翻姿态。实测 35 张卡同时约 9~10 张在翻。[独立文档](docs/分体翻页牌驱动翻页系统.md) / [脚本包](scripts/flip-card/) / [Skill](skills/blender-split-flap-flip/) |
| 46 | 射灯阵列径向摆动绽放系统 | 一圈射灯各自**锁在自己的竖直径向平面**里摆动,像花开合:起始线 = 灯→中轴线对象的连线(中轴被抬高时是**倾斜**的),旋转轴 = 水平切向 `ẑ × r̂`;必须**插一层「铰链」空物体**承载摆动(灯的局部旋转 = `π/2 + 起始线仰角`,XYZ 欧拉下"X 轴水平 ⇒ Z 轴必竖直"导致不能一步到位);**拍频公式** `θ_i = 2π(t·f_i − sync·(f_i−1))/period`、`f_i = 1 + spread·i/7` ⇒ 起初依次展开、**sync 帧精确同步**、之后错位,同步瞬间的展开角由 **`sync/period` 的小数部分**决定(2.5→全开 / 2.0→全闭合),对齐周期 `7×period/spread`(默认 16800 帧);★ 5.2 `DriverTarget.id` 必须先 `id_type='SCENE'`(否则只接受 Object)、★ **批量脚本中途失败会留半改造状态**(实测 8 盏只改了 1 盏,朝向跟其余不一致)、★ 桥 exec 整段代码、异常会让前面所有 print 全丢 ⇒ 先探 API、★ 定位空对象常无旋转(朝向缺失,必须问用户)。[独立文档](docs/射灯阵列径向摆动绽放系统.md) / [脚本包](scripts/spot-bloom-swing/) / [Skill](skills/blender-spot-bloom-swing/) |
| 47 | 体积光柱羽化系统 | 让射灯的光柱在 Cycles/EEVEE 里**可见且边缘柔和**:闭合锥体当体积域 + 局部体积材质。★ **决定性发现——`Principled Volume` 的 Emission 不受 `Density` 控制**(实测 `Density` 接 `Value=0.0` 画面**依然亮**,而且比 0.8 浓度**更亮**:浓度低→吸收少→自发光累积更多)⇒ **只把渐变接 Density 是白费的**,必须**同时接 `Emission Strength`**(边缘 50%→10% 过渡宽度实测 **6px → 18px**);径向衰减 `1 − ρ^p`、`ρ = √(x²+y²)/radius(z)`(锥局部坐标 `radius(z)=R/2−R·z/L`);★ 5.2 **`nodes.remove()` 之后旧节点引用会失效**(`out.name` 读乱码抛 `UnicodeDecodeError`、`out.inputs["Volume"]` 抛 `KeyError`,更阴的是**链接静默丢失**)⇒ 删完必须**重新遍历**取输出节点;★ 改自定义属性后**依赖图不自动重算**,脚本要 `id.update_tag()`(GUI 拖滑块会自动打 tag),驱动器求值**有延迟**(同一脚本内读到旧值);参数用**场景自定义属性(中文键=显示名)+ `AVERAGE` 型驱动器**做成滑块(避开非受信任文件里 SCRIPTED 静默不求值);★ 材质里**烘焙了 R/L 常量** ⇒ 只有 `spot_size`/`cutoff_distance` **完全一致**的灯才能共用一份材质(实测 8 盏共用 = **同一组驱动器**,改一个数全变);★★★ 血泪铁律:**换文件级 operator(`read_factory_settings`/`read_homefile`/`wm.open_mainfile`)绝不许通过桥送进用户正在用的会话** —— 实测卡死并崩溃、**未存盘改动全丢**。[独立文档](docs/体积光柱羽化系统.md) / [脚本包](scripts/volume-beam-feather/) / [Skill](skills/blender-volume-beam-feather/) |

## Agent Skills(给 AI 助手用的作业规范)
| 39 | 滚筒斜纹材质 | 圆柱面上的**螺旋斜条纹**发光材质:条纹斜着沿柱身流动(右下→左上)。核心是**波形放 Math 域**而不是让 ColorRamp 兼职 —— 后者会把参数耦合、色标被驱动锁死、拖尾长度被结构卡在 58%;含**两套并列调参方案**(按条数 / 按角度,跑哪个装哪个)、端盖按法线单独分槽(否则条纹摊成扇形风车),以及 5 条渲染管线级实测坑(隔离场景驱动不被求值 / images 按路径缓存 / pixels 返 sRGB / ortho_scale 对应较长边 / 比对前先自证 φ 映射)。[独立文档](docs/滚筒斜纹材质.md) / [脚本包](scripts/streak-material/) / [Skill](skills/blender-cylinder-spiral-material/) |

`skills/` 目录收录 **Agent Skill**：`SKILL.md` 写清「怎么干、先干什么、什么绝对不能干」，
并把配套脚本作为附件带上，让 AI 助手不必每次重新推演流程与安全闸。

| Skill | 作用 | 关联 |
|---|---|---|
| [blender-bridge-ops](skills/blender-bridge-ops/) | 9877 桥的**传输层作业规范**：客户端封装、120s 上限规避、Blender 5.x Slotted Action、引用判定、删除后引用失效 | [§1](docs/技巧速查.md#1-远程控制运行中的-blender) / [脚本包](scripts/blender-remote-control/) |
| [blender-scene-cleanup](skills/blender-scene-cleanup/) | 工程**清理类**改造：EMPTY 收敛清理(不动点)、孤儿数据块、空集合、缺失贴图审计与还原 | [主题 34](docs/空物体收敛清理.md) / [脚本包](scripts/scene-cleanup/) |
| [blender-render-blackout-diagnose](skills/blender-render-blackout-diagnose/) | **渲染发黑 / 材质不发光**排查：材质覆盖、引擎不读材质、Holdout、输出未连线或改错节点、AgX 压暗等七条路径 | [主题 35](docs/渲染发黑与材质不发光排查.md) / [脚本包](scripts/blackout-diagnose/) |
| [blender-overlap-difference](skills/blender-overlap-difference/) | 让两个互相穿插的网格体「**物理上不重叠**」——用**面级剔除**替代布尔差集（只删目标件伸进刀具体的面，刀具体分毫不动）；含动刀前分类着色预览、三票制内外判定、布尔干跑评估、还原点与 `__BAK__` 撤回、独立核验 | 脚本包随 skill 自带：`skills/blender-overlap-difference/scripts/`（`cull_overlap.py` / `probe_overlap.py` / `render_classify.py` / `restore_from_backup.py`） |
| [blender-procedural-emission-material](skills/blender-procedural-emission-material/) | **世界空间程序化噪波滚动发光材质** + 全套数字控件：不用 UV，标准链 `纹理坐标→Mapping(滚)→噪波4D→ColorRamp(对比度)→×强度→Emission`；含 SINGLE_PROP 驱动、**看门狗定时器**自动刷新、AREA 面光灯节点树同构接入与**依赖环铁律**（驱动变量绝不能指向宿主自身属性） | [主题 25](docs/渐变发光滚动材质.md) / [主题 28](docs/材质参数统一控制器与实时面板.md) |
| [blender-plane-procedural-material](skills/blender-plane-procedural-material/) | **平面（flat plane）专项**：法线轴零跨度导致的坐标退化、**平面 = 3D 噪声体的一片切片**、把平面当**验收测试卡**出客观读数（暗区占比 / 滚动方向 / 位移的像素级测法） | 母 skill `blender-procedural-emission-material` / [主题 25](docs/渐变发光滚动材质.md) |
| [blender-radial-pulse-material](skills/blender-radial-pulse-material/) | **世界空间径向距离场发光材质**：图案只依赖到**共享中心的距离 r**（和方向 d）⇒ 共心的 XY/XZ/YZ 平面切过去天然同心、交线连续；含五种模式、**四段循环脉冲**（`TVAL≡帧号` 关键帧技巧 + 周期/相位分离：时长类参数只进周期就是空操作）、**空物体自定义属性 + SINGLE_PROP 驱动器**（数据驱动，不写面板）；附 Math 第 3 输入口 / 未连输入默认 0.5 / 接触表行序三个静默陷阱 | 母 skill `blender-procedural-emission-material` |
| [blender-inward-pulse-material](skills/blender-inward-pulse-material/) | **径向内收多脉冲**：若干同心亮环从外往内收、无缝循环；核心是**环数恒定的有效窗口公式**（`L + 占空比 − 软边 − 2×最小可见宽度 ≈ N`，缺一项环数就会在 N±1 间跳）与**计数基准的选择**（内切圆 vs 角点，相差 √2）；含亮面裁切把发光限制在圆内、从姊妹材质读 ColorRamp 复制配色、**驱动只能挂 Value 节点**的守卫 | [主题 36](docs/径向内收多脉冲材质.md) / [脚本包](scripts/radial-inward-pulse/) |
| [blender-driver-param-maintenance](skills/blender-driver-param-maintenance/) | **参数化驱动的运维改造**：两张体检表 —— `refs`（谁在读这个参数，**必须扫到 `物体数据 → node_tree`**，灯光 Shader Nodetree 层漏扫 ⇒ 误判"假控件" / 改名留静默失效驱动）、`health`（全库 `is_valid=False` + 悬空引用，判据 0 条）；含关键帧 → 常量的存档纪律、改名换轴六步（`driver_add` 自动填常量表达式、**驱动重建完才删旧键**）、三个易混的「index」 | [主题 38](docs/驱动参数化材质维护.md) / [脚本包](scripts/driver-param-maintenance/) |
| [blender-cylinder-spiral-material](skills/blender-cylinder-spiral-material/) | **圆柱面螺旋斜条纹发光材质**：斜纹走柱面坐标相位取模（`f = u×K − v×N` + `FLOORED_MODULO`），波形走 Math 域（`MapRange(SMOOTHSTEP)×2 + MINIMUM`，ColorRamp 零驱动只管颜色）；含两套并列调参方案（按条数 / 按角度，跑哪个装哪个）、端盖按**法线**单独分槽、**方向以实测标定**（纸面推导曾推反） | [主题 39](docs/滚筒斜纹材质.md) / [脚本包](scripts/streak-material/) |
| [blender-headless-batch](skills/blender-headless-batch/) | **不开 GUI 处理巨型工程**（**不走 9877 桥**、用 `--background` 命令行）：按材质合并海量网格降对象数、结构扫描、删集合；含多实例红线、**世界变换烘焙**（`CLEAR_KEEP_TRANSFORM`，不烘焙模型散架）、join 开销看**对象数**的非直觉真相、后台跑与 **CPU 增量判活法**、**重开复核**铁律、「重名是假警报」的几何指纹判据（**两个工程合并另见下条**） | [主题 43](docs/按材质合并为单个网格体.md) / [脚本包](scripts/merge-by-material/) |
| [blender-blend-append-merge](skills/blender-blend-append-merge/) | **把两个 `.blend` 追加合并成一个**（同走 `--background` 无头通道）：**append 耗时 ≈ 15 ms × 被追加的对象数**（与几何/贴图量几乎无关）⇒ **以对象少的一边为底**（实测 458 s vs 7 s，差 **80 倍**）；含三个坑（**链式挪号改名 3.4%** / **游离对象整批漏追** / **世界与场景设置不随集合追加**）与**多重集（Counter）对账口径** | [主题 44](docs/追加合并两个工程.md) / 脚本包随 skill 自带 `skills/blender-blend-append-merge/scripts/` |
| [blender-split-flap-flip](skills/blender-split-flap-flip/) | **翻页牌批量翻页动画**：中缝轴 Empty + **单重补偿**挂接（补偿两次会把卡片平移到 `T(-center)@orig`）、**总转角必须是 360 的整数倍**否则停在背面看不到字、smoothstep 缓动、斜向波浪相位；★ **非受信任文件里 SCRIPTED 驱动静默不求值**（改走 `frame_change_post` 处理器）、★ **驱动表达式必须返回 `radians()`**、★ **处理器不随文件保存 ⇒ 存盘前停静止帧**；含改前快照/改后核验与一键撤销 | [主题 45](docs/分体翻页牌驱动翻页系统.md) / [脚本包](scripts/flip-card/) |
| [blender-spot-bloom-swing](skills/blender-spot-bloom-swing/) | **环形射灯「花开/花闭合」径向摆动**：几何三要素（起始线 = 灯→中轴对象连线、**常被抬高而倾斜**；旋转平面 = 灯与竖直中轴；旋转轴 = 水平切向 `ẑ × r̂`）；**必须插「铰链」空物体**承载摆动（灯的局部旋转 `π/2 + elev` 有推导，XYZ 欧拉下"X 轴水平 ⇒ Z 轴必竖直"故不能一步到位）；**拍频公式** `θ_i = 2π(t·f_i − sync·(f_i−1))/period` ⇒ 依次展开 → sync 帧精确同步 → 错位，同步时展开角由 **`sync/period` 小数部分**决定；★ **批量脚本中途失败留半改造状态**、★ 5.2 `DriverTarget.id` 必须先 `id_type='SCENE'`、★ 空对象常无旋转（方向必须问用户） | [主题 46](docs/射灯阵列径向摆动绽放系统.md) / [脚本包](scripts/spot-bloom-swing/) |
| [blender-volume-beam-feather](skills/blender-volume-beam-feather/) | **射灯光柱可见 + 边缘羽化**：闭合锥体当体积域 + 局部体积材质。★ **`Principled Volume` 的 Emission 不受 `Density` 控制**（Density 接 `Value=0` 依然亮，且比 0.8 浓度更亮）⇒ 渐变**必须同时接 `Emission Strength`**；★ **5.2 `nodes.remove()` 后旧节点引用失效**（`out.name` 读乱码 / `out.inputs["Volume"]` KeyError / **链接静默丢失**）⇒ 删完重新遍历取输出节点；★ 改自定义属性后需 `update_tag()` 且驱动器求值有延迟；★ 材质烘焙 R/L ⇒ **只有几何完全一致的灯才能共用一份材质**；★★★ **换文件级 operator 绝不许通过桥送进用户会话**（实测崩会话、未存盘改动全丢） | [主题 47](docs/体积光柱羽化系统.md) / [脚本包](scripts/volume-beam-feather/) |
安装(拷到用户级 skill 目录)：`Copy-Item .\skills\* "$env:USERPROFILE\.workbuddy\skills\" -Recurse`，
详见 [skills/README.md](skills/README.md)。

## 文档

- [📖 技巧速查(完整内容)](docs/技巧速查.md)
- [🤖 AGENTS.md(给 AI/未来的你:关键坑速记)](AGENTS.md)
- [🔧 DEVELOPMENT.md(架构与问题记录)](DEVELOPMENT.md)
- [📜 CHANGELOG.md(版本历史)](CHANGELOG.md)

## 快速开始(远程控制桥)

1. Blender → Scripting 工作区 → 文本编辑器 **Open** 打开 `blender_bridge.py` → **Run Script**
2. 看到 `[Bridge v2] BRIDGE READY` 即成功
3. 外部客户端:`python send.py <code.py>` 发送代码到 `127.0.0.1:9877` 远程执行

> 桥脚本与客户端位于工作区 `blender_control/` 目录,详见 [docs/技巧速查.md](docs/技巧速查.md) §1。
