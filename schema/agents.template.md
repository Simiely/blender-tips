# AGENTS.md · 项目规则

> 📌 **文档基线**:2026-11-24（commit `0e40997`） —— 规范 2.1.4 拆分：坑库（171 条）→ `rules/坑库.md`、
> 2026-11-18 之前的基线记录 → `rules/订正日志.md`；`AGENTS.md` 只留门面与 8 条最高频坑
> **更新文档/代码后,请更新此行**(日期 + 新 commit hash),并在 CHANGELOG 追加版本
>
> 生成文件，勿手改。改规则请改 `schema/agents.template.md`，再运行 `python tools/repo-kit/generate.py --root . --write`。

## 技术栈



- Blender 5.2(Windows)+ Python API(bpy),脚本在 Blender Scripting 工作区运行

- 远程控制:本地 Socket 桥(`127.0.0.1:9877`),主线程执行,零插件依赖

- 多 Blender 并存:桥端口可改(如 9878),send.py 第二参数指定端口

- **★ 另有一条不走桥的通道:`blender.exe --background --factory-startup <blend> --python <脚本>.py -- <参数>`**

  (**无头批处理**)。什么时候用它而不用桥:改动>120s(桥会超时)、目标工程大到 GUI 打不开、

  或压根不想开 GUI。详见 `skills/blender-headless-batch/` 与 `docs/按材质合并为单个网格体.md`

## 关键坑（最高频 8 条;全量 171 条见 @rules/坑库.md）

1. **★★★ 取灯必须走 `obj.data`** —— 本工程数据块名与对象名错位(对象 `面光.002` 的数据块叫 `面光.004`),按名字取会改到另一盏灯,表现为「怎么调画面都不变」;`L.users > 1` 说明被多盏灯共用
2. **★★★ 面积光的 `自发光` 必须接 `灯光输出.Surface`** —— 漏接则静默全黑、属性面板一切正常;开节点后亮度看 `自发光.Strength`,`light.energy` 失效
3. **★★ `blocker_collection` 是「挡光体」不是「不收光」** —— 排除物件只能用 `receiver_collection` 白名单;误用 blocker 画面反而变亮
4. **★★ 翻转型渐变不能用全幅均值验证** —— 左黑→右白 与 左白→右黑 总光通量相同,均值差恒为 `0.000000`;判据只能看左右半互换
5. **★★★ 世界轴对「同一高度 / 同一条等值线」上的面只能全亮/全不亮** —— 要由亮到暗铺开必须用 **UV**;且「数值对 ≠ 画面对」,只能靠出图确认面上位置
6. **★★★ Blender 5.2 是 Slotted Action,`action.fcurves` 不存在** —— 读/建曲线用 `action.fcurve_ensure_for_datablock(obj, path, index=i)`(index 必须关键字传参);读已有曲线走 `layers → strips → channelbags → fcurves → keyframe_points`
7. **★★ 同一次 exec 内改完立即验证会读到未刷新缓存** —— 修改与验证必须分两次请求,以新请求为准
8. **★★ 探查脚本禁止 `round(kp.co[0])` 统计帧号** —— banker's rounding 会把 361.5→362 掩盖掉;用精确值 + `abs(f-round(f))>1e-6` 筛小数帧

## 约定



- 文档用中文;技巧按“场景 → 做法 → 坑”组织;一坑一篇进 DEVELOPMENT.md

- `skills/` 放**给 AI 助手用的作业规范**(`SKILL.md` + 附件脚本);`scripts/` 放**给人用的脚本包**(README + 脚本);**同一套脚本若两边都有,必须两处同步** —— 目前只有 `blender-scene-cleanup`(→ `scripts/scene-cleanup/`)与 `blender-render-blackout-diagnose`(→ `scripts/blackout-diagnose/`)是两边都有,其余 skill 的脚本只随 skill 自带

- 文档内链接用**相对本文件**的路径;结构改动后跑一次「链接可及性 + 锚点存在性」检查(本地模拟 GitHub 解析)



## 常用命令



- 远程执行:`python send.py <code.py>`(桥脚本在 `scripts/blender-remote-control/`,跨机器可复用;README 含完整说明)

- 验证桥:`netstat -ano | grep 9877`

- 手动改 handle:Graph Editor 选中关键帧按 V



## 详细规则(按需 @引用)



- @docs/技巧速查.md
- **全量坑库（171 条）**：@rules/坑库.md
- **2026-11-18 之前的基线 / 订正记录**：@rules/订正日志.md

## 当前规模

- 页面：{{PAGES}}（critical={{CRITICAL}}）
- 按 type：{{TYPES}}
- 词表版本：{{VERSION}}
