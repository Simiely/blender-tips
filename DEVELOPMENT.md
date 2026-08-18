# DEVELOPMENT.md · 架构与问题记录

## 项目概览

Blender 5.x 技巧速查仓库:沉淀实战验证的 Blender 操作技巧,核心资产是 `docs/技巧速查.md`,配套 AGENTS/CHANGELOG 按单项目规范维护。

## 架构说明

**远程控制桥**(§1 技巧的核心设施):

```
外部客户端(python send.py)
  → TCP 127.0.0.1:9877
  → Blender 内桥脚本(blender_bridge.py)
  → bpy.app.timers 调度到主线程执行 → 回传 stdout/异常
```

- 桥脚本在 Blender Scripting 工作区运行一次即可,重启 Blender 后需重跑
- v1 为后台线程直接 exec(有 context 缺陷,废弃);v2 改 timer 主线程调度

## 关键问题与方案(一坑一篇)

## 问题:`bpy.context` 在后台线程不可访问

**TL;DR**:远程 exec 放后台线程会报 `'Context' object has no attribute 'active_object'`,必须主线程。

- 问题:Socket 接收线程直接 `exec()` 访问 bpy.context 失败
- 根因:Blender 的 context 绑定主线程,其他线程拿到的是空 context
- 解决:桥用 `bpy.app.timers.register` 每 0.05s 在主线程消费任务队列,线程只做收发
- 预防:所有远程 Blender 操作统一走主线程调度,不要在线程里碰 bpy

## 问题:Blender 5.2 没有 `action.fcurves`(Slotted Action)

**TL;DR**:新版动画用 slotted action,曲线要经 `fcurve_ensure_for_datablock` 访问。

- 问题:`action.fcurves` 报 `'Action' object has no attribute 'fcurves'`
- 根因:Blender 5.x 引入 slotted action,ActionSlot 无 fcurves,slot.handle 是 int 句柄
- 解决:`fcu = action.fcurve_ensure_for_datablock(obj, 'location', index=0)`(index 必须关键字)
- 预防:访问动画数据前先探测 action 结构;旧教程的 action.fcurves 在 5.x 失效

## 问题:改 IDProperty 后驱动不重算

**TL;DR**:`obj['vis']=[0]` 后驱动值不变,需 `update_tag()` 强制刷新。

- 问题:驱动引用自定义属性,直接赋值后驱动仍取旧值
- 根因:IDProperty 直接赋值不触发依赖图更新通知
- 解决:`ctrl.update_tag()` + `bpy.context.view_layer.update()`
- 预防:用户打关键帧走动画通道自动刷新,无此问题;脚本改值必须 update_tag

## 问题:关键帧"结尾不是线性"(插值机制)

**TL;DR**:插值模式=从该帧到下一帧的段;末帧插值不影响任何可见段。

- 问题:最后一帧设 LINEAR,结尾段(由倒数第二帧决定)仍是平滑
- 根因:官方手册明确"interpolated from that key to the next one",末帧无后继段
- 解决:要结尾段直线 → 把**倒数第二帧**设为 LINEAR
- 预防:理解段插值语义后再设置,不要依赖末帧

## 问题:interpolation=LINEAR 有折角,C4D 式"中间平滑两头线性"怎么做

**TL;DR**:两头关键帧 handle 改 FREE,手动对齐线段方向;中间保持平滑。

- 问题:改 LINEAR 段是直线但关键帧处折角;VECTOR handle 自动拉直不满足
- 根因:Blender 段插值线性化必然在段交界产生尖角;C4D 的切线控制更细
- 解决:中间帧保持 BEZIER/AUTO;两头帧 handle 改 FREE 并手动拖到与线段平行
- 预防:涉及"线性+平滑混合"需求优先 Free handle 方案,别先改 interpolation

## 问题:远程脚本修改合成器节点树导致 Blender 崩溃

**TL;DR**:Blender 5.x 的 File Output 节点有已知崩溃 bug,远程脚本(主线程 timer)新建/操作该节点会直接崩溃(无崩溃日志)。

