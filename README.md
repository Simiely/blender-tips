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

## Agent Skills(给 AI 助手用的作业规范)

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
