# Blender 5.x 技巧速查



> 日常 Blender 踩坑与可复用技巧的速查手册,按主题索引。

> 遵循 knowledge-base [单项目规范](https://github.com/Simiely/knowledge-base/tree/main/模板库/单项目规范)。



## 这是什么



记录在 Blender(当前环境 5.2)实战中验证过的技巧,每个主题含**场景 → 做法 → 坑**。覆盖:

## 主题索引

| # | 主题 | 入口 |
|---:|---|---|
| — | **材质与驱动规范** | [文档](docs/材质与驱动规范.md) |
| 1 | 远程控制运行中的 Blender | [速查](docs/技巧速查.md) |
| 2 | 自定义属性 + 驱动控显隐 | [速查](docs/技巧速查.md) |
| 3 | 给自定义属性打关键帧 | [速查](docs/技巧速查.md) |
| 4 | Blender 5.2 动画数据 API | [速查](docs/技巧速查.md) |
| 5 | 关键帧插值机制 | [速查](docs/技巧速查.md) |
| 6 | C4D 式"中间平滑+两头线性" | [速查](docs/技巧速查.md) |
| 7 | 合成器与渲染输出(5.2) | [速查](docs/技巧速查.md) |
| 8 | Cycles 渲染提速 | [速查](docs/技巧速查.md) |
| 9 | 渲染白膜(材质覆盖) | [速查](docs/技巧速查.md) |
| 10 | 时间轴整体前移 | [速查](docs/技巧速查.md) |
| 11 | 关键帧小数帧(.5帧) | [速查](docs/技巧速查.md) |
| 12 | 首尾帧交换/反转 | [速查](docs/技巧速查.md) |
| 13 | 时间轴标记管理 | [速查](docs/技巧速查.md) |
| 14 | 大场景去重优化 | [速查](docs/技巧速查.md) |
| 15 | 打组/轴心位置保持 | [速查](docs/技巧速查.md) |
| 16 | 循环渐变色 | [速查](docs/技巧速查.md) |
| 17 | 圆柱贴图/理发店滚筒 | [速查](docs/技巧速查.md) |
| 18 | 3ds Max 导入场景清理与轴心修复 | [文档](docs/3dsmax导入场景清理与轴心修复.md) |
| 19 | 驱动式上下浮动噪声系统 | [文档](docs/驱动式上下浮动噪声系统.md) / [脚本](scripts/driver-bob/) |
| 20 | 驱动式 Z 轴匀速旋转系统 | [文档](docs/驱动式Z轴匀速旋转系统.md) / [脚本](scripts/driver-spin/) |
| 21 | 视口预览录制(录屏式) | [文档](docs/视口预览录制录屏式.md) / [脚本](scripts/playblast/) |
| 22 | 集合内对象数据独立化 | [文档](docs/集合内对象数据独立化.md) / [脚本](scripts/make-independent/) |
| 23 | 天空太阳控制驱动 | [文档](docs/天空太阳高度驱动.md) / [脚本](scripts/driver-sky/) |
| 24 | 运动网格灯光方案 | [文档](docs/运动网格灯光方案.md) / [脚本](scripts/driver-lights/) |
| 25 | 渐变发光滚动材质 | [文档](docs/渐变发光滚动材质.md) / [脚本](scripts/glow-scroll-material/) |
| 26 | 输出路径与序列帧输出规范 | [文档](docs/输出路径与序列帧输出规范.md) |
| 27 | 速度驱动灯光亮度 | [文档](docs/速度驱动灯光亮度.md) / [脚本](scripts/speed-light/) |
| 28 | 材质参数统一控制器与实时面板 | [文档](docs/材质参数统一控制器与实时面板.md) / [脚本](scripts/ring-control-panel/) |
| 29 | 帧窗口驱动时间开关 | [文档](docs/帧窗口驱动时间开关.md) / [脚本](scripts/frame-window-time-switch/) |
| 30 | 粒子系统礼花喷射方案 | [文档](docs/粒子系统礼花喷射方案.md) / [脚本](scripts/firework-confetti/) |
| 31 | 动画转移到父级空对象(动态转移) | [文档](docs/动画转移到父级空对象.md) / [脚本](scripts/anim-transfer-to-empty/) |
| 32 | 位移坐标系:沿自身轴 / 沿世界轴运动 | [文档](docs/轴向位移-自身轴与世界轴.md) / [脚本](scripts/axis-space-motion/) |
| 33 | 按材质拆分为多个网格体 | [文档](docs/按材质拆分为多个网格体.md) / [脚本](scripts/separate-by-material/) |
| 34 | 空物体收敛清理 | [文档](docs/空物体收敛清理.md) / [脚本](scripts/scene-cleanup/) / [Skill](skills/blender-scene-cleanup/) |
| 35 | 渲染发黑与材质不发光排查 | [文档](docs/渲染发黑与材质不发光排查.md) / [脚本](scripts/blackout-diagnose/) / [Skill](skills/blender-render-blackout-diagnose/) |
| 36 | 径向内收多脉冲材质 | [文档](docs/径向内收多脉冲材质.md) / [脚本](scripts/radial-inward-pulse/) / [Skill](skills/blender-inward-pulse-material/) |
| 37 | 径向材质多位置部署与播放时差 | [文档](docs/径向材质多位置部署与时差.md) / [脚本](scripts/radial-inward-pulse/) |
| 38 | 驱动参数化材质维护:引用体检 / 关键帧收敛 / 改名换轴 | [文档](docs/驱动参数化材质维护.md) / [脚本](scripts/driver-param-maintenance/) / [Skill](skills/blender-driver-param-maintenance/) |
| 39 | 星芒散射光效系统 | [文档](docs/星芒散射光效系统.md) / [脚本](scripts/starburst-scatter/) |
| 40 | 循环三角波关键帧动画 (Skill) | [Skill](skills/blender-loop-keyframe-anim/) |
| 41 | 雪花下落系统 | [文档](docs/雪花下落系统.md) / [脚本](scripts/snowfall-scatter/) |
| 42 | 空物体父级整体挪动集合 | [文档](docs/空物体父级整体挪动集合.md) |
| 43 | 按材质合并为单个网格体 | [文档](docs/按材质合并为单个网格体.md) / [脚本](scripts/merge-by-material/) / [Skill](skills/blender-headless-batch/) |
| 44 | 追加合并两个工程 | [文档](docs/追加合并两个工程.md) / [Skill](skills/blender-blend-append-merge/) |
| 45 | 分体翻页牌驱动翻页系统 | [文档](docs/分体翻页牌驱动翻页系统.md) / [脚本](scripts/flip-card/) / [Skill](skills/blender-split-flap-flip/) |
| 46 | 射灯阵列径向摆动绽放系统 | [文档](docs/射灯阵列径向摆动绽放系统.md) / [脚本](scripts/spot-bloom-swing/) / [Skill](skills/blender-spot-bloom-swing/) |
| 47 | 体积光柱羽化系统 | [文档](docs/体积光柱羽化系统.md) / [脚本](scripts/volume-beam-feather/) / [Skill](skills/blender-volume-beam-feather/) |
| 48 | 参数化摆动驱动系统(单物体自包含版) | [文档](docs/参数化摆动驱动系统.md) / [脚本](scripts/swing-driver/) |
| 49 | 空间雷达扫描材质 | [文档](docs/空间雷达扫描材质.md) / [脚本](scripts/radar-scan-material/) / [Skill](skills/blender-radar-scan-material/) |
| 50 | 覆盖区框选批量删除对象(俯视 Z 轴) | [速查](docs/技巧速查.md) |
| 51 | 渐变扫过材质 · UV 方向角 | [速查](docs/技巧速查.md) |
| 52 | 滚筒斜纹材质 | [文档](docs/滚筒斜纹材质.md) / [脚本](scripts/streak-material/) / [Skill](skills/blender-cylinder-spiral-material/) |
| 53 | 合成器后期辉光(Glare) | [文档](docs/合成器后期辉光-Glare.md) / [脚本](scripts/post-glare-glow/) / [Skill](skills/blender-post-glare-glow/) |
| 54 | 水晶色散材质 | [速查](docs/技巧速查.md) |
| 55 | 车辆速度驱动与刹车收尾 | [速查](docs/技巧速查.md) |
| 56 | 发光遮罩选轴：世界轴 vs UV | [速查](docs/技巧速查.md) |
| 57 | 面光渐变发光面 | [速查](docs/技巧速查.md) |
| 58 | 贴面细节光：小面光画高光 | [速查](docs/技巧速查.md) |
| 59 | 灯光链接排除物件：receiver 不是 blocker | [速查](docs/技巧速查.md) |
| 60 | 几何节点泡泡发射系统 | [速查](docs/技巧速查.md) |
| 61 | 参数化弹出门与角色控制系统 | [速查](docs/技巧速查.md) |

## Agent Skills（给 AI 助手用的作业规范）

`skills/` 目录收录 Agent Skill：`SKILL.md` 写清怎么干、先干什么、什么绝对不能干；脚本包见 `scripts/`。

| Skill | 入口 |
|---|---|
| [blender-bridge-ops](skills/blender-bridge-ops/) | [文档](docs/技巧速查.md#1-远程控制运行中的-blender) / [脚本](scripts/blender-remote-control/) |
| [blender-scene-cleanup](skills/blender-scene-cleanup/) | [文档](docs/空物体收敛清理.md) / [脚本](scripts/scene-cleanup/) |
| [blender-render-blackout-diagnose](skills/blender-render-blackout-diagnose/) | [文档](docs/渲染发黑与材质不发光排查.md) / [脚本](scripts/blackout-diagnose/) |
| [blender-overlap-difference](skills/blender-overlap-difference/) | — |
| [blender-procedural-emission-material](skills/blender-procedural-emission-material/) | [文档](docs/渐变发光滚动材质.md) |
| [blender-plane-procedural-material](skills/blender-plane-procedural-material/) | [文档](docs/渐变发光滚动材质.md) |
| [blender-radial-pulse-material](skills/blender-radial-pulse-material/) | — |
| [blender-inward-pulse-material](skills/blender-inward-pulse-material/) | [文档](docs/径向内收多脉冲材质.md) / [脚本](scripts/radial-inward-pulse/) |
| [blender-driver-param-maintenance](skills/blender-driver-param-maintenance/) | [文档](docs/驱动参数化材质维护.md) / [脚本](scripts/driver-param-maintenance/) |
| [blender-cylinder-spiral-material](skills/blender-cylinder-spiral-material/) | [文档](docs/滚筒斜纹材质.md) / [脚本](scripts/streak-material/) |
| [blender-headless-batch](skills/blender-headless-batch/) | [文档](docs/按材质合并为单个网格体.md) / [脚本](scripts/merge-by-material/) |
| [blender-blend-append-merge](skills/blender-blend-append-merge/) | [文档](docs/追加合并两个工程.md) |
| [blender-split-flap-flip](skills/blender-split-flap-flip/) | [文档](docs/分体翻页牌驱动翻页系统.md) / [脚本](scripts/flip-card/) |
| [blender-spot-bloom-swing](skills/blender-spot-bloom-swing/) | [文档](docs/射灯阵列径向摆动绽放系统.md) / [脚本](scripts/spot-bloom-swing/) |
| [blender-volume-beam-feather](skills/blender-volume-beam-feather/) | [文档](docs/体积光柱羽化系统.md) / [脚本](scripts/volume-beam-feather/) |
| [blender-radar-scan-material](skills/blender-radar-scan-material/) | [文档](docs/空间雷达扫描材质.md) / [脚本](scripts/radar-scan-material/) |
| [blender-region-batch-delete](skills/blender-region-batch-delete/) | [文档](docs/覆盖区框选批量删除对象.md) / [脚本](scripts/region-batch-delete/) |
| [blender-sweep-angle-material](skills/blender-sweep-angle-material/) | — |
| [blender-post-glare-glow](skills/blender-post-glare-glow/) | [文档](docs/合成器后期辉光-Glare.md) / [脚本](scripts/post-glare-glow/) |
| [blender-gn-bubble-emitter](skills/blender-gn-bubble-emitter/) | [文档](docs/几何节点泡泡发射系统.md) / [脚本](scripts/geometry-node-bubble-emitter/) |
| [blender-parameter-popup-door](skills/blender-parameter-popup-door/) | [文档](docs/参数化弹出门与角色控制系统.md) / [脚本](scripts/parameter-popup-door/) |

安装(拷到用户级 skill 目录)：`Copy-Item .\skills\* "$env:USERPROFILE\.workbuddy\skills\" -Recurse`，

详见 [skills/README.md](skills/README.md)。



## 文档



- [📖 技巧速查(完整内容)](docs/技巧速查.md)

- [🤖 AGENTS.md(给 AI/未来的你:关键坑速记)](AGENTS.md)

- [🔧 DEVELOPMENT.md(架构与问题记录)](DEVELOPMENT.md)

- [架构说明](docs/架构.md)

- [问题记录索引](docs/问题记录/索引.md)

- [📜 CHANGELOG.md(版本历史)](CHANGELOG.md)



## 快速开始(远程控制桥)



1. Blender → Scripting 工作区 → 文本编辑器 **Open** 打开 `blender_bridge.py` → **Run Script**

2. 看到 `[Bridge v2] BRIDGE READY` 即成功

3. 外部客户端:`python send.py <code.py>` 发送代码到 `127.0.0.1:9877` 远程执行



> 桥脚本与客户端位于工作区 `blender_control/` 目录,详见 [docs/技巧速查.md](docs/技巧速查.md) §1。

