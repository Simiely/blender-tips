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
