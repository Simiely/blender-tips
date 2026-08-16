# AGENTS.md · 项目规则

> 📌 **文档基线**:2026-08-17(commit `3bbdbce1`)渲染提速技巧 v0.2.2
> **更新文档/代码后,请更新此行**(日期 + 新 commit hash),并在 CHANGELOG 追加版本

## 技术栈

- Blender 5.2(Windows)+ Python API(bpy),脚本在 Blender Scripting 工作区运行
- 远程控制:本地 Socket 桥(`127.0.0.1:9877`),主线程执行,零插件依赖

## 关键坑(代码里看不出的)

- `bpy.context` 只能**主线程**访问 → 远程执行必须用 `bpy.app.timers` 调度
- **Blender 5.2 Slotted Action**:`action.fcurves` 不存在!读/建曲线用 `action.fcurve_ensure_for_datablock(obj, path, index=i)`(index 必须关键字传参)
- 直接改 IDProperty(如 `obj['vis']=[0]`)后驱动不重算 → 必须 `obj.update_tag()` + `bpy.context.view_layer.update()`
- 关键帧**末帧插值不影响任何可见段**(段由段首帧决定);要"结尾直线"改**倒数第二帧**为 LINEAR
- C4D 式"中间平滑+两头线性":**两头 Free handle 手动对齐线段**,中间保持平滑;改 LINEAR 会产生折角
- **5.2 合成器**:`scene.node_tree` → `scene.compositing_node_group`;**Composite 节点已移除**(渲染结果不自动显示,用 Viewer 或移除节点组);File Output 的 Media Type 默认 Multi-Layer EXR(要 PNG 必须改 Image 或槽勾 Override Node Format)
- **use_nodes 在 5.x 恒 True 无法关闭**;"关合成器"= 移除 compositing_node_group(空节点组=幽灵状态,渲染不输出)
- **远程脚本不要写合成器节点树**(新建/删除 File Output、槽操作会触发 5.x 已知崩溃 bug)→ 合成器写操作一律 GUI 手动,远程只读探查

## 约定

- 文档用中文;技巧按"场景 → 做法 → 坑"组织;一坑一篇进 DEVELOPMENT.md

## 常用命令

- 远程执行:`python send.py <code.py>`(桥在 blender_control/)
- 验证桥:`netstat -ano | grep 9877`
- 手动改 handle:Graph Editor 选中关键帧按 V

## 详细规则(按需 @引用)

- @docs/技巧速查.md
