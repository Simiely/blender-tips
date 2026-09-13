# AGENTS.md · 项目规则

> 📌 **文档基线**:2026-09-13(commit `ba8d942`)v1.17.0 渲染发黑与材质不发光排查(#35)+Skill `blender-render-blackout-diagnose`+材质覆盖/孤儿 BSDF/BOM 三条坑
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
- **材质节点驱动引用自定义属性,改属性值不自动重算**;实时刷新落地:UI 面板(Panel.draw)里检测属性变化后 `ctl.update_tag()` + `view_layer.update()`;面板/函数注册用 Register 文本块(use_module=True)+ Auto Run 随 .blend 自愈(见 docs/材质参数统一控制器与实时面板.md,脚本 scripts/ring-control-panel/;`frame` 在 5.2 SCRIPTED 驱动表达式里可用)`
- **5.2 给 Value 节点输出打关键帧不生效**:对 `outputs[0].default_value` `keyframe_insert` 后 fcurve 求值对,但 Slotted Action 下评估值恒定(原始/评估都=默认)→ UI 看开关一直是 1。**时间开关参数要用驱动**:命名空间函数读 `scene.frame_current`,SCRIPTED 驱动 `grad_window(fr)`,函数写 Register 文本块持久化;验证必须 `deps.id_eval_get(mat)` 读评估值;读关键帧走 `action.layers[].strips[].channelbag.fcurves`(见 docs/帧窗口驱动时间开关.md,脚本 scripts/frame-window-time-switch/)`
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
- **驱动引用的命名空间函数:源码存于文本块、随 .blend 保存;但运行期的 `bpy.app.driver_namespace` 映射不落盘**(API 只存"把哪些文本块标 Register",运行后再把函数填进 namespace)→ 重开文件若没人重新注册,驱动变红、物体掉 Z=0。**正解(官方机制,5.2 实测)**:文本块勾 Register(=`use_module=True`, UI 的 Register 复选框;`use_register` 是 5.2 已不用的旧 API 名)+ 偏好设置开 Auto Run Python Scripts → 载入时该文本块**自动执行**把函数重新填进 namespace,无需手动恢复。判断依据:Blender 手册 Scripting & Security("Registered Text-Blocks ... will load on start",受 Auto Run / Trusted Source 控制)
- **基准位置要保留**:给物体挂驱动时只在首次记录 `bob_base_z`(当前静止 Z),重建若已存在则跳过,避免把"被驱动当前值"误当基准导致跳原点
- **驱动里读帧用 SINGLE_PROP 指向 scene.frame_current**(不依赖内置 `frame` 变量,5.x 驱动命名空间默认无 `frame` 键,更稳)
- **Z 轴旋转驱动用 `rotation_euler[2]`,不是 `rotation`/`rotation_quaternion`**:直接给四元数 `rotation` 挂驱动路径会被当四元数读,结果错乱;务必 `driver_add('rotation_euler', 2)`;构建时把基准角 `rotation_euler.z` 复位为 0,否则会从被污染角度(如残留 100°)累加
- **Blender 5.2 视口录制(opengl/FFMPEG)输出配置顺序**:必须先 `image_settings.media_type='VIDEO'`,**再** `image_settings.file_format='FFMPEG'`;顺序反了直接报 `'FFMPEG' not found in enum`(VIDEO 之前该枚举项未就绪)
- **驱动命名空间函数持久化(spin 同 bob)**:运行期 `driver_namespace` 映射不落盘,靠 **Register 文本块(源码随文件保存)载入时自动重注册**自愈;或 `scripts/driver-restore/restore_drivers.py` 一键恢复(内置强制重编译),避免重开文件驱动变红
- **Register 自动恢复已实测 100% 生效**:light_off/scroll_speed 文本块勾 Register + Auto Run → 重启后函数自动进命名空间、**全部驱动 is_valid=True 自动恢复**(843 驱动实测 INVALID 0),无需手动操作。文本块模板见 scripts/driver-lights/light_driver.py 与 scripts/glow-scroll-material/scroll_driver.py
- **恢复命名空间函数后必须强制驱动重新编译**:只 exec 文本块注册函数**不够**——depsgraph 仍缓存旧失败状态(`driver.is_valid=False`,求值失败返回 0 → 物体全部掉到 Z=0 错位)。必须对引用该函数的每条 SCRIPTED 驱动**重新赋值同值表达式**(`d.expression = d.expression`)强制重算。restore_drivers.py 已内置此步骤(注: 正常重启路径 Register 自动执行会连驱动一起恢复,无需手动重编译;此坑仅出现在"运行中 exec 注册"场景)
- **桥接 exec 时 `__name__` 是 `builtins` 不是 `__main__`**:远程执行的脚本若写 `if __name__=='__main__': main()` 会**静默不执行**(桥端只回 `OK` 无输出);脚本应直接调用 `main()`(Scripting 工作区 Run Script 同样如此)。仓库所有经桥执行的脚本(build_bob_drivers/build_spin_drivers/restore_drivers)均已去掉守卫
- **场景相机按帧切换通常靠时间轴标记绑定(Bind Camera to Markers),不是 action 动画**:playblast/录屏脚本**不要写死 `s.camera=某相机`**,否则覆盖标记绑定、丢机位切换;直接 `render.opengl(view_context=False)` 即跟随标记自动换机位(详见 docs/视口预览录制录屏式.md)
- **5.2 天空纹理(TEX_SKY)的太阳参数是节点属性,不是输入 socket**:inputs 里只有 Vector,`sun_elevation`/`sun_rotation`/`sun_intensity`/`sun_size` 全是节点属性,`sky.sun_elevation` 直接访问;挂驱动用 `sky.driver_add('sun_elevation')`
- **节点驱动存在 node_tree.animation_data 上,不是节点上**:`ShaderNodeTexSky` 无 animation_data 属性,驱动挂在 `sky.id_data`(节点树),路径 `nodes["天空纹理"].sun_elevation`;移除/排查驱动遍历 `nt.animation_data.drivers`(详见 docs/天空太阳高度驱动.md)
- **判断数据块共享用 `users > 1`,别只看数据块名**:`Mesh.537` 等序号名不代表独立,可能被多对象同时引用;遍历 `col.objects` 只处理目标集合内对象,集合外共享同数据块的对象不受影响(详见 docs/集合内对象数据独立化.md)
- **新建空物体后必须 `view_layer.update()` 再读 `matrix_world`**:否则读到单位矩阵 → `matrix_parent_inverse` 设成 identity → 子对象世界坐标 = 父位置+自身位置(翻倍偏移跑出集合)。任何"parent + 手动 matrix_parent_inverse"的脚本都要先 update
- **5.2 `DriverTarget` 无 `array_index` 属性**:SINGLE_PROP 读数组分量(如 location[0])用 `data_path='location[0]'` 带下标,不是设 `target.array_index`(会报 AttributeError)
- **驱动单向,不能 A↔B 互指**:循环依赖直接报错。旋转/位置联动只能"一主一从":主灯自由,从灯挂驱动读主灯 + 固定差(如向上灯为主,向下灯 = 向上 + (−π,0,0))(详见 docs/运动网格灯光方案.md)
- **SINGLE_PROP 读自定义属性"脚本内改值不重算"(可能读到 0),且旧脚本会写回常量覆盖 sun 驱动 → 用命名空间函数实时读 bpy**(`sky_sun_angle()` / `sky_sun_elev()` 读 天空控制["太阳角度"/"太阳高度"]);别再用旧 `build_sky_sun_driver.py`(详见 docs/天空太阳高度驱动.md,推荐脚本 `scripts/driver-sky/sky_driver.py`)
- **重启后天空驱动断开,多半是 .blend 内嵌的 sky_driver.py 文本块是旧版**(只含 `sky_sun_angle`,缺 `sky_sun_elev`)→ Auto Run 正常但高度驱动仍红:用仓库权威版覆盖该文本块,保持 Register,重注册并强刷驱动后 Ctrl+S(`d.expression=d.expression` 强制 Sun 驱动重编,Scripted 5.2 无 `d.update()` 需 try/except 兜底)
- **输出序列帧路径规范**:路径用相对 `//`(=工程文件目录)+ `output/<批次>/` + 文件名 `#` 帧占位(如 `260821x01####` → `260821x010001.png`,帧号插扩展名前);设图像格式**先 `media_type='IMAGE'` 再 `file_format='PNG'`**(镜像本表"5.2 视口录制 VIDEO 顺序",media_type 决定枚举域,顺序反了报 `PNG not found in enum`);用 `bpy.path.abspath()` 复核落盘路径;F12 不写盘先查合成器空节点组 ghost 状态(详见 docs/输出路径与序列帧输出规范.md)

- **应用缩放(scale归1)前先核实"几何本体自然尺寸"**:顶点已被放大而 scale 仍大(如局部±0.39 但 scale=37.9)→ 世界=几何×scale 双重叠加,应用后"越改越大"(实测 C-DT 569 应 15)。识别:对比同装置件量级、`dims≈几何范围×scale` 自洽性;批量前重梳理清单(仅静态 MESH)并排除可疑巨件再动手
- **应用缩放附加坑**:多用户网格(`data.users>1`)先 `copy()` 独立;负缩放(镜像)法向由 depsgraph 自动重算(5.2 已移除 `mesh.calc_normals`);对 scale≈40 的对象应用后局部坐标同倍数放大、局部空间操作精度下降;改/验分两次请求,先备份(记录原 scale 可逆还原)
- **⚠️ `obj.parent` 赋值会静默重置 `matrix_parent_inverse` 为单位矩阵**:必须**先设 `parent`、后设 `matrix_parent_inverse`**,写反了 MPI 被清成 identity(症状: 对象飞到别处、MPI 平移回读 `(0,0,0)`)。隔离实验逐项验证: `parent_type` 赋值 / `animation_data_clear()` / 写 loc·rot·scale / `frame_set()` 都**不**重置,**只有 parent 赋值重置**(详见 docs/动画转移到父级空对象.md §坑1,脚本 scripts/anim-transfer-to-empty/)
- **动画转移到父级空对象(动态转移)的通用解是 `MPI = B(F)⁻¹`(局部 basis 的逆),不是 `M(F)⁻¹`(世界矩阵的逆)**:只有参考帧处"局部==世界"(`mpi_old @ parent.world(F) == I`,如 F 帧父级 Z 旋转为 0)时两者才相等;自测构造 `M(F)` 与 `B(F)` 相差 6.35 单位的场景,用 `B(F)⁻¹` 得 0 偏差、用 `M(F)⁻¹` 会挪偏 6.35 单位。**推荐做法是再插一个无动画基点空对象、三段全用单位 MPI+单位 basis** → `M'(t) = D.world(t) @ I @ I`,乘单位矩阵精确,实测对原始基线偏差 **0.000e+00**,且本体本地变换彻底归零(打开 N 面板一眼可见动态全在上游,不会再误 K 本体)
- **验收角度偏差别用 `2*acos(qa.dot(qb))`**:`dot≈1` 时 acos 病态放大,实测把 **3.8e-06** 的矩阵差虚报成 **0.0396°**(放大 100+ 倍),会误判成"有真实漂移"。改用旋转矩阵**元素最大差**,或良态式 `2*asin(sqrt(x²+y²+z²))`;注意 `mathutils.Quaternion` **没有 `.vector` 属性**(用 `.x/.y/.z`)。验证量级参考: float32 eps = 1.19e-07,场景坐标量级 ~25 单位时位置偏差应在 ~1e-6
- **`location` 的坐标系是「父空间基底」(`parent.matrix_world @ matrix_parent_inverse`),既不是世界空间也不是对象自身空间**:`matrix_basis = T(location) @ R @ S` 平移在最左端 ⇒ 对象自身 `rotation` / `delta_rotation` 都**改变不了**位移方向。实测(父级绕 X 转 90°、子级自转 90°)K `location[2]` 的位移方向与自身 Z 偏 **90.0000°**。**`delta_location` 与 `location` 同坐标系**(不是"对象局部位移"),`delta_rotation` 也不把 `location` 带转(详见 docs/轴向位移-自身轴与世界轴.md,脚本 scripts/axis-space-motion/)
- **让位移沿【自身轴】/【世界轴】的统一心法**:想让位移沿哪个坐标系,就把"承载位移那一层"的**父空间**做成那个坐标系 —— 沿自身轴: `朝向层(放旋转) → 位移层(自身旋转恒 0,只 K location[2])`;沿世界轴: 中间插一层"抵消旋转"的**世界对齐层**。两种都**只需 K `location`,不做换算**;上层旋转即使是动画也逐帧精确(实测 0.000000°)
- **父级/上层朝向是动画时,"换算 + 只 K 两端"会走偏**(实测偏 **7.07 单位**,两帧之间只做父空间直线插值)⇒ 必须**逐帧 bake**,或用**世界空间约束**: 新建无父级空对象(世界空间)K 好动画 + 目标挂 `Copy Location`(`owner_space='WORLD'`,`target_space='WORLD'`,`use_offset=True`)—— 实测父级单轴/复合旋转均 **0.000000**,最通用
- **⚠️ 存 `matrix_world` 必须 `.copy()`**:`evaluated_get(dg).matrix_world` 返回的是**活引用**,不拷贝直接存进列表,循环结束后**所有样本都会变成最后一帧的值**(实测三帧采样全打印末帧,导致诊断脚本输出"自身Z vs 世界Z = 0.0000°"的**假结论**);`to_3x3()` / `to_translation()` 返回新对象,天然安全
- **验收"沿轴"别用"逐帧步进方向 vs 轴方向"**:目标轴随时间旋转时(如"沿自身轴"而自身轴在公转),位移向量本身就在转、基准轨迹也在动,该指标**必然误报**(实测真实偏差仅 8.1e-06 单位却报出 **112° / 163.86°**、被判失败)→ 正确判据是把位移向量分解为"沿轴分量 + **垂轴分量**",垂轴分量必须 ≈ 0
- **`Copy Rotation` 的 `owner_space` 只有 `WORLD`/`CUSTOM`/`LOCAL`(没有 `LOCAL_WITH_PARENT`)**:用来"抵消父级旋转"必须 `owner_space='LOCAL'` + `target_space='WORLD'` + `invert_x/y/z=True`(实测 `WORLD`/`CUSTOM` 均无效、仍偏 90°);且**逐分量 invert ≠ 矩阵求逆**,单轴成立、**复合旋转不成立**(实测偏 3.83 单位 / 45°),复合旋转改用 bake 或 `Copy Location`
- **判 `bpy.ops` 算子存在性必须用 `get_rna_type()` 包 `try`,不能信 `hasattr`**:实测 `hasattr(bpy.ops.mesh, "separate_by_material")` 返回 **`True`(假阳性)**,但 `get_rna_type()` 直接 `KeyError` —— 这个算子**根本不存在**,执行 `bpy.ops.mesh.separate_by_material()` 会失败。`bpy.ops` 上同类假阳性普遍存在
- **按材质拆分 = `bpy.ops.mesh.separate(type='MATERIAL')`(唯一真实算子)**:语义是"按**材质槽**、对**整个网格**生效、**与选择无关**"(官方手册原文)。**原对象保留「面序中首次出现最晚」的那一组**材质的几何(名字不变,故**名字与材质常对不上**;规则由源码 `mesh_separate_material` 与 7 用例判别实验双向确认,旧文档写的「最后一个材质槽」是错的),其余各组各生成 `原名.001/.002/.003`,**每个新网格只留自己那一个材质槽**;所有部件沿用原对象的局部变换与 `matrix_parent_inverse` ⇒ 世界位姿逐位重合(实测 4 部件 `max|Δworld| = 0.000e+00`)
- **空材质槽(有材质但零面)不产生对象,且其材质会被「存盘」丢弃**:源码只遍历**面的** `mat_nr`
  ⇒ 空槽不产生对象、也不被保留;`mesh_separate_material_assign_mat_nr` 把数据块 resize 到 1 个槽 ⇒ 空槽被清除。
  ⇒ **部件数 = 「有面的」材质槽数**(不是槽总数);只有 1 个槽有面时**完全不拆分**。
  ⚠️ **风险**:空槽材质在拆分后 users=0;**拆分算子不删它,是 Blender 落盘时按孤儿清理删的** ——
  实测三级分辨:拆分前 `users=1` → 拆分后未存盘**数据块仍在**、`users=0` → 存盘后同进程仍 `users=0`
  → **重新打开文件后已不存在**。若该材质只被本对象引用,**「拆分 + Ctrl+S」= 永久丢失**。
  要保住:拆分前 `mat.use_fake_user = True`(脚本包 `KEEP_EMPTY_SLOT_MATERIALS = True` 已内建,
  实测材质存活 `fake=True`、验证 24 项全绿),或先手工清空/移走这些槽。
  判定要看 **users 是否归零**,不能只看"是否下降":真实场景 `对象9287` 两个空槽材质另有使用者(3→2),**不受影响**
- **拆分后属性层"消失"≠ 数据丢失,但必须靠基线判定**:Blender 会丢弃结果网格上**全为默认值**的属性层。某部件 `sharp_edge` 层不见了,只有知道"**该材质组原本锐边数**"才能定性 —— 基线里必须记录 `sharp_by_mat`(逐组锐边数):该组为 `0` ⇒ 无信息损失,`> 0` ⇒ 真数据丢失。真实案例:材质3组 = **0**(属性层消失,无损失),其余三组 = 68142 / 2461210 / 80886,与拆分后部件逐组精确吻合
- **拆分后顶点数可能增加,属正常**:材质边界处**共享顶点**会被各组各复制一份(合成自测 52 → 64);只有各组拓扑独立时顶点数才精确守恒(真实案例 2,020,266 → 精确相等,说明跨材质边界共享边 = 0)。`material_index` 与 `.select_*` 掩码的消失也属正常(前者在每部件只剩 1 槽时无意义)。验证器把这类按**提示(ℹ️)**报出而非失败(❌)
- **⚠️ 判几何守恒别用「世界包围盒」——两侧口径不等价,必然误报**:基线侧是`obj.bound_box`(局部 AABB)× `matrix_world`(**松上界**,AABB 经旋转必膨胀);
  拆分后侧是各部件局部 AABB 变换后的**并集**(每部件跨度更小 ⇒ 上界更紧),并集几何上必然 ⊂ 原上界。
  实测反例:`对象9287` 真实世界范围 Y `0.14~7.31`,旧口径给出 `-11.28~16.31`(差一个数量级),旧判据报 `1.557e-03` 漂移,
  而几何实际逐位未变。**正确判据 = 两侧都取「逐顶点局部坐标 min/max」**(算法一致、与帧无关,应精确相等):
  实测 `对象9287` `4.551e-07`、`对象9041` `4.141e-07`,而该量级 float32 可表示间隔约 `3.05e-05` ⇒ 差值**小于一个浮点台阶**
- **⚠️ 桥的 `_env()` 命名空间里没有 `__name__`** ⇒ 经桥执行的脚本结尾**禁止**写 `if __name__ == "__main__"`(直接 `NameError`),必须**无条件**调用 `main()`。同源问题:Blender 执行 `scripts/startup/*.py` 时 `__name__` 是**模块名**而非 `"__main__"`
- **长耗时算子必须"状态逐阶段写盘"**:桥 `exec` 在**主线程**跑,客户端 **120s 超时**后结果即丢;且主线程忙时新请求**只排队不执行** ⇒ 算子运行期间**无法轮询进度**。做法:每阶段 `json.dump` 一次状态文件,超时后读磁盘回捞结论(真实案例 350 万面拆分 10.5s)
- **`Material.use_nodes` 已弃用**:Blender 5.2 起抛 `DeprecationWarning`(预计 6.0 移除)。判"材质有无节点"用 `mat.node_tree is not None`
- **Empty 不支持修改器**:`empty.modifiers.new(...)` 返回 `None`,随后赋值/读取属性会 `AttributeError`。需要挂修改器做引用测试时必须用**网格对象**
- **文档相对链接必须相对「本文件所在目录」**:`docs/` 下的文档写成 `[x](docs/x.md)`,GitHub 会解析为 `docs/docs/x.md` → **404**(实测 HTTP 状态码);同目录写 `x.md`,指向仓库根写 `../scripts/x/`。**改完必须跑可及性扫描复验**(相对路径 + 锚点)
- **GitHub 锚点生成规则(实测)**:小写 → 移除标点 → **每个空白字符各转一个连字符(不合并)**。`## 16. 循环渐变色(ColorRamp 三色自然循环)` ⇒ `#16-循环渐变色colorramp-三色自然循环`;`## 2. 自定义属性 + 驱动控制显隐` ⇒ `#2-自定义属性--驱动控制显隐`(`+` 被移除后留两个空格 ⇒ 两个连字符)。**权威核验法**:抓线上页面 HTML 里的 `id="user-content-..."`(GitHub 的 `/markdown` API 返回的 HTML **不含** heading id,别用它验)
- **删除文档必须连带清理全部引用与副本**:教训 —— 2026-08-28 删 `docs/应用缩放Scale归1.md` 时只删了本体 + 索引行,**正文整节 / 锚点 / 重复副本**全部残留,长期无人察觉。删文档检查单:① 本体 ② README 索引 ③ 技巧速查索引 ④ 技巧速查正文整节 ⑤ 其他文档引用 ⑥ CHANGELOG 补「后续变更」注记(不改写历史)
- **不支撑几何的 EMPTY 必须用「引用图 + 不动点」清**:只删"当前无子级"的会漏掉级联(实测 5006 → 7467 —— 中转容器 `Group-*`/`Arc*` 删完自己变叶子)。引用判定**必须排除** `Scene.objects`/`Collection.objects`/`ViewLayer.objects`/`Collection.all_objects`(成员关系)与 `ID.original`,否则全场景对象都会被标成"被引用"
- **禁止 `bl_rna.properties` 全属性遍历上万对象**(22315 对象 ≈ 7 分钟,必超 120s)⇒ 改**打靶式**:约束 `c.target` / 修改器指针 / 节点 OBJECT·COLLECTION socket / 驱动 `variable.targets[*].id` / `scene.camera` / 相机 `dof.focus_object` / 粒子 `dupli_object`(全场景 12~20s)。也别在循环里用 `ob.children`(每次 O(n) 重算),自建 `parent.name -> [child]` 映射
- **⚠️ 删除后旧引用立即失效**:`bpy.data.objects.remove()` 之后连 `o.name` 都抛 `ReferenceError: StructRNA of type Object has been removed` ⇒ 要用的字段**删除前冻结成纯值**、「被删名单」**先落盘再删**、核验**重新取引用**(本机连踩两次)
- **空集合 ≠ 空对象**:`objects=0` 且 `children=0` 的集合用 `bpy.data.collections.remove(col, do_unlink=True)`(实测 `Export` 集合 `users=1`、挂在场景根),要**单独问用户**
- **判贴图缺失必须带 `not img.packed_file`**:否则会把"路径失效但已打包"的贴图误报为缺失(真实工程 105 个);同一判据散落在体检/核验/文档多处时要交叉核对口径
- **孤儿数据块清理顺序:先材质再图像**;删前逐个判"磁盘有同名副本或已打包"(磁盘无副本的打包数据一旦变孤儿,存盘即永久丢失)
- **"配了发光材质渲染还是黑的"先查 `view_layer.material_override`,别去材质树里翻**:它是 **View Layer 级属性、不在材质里** ⇒ 材质节点树里永远查不到;非 None 时该视图层下**全部对象**材质被替换,此时改任何材质都不生效。第二查**引擎**(`BLENDER_WORKBENCH` **完全不读材质节点树**,发光永不生效,必须 `CYCLES`/`BLENDER_EEVEE_NEXT`),第三查 `ob.is_holdout`·`ob.visible_camera`·视图层 Exclude(症状都极像"材质没用"),最后才怀疑数值
- **一个材质可以有多个 BSDF,只有「接到 `OUTPUT_MATERIAL.Surface`」的那个生效**:实测 `Material #18526fds.001` 里 `原理化 BSDF`(`Emission Strength=100`)**未接输出**、真正生效的 `原理化 BSDF.001` 只有 **10** ⇒ 用户看到的 100 是假的。排查必须**打印"输出连的是谁"**并列出"发光>0 但未接输出"的**孤儿节点**;多个 `OUTPUT_MATERIAL` 时只有 `is_active_output=True` 那个生效
- **`view_transform` 默认 AgX(4.x/5.x)会压暗高亮**:同强度发光在 Filmic/Standard 下亮、AgX 下像哑光 ⇒ 它只解释"**不够亮**",**不解释"纯黑"**(纯黑往覆盖/Holdout/未连线找);`mat.diffuse_color` 是视口颜色,与节点树结果无关,不能当判断依据
- **送给桥的脚本文件绝不能带 BOM**:桥端 `exec` 直接 `SyntaxError: invalid non-printable character U+FEFF`。**Windows PowerShell 5.1 的 `Set-Content -Encoding UTF8` / `Out-File -Encoding UTF8` 会写 BOM** ⇒ 用它生成送桥脚本必炸(实测踩过一次);改用 `[System.IO.File]::WriteAllText($p,$s,(New-Object System.Text.UTF8Encoding($false)))` 或 Python `open(...,encoding='utf-8',newline='\n')`

## 约定

- 文档用中文;技巧按"场景 → 做法 → 坑"组织;一坑一篇进 DEVELOPMENT.md
- `skills/` 放**给 AI 助手用的作业规范**(`SKILL.md` + 附件脚本);`scripts/` 放**给人用的脚本包**(README + 脚本);同一套脚本**两处需同步**
- 文档内链接用**相对本文件**的路径;结构改动后跑一次「链接可及性 + 锚点存在性」检查(本地模拟 GitHub 解析)

## 常用命令

- 远程执行:`python send.py <code.py>`(桥脚本在 `scripts/blender-remote-control/`,跨机器可复用;README 含完整说明)
- 验证桥:`netstat -ano | grep 9877`
- 手动改 handle:Graph Editor 选中关键帧按 V

## 详细规则(按需 @引用)

- @docs/技巧速查.md
