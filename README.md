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
| 33 | 按材质拆分为多个网格体 | 一个对象多材质槽 → 「**有面的**」槽各一个独立对象(整网格生效、与选择无关);原对象保留**「面序中首现最晚」**那组(不是"最后一个槽");附拆分前基线(含逐组锐边数)、11 组逐项验证、下游引用扫描。[独立文档](docs/按材质拆分为多个网格体.md) / [脚本包](scripts/separate-by-material/) |
| 34 | 空物体收敛清理 | 不支撑任何几何的 EMPTY 全清 —— 不能只删"无子级"的(删完会"长出"新的),要用**引用图 + 不动点**一次算准最终可删集;三重安全闸 + 独立核验(非 EMPTY 对象数 / 可见几何包围盒逐位不变)。附空集合、孤儿数据块连带处理。[独立文档](docs/空物体收敛清理.md) / [脚本包](scripts/scene-cleanup/) / [Skill](skills/blender-scene-cleanup/) |
| 35 | 渲染发黑与材质不发光排查 | "配了发光材质渲染还是黑的" —— 七条按命中率排序的排查路径:头号嫌疑是 **View Layer 材质覆盖**(它是视图层属性、不在材质里,在材质树里永远查不到);其次是 Workbench 引擎不读材质节点、Holdout/相机可见性、**发光值改在了未接输出的孤儿 BSDF 上**(实测第二层原因)、AgX 色彩变换压暗。附一次打全的诊断脚本(236 材质 0.05s)。[独立文档](docs/渲染发黑与材质不发光排查.md) / [脚本包](scripts/blackout-diagnose/) / [Skill](skills/blender-render-blackout-diagnose/) |

## Agent Skills(给 AI 助手用的作业规范)

`skills/` 目录收录 **Agent Skill**：`SKILL.md` 写清「怎么干、先干什么、什么绝对不能干」，
并把配套脚本作为附件带上，让 AI 助手不必每次重新推演流程与安全闸。

| Skill | 作用 | 关联 |
|---|---|---|
| [blender-bridge-ops](skills/blender-bridge-ops/) | 9877 桥的**传输层作业规范**：客户端封装、120s 上限规避、Blender 5.x Slotted Action、引用判定、删除后引用失效 | [§1](docs/技巧速查.md#1-远程控制运行中的-blender) / [脚本包](scripts/blender-remote-control/) |
| [blender-scene-cleanup](skills/blender-scene-cleanup/) | 工程**清理类**改造：EMPTY 收敛清理(不动点)、孤儿数据块、空集合、缺失贴图审计与还原 | [主题 34](docs/空物体收敛清理.md) / [脚本包](scripts/scene-cleanup/) |
| [blender-render-blackout-diagnose](skills/blender-render-blackout-diagnose/) | **渲染发黑 / 材质不发光**排查：材质覆盖、引擎不读材质、Holdout、输出未连线或改错节点、AgX 压暗等七条路径 | [主题 35](docs/渲染发黑与材质不发光排查.md) / [脚本包](scripts/blackout-diagnose/) |

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