- 问题:通过远程桥在合成器节点树新建 `CompositorNodeOutputFile`、操作 `file_output_items` 时,Blender 进程直接消失
- 根因:Blender Artists 社区确认 —— Blender 5.x 的 file output 节点(带 vec1 输入)存在崩溃 bug,5.1 Alpha 修复;官方 devtalk 也讨论过 File Output 节点在 5.2 的行为问题
- 解决:该环节放弃脚本,改 GUI 手动添加/配置 File Output 节点
- 预防:远程桥只做只读探查;合成器节点树的写操作(新建/删除/槽操作)一律 GUI 手动

## 问题:Blender 5.2 渲染后查看器不显示结果(透明/需手动切)

**TL;DR**:5.2 移除 `CompositorNodeComposite`,合成器开启时渲染结果不再自动显示在图像查看器。

- 问题:F12 渲染后,图像查看器显示透明/空白,要手动选择 Viewer 等才能看到
- 根因:4.x 靠 Composite 节点把结果送进 Render Result;5.2 该节点被移除(官方 API 文档 404、bpy.types 无此类)
- 解决:方式 A 加 Viewer 节点预览;方式 B 取消 Use Nodes 直接渲染(结果自动显示)
- 预防:开启合成器=必须自己安排预览节点或接受查看器无自动显示

## 问题:File Output 输出是 EXR 而不是 PNG

**TL;DR**:节点 Media Type 默认 Multi-Layer EXR,槽需勾 Override Node Format 才能用 PNG。

- 问题:明明槽里选了 PNG,输出却是 .exr
- 根因:节点级 format 在 Multi-Layer EXR 模式锁定 OPEN_EXR_MULTILAYER(设置 PNG 报 enum 错);槽 override_node_format=False → 用节点级格式
- 解决:Media Type 改 Image;或槽勾 Override Node Format 选 PNG
- 预防:File Output 节点优先检查 Media Type,再检查槽的 Override

## 问题:F12 渲染后输出文件夹是空的

**TL;DR**:F12 单帧渲染不写序列;File Output 只写当前帧,完整序列要 Ctrl+F12。

- 问题:输出目录空,以为没渲染
- 根因:Blender 渲染属性(F12 单帧)不保存文件;File Output 节点在 F12 时也只写当前帧(文件名带当前帧号)
- 解决:渲染动画用 Ctrl+F12(Render Animation);F12 仅预览单帧
- 预防:区分 F12 预览与 Ctrl+F12 出序列

## 问题:输出的 PNG 打开是透明的

**TL;DR**:PNG 带 alpha 且 alpha=0(透明背景),查看器按 RGBA 显示棋盘格。

- 问题:渲染出的 PNG 打开显示透明/棋盘格
- 根因:RGBA PNG 的 alpha 通道为 0(场景无背景/透明)
- 解决:查看时切 RGB;不需要透明则输出颜色模式改 RGB,或渲染属性 Film 关 Transparent
- 预防:出图前明确要透明底还是实底,对应设置颜色模式

## 问题:空的合成器节点组导致"无法渲染/不输出"

**TL;DR**:5.2 的 use_nodes 恒 True;compositing_node_group 存在但树空 = "幽灵状态",渲染结果不保存。

- 问题:删光合成器节点后,渲染不再输出文件;新工程(无节点组)却能正常输出
- 根因:实测确认 —— 新场景 use_nodes=True 但 compositing_node_group 不存在 → 渲染按 render.filepath 正常输出;有节点组但树被清空 → 合成器激活但无输出节点 → 结果无处写
- 解决:移除空节点组(GUI:Outliner → Blender File → Node Groups → 删"合成器节点";脚本:`scene.compositing_node_group=None` + `node_groups.remove`)
- 预防:use_nodes 在 5.x 无法关闭(废弃);"关合成器"的正确操作是移除节点组,不是设 use_nodes=False

## 问题:File Output 与渲染属性双份输出(文件名/大小不同)

**TL;DR**:File Output 节点与 render.filepath 同目录时各输出一份;位深不同导致大小差约 2.7 倍。

