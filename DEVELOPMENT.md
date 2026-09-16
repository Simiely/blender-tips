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

## 问题:send.py 发送大任务报超时,但桥实际执行完了

**TL;DR**:桥内任务耗时 >120s 时 send.py 的 socket 先超时抛错(误报失败),但桥的 timer 线程会继续把任务执行完。

- 问题:发送"全量网格指纹计算+合并"(9,079 数据块)时,send.py 报 `TimeoutError: timed out`(exit 1),看起来失败了
- 根因:桥端 `_handle` 等待 res 的 deadline 与 send.py 的 socket timeout 都是 120s,几乎同时到点;send.py 在收到桥的 ERR 前先抛超时;桥端 timer 仍在主线程跑完该任务(exec 不中断)
- 解决:超时后**重跑一次同样的脚本**——若输出"冗余 0 / 已完成"说明第一次实际执行完了;写操作先备份、幂等设计(合并脚本重跑无副作用)
- 预防:大任务(全量遍历 5 万+ 对象)拆分批次或接受超时重跑验证;只读探查超时同样用重跑确认

## 问题:重复网格合并的指纹陷阱(材质/UV)

**TL;DR**:仅按"同基础名+顶点数+面数"合并会误伤;必须用完整指纹(顶点坐标+面拓扑+材质+UV),且抽检真实几何。

- 问题:同基础名 mesh 变体(如 G-物体.001~.5251)大量存在,但同名的几何不一定相同
- 根因:3ds Max 导出同名组可能内容不同;顶点数+面数相同 ≠ 顶点坐标/拓扑相同;材质/UV 不同合并会改外观
- 解决:指纹 = (基础名, 顶点坐标取整 tuple, 面顶点索引 tuple, 材质名 tuple, UV 层名 tuple) 完全一致才合并;合并前抽检 2~3 块比对顶点坐标
- 预防:指纹越全越安全;合并后抽查对象确认材质保留;对象共享数据后编辑一个会同步全部

## 问题:Blender 5.x parent 赋值后子对象世界位置翻倍

**TL;DR**:`child.parent = empty` 后 matrix_parent_inverse 不自动设置(保持单位矩阵),空对象不在原点时子对象世界位置 = 空对象位置 + 局部坐标(如 743+743=1486)。

- 问题:把 (743,380,0.5) 处对象挂到空对象,世界位置变成 (1486,760,1.9)(翻倍);撤销/再移动时偏移叠加,局部坐标被反复重写(743 大数 ↔ 小数)
- 根因:Blender 5.x 中 parent 赋值**不自动更新 matrix_parent_inverse**;世界 = parent.world @ mpi @ local,mpi=Identity 时 = parent.world @ local;空对象与物体距离越远越明显
- 解决:挂载后手动 `child.matrix_parent_inverse = parent.matrix_world.inverted()`;世界位置立即恢复,局部坐标变为相对父级的小数
- 预防:远程 parent 一律手动设 mpi;**空对象先定位到目标位置再挂载**;设置 location 后 `bpy.context.view_layer.update()` 刷新;同 exec 内读取 matrix_world 是缓存值,用新请求验证

## 问题:ColorRamp 渐变"抖"(EASE 插值 + 过渡区多余色标)

**TL;DR**:循环渐变色显示不平滑 = 两个原因叠加:插值类型被改成 EASE(非线性)+ 过渡区中间残留色标(打断线性)。

- 问题:黑白渐变波播放时过渡区"抖",不是平滑线性;用户手动调色标后出现
- 根因:ColorRamp 默认 LINEAR,但**手动拖动色标时插值类型可能被切到 EASE**(缓动,过渡在两端加速减速 → 视觉上"抖");且过渡区中间若留色标,插值被钉住形成台阶
- 解决:`cr.color_ramp.interpolation = 'LINEAR'`;删掉两平台之间的色标,让过渡由两侧平台色标线性决定
- 预防:任何 ColorRamp 做完后检查 interpolation;循环渐变按"平台(同色连标)+ 过渡(无中间色标)+ 首尾同色"布局(见 docs §16)

## 问题:Object 坐标不跟随空物体旋转 + 材质节点 driver 路径

**TL;DR**:Texture Coordinate 的 Object 输出只跟随平移;材质节点 driver/keyframe 路径必须用 inputs[N] 数字索引。

- 问题1:旋转控制空物体 90°,条纹毫无变化——Blender 的 Object 坐标仅用空物体原点做平移参考,旋转/缩放不影响采样坐标
- 解决1:条纹旋转用材质节点内偏移(节点 ADD + driver/keyframe),不要转空物体;空物体只用于平移类控制
- 问题2:材质 driver `nodes["UOffset"].inputs["Location"].default_value` 报 not found(5.2 slotted action 路径解析 bug)
- 解决2:路径改用数字索引 `inputs[1]`(与 keyframe 经验一致,见 §16);对象级 driver(rotation/location)不受影响
- 预防:涉及材质节点动画一律用 inputs[N];旋转类动画走节点偏移;文档 §17

## 问题:理发店滚筒条纹底部"裁剪"

- 问题:圆柱底部条纹被截断/扭曲——v 归一化后圆柱底部超出 0~1 为负值,普通 MODULO 负结果被钳制
- 解决:用 FLOORED_MODULO(数学取模,负数返回非负)替代 MODULO → 条纹上下/环绕无缝循环
- 预防:任何循环坐标/值用 FLOORED_MODULO;MODULO 在 Blender 对负数按 C 风格(带符号)

## 问题:Blender 5.2 驱动变量类型无 SELF(use_self 替代)

**TL;DR**:给物体挂驱动想引用"自身属性"时,旧教程 `vf.type='SELF'` 报非法变量类型;正确做法是 `driver.use_self=True`,表达式里 `self` 即可用。

- 问题:想在每个网格物体的 `location.z` 驱动里读它自己的 `bob_base_z` / `bob_seed`,按旧方法加 `SELF` 变量时报错
- 根因:Blender 5.x 驱动变量合法类型里没有 `SELF`(旧版有但已移除)
- 解决:`d.use_self = True`,表达式写成 `bob(fr, self)`,函数签名 `def bob(frame, self)` 里 `self` 即当前物体
- 预防:任何"驱动引用自身数据"的需求统一走 use_self,不碰 SELF 变量类型

## 问题:自定义属性显示名就是键名(update(name=) 无效)

**TL;DR**:想让控制面板滑块显示中文,没有"改显示名"的 API;显示名 = 键名,直接把键设成中文即可。

- 问题:自定义属性键是 `max_up`,想界面显示「最大上移」,尝试 `id_properties_ui(k).update(name='最大上移')` 报错
- 根因:Blender 自定义属性**显示名与键名是同一个东西**,`update()` 只接受 `min/max/description` 等,不接受 `name`
- 解决:直接用中文键 `obj['最大上移']=1.0`,逻辑读取也同步用中文键;`bob()` 函数读 `ctrl['最大上移']` 等
- 预防:自定义属性要中文 UI → 键即中文;纯内部属性(基准/种子)可保留英文避免混淆

## 问题:改名控制物体 / 替换驱动函数后,旧驱动"陈旧"返回基准值

**TL;DR**:重构后旧驱动在依赖图里没被标记为需重算,求值直接返回基准 Z(看似不动);给每个驱动 `driver.update()` 刷新即可,不动 seed/基准。

- 问题:把控制物体 `运动控制` 改名为 `运动控制01`、并重写 `bob()` 后,主装置01 的 12 个网格跨帧完全静止(偏移全 0),但手动调 `bob(75, obj)` 正常返回位移
- 根因:旧驱动记录的是改名前的变量绑定/函数引用,depsgraph 未将其标脏,求值走陈旧缓存 → 返回基准值;新建驱动(02~05)因是新建所以正常
- 解决:对每个受影响物体的 Z 驱动调一次 `d.update()`(强制重算绑定),运动立即恢复;**完全不动 seed/rand/base_z**,原花样保留
- 预防:凡是改名驱动引用的对象、或替换驱动调用的命名空间函数后,记得批量 `driver.update()` 刷新旧驱动

## 问题:驱动依赖的命名空间函数(bob)不随 .blend 保存

**TL;DR**:`bpy.app.driver_namespace['bob']` 是运行期全局,关闭重开 .blend 后函数丢失 → 驱动表达式报错变红。

- 问题:保存并重新打开文件,所有浮动驱动变红(找不到 `bob`)
- 根因:命名空间函数只存在于当前进程内存,不序列化进 .blend
- 解决:把 `bob()` 源码存成文本块 `bob_driver.py` 并勾 **Register**(文本编辑器右上角),下次打开自动 Run Script 重新注册;或手动 Run Script 一次
- 预防:任何被驱动调用的自定义函数,必须文本块化 + Register 持久化;远程脚本改了 bob 逻辑要同步更新文本块内容

