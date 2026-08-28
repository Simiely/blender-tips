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
| 30 | 修改缩放(scale归1)保持大小 | 顶点烘焙×scale + scale=1,世界位 `T·R·(S·v)` 不变;坑:几何预放大叠加 / multi-user / 负缩放 | [https://github.com/Simiely/blender-tips/blob/main/docs/应用缩放Scale归1.md](https://github.com/Simiely/blender-tips/blob/main/docs/应用缩放Scale归1.md) |
| 30 | 修改缩放(scale归1)保持大小 | 顶点烘焙×scale + scale=1,世界位 `T·R·(S·v)` 不变;坑:几何预放大叠加 / multi-user / 负缩放 | [https://github.com/Simiely/blender-tips/blob/main/docs/应用缩放Scale归1.md](https://github.com/Simiely/blender-tips/blob/main/docs/应用缩放Scale归1.md) |
| 30 | 粒子系统礼花喷射方案 | 粒子系统 + 碰撞杀死 + 湍流场实现持续向上喷射金色纸片 | [文档](docs/粒子系统礼花喷射方案.md) / [脚本包](scripts/firework-confetti/) |

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