- 问题:输出目录出现 frame_0001.png(8-bit,3.6MB)与 frame_0001Image.png(16-bit,9.9MB)两份
- 根因:File Output 节点(文件名 = file_name+槽名+帧号)与渲染属性(render.filepath)同时生效;File Output 槽可 16-bit
- 解决:只留一条输出 —— 删 File Output 节点(保渲染属性)或清空渲染属性路径(保 File Output)
- 预防:配置输出前明确"合成器节点输出"还是"渲染属性输出",避免双份

## 问题:0 灯光场景渲染白膜平淡/无轮廓

**TL;DR**:CAD 导入场景通常没有灯光对象,白膜渲染全靠世界光;World 节点树里 Sky Texture 未连接 Background 时,世界只是默认灰。

- 问题:50186 对象 CAD 大场景,0 个灯光对象,直接渲染白膜效果平淡
- 根因:Blender 无灯光对象时唯一光源是 World;节点树里存在 TEX_SKY 节点但 Background.Color 未连线(孤立节点),世界按默认灰照亮 → 无天空光影轮廓
- 解决:检查并补连 `TEX_SKY.outputs[0] → Background.inputs[0]`;白膜材质用 Principled 纯白(Base Color 0.6 防过亮, Roughness 1.0, Metallic 0)
- 预防:白膜前先探查 world 节点连接(sky/bg 是否存在、Color 是否 linked);0 灯光场景默认走天空光,不够再加 Sun

## 问题:探查脚本 round() 掩盖小数帧(361.5 显示成 362)

**TL;DR**:统计关键帧帧号用 `int(round(kp.co[0]))`,banker's rounding 把 .5 帧显示成整数,导致误判"数据没变"。

- 问题:用户发现时间轴上有 .5 帧,但之前探查脚本显示的都是整数
- 根因:Python `round(361.5)` 取偶数 = 362,`round(988.5)` = 988;所有小数帧被四舍五入掩盖
- 解决:统计时输出精确值 `kp.co[0]`,用 `abs(f - round(f)) > 1e-6` 单独筛小数帧
- 预防:探查脚本禁止 round() 关键帧帧号;批量操作(平移/吸附)前先跑小数帧检测

## 问题:同一次 exec 内修改后立即验证读到旧缓存值

**TL;DR**:桥脚本改关键帧后在同一请求里马上重读,拿到的是未刷新值(数值错误但数据实际正确)。

- 问题:execute 脚本内"修改→验证"输出 min=2 max=47,与新请求重读的 min=1 max=106 不符
- 根因:Blender 主线程 exec 内关键帧修改后,同上下文读取走缓存/延迟路径
- 解决:修改与验证分成两次 send 请求;以新请求读取结果为准
- 预防:所有"改完验证"一律新请求;探查脚本只读不会触发

## 问题:Blender 没有"反转关键帧"菜单(Reverse Keyframes 不存在)

**TL;DR**:反转关键帧的正确操作是「关键帧 → 镜像」;官方文档/API 均无 Reverse Keyframes 操作。

- 问题:用户按教程找"反转关键帧"菜单项,怎么都找不到
- 根因:"Reverse Keyframes" 是错误记忆(来自其他软件/旧版教程);Blender 官方文档(Manual Mirror 部分)与 bpy.ops.graph/bpy.ops.action 均无此操作
- 解决:反转 = 关键帧菜单 → 镜像(`Ctrl-M`)→ 沿时间轴关于当前帧(播放头放中间帧)或沿时间轴关于时间 0
- 预防:涉及 Blender 功能术语先查官方文档核实;中文界面给中文菜单名(镜像/沿时间轴关于当前帧)

## 问题:时间轴整体平移产生负帧关键帧

**TL;DR**:整体前移时若直接 `kp.co[0] -= delta`,原本在帧 1 的关键帧会变负帧。

- 问题:场景有对象动画从帧 1 开始,整体前移 74 帧后该对象关键帧变成 -73
- 根因:平移量按"最靠前相机"计算,忽略了更早的关键帧
- 解决:平移循环加负帧保护 —— `new = kp.co[0] - delta; if new < 最小帧: continue`(co + handle 整体跳过)
- 预防:计算 delta 前先取全部关键帧的最早帧;单帧常量曲线(如 loc/rot/scale @1)跳过无影响