## 问题:重建驱动时基准位置(bob_base_z)被误覆盖导致跳原点

**TL;DR**:挂驱动时要记录物体静止 Z 作基准,但重建时若覆盖了被驱动"当前值",物体会跳到原点附近;只在首次记录、已存在则跳过。

- 问题:设想在已有驱动的物体上重跑构建,若直接 `o['bob_base_z'] = o.location.z`,此时 location.z 是被驱动后的偏移值,基准被污染 → 整体位移错位
- 根因:有驱动时 `obj.location.z` 返回的是驱动求值结果,不是原始静止位置
- 解决:记录基准前先判断 `if 'bob_base_z' not in o: o['bob_base_z'] = o.location.z`,只在无基准时写(首次);已有则保留
- 预防:任何"基于当前位置记基准"的脚本,都要先判存在再写,保证幂等重建不污染

## 问题:Blender 5.2 视口录制(opengl + FFMPEG)输出配置顺序

**TL;DR**:配置视频输出必须先 `image_settings.media_type='VIDEO'`,再 `file_format='FFMPEG'`;顺序反了报枚举找不到。

- 问题:`bpy.ops.render.opengl` 想导出 mp4,脚本先设 `file_format='FFMPEG'` 再设 `media_type='VIDEO'`(或只设 file_format),报 `'FFMPEG' not found in enum` / 配置无效,输出全空
- 根因:Blender 5.2 把渲染输出拆成 media_type(IMAGE/VIDEO/MULTILAYER)与 file_format 两层;在 media_type 还不是 VIDEO 时,file_format 枚举里还没有 FFMPEG 项
- 解决:严格顺序——`isx.media_type='VIDEO'` → `isx.file_format='FFMPEG'` → 再设 `ffmpeg.format/codec`
- 预防:任何"视口录屏/视频输出"脚本,把 media_type 写在 file_format 之前;录屏用 `render.opengl(animation=True, view_context=False)`(False=从场景相机出画面)

## 问题:Z 轴匀速旋转驱动用 rotation_euler 而非 rotation / 基准角被污染

**TL;DR**:想让物体绕 Z 轴匀速转,驱动必须挂在 `rotation_euler[2]`;挂之前把基准角复位为 0,否则从被污染角度累加。

- 问题1:直接 `driver_add('rotation', 2)` 或读 `rotation`(四元数)做 Z 旋转,角度结果错乱、不直观
- 解决1:统一用欧拉角 Z 分量 `driver_add('rotation_euler', 2)`,`rotation_mode='XYZ'`,表达式 `0 + fr * spin_speed() * DEG2RAD * sign`
- 问题2:目标物体此前被驱动污染过 Z 角(实测残留 100°),重挂驱动时若不复位,角度从 100° 起累加 → 起始姿态错
- 解决2:挂驱动前显式 `o.rotation_euler.z = 0.0`(原始基准即 0°);幂等重建:先移除旧 Z 驱动再重建
- 预防:任何"复位基准"的旋转脚本,挂驱动前强制写 0,不要依赖"当前值";速度用 `SINGLE_PROP` 读 `scene.frame_current`,保证每帧重算、调速即时生效

## 问题:桥接 exec 时 __name__ 是 builtins,__main__ 守卫导致脚本静默不执行

**TL;DR**:经控制桥远程执行的脚本,`__name__` 为 `builtins` 而非 `__main__`,写 `if __name__=='__main__': main()` 会静默跳过,桥端只回 `OK` 无任何输出。

- 问题:新写 make_independent.py 带 `__main__` 守卫,桥里跑只回 `OK`,集合数据块毫无变化;改为内联 `-c` 执行同样逻辑却立即生效
- 根因:桥脚本用 `exec(code)` 在当前命名空间执行,`__name__` 是 `builtins`;`__main__` 分支永远不满足
- 解决:脚本末尾直接调用 `main()`,不写 `__main__` 守卫(Scripting 工作区 Run Script 同理可跑)
- 预防:凡"经桥远程执行"的脚本一律直接执行;若要区分导入/直跑,用 `__file__` 或环境变量,不要依赖 `__name__`

## 问题:linked duplicate 共享网格数据块导致复制出去联动

**TL;DR**:外部导入的对象常多个共用一个网格数据块(43 网格只 21 唯一块),复制/导出后改一个全跟着变;用 `users>1` 判断 + `data.copy()` 逐对象独立化。

- 问题:新工程「补充」集合 43 个网格对象只有 21 个唯一数据块(`组7912/7913_GeomAdjust` 共引 `Mesh.537` 等),复制出去后联动编辑
- 根因:导入/复制产生的 linked duplicate,对象与数据块是"多对一"引用关系
- 解决:遍历集合内 MESH,`if o.data.users>1: o.data = o.data.copy()`;材质可选独立;幂等可重跑
- 预防:排查共享用 `users>1`(勿看数据块名);只处理目标集合,集合外共享不受影响(详见 docs/集合内对象数据独立化.md)

## 问题:恢复驱动命名空间函数后,驱动仍 is_valid=False,物体停在 Z=0 错位

**TL;DR**:重开 .blend 后 exec 文本块把 bob/spin_speed 重新注册进命名空间,但驱动仍不求值(物体掉 Z=0);必须对每条 SCRIPTED 驱动**重新赋值同值表达式**(`d.expression = d.expression`)强制重新编译才恢复。

- 问题:9877 工程重开后 bob/spin 函数丢失(5.2 文本块不自动执行),主装置01-05 全部物体 Z 掉到 0 错位。exec 文本块后 `driver.is_valid` 仍 False,物体不动
- 根因:函数注册只是把符号放回命名空间;depsgraph 对驱动的失败状态有缓存,不会自动重算。驱动求值失败时 Blender 返回 0(不是保持基础值)→ 物体全落 Z=0
- 解决:恢复函数后,遍历全场景 SCRIPTED 驱动,若表达式含恢复的函数名,执行 `d.expression = d.expression`(同值重赋值触发重新编译),再 view_layer.update()
- 预防:restore_drivers.py 已内置该步骤(EXPR_MAP 声明 文本块→函数 映射);任何"恢复驱动函数"脚本都要带强制重编译,否则看似恢复实则物体停 0 位

## 问题:场景相机按帧切换是标记绑定(Bind Camera to Markers),写死 s.camera 会丢机位

**TL;DR**:相机切换常用时间轴标记绑定实现(非 action 动画);录屏脚本若写死 `s.camera=某相机` 会覆盖标记绑定,整段锁死一个机位;直接 `render.opengl(view_context=False)` 即自动跟随标记切换。

- 问题:playblast 录屏前在工程里写死 `s.camera=摄像机006`,导出整段视频都是中景机位,丢了开头/结尾的广角机位
- 根因:工程相机切换靠 9 个时间轴标记绑定(如 F1→摄像机001 … F1043→摄像机009),`scene.camera` 在各帧被标记驱动;直接赋值 s.camera 覆盖了这个绑定
- 解决:录屏脚本不写死相机,`bpy.ops.render.opengl(animation=True, view_context=False)` 自动跟随标记切换机位;排查用 `scene.timeline_markers` 看 `m.camera`
- 预防:任何"相机动画"相关脚本,先确认相机切换机制(标记绑定 vs action 动画)再动 s.camera

## 问题:send.py 不支持端口参数,多 Blender 并存连不上

**TL;DR**:仓库 send.py 硬编码 9877,AGENTS.md 却声称"第二参数指定端口";多 Blender 并存(如 9877+9897)时无法用仓库客户端连第二实例。

- 问题:新开工程在 9897,仓库 send.py 只能连 9877,AGENTS.md 文档与代码不符
- 根因:send.py 写死 `PORT=9877`,没解析命令行端口参数
- 解决:send.py 加 `-p/--port` 参数解析(默认仍 9877);顺带把超时从 120s 提到 300s(playblast 等长任务)
- 预防:AGENTS.md 声称的能力必须与 send.py 代码一致;多 Blender 工作流统一用 `python send.py -p PORT script.py`

## 问题:5.2 天空纹理太阳参数是节点属性,且节点驱动挂在 node_tree.animation_data

**TL;DR**:TEX_SKY 的 sun_elevation 等是节点属性(非输入 socket),挂驱动用 `sky.driver_add('sun_elevation')`;但 ShaderNodeTexSky 没有 animation_data,驱动实际存在节点树 `sky.id_data` 上。

