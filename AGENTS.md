# AGENTS.md · 项目规则

> 📌 **文档基线**:2026-08-21(commit 2f8ad54)驱动式旋转 + 视口录屏 v1.3.0
> **更新文档/代码后,请更新此行**(日期 + 新 commit hash),并在 CHANGELOG 追加版本

## 技术栈

- Blender 5.2(Windows)+ Python API(bpy),脚本在 Blender Scripting 工作区运行
- 远程控制:本地 Socket 桥(`127.0.0.1:9877`),主线程执行,零插件依赖
- 多 Blender 并存:桥端口可改(如 9878),send.py 第二参数指定端口

## 关键坑(代码里看不出的)

- `bpy.context` 只能**主线程**访问 → 远程执行必须用 `bpy.app.timers` 调度
- **Blender 5.2 Slotted Action**:`action.fcurves` 不存在!读/建曲线用 `action.fcurve_ensure_for_datablock(obj, path, index=i)`(index 必须关键字传参);**读取已存在曲线**:`action.layers → layer.strips → strip.channelbags → cb.fcurves → fc.keyframe_points`(channelbag 有 slot_handle 区分 OB对象/CA相机数据)
- **同一次 exec 内改完立即验证会读到未刷新缓存值** → 修改与验证必须分两次请求,以新请求为准
- **探查脚本禁止 `round(kp.co[0])` 统计帧号**(banker's rounding 掩盖 .5 帧,如 361.5→362);用精确值 + `abs(f-round(f))>1e-6` 筛小数帧
- **Blender 没有"反转关键帧"菜单**!反转 = 关键帧菜单 → 镜像(`Ctrl-M`)→ 沿时间轴关于当前帧(播放头放中间帧)或沿时间轴关于时间 0
- **send.py 大任务(全量遍历 5 万+ 对象)>120s 会报超时,但桥实际执行完** → 超时后重跑同脚本验证(幂等脚本);写操作先备份
- **重复网格合并指纹必须含材质+UV**(几何相同≠可合并);合并前抽检真实顶点坐标;合并后同组对象共享数据,编辑一个全部同步
- **parent 赋值后手动设 mpi**:`child.parent = empty` 在 5.x 不自动更新 matrix_parent_inverse → 世界位置 = 父位置+局部(翻倍)!必须 `child.matrix_parent_inverse = empty.matrix_world.inverted()`;空对象先定位到目标位置再挂载;设置 location 后 view_layer.update() 刷新
- **循环渐变 ColorRamp**:等分数=颜色数×4;同色连标=平台,删过渡中点=线性过渡,首尾同色=无缝循环;插值必须 LINEAR(EASE 会抖);滚动用 Mapping Location 关键帧,勿移动空对象
- **Object 坐标只跟随平移,不跟随旋转**:转空物体不会让纹理旋转!旋转类动画用材质节点内偏移(ADD + driver);循环取模用 FLOORED_MODULO(负数正确,普通 MODULO 负值裁剪);材质节点 driver/keyframe 路径必须 inputs[N] 数字索引(名称形式报 not found)
- 直接改 IDProperty(如 `obj['vis']=[0]`)后驱动不重算 → 必须 `obj.update_tag()` + `bpy.context.view_layer.update()`
- 关键帧**末帧插值不影响任何可见段**(段由段首帧决定);要"结尾直线"改**倒数第二帧**为 LINEAR
- C4D 式"中间平滑+两头线性":**两头 Free handle 手动对齐线段**,中间保持平滑;改 LINEAR 会产生折角
- **5.2 合成器**:`scene.node_tree` → `scene.compositing_node_group`;**Composite 节点已移除**(渲染结果不自动显示,用 Viewer 或移除节点组);File Output 的 Media Type 默认 Multi-Layer EXR(要 PNG 必须改 Image 或槽勾 Override Node Format)
- **use_nodes 在 5.x 恒 True 无法关闭**;"关合成器"= 移除 compositing_node_group(空节点组=幽灵状态,渲染不输出)
- **远程脚本不要写合成器节点树**(新建/删除 File Output、槽操作会触发 5.x 已知崩溃 bug)→ 合成器写操作一律 GUI 手动,远程只读探查
- **3ds Max 导入对象改轴心必须"先 Apply 再设原点"**:导入对象全带非单位缩放/旋转(部分负缩放),直接 `origin_set` 位置跳变 → 先 `bpy.ops.object.transform_apply(rotation=True, scale=True)` 再 `origin_set`;multi-user 网格(data.users>1)先 `obj.data = obj.data.copy()`;有动画对象跳过(详见 docs/3dsmax导入场景清理与轴心修复.md §3)
- **5.2 API 变化**:`obj.apply_transform()` 不存在(用 ops `transform_apply`);`action.fcurve_find`/`ActionSlot.fcurves` 不存在(用 `fcurve_ensure_for_datablock` 判空);`bpy.context.undo` 移除;`obj.lock_get()` 不存在(用 `hide_select`);`bpy.data.user_map()` 返回 set 不可切片
- **清动画先静态化**:`animation_data_clear()` 是 API 不进 undo 栈、action remove 不可撤回 → 清前先记录 matrix_world 恢复 matrix_basis,相机动画(对象级 + camera data 级)先确认保留名单
- **Blender 5.2 驱动变量无 `SELF` 类型**:旧写法 `vf.type='SELF'` 报非法类型 → 用 `d.use_self=True`,表达式里 `self` 即可引用当前物体(用于读 `self['bob_base_z']` 等自身属性)
- **自定义属性显示名就是键名**:想中文 UI 直接把键设成中文(`obj['最大上移']=1.0`);`id_properties_ui(k).update(name=...)` **不接受** `name` 参数,改显示名只能改键本身(逻辑读键也得同步改)
- **改名控制物体 / 替换驱动函数后旧驱动"陈旧"**:depsgraph 不把旧驱动标记为需重算,求值直接返回基准值(看似不动);给每个 Z 驱动调一次 `d.update()` 刷新(不动 seed/基准,花样保留)
- **驱动依赖的命名空间函数(如 bob)不随 .blend 保存**:`bpy.app.driver_namespace` 是运行期全局,重开文件函数丢失 → 驱动变红;必须用文本块 `bob_driver.py` 勾 Register 持久化,或手动 Run Script 一次
- **基准位置要保留**:给物体挂驱动时只在首次记录 `bob_base_z`(当前静止 Z),重建若已存在则跳过,避免把"被驱动当前值"误当基准导致跳原点
- **驱动里读帧用 SINGLE_PROP 指向 scene.frame_current**(不依赖内置 `frame` 变量,5.x 驱动命名空间默认无 `frame` 键,更稳)
- **Z 轴旋转驱动用 `rotation_euler[2]`,不是 `rotation`/`rotation_quaternion`**:直接给四元数 `rotation` 挂驱动路径会被当四元数读,结果错乱;务必 `driver_add('rotation_euler', 2)`;构建时把基准角 `rotation_euler.z` 复位为 0,否则会从被污染角度(如残留 100°)累加
- **Blender 5.2 视口录制(opengl/FFMPEG)输出配置顺序**:必须先 `image_settings.media_type='VIDEO'`,**再** `image_settings.file_format='FFMPEG'`;顺序反了直接报 `'FFMPEG' not found in enum`(VIDEO 之前该枚举项未就绪)
- **驱动命名空间函数持久化(spin 同 bob)**:`spin_speed()` 也不随 .blend 保存;用 `spin_driver.py` 文本块 + Register,或用 `scripts/driver-restore/restore_drivers.py` 一键重跑 bob/spin 文本块恢复,避免重开文件驱动变红

## 约定

- 文档用中文;技巧按"场景 → 做法 → 坑"组织;一坑一篇进 DEVELOPMENT.md

## 常用命令

- 远程执行:`python send.py <code.py>`(桥脚本在 `scripts/blender-remote-control/`,跨机器可复用;README 含完整说明)
- 验证桥:`netstat -ano | grep 9877`
- 手动改 handle:Graph Editor 选中关键帧按 V

## 详细规则(按需 @引用)

- @docs/技巧速查.md
