# CHANGELOG.md

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