- 问题:给天空纹理的太阳高度做驱动,脚本里 `sky.animation_data` 报 `AttributeError`(ShaderNodeTexSky 无此属性)
- 根因1:5.2 天空纹理 inputs 只有 Vector,太阳参数全是节点属性(`sun_elevation`/`sun_rotation`/`sun_intensity`/`sun_size`),不是 socket
- 根因2:节点驱动的 FCurve 挂在节点树的 animation_data(路径 `nodes["天空纹理"].sun_elevation`),节点自身没有 animation_data
- 解决:挂驱动用 `sky.driver_add('sun_elevation')`(返回 FCurve 存于 nt.animation_data);移除/排查遍历 `nt.animation_data.drivers` 匹配 data_path
- 预防:任何"给材质/世界节点属性挂驱动"的脚本,先确认目标是节点属性还是 socket;驱动一律在 `node.id_data.animation_data` 上找

## 问题:新建轴心空物体后立即读 matrix_world 是单位矩阵,matrix_parent_inverse 变 identity

**TL;DR**:创建空物体后马上读 `matrix_world` 是单位矩阵 → `matrix_parent_inverse = matrix_world.inverted()` 变成 identity → 子对象世界坐标 = 父位置 + 自身位置(翻倍偏移);必须先 `view_layer.update()` 再读。

- 问题:批量给 168 个灯 parent 到组轴心空物体,灯世界坐标全部 = 轴心位置 + 网格位置(翻倍),跑出集合外
- 根因:轴心空物体刚 `objects.new()` + 设 location,未刷新 depsgraph 时 `matrix_world` 是单位矩阵,`inverted()` 也是 identity → parent 变换没抵消
- 解决:所有轴心空物体创建并设好位置后,先 `bpy.context.view_layer.update()`,再读 `matrix_world` 设 `matrix_parent_inverse`
- 预防:任何"建空物体 + parent + 手动 matrix_parent_inverse"的脚本,把 update() 放在读 matrix_world 之前(详见 docs/运动网格灯光方案.md)

## 问题:Blender 5.2 DriverTarget 没有 array_index 属性

**TL;DR**:SINGLE_PROP 驱动变量要读数组的某个分量(如 location 的 X),不能设 `target.array_index`(5.2 无此属性,报 AttributeError);改在 `data_path` 里带下标 `'location[0]'`。

- 问题:`v.targets[0].array_index = 0` 报 `AttributeError: 'DriverTarget' object has no attribute 'array_index'`
- 根因:Blender 5.2 移除了 DriverTarget.array_index,数组分量索引并入 data_path
- 解决:`v.targets[0].data_path = 'location[0]'`(或 `'rotation_euler[2]'` 等)
- 预防:任何挂"读对象数组属性分量"驱动的脚本,data_path 直接带下标(详见 docs/运动网格灯光方案.md)

## 问题:驱动循环依赖——两个物体不能互指跟随

**TL;DR**:A 跟随 B 和 B 跟随 A 的驱动互指会形成循环依赖,Blender 直接报错;联动只能"一主一从"。

- 问题:想让向上灯和向下灯"互相跟随"旋转(转哪个另一个都动),两边都挂驱动互指 → 驱动循环报错
- 根因:Blender 驱动求值是有向无环图,循环引用无法求值
- 解决:设计为单向——向上灯为主(无驱动,自由转),向下灯挂驱动 = 向上灯 + (−π,0,0);要换主从就反转(把驱动从从灯移到主灯)
- 预防:任何双物体联动需求,先确定主从;若真要"转哪个都行",改用共享控制空物体(两灯都驱动跟随它)(详见 docs/运动网格灯光方案.md)

## 问题:`obj.parent` 赋值会静默重置 `matrix_parent_inverse`(挂父级顺序陷阱)

**TL;DR**:`obj.parent = p` 会把 `matrix_parent_inverse` 重置为单位矩阵 → 必须**先设 parent、后设 MPI**;写反了对象会飞走,且 MPI 平移回读 `(0,0,0)`。

- 问题:把相机改挂到新父级空对象下,脚本里先写 `cam.matrix_parent_inverse = mpi` 再写 `cam.parent = emp`,执行后相机相对原位偏了最多 25.3 单位(看起来像"父级/MPI 全算错了");回读 `cam.matrix_parent_inverse` 平移为 `(0,0,0)`,即被清成了单位矩阵
- 根因:`Object.parent` 的 RNA setter 在赋值时重置 `matrix_parent_inverse`(与"是否同父级""是否有 tty"无关),不是缓存问题
- 解决:严格顺序 —— `obj.parent = p; obj.parent_type = 'OBJECT'; obj.matrix_parent_inverse = mpi`;补设 MPI 后世界位姿立即回到预期
- 隔离实验(排除其他嫌疑,`blender --background --factory-startup` 逐项单测):设 MPI → 再赋 `parent` = **被重置**;赋 `parent` → 再设 MPI = 保留;赋 `parent_type` / `animation_data_clear()` / 写 `location`·`rotation_euler`·`scale` / `scene.frame_set()` 均**不**重置
- 预防:任何"parent + 手动 matrix_parent_inverse"的脚本,MPI 赋值一律放在 parent 赋值**之后**;排查此类"改完就飞"的问题,第一件事是回读 MPI 是不是成了单位阵(详见 docs/动画转移到父级空对象.md §坑1)

## 问题:动态转移的目标 MPI 通用解是 B(F)⁻¹ 而非 M(F)⁻¹ + 角度验收指标病态

**TL;DR**:把对象动画搬到新父级后冻结本体,`MPI` 要取 **局部 basis 的逆 `B(F)⁻¹`**;`M(F)⁻¹`(世界矩阵的逆)只在"参考帧局部==世界"时才对。另外算角度差别用 `2*acos(dot)`,会虚报 100 倍。

- 问题1(通用性):参考以往"某相机在 151 帧挂父级、`MPI = parent.world(151)⁻¹`、且该帧父级 Z 旋转为 0 → 局部==世界"的经验,把新父级 MPI 写成 `M(F)⁻¹`。这在上述特例里恰好正确,但**换一个参考帧就错**:自测构造"第 200 帧挂父级、用第 151 帧做参考帧"的场景,`M(151)` 与 `B(151)` 相差 6.35 单位 → 用 `M(F)⁻¹` 会把对象挪偏 6.35 单位
- 根因:`M'(t) = D.world(t) @ X @ B(F)`,要恒等于 `M(t)` 需 `X·B(F) = I` 即 `X = B(F)⁻¹`;`M(F)⁻¹` 只在 `M(F) = B(F)`(局部==世界)时与 `B(F)⁻¹` 相等
- 解决1:统一用 `X = B(F)⁻¹`;更推荐**再插一个无动画基点空对象、三段全用单位 MPI + 单位 basis**,此时 `M'(t) = D.world(t) @ I @ I`,**乘单位矩阵是精确的**(无大数相消),实测对原始基线偏差 **0.000e+00**(优于 `B(F)⁻¹@B(F)` 路径的 1.19e-07 / 7.63e-06)
- 问题2(验收):验证脚本最初用 `2*acos(qa.dot(qb))` 算角度差,报出 **0.0396°**,看起来像有真实漂移;换成矩阵元素差复核后真实偏差只有 3.8e-06(矩阵元素)、约 1.5e-05 度
- 根因:`dot ≈ 1` 时 `acos` 导数趋于无穷(病态),`dot = 1 − 6e-8` 这种 float32 级噪声会被放大成 ~0.04°,放大 100+ 倍
- 解决2:角度偏差用**旋转矩阵元素最大差**或良态式 `2*asin(sqrt(x²+y²+z²))`;注意 `mathutils.Quaternion` **没有 `.vector` 属性**(用 `.x/.y/.z`)
- 预防:凡"参考帧/父级"相关公式,先问"这个结论是在哪个特例下成立的",再用另一个参考帧做反例自测;凡"用反三角算小量差"的验收指标,先做病态性检查(扰动 1e-7 看输出放大了多少倍)(详见 docs/动画转移到父级空对象.md、脚本 scripts/anim-transfer-to-empty/)

## 问题:位移想沿"自己的轴"或"世界轴",K 出来的 `location` 却哪个都不是

**TL;DR**:`location` 的坐标系是**父空间基底**(`parent.matrix_world @ matrix_parent_inverse`),`matrix_basis = T(location) @ R @ S` 里**平移在最左端**,所以对象自身怎么转都不影响位移方向。想沿自身轴 ⇒ 让"承载位移的那一层"自身旋转为 0;想沿世界轴 ⇒ 让那一层的父空间与世界对齐。

- 问题:物体轴向与世界轴不一致时(被转过的父级下、或自身带旋转),在对象上 K `location[2]` 得到的世界位移方向,既不是自身轴也不是世界轴;实测(父级绕 X 转 90°、子级自转 90°)与自身 Z 偏 **90.0000°**
- 根因:`matrix_world = parent.matrix_world @ matrix_parent_inverse @ matrix_basis`,而 `matrix_basis = T @ R @ S` —— 一个点先经 `S`、`R` 再被 `T` 平移 ⇒ `T` 作用于 `parent.matrix_world @ MPI` 这个坐标系(父空间基底),与 `R` 无关。顺带:**`delta_location` 与 `location` 同坐标系**(常见误解),`delta_rotation` 也不把 `location` 带转(均实测偏 90.0000°)
- 解决(统一心法:**想沿哪个坐标系,就把承载位移那一层的父空间做成它**):
  - 沿**自身轴**: `父级 → 朝向层(放旋转,location 恒 0) → 位移层(自身旋转恒 0,K location[2])`;上层旋转即使是动画也逐帧精确(实测逐帧 0.000000°)
  - 沿**世界轴**: 中间插一层"抵消旋转"的**世界对齐层**(静态父级填固定逆角 · 实测 0.000000;动态单轴父级挂 `Copy Rotation` invert · 0.000000),或直接用**世界空间约束**(无父级空对象 K 动画 + `Copy Location` with `owner_space/target_space='WORLD'`+`use_offset` · 实测含复合旋转也是 0.000000)
  - 不想改结构:`loc = d·(R_own @ AXIS)`(自身轴)/ `loc = d·(P_basis_rot⁻¹ @ AXIS)`(世界轴),**父级朝向是动画时必须逐帧 bake**(只 K 两端实测偏 7.07 单位)
- 预防:凡"位移方向不对"的问题,先跑 `scripts/axis-space-motion/axis_report.py` 量三个夹角(父空间基底 vs 自身轴 / vs 世界轴,以及坐标基底是否随时间变),夹角为 0 的那一项就是"现状已经对"的方向,别瞎试(详见 docs/轴向位移-自身轴与世界轴.md)

## 问题:循环采样时 `matrix_world` 没 `.copy()`,所有样本都变成最后一帧的值

**TL;DR**:`evaluated_get(dg).matrix_world` 返回的是**活引用**,存进列表前必须 `.copy()`,否则遍历结束后读到的全是末帧值;`to_3x3()` / `to_translation()` 返回新对象,天然安全。

- 问题:诊断脚本按 `for f in frames: scene.frame_set(f); mw = obj.evaluated_get(dg).matrix_world; rows.append((f, mw, ...))` 收集采样,随后打印表里 **f=151 / f=315 / f=480 三行的"自身Z→世界"完全一样**,且恰好等于最后一帧(f=480)的值 → 由此算出"自身Z vs 世界Z = 0.0000 度"的**假结论**(真实应为 101.53°)
- 根因:`evaluated_get()` 拿到的是**求值代理对象**,其 `matrix_world` 暴露的是内部内存的引用/视图;下一次 `frame_set` 重新求值后该内存被改写,先前存下的 3 个对象**指向同一处**,于是全部反映末帧。同一循环里 `(pw @ mpi).to_3x3()` 因为 `to_3x3()` 生产了新矩阵,所以没有这个症状 —— 这也解释了为什么只有"直接存的 `matrix_world`"那一列坏了
- 解决:`mw = ev.matrix_world.copy()` 后再存;或只取需要的数值(`to_translation().copy()` / `to_3x3()`)
- 预防:任何"多帧采样后统一比对"的脚本,凡把矩阵/向量**存进容器**的,一律显式 `.copy()`;写完先打印首末两帧做自检(两帧完全相同 = 踩了这个坑)(详见 docs/轴向位移-自身轴与世界轴.md、脚本 scripts/axis-space-motion/axis_report.py)

## 问题:验收"沿某个轴运动"用"逐帧步进方向"会必然误报

**TL;DR**:目标轴随时间旋转时(如"沿自身轴"而自身轴在公转),位移向量本身就在转,逐帧步进方向**不可能**等于轴方向 —— 实测真实偏差只有 8.1e-06 单位,该指标却报出 **112° / 163.86°** 的假失败。正确判据是"**垂轴分量 ≈ 0**"。

- 问题:验证"位移是否沿目标轴"时,先写的是"每帧位移增量方向 vs 当帧目标轴方向的夹角,应 ≈ 0";结果两个完全正确的案例(位置对理想轨迹偏差 8.09e-06 / 4.29e-06)都报出 112°/163.86° 的夹角,看起来像彻底失败
- 根因:两个叠加效应 —— ① 判据分子里混进了**基准轨迹自身的运动**(父级链在动)② 目标轴随时间旋转时,位移向量 `axis(t)·d(t)` 的时间导数含 `axis'(t)·d(t)` 这个**垂直于轴**的分量。所以"步进方向 = 轴方向"只在"轴恒定"时成立
- 解决:改判 **垂轴分量** `perp = |(real−base) − axis·((real−base)·axis)|`,与"沿轴投影 vs 期望距离""位置 vs 理想轨迹"三项并列;三项阈值都取 1e-4 单位(实测三项均 ~1e-5)
- 预防:凡验收"沿某方向"的量,先问该方向是否随时间变化;会变就一律用"分解成 沿轴/垂轴 两个分量"来判,别用"相邻帧差向量"这类混入其他运动的量(详见 docs/轴向位移-自身轴与世界轴.md、脚本 scripts/axis-space-motion/verify_axis_motion.py)

## 问题:`hasattr(bpy.ops.xxx, "yyy")` 会假阳性,判算子存在性必须用 `get_rna_type()`

**TL;DR**:`hasattr(bpy.ops.mesh, "separate_by_material")` 返回 **`True`**,但这个算子**根本不存在**;真调 `get_rna_type()` 直接 `KeyError`。判 `bpy.ops` 算子是否存在,一律用 `get_rna_type()` 包 `try`。

- 问题:要按材质拆分网格,顺手写了 `hasattr(bpy.ops.mesh, "separate_by_material")` 做能力探测,得到 `True` 就照着这个"更语义化"的算子去写方案;后来在真实网格上跑才发现路径不对,回头做运行时自省才确认它并不存在
- 根因:`bpy.ops` 是**动态命名空间**,`__getattr__` 对任意属性名都返回一个 `BPyOpsSubModOp` 包装对象(真正的解析推迟到调用时),所以 `hasattr` 对它几乎恒为真 —— 只能证明"名字能被包装",不能证明"算子存在"。唯一权威判据是 `op.get_rna_type()`:存在才有 RNA 类型,不存在则 `KeyError`
- 解决:能力探测统一写成
  ```python
  try:
      t = getattr(bpy.ops.mesh, name).get_rna_type()
      print("exists:", t.identifier, t.description)
  except Exception:
      print("NOT exists:", name)
  ```
  同时用 `bpy.ops.mesh.separate.get_rna_type()` 把 `type` 的枚举打出来核对(实测只有 `SELECTED / MATERIAL / LOOSE`)
- 预防:本项目里"探测 Blender 能力"一律**读运行时 RNA**(`get_rna_type()` / `bl_rna.properties[...].enum_items`),不要凭记忆或 `hasattr`。查文档也以**官方手册原文 + 运行时自省**双向交叉验证为准(本次官方手册确认 By Material 是"按材质槽、对整网格生效、与选择无关")(详见 docs/按材质拆分为多个网格体.md、脚本 scripts/separate-by-material/)

## 问题:拆分后属性层"消失",不靠逐组基线就分不清"无损失"还是"真丢数据"

**TL;DR**:Blender 会丢弃结果网格上**全为默认值**的属性层 —— 按材质拆分后某部件的 `sharp_edge` 层会不见。判定必须是"**该材质组原本的锐边数**":基线为 `0` ⇒ 无信息损失,`> 0` ⇒ 真数据丢失。所以拆分前**必须**把逐组锐边数写进基线。

- 问题:350 万面的对象按 4 个材质槽拆成 4 个部件后,`对象13735` 的 `sharp_edge` 属性层**消失了**,另外三个部件都保留着。第一反应是"拆分布丢失了属性数据",但拿隔离合成网格做实验**没能复现**丢失 —— 说明机制假设不成立,必须换证据渠道
- 根因:不是"某类网格会丢",而是"**该组锐边数恰为 0**"时属性层退化成了全默认值,Blender 于是不落这一层。所以问题不在拆分,而在**验证口径**:只比对"属性层在不在"永远得不出结论,必须比对"**逐组的真实锐边计数**"
- 解决:
  - 基线里加 `sharp_by_mat`(每个材质组内的锐边数,按"边两端点都被该材质的面用到"统计)
  - 用**独立 headless 进程只读打开改前的存盘文件**做权威对照(不碰用户正在编辑的实例)
  - 实测判定:材质 3 组 = **0** ⇒ 属性层消失**无信息损失**;另外三组 = **68,142 / 2,461,210 / 80,886**,与拆分后对应部件**逐组精确吻合**
- 预防:凡"结构重组后某属性层不见了"的问题,先问"**它在源数据里的真实取值分布是什么**",据此设计基线字段;验证器把"消失且基线为 0"判为 ✅、"消失但基线 > 0"判为 ❌,不要用"属性层是否存在"这种弱判据。同理 `material_index` / `.select_*` 掩码的消失属正常(前者在每部件只剩 1 槽时无意义)(详见 docs/按材质拆分为多个网格体.md、脚本 scripts/separate-by-material/verify_separation.py)

## 问题:桥在主线程执行 + 120s 超时 ⇒ 长耗时算子必须"状态逐阶段写盘"

**TL;DR**:桥的 `exec` 跑在 Blender **主线程**,客户端 **120s** 超时后结果即丢;且主线程忙时新请求**只排队不执行** —— 算子运行期间**无法轮询**。做法:每阶段 `json.dump` 一次状态文件,超时后从磁盘回捞结论。

- 问题:350 万面的对象要跑 `mesh.separate`,怕超时,本想"先发一个短请求查进度",结果查进度那次一直不返回 —— 因为算子在主线程占着,后续请求全在队列里排队
- 根因:桥是 `_run_timer` 每 0.05s 从队列取一条代码在**主线程** `exec`;主线程被长算子占满时,timer 回调根本没机会跑,队列只进不出。而客户端侧是**固定 120s socket 超时**,超时即断开,结果无从送达(即使算子后来跑完了)
- 解决:让被执行的脚本**自己把过程写盘** —— `stamp(stage, **kw)` 每阶段 `json.dump` 到 `STATUS_JSON`(含 `elapsed_s` / `clock` / 关键计数),于是"拆分前基线""算子已返回""结果盘点"这些节点都留痕;客户端超时后直接读该文件即可完整复盘。真实案例实测 **10.5s** 完成,远低于 120s
- 预防:凡经桥执行的**长耗时**操作(拆分 / 布尔 / 大批量 bake / 渲染),一律:① 脚本内逐阶段写盘 ② 关键结果(计数、异常 traceback)也写盘 ③ 客户端超时不要重发同一请求(会重复执行),先读状态文件。另外桥的 `_env()` 命名空间里**没有 `__name__`**,脚本结尾不能写 `if __name__ == "__main__"`(会 `NameError`),必须无条件调用 `main()`(详见 docs/按材质拆分为多个网格体.md、脚本 scripts/separate-by-material/separate_by_material.py)

## 问题:文档相对链接与锚点"本地看不出问题,在 GitHub 上却全部点不开"

**TL;DR**:GitHub 按**当前文件所在目录**解析相对链接 —— `docs/技巧速查.md` 里长期写作 `[x](docs/x.md)`,被解析成 `docs/docs/x.md`,**17 处链接全部 404**(实测 HTTP 状态码)。锚点同理:规则是"**每个空白字符各转一个连字符,不合并**",少一个连字符就打不开。这类问题本地编辑器与 Markdown 预览**都不会报错**,属"本地无感、线上全坏"。

- 问题:不新增任何内容,只做一次存量文档可及性扫描,发现 `docs/技巧速查.md` 里指向同目录文档的链接**全部 404**,且一个索引锚点(`#16-循环渐变色colorramp三色自然循环`)也打不开 —— 此前长期无人察觉
- 根因:
  - **相对链接**:原作者按"从仓库根看的路径"写(`docs/x.md`)。README 在根目录,这样写恰好正确;但同一个写法被复制到 `docs/` 下的文件里,基准目录变成 `docs/`,于是指向了 `docs/docs/x.md`
  - **锚点**:GitHub 生成 id 的规则是"小写 → 移除标点 → **逐空白字符各转一个连字符**"。标题 `## 16. 循环渐变色(ColorRamp 三色自然循环)` 的真实 id 是 `16-循环渐变色colorramp-三色自然循环`(`Ramp` 与 `三色` 之间**有**连字符),而索引里写漏了它
  - 两者**都不产生任何本地报错**:编辑器/预览工具的相对链接解析基准与锚点算法都与 GitHub 不完全一致,肉眼与工具都发现不了
- 解决:
  - 链接:`docs/` 下的文档一律用**同目录相对路径** —— 同目录写 `x.md`,指向仓库根的脚本写 `../scripts/x/`
  - 锚点:按实测规则重算;核验**不要用 `POST /markdown` API**(它返回的 HTML **不含 heading id**),要**抓真实页面**取 `id="user-content-..."`
  - 扫描:本地按 GitHub 规则模拟解析(基准目录 = 文件所在目录;锚点算法见上)全量过一遍,并**跳过行内代码**(反引号内的示例不是真链接)
- 预防:① 文档内链接一律"相对本文件",不要图省事从仓库根写 ② 结构改动后跑一遍「相对链接可达性 + 锚点存在性」扫描 ③ **判断链接可用性要看 HTTP 状态码,不要凭肉眼或编辑器预览**(实测"看起来正常"与 404 可以并存很久)(详见 AGENTS.md 关键坑、v1.15.1 CHANGELOG)

## 问题:删除文档只删了"本体 + 索引",正文副本残留成了第二份内容

**TL;DR**:2026-08-28 按用户要求删除 `docs/应用缩放Scale归1.md`,但只删了**文档本体**与**索引表行**,技巧速查里的**正文整节**(28 行,含死链)以及另一份**逐字重复的礼花节**(29 行)都留着,直到做可及性扫描才露出。结论:删文档是一张**检查单**,不是一个 `rm`。

- 问题:扫描发现 `docs/技巧速查.md` 里存在指向已删文档的死链整节,且 `## 30、粒子系统礼花喷射方案` 有**两份逐字相同的内容**
- 根因:
  - 删除动作拆成三次提交(删本体 `9ed89ed` / 改索引 `0e4fe21`、`7c04d73`),每次都只处理"看得见的那一处",**正文里的副本没进检查范围**
  - 重复节则来自 `3f3ef2b`(为修编号冲突,往正文**追加**了第二份礼花节)与 `7c04d73`(只把标题编号改回 30,**没删那份多余正文**)
  - 更深一层:同一内容常有多个副本(README 索引 / 技巧速查索引 / 技巧速查正文 / 其他文档引用 / CHANGELOG),删一处 ≠ 删干净
- 解决:按检查单逐一清理并复扫;`CHANGELOG` 用**「后续变更」注记**说明文档已删除,**不改写历史记录**
- 预防:**删除文档检查单** —— ① 文档本体 ② README 索引行 ③ 技巧速查索引行 ④ 技巧速查正文整节 ⑤ 其他文档的引用 ⑥ CHANGELOG 补注记。另:追加式写作容易产生重复节,改编号时要**同时核对"正文份数 == 索引份数"**(详见 v1.15.1 CHANGELOG)

## 问题:文档写死的规则是错的 —— 靠"判别实验 + 源码"双向确认才纠正过来

**TL;DR**:v1.15.0 文档写的"按材质拆分后**原对象保留最后一个材质槽**"是**错的**,正确规则是
**"面序中首次出现位置最晚的那一组"**。错在哪不是靠读代码"看出来"的,而是 ① 拿两个真实对象的实测结果反推,
② 设计 7 个**互相排斥**的用例 × 4 种候选理论做判别实验, ③ 再去 Blender 源码里找到对应实现。三个证据链独立同向才算定案。

- 问题:把 350 万面对象按 4 个材质槽拆分后,原对象拿到的是**槽 0**,而不是文档说的"最后一个槽"。当时先按"我的理解"把文档写成"保留最后一个材质槽"就发了 v1.15.0,直到这次拆 `对象9287` / `对象9041` 才发现两个原对象拿到的**都是槽 0** —— 与文档相反
- 根因:Blender 的实现是"**反复把当前第一个面的材质组切走**",最后剩下的那组留在原对象;而"最后剩下的"= **面序里首次出现位置最晚的**那组,与"材质槽索引最大"**没有必然关系**。我先前是**从直觉(槽顺序)反推**,而不是从数据反推
- 解决:
  - **判别实验**:构造 7 个用例,让 4 种候选理论("最低索引"/"最高索引"/"最后一个面的材质"/"首现最晚")给出**互相排斥**的预测,一次性筛掉 3 种(前三种全部被证伪;
    注意:第一版实验用共享边的三角条带造拓扑,触发 `EXCEPTION_ACCESS_VIOLATION` 崩溃,改**互不相邻的独立四边形**才稳定)
  - **源码印证**:`source/blender/editors/mesh/editmesh_tools.cc` · `mesh_separate_material` ——
    逐轮取 `BM_iter_at_index(bm_old, BM_FACES_OF_MESH, nullptr, 0)`(当前第一个面)的 `mat_nr`,
    若该材质已覆盖全部剩余面(`tot == bm_old->totface`)则 `mesh_separate_material_assign_mat_nr(...)` 并 `break`,
    否则 `mesh_separate_tagged(...)` 把这组切走。机制与实验结果完全一致
  - **真实对象复核**:累计 **9/9** —— `对象9041` 各组首现面 = 槽0:1128 / 槽1:0 / 槽2:660 / 槽3:664 ⇒ 槽0 首现最晚 ⇒ 原对象拿到槽0(与实测一致)
  - 已修正 v1.15.0 起的 **5 处**文档表述(README 索引 / 技巧速查索引 / 独立文档 / 包 README / AGENTS),
    CHANGELOG 的历史条目**不改写**,只加"此项表述已被 v1.15.2 修正"标记
- 预防:① 凡是把"行为规则"写进文档,必须**先做判别实验再写**,不能凭对 API 的记忆或类比 ② 设计实验时让候选理论给出**互相排斥**的预测,
  一次实验就能筛掉多个 ③ 有能力时一定回到**源码**找实现,源码能给"为什么"而不只是"是什么" ④ 发现写错后,
  **历史 CHANGELOG 不改写、只加修正标记**(详见 CHANGELOG v1.15.2、docs/按材质拆分为多个网格体.md)

## 问题:验证器的"判据口径"两侧不等价 ⇒ 会稳定误报,而数据其实没变

**TL;DR**:验证器用"世界包围盒并集"判几何守恒,但基线侧算的是"局部 AABB × `matrix_world`"(**松上界**),
拆分后侧算的是"各部件局部 AABB 的并集"(**更紧的界**),并集几何上必然 ⊆ 原上界 ⇒ **无论数据对不对都会报漂移**。
两次真实拆分各报一次(`1.557e-03` / 另一个),把人往"拆分损坏了几何"的方向引,实际几何**逐位未变**。
改用"两侧都取逐顶点局部坐标 min/max"后偏差降到 `4.5e-07`(小于该量级 float32 的一个台阶)。

- 问题:`对象9287` 拆分后,验证报告第 7 节"世界包围盒漂移 `1.557e-03`",但同一对象的第 2 节(面/顶点精确守恒)、
  第 4 节(`max|Δworld| = 0.000e+00`)、第 11 节(无孤儿)全部 ✅。"有些项全绿、唯独一项红"是典型的**判据问题**信号
- 根因:**两侧算法不等价**。`matrix_world @ bound_box[8点]` 是把"局部 AABB 的 8 个角"变换后取包围盒 —— 局部 AABB 经旋转必然膨胀;
  而拆分后是把**每个部件各自**的局部 AABB 变换后再取并集,每部件跨度更小、上界更紧。并集 ⊆ 原上界是几何必然。
  实测该对象真实世界范围是 Y `0.14~7.31`,而旧口径给出 `-11.28~16.31` —— **差一个数量级**,可见"松上界"松到什么程度
- 解决:
  - 换成**逐顶点局部坐标的 min/max** 做判据。两侧算法完全一致、与帧无关、不涉及旋转,应**精确相等**:
    `对象9287` 并集 vs 磁盘未拆分快照 `max|Δ| = 4.551e-07`;`对象9041` `4.141e-07`。
    该量级(坐标约 25 单位)下 float32 的可表示间隔约 `3.05e-05` ⇒ 差值**小于一个浮点台阶**,即逐位一致
  - 基线里新增 `local_extent` 字段;世界包围盒降级为"**仅供参考、不参与判定**",并打印说明为何不判定
  - **权威对照源**:用户存盘的 .blend(拆分前)+ 独立 headless 进程**只读**打开取基线 —— 不碰用户正在编辑的会话
- 预防:① 写验证器时,先问"**两侧算的是不是同一个量**",算法不一致的指标宁可不判也别误报
  ② 出现"多数项绿、个别项红"时优先怀疑判据,而不是数据 ③ 与"不可能变"的权威快照(磁盘文件)对照,
  是消解"到底变没变"争论的最快路径 ④ 精度判据要给出"对照量级"(如 float32 eps),否则 `4.5e-07` 是好是坏无法判断
  (详见 docs/按材质拆分为多个网格体.md、脚本 scripts/separate-by-material/verify_separation.py)

## 问题:空槽材质「拆分后还在、Ctrl+S 后永久消失」—— 删它的不是拆分算子,是存盘孤儿清理

**TL;DR**:`separate(type='MATERIAL')` 对**空材质槽**(有材质、零面)的对象拆分后,空槽里的材质数据块变成
`users=0` 的孤儿 —— **当时还在**(Blender 不立即释放),但**一存盘就被当作孤儿丢弃**,重新打开文件即不存在。
所以「拆分 + Ctrl+S」对**只被本对象引用的空槽材质**等于永久丢失。要保命就先打 `use_fake_user`。

- 问题:空槽自测里 `MAT1_beta`/`MAT3_delta` 拆分后从场景消失,第一反应是"算子把材质删了";
  但真实场景 `对象9287` 的两个空槽材质 `users` 却只是 3→2(没丢) —— 两种现象必须用同一机制解释
- 根因:三级分辨实验(拆分前 / 拆分后未存盘 / 存盘后同进程 / 重新打开)钉死时序:
  `users=1` → 拆分后**仍在、users=0** → 存盘后同进程**仍 users=0** → **重新打开 = GONE**。
  即算子只清槽不删材质;真正的删除者是 **Blender 存盘时的孤儿数据清理**。
  真实场景材质没丢,只是因为它们**另有别的使用者**(users 归零才是丢失的充分条件)——两种现象同源
- 解决:
  - 执行脚本新增 `KEEP_EMPTY_SLOT_MATERIALS = True`:拆分前给空槽材质打 `use_fake_user`,实测材质存活、`fake=True`
  - 验证器第 9 节改**分级判定**:`[有面槽]`材质丢失 = ❌ 真问题;`[空槽]`材质消失/归零 = ⚠️ 预期内但确实变了数据,
    计入新 `WARN` 列表、不计入 FAIL —— 报告必须让人"知道发生了什么",而不是简单红绿
- 预防:① 凡改变对象-数据块引用关系的操作,先问"**引用归零的数据块会怎样**"——Blender 的答案几乎总是
  "存盘时清掉";`use_fake_user` 是唯一的拦路符 ② 探究"X 什么时候发生的"用**三级/多阶段分辨实验**
  (操作前/操作后未落盘/落盘后/重开文件),一次只动一个变量 ③ "另有个案没丢"与"机制会丢"不矛盾,
  解释差异的钥匙往往是 users 计数(详见 docs/按材质拆分为多个网格体.md、CHANGELOG v1.15.2)

## 问题:删除对象后"旧引用立即失效" —— 连 `o.name` 都会抛 `ReferenceError`

**TL;DR**:`bpy.data.objects.remove(o)` 之后,`o` 这个 Python 包装器**当场变成死对象**,
连读 `o.name` 都抛 `ReferenceError: StructRNA of type Object has been removed`。
⇒ 所有要用的字段必须在**删除之前冻结成纯 Python 值**;删除后的核验必须**重新取引用**。

- 问题:删除脚本跑完 71.88 s、实际删除也成功了,但末尾的核验段直接抛 `ReferenceError`,
  结果报告一个字都没落盘 —— 看起来像"删除失败",实际是**报告代码踩了自己的坑**
- 根因:Blender 删除 ID 会立刻回收其 RNA 结构;Python 侧保留的引用不再有效(不是惰性失效,是**立即**失效)。
  删除循环里 `bpy.data.objects.remove(o)` 之后再去 `o.name`、`o.users_collection`、`o.parent`、`o.animation_data`
  全都炸 —— 而"把被删对象记进名单"这个需求天然要用到这些字段
- 解决:
  - 删除**之前**遍历一遍待删集,把 `(name, collections, parent, ancestor_chain, children, has_anim)` 全部读成
    `str/int/tuple` 存进纯 Python 列表,再执行删除、再写名单
  - 核验段**重新** `objs2 = list(bpy.data.objects)` 取全新引用,**绝不复用** `objs` / `deletable`
  - 保留对象要做前后对比时,同样在删除前把 `matrix_world.translation` 冻结成 `(x, y, z)`
- 预防:① 凡"遍历删除"的脚本,先划一条界线:**界线之上只读、只冻结;界线之下才删**;
  ② 别在循环外继续用循环里的元素;③ 报告/名单一律"先写盘再删"(顺序错了超时后连痕迹都没有);
  ④ 这个坑在本机**连踩两次**才写进文档 —— 加 `mark(stage)` 逐阶段落盘能让它更早暴露
  (详见 docs/空物体收敛清理.md、scripts/scene-cleanup/purge_empties.py)

## 问题:全属性遍历 2 万对象要 7 分钟(桥 120s 上限) —— 改"打靶式扫描"

**TL;DR**:用 `ob.bl_rna.properties` 逐属性找"谁引用了这个对象",在 22315 个对象上要跑约 **7 分钟**,
必然超过桥的 120s;而且超时**不会**中止脚本、桥在期间对外完全无响应。
改成"只打有引用可能的靶点"只需 **12~20 s**。

- 问题:第一次写"空物体能不能删"的体检脚本,想穷举所有可能持有 Object 引用的属性,于是对每个对象跑
  `bl_rna.properties` 全遍历。脚本发出去 120s 超时,客户端断线;**Blender 主线程还在跑**,
  后续请求只排队不执行,一度以为把 Blender 搞死了(CPU 从 254s 涨到 535s 才结束)
- 根因:`bl_rna.properties` 返回的是**该类型全部属性**(含数百个内置项),对每个属性还要 `getattr`,
  单对象成本 ~18 ms × 22315 ≈ 7 min。而真正能持有 Object 引用的属性**只有那么几个**
- 解决:列白名单**打靶**扫描 —— 对象约束 `c.target`、姿态骨骼约束、`pose.bones[*].custom_shape`、
  修改器指针属性(仅修改器用 `bl_rna` 细扫,数量少)、驱动 `variable.targets[*].id`、
  骨骼约束、`camera.dof.focus_object`、粒子 `dupli_object/instance_object/object/render_object`、
  `scene.camera`、节点树 `inputs[*].type == 'OBJECT'/'COLLECTION'` 的 `default_value`
  - 同时**必须排除** `Scene.objects` / `Collection.objects` / `ViewLayer.objects` / `Collection.all_objects`(成员关系)
    与 `ID.original`(副本来源指针) —— 否则全场景 5006 个对象都会被标成"被引用",体检直接失效
  - 另外别用 `ob.children` 做父子关系遍历(每个调用都是对全场景的 O(n) 重算),自己建一次映射
- 预防:① 远程脚本先估"单元素成本 × 元素数",超过 60s 就换算法;② 长任务**状态逐阶段写盘**,
  超时后读盘回捞(`[stage fixpoint 12.3s]` 这类标记);③ "扫不出来"和"真的没有"要能区分 ——
  本机正是靠"扫描量为 0"这一行才敢断定该工程**没有驱动器**(动画全靠 Action)
  (详见 docs/空物体收敛清理.md、scripts/scene-cleanup/purge_empties.py)

## 问题:"缺 105 个贴图"是误报 —— 判缺失必须带 `not img.packed_file`

**TL;DR**:清理后核验脚本报"真缺失贴图 105 个",虚惊一场 —— 它们**已打包在 .blend 里**,
只是原始 `filepath` 早就失效。判定缺失必须加 `not img.packed_file`。

- 问题:清理完跑核验,`[6] 真缺失贴图: 105` —— 数字很大,第一反应是"清理删坏了贴图"
- 根因:判定式只看了 `img.source == 'FILE' and img.filepath and not os.path.exists(abspath)`,
  漏了 `packed_file` 这一项。这 105 个贴图的原始路径(`游里屋顶街区模型(水晶版)\maps\`)早年就失效了,
  但**数据已打包进 .blend**,Blender 自己不会报警(它优先用打包内容)
- 解决:判定式补齐 `and not img.packed_file`;清理前的体检脚本本来就有这一条,是**核验脚本漏抄**了
- 预防:① 同一条判据在"体检脚本 / 核验脚本 / 技能文档"里出现多次时,抽成同一段说明并交叉核对;
  ② 核验报出大数字时先与"清理前体检结论"对照 —— 前后不一致的**要么是真问题、要么是口径不一致**,
  两种都必须查清才能结案,不能只回一句"误报"
  (详见 docs/空物体收敛清理.md §8、CHANGELOG v1.16.0)

## 问题:"只删无子级空物体"删不干净 —— 中转容器会迭代"长出"新的无子级

**TL;DR**:空物体清理**不是一次性过滤**。删掉一批叶子后,原本挂着它们的中转容器自己变成了叶子,
必须**迭代到不动点**;一次性按"当前无子级"删会漏掉约 1/3(实测 5006 → 7467)。

- 问题:按字面"清理没有子级的空物体"删掉 5006 个后,Outliner 里**又出现 2026 个无子级空物体**,
  用户看到后问"怎么还有"
- 根因:空物体是**树**。`Group-* → Untitled.001`(叶子)删掉叶子后,`Group-*` 变成新的叶子。
  "无子级"这个谓词在删除后会**重新变真** ⇒ 这是**求不动点**问题,不是一次筛选
- 解决:**一次算准最终可删集**(引用图 + 不动点),而不是删一轮再扫一轮(反复全量扫描还会撞 120s 上限):
  `EMPTY 需要保留 ⟺ 它支撑某个非 EMPTY 对象`,支撑含"子级里有需保留的 EMPTY"这一条传递闭包:
  种子 = 全部非 EMPTY 对象 + 被外部数据块引用的对象,每轮把满足规则的 EMPTY 加进保留集,直到无新增(实测 2 轮)
  - 顺带一个用户预期管理点:**清理要给出范围选项**(只删当前无子级 / 迭代到收敛 / 只删静态的),
    并**明确告知选第一种会剩下什么** —— 本机第一次就选了字面范围,第二轮才补做
  - 另附:空集合 ≠ 空对象(`objects=0` 的 `Export` 集合 `users=1` 挂在场景根,
    用 `bpy.data.collections.remove(col, do_unlink=True)`,要单独问用户)
- 预防:① 凡"批量删除会改变判定条件"的操作,一律先想"**这个谓词删完还成立吗**",成立就求不动点;
  ② 给用户的选项要带"**选了之后还剩什么**",否则用户只能靠猜;③ 交付必须带独立核验(另一支脚本 + 重新取引用),
  "非 EMPTY 对象数""可见几何包围盒"这类**不可能变**的量逐位相等,才是"没动几何"的硬证据
  (详见 docs/空物体收敛清理.md、scripts/scene-cleanup/README.md)

## 问题:"配了发光材质渲染还是黑的" —— 两层原因叠加,只查一层必得出错误结论

**TL;DR**:这类问题 90% **不在材质节点里**。本次真凶是 **View Layer 材质覆盖**(视图层属性,
材质树里永远查不到);清掉之后**还有第二层** —— 用户把 `Emission Strength=100` 设在了
**未接输出**的孤儿 BSDF 上,真正生效的那个只有 10。

- 现象:对象 `图形1371.001` 配了发光材质,渲染出来是黑的
- 排查(按命中率,一次打全七条):
  ① `view_layer.material_override` —— **命中**。它是 View Layer 级属性,非 None 时该层**全部对象**材质被替换,
     在材质树里怎么翻都翻不到
  ② 引擎 —— 原为 `BLENDER_WORKBENCH`(**完全不读材质节点树**,发光永不生效),用户已切 `CYCLES`
  ③ Holdout / 相机可见性 / 视图层 Exclude —— 全 False,不命中
  ④ 输出连线 —— **第二层命中**:该材质内有 **2 个 Principled BSDF**,`原理化 BSDF`(`Emission Strength=100`)
     **未接输出**,真正接到 `材质输出.Surface` 的是 `原理化 BSDF.001`(只有 **10**)
  ⑤ `view_transform = AgX` —— 仍在生效,AgX 下 10 的强度偏弱(它只解释"不够亮",**不解释"纯黑"**)
- 根因:两个独立的坑叠在一起,且**第二个在第一个被解决之后才会暴露** ⇒
  只盯着用户提到的那一条线索,会直接漏掉第二层
- 解决:先 `vl.material_override = None`;再确认发光设在了**接到输出的那个**节点上;
  最后按 AgX 特性提高强度。诊断脚本 `scripts/blackout-diagnose/diagnose_blackout.py` 一次打全七条路径
  (236 材质实测 **0.05 s**),并自动列出"发光>0 但未接到输出"的**孤儿节点**
- 预防:① 报"材质不生效"按**全局 → 局部**顺序查(覆盖/引擎/Holdout 是一刀切级的,命中率远高于节点连线);
  ② 排查脚本必须显式输出"**输出节点连的是谁**"+"**孤儿发光节点**";
  ③ 别用 `mat.diffuse_color` 判断(那是视口颜色,与节点树结果无关);
  ④ 材质可能被几十个对象共享(本例 **62 users**)⇒ 改前先报 users 数
  (详见 docs/渲染发黑与材质不发光排查.md、scripts/blackout-diagnose/README.md)

## 问题:PowerShell `Set-Content -Encoding UTF8` 会写 BOM —— 桥端 `exec` 直接 SyntaxError

**TL;DR**:Windows PowerShell 5.1 的 `Set-Content -Encoding UTF8` / `Out-File -Encoding UTF8`
**会写入 UTF-8 BOM**(PS 7 才有 `utf8NoBOM`);送给桥的脚本第一行就被判非法字符,脚本完全跑不起来。

- 现象:用 PowerShell 拼接生成的 `_smoke.py` 发到桥,返回
  `SyntaxError: invalid non-printable character U+FEFF`,报错行是 `# -*- coding: utf-8 -*-`
- 根因:桥端是 `exec` 收到的源码文本,**不吞 BOM**;
  而 PowerShell 5.1 的 `-Encoding UTF8` 语义恰恰是"UTF-8 带 BOM"
- 解决(任选):用 Write 类工具直接落盘 / PowerShell
  `[System.IO.File]::WriteAllText($p,$s,(New-Object System.Text.UTF8Encoding($false)))` /
  Python `open(p,"w",encoding="utf-8",newline="\n")`
- 预防:凡"**生成文件 → 交给另一个程序解析**"的链路,都要核对首字节。
  注意本机 `bl.py` 落的 `.out` 是客户端写的、不受影响;**手工生成的输入脚本才是风险点**
  (详见 skills/blender-bridge-ops/SKILL.md「脚本文件绝不能带 BOM」)

## 问题:验证器判据用了「绝对值 / 全场景口径」⇒ 必然误报或串扰(两个同源实例)

**TL;DR**:验证器第 11 节两条判据都错在**口径**上 —— ①"存在 `users=0` 的 mesh 就 ❌"是**绝对判据**,
工程本就有历史遗留孤儿时**干净操作也必然报失败**;②"新增对象数 == 槽数-1"用的是**全场景**差集,
多对象连做时会把别的操作新增的对象也数进来。正解:**判据一律取差集,且精确到本次操作的对象集合**。

- 现象:对象 `水晶走廊_纵向灯2`(3,505,328 面 / 4 个材质槽)按材质拆分后,
  面数·顶点数·世界矩阵·UV·自定义法线·逐组锐边·材质 users 等 **35 项全绿**,
  结论却是「❌ 判定:不通过 —— 1 项异常 / 35 项通过」。**"不通过"这三个字会让人误以为拆分坏了**
- 定位:异常项是 `存在 users=0 的孤儿 mesh: [Mesh.5301, …, Mesh.5658]`(10 个)。单独核实这 10 个:
  `users=0`、每个仅 **26~78 面**、统一用材质 `std_8twe.002`、**编号远早于本次新增的 `Mesh.6209~6211`**
  ⇒ 早期删对象留下的数据块,**与本次拆分无关**。反证也成立:拆分只把 1 个 mesh 变成 4 个
  (原 mesh 保留 + 3 个新建),**从不产生孤儿**;基线 mesh 数 5867 → 现在 5870 恰好 +3
- 根因:`verify_separation.py` 第 11 节 `orphan_mesh = [m.name for m in D.meshes if m.users == 0]`
  之后**有则报错** —— 判据取的是"**此刻的绝对值**"。而基线里明明已经存了"操作前的全场景数据块名单"
  (`mesh_names_before`),却没有拿它做对比。**手上有基线却用绝对值 ⇒ 等于没用基线**
- 解决:基线新增 `orphan_mesh_before`(名单)+ `orphan_mesh_count_before`;
  验证改为 `orphan_now - orphan_before`(本次**新增**)= ❌、`orphan_now & orphan_before`(操作前既有)= ℹ️ 提示
  (与本次无关,且 Blender 存盘时本就会按孤儿丢弃)。兼容旧基线:缺该字段时本项降级 ⚠️、**不计入失败**。
  复跑同一工程 → **36 项全绿**,结论由"不通过"变为"全部通过"
- 预防:凡"存在性检查"(孤儿数据块 / 空集合 / 缺贴图 / 游离引用),先问自己
  "**这个现象是本次操作造成的,还是操作前就有?**" —— 只有**基线差集**能回答。
  绝对值判据在干净的新场景里看不出问题,**一到真实工程就稳定误报**
  (详见 docs/按材质拆分为多个网格体.md §坑11、脚本 scripts/separate-by-material/verify_separation.py)

### 同一病根的第二例:计数判据用了「全场景口径」,多对象连做时串扰

- 另一条判据 `新增对象数 == 材质槽数-1`,其 `new_objs` 取的是 `set(D.objects) - before_objs`
  —— 这是**全场景**差集,**没有精确到本次操作的对象**
- 触发:同一场景**连着拆两个对象**(先 `水晶走廊_纵向灯`、后 `水晶走廊_竖向灯`),
  回头复验前者时,看到「ℹ️ 新增对象数 **4** != 材质槽数-1 (1)」——
  多出来的 3 个是**后拆那个对象**产生的新部件
- 与上一例的共性:**不是"操作错了",而是"判据口径错了"**。判据取"全场景此刻的绝对值",
  而基线录完之后场景里只要**还发生过别的结构改动**,口径就串了
- 解决:只统计「以 `TARGET + "."` 为前缀的新增对象」= **本组新增**;全场景多出的部分降为附注
  ("另有 N 个新增对象,属其它操作"),并把本项由 note 升级为**真判据**(本组数不对 ⇒ ❌)。
  前缀写法对"名字互为前缀"的对象安全:`纵向灯` 是 `纵向灯2` 的前缀,但 `纵向灯2.001` 不匹配 `纵向灯.`
- 复验:`水晶走廊_纵向灯` 23 项 → **24 项全绿**,误导性提示消失
- 预防:**凡判据里出现"全场景统计量"(对象数 / 数据块数 / 类别计数),
  先问"这个数会不会被其它操作影响"** —— 会,就必须限定到本次操作的对象集合。
  工程里的操作**是连着做的**,这一点比"场景是否干净"更容易被忽略

## 问题:改名一个参数,却把 7 盏灯的驱动改成了「静默失效」(漏扫 `data.node_tree` 层)

**TL;DR**:查"谁在读这个自定义属性"时只扫了对象/数据块/材质,漏掉了**灯光数据块自带的节点树**
(`o.data.node_tree.animation_data`)⇒ 同一处漏扫造成两个后果:**先**把接了线的参数误判成"假控件",
**后**在改名时把漏扫到的 7 条驱动变成 `is_valid=False`(画面停了、UI 毫无异常)。

- 问题:用户要求把控制物体 `竖向灯001_噪波控制` 的 `Z向速度` 改名为 `X向速度`(滚动轴 Z→X)。
  按"改名 + 驱动换分量 + 删旧键"做完,主材质实测正确(X 分量逐帧 = 帧号×速度)。
  但**交叉复检**发现:7 盏面光灯各自节点树里都有一条 `nodes["滚动映射"].inputs[1].default_value`
  (idx=2)的驱动指向 `["Z向速度"]` —— 属性删了、它们没跟着改,于是全部 `is_valid=False`。
- 根因:第一轮"谁在读这个属性"的扫描清单少了 `物体数据 → node_tree` 一层
  (`o.animation_data` / `o.data.animation_data` / 材质 / 材质节点树 / 对象 / 对象数据都扫了)。
  **Blender 5.x 的灯光/网格数据块自带 node_tree**,而这套系统的面光灯是"材质节点链同构接入"的,
  驱动全挂在 `AreaLight → Shader Nodetree` 上 ⇒ 漏扫直接导致"消费者清单"少了 7 条。
- 同一漏扫的第一次发作(**更早、更容易骗过人**):我曾据此断言 `面光统一强度` 是"假控件(全库零引用)",
  而它其实由 7 盏灯的 `发光强度.001` 在读(`expr='st * k'`)。**为证伪,改一次值读下游**:
  12.757 → 20,7 盏灯节点读数**当场全变 20.0000** ⇒ 链路完好,结论完全相反。
- 解决:
  1. 扫描清单补齐 `o.data.node_tree.animation_data` 与 `o.modifiers[i].node_group.animation_data`;
  2. 把 7 条驱动 retarget 到 `["X向速度"]` **并同步搬到 X 分量**(与主材质同轴);
  3. 新增"失效体检":全库 `is_valid=False` + 悬空引用(`data_path` 指向已不存在的键)⇒ **判据 0 条**
     (修复后实测:驱动总数 78、失效 0、悬空 0 = PASS);
  4. 动态验证:参数设 0.5、`frame_set(100)` → **主材质 + 7 盏灯共 8 个插槽全部 = 50.0**,逐位一致
- 预防:
  - **凡按名字/引用做跨 data-block 的改名或删键,先跑引用体检拿清单**;数量对不上就别动手;
  - **改完必须跑失效体检**(两类静默问题只有体检能抓到);
  - 经验法则:**`hasattr(x, "node_tree")` 为真的 data-block 都要往下再扫一层**;
    下"假控件"结论前的最后一道闸是**实测**(改值读下游),不是静态判断
  - (详见 docs/驱动参数化材质维护.md,脚本 scripts/driver-param-maintenance/)
