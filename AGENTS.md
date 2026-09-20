# AGENTS.md · 项目规则

> 📌 **文档基线**:2026-09-20 v1.24.6(commit `3f7d68b`) —— 新增 blender-cylinder-spiral-material（螺旋 / 滚筒斜纹）
> (**波形放 Math 域,别让 ColorRamp 兼职** · 「斜角」经 `RADIANS→TANGENT→K×(柱高/周长)÷tanθ` 反算 N · 端盖按法线分纯黑槽 · 11 条坑含 5 条渲染管线级 · **方向以实测标定,纸面推导曾推反**)
> 前序 v1.24.5(commit `2f21fea`) 作业循环补「跑带还原逻辑的技能脚本前先用隔离探针验它」
> (**技能脚本头部的「与基线逐字节等价」是声明不是事实** · 先建 2 槽 mesh 探针(面索引交替 0/1)记状态 → 跑脚本 → 读探针确认原封未动 + 核对对象/材质总数 · 原第 5~7 步顺延为 6~8)
> 前序 v1.24.4(commit `ab6a919`) self_test 还原逻辑修两处真缺陷
> (**`restore()` 须删自建的 `ctrl` 空物体,否则每次试跑留 1 个无主 EMPTY** · `me.materials.clear()` 会把该 mesh 所有面的 `material_index` 归零,须「槽位未变就 `continue`」——实测 141 个 mesh 中招,单个最多 140 万面用槽 1 · 失败报告只输出差异,别打全量材质表(实测 44 万字节噪声,且把方向带向「材质没删净」而真残留是对象))
> 前序 v1.24.3(commit `5bba3cd`) 修复技能安装链路断链 + 订正环境事实
> (**只拷 `skills/` 会断链,须三件套一起拷 `skills`+`scripts`+`docs`** · 从 `skills/<名>/` 出发是**一级** `../`,写两级会落到安装根之外 · 删除「bash 已损坏」错误条目(bash 实测可用) · 新增「heredoc 吃成对反斜杠致 `replace` 静默失败,须 `chr(92)`」)
> 前序 v1.24.2(commit `bec7ef47`) 双径向 Skill 铁律统一补「三平面下做效果才对 + 便于检验」
> (**内收多脉冲 Skill 补铁律 #6;四段脉冲 Skill #7 补「三面同场交线连续、一眼可验」**)
> 前序 v1.24.1(commit `b12db2b1`) Skill blender-radial-pulse-material 铁律补充「部署目标非三平面须提示补齐」
> 前序 v1.24.0(commit `20f98649`) 新增主题 #41「雪花下落系统」(EMPty 宿主几何节点下雪 + FLOORED_MODULO 触地回卷)
> (**宿主必须 loc=0/rot=0/scale=1 否则雪埋地** · `FLOORED_MODULO` 触地回卷不加贴地淡出 · RandomValue 显式接 Index+独立种子防堆积 · `'%s' % (tuple)` 单%s×三元组报 not all arguments)
> 前序 v1.22.0(commit `80c1e8b`) 新增主题 #39「星芒散射光效系统」(隐藏源 + ObjectInfo RELATIVE)
> (**源隐藏渲染、散布实例照常** · `ObjectInfo` 必须 **RELATIVE** 才继承源缩放/动画,ORIGINAL 会忽略 · 位置偏移经 `设置位置` 施加在实例化前 · `mod.properties.inputs` 不可迭代 · EMPTY 属性驱动几何 socket 不稳)
> 同批 v1.23.0 新增 Skill `blender-loop-keyframe-anim`(循环三角波关键帧;Slotted Action 写入路径)
> 前序 v1.21.0(commit `bad5a70`) 新增主题 #38「驱动参数化材质维护」(引用体检 / 关键帧收敛 / 改名换轴)
> 前序 v1.20.0(commit `9cf12e5`) 新增主题 #37「径向材质多位置部署与播放时差」
> 前序 v1.19.0(commit `bcc96c6`) 新增主题 #36「径向内收多脉冲材质」+ Skill `blender-inward-pulse-material`
> 前序 v1.18.0(commit `e08b05b`) 新增 Skill `blender-radial-pulse-material` + 双勘误(驱动内建 `frame` 可用 / UI tag 未隔离实测)
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
- **bash heredoc 会吃掉成对反斜杠**:`python - <<'PY'` 里写 `'C:\\path\\to'`,Python 实际收到 `C:\path<TAB>o`(因为 `\t` 被解释成制表符)→ 字符串 `in` / `replace` **静默失败**(返回 False 而不是报错)。构造含反斜杠的路径一律用 `chr(92)` 拼接,或用 `split(chr(10))` 这类不依赖反斜杠字面的写法。**判据:替换后必须回读并打印结果核对,别信 `replace` 的返回值**
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
- **驱动里读帧:内置 `frame` 在 5.2 是【可用】的**(2026-09-14 五组对照实测:节点插槽驱动与对象级驱动都精确通过)。它是驱动求值器注入的**内建变量**,**与 `bpy.app.driver_namespace` 无关** —— 旧笔记"5.x 驱动命名空间默认无 `frame` 键"是**范畴错误**。`SINGLE_PROP → scene.frame_current` 同样可用,价值在于**显式声明依赖边**。**真正的坑是 `frame * <某个未注册的命名空间函数>()`**:整条驱动 `is_valid=False`、值恒为默认 0、画面零变化(曾据此误判"frame 无效")。**分辨判据:读 `driver.is_valid`,变红就是表达式里有东西解析不了,与 `frame` 无关**
- **Z 轴旋转驱动用 `rotation_euler[2]`,不是 `rotation`/`rotation_quaternion`**:直接给四元数 `rotation` 挂驱动路径会被当四元数读,结果错乱;务必 `driver_add('rotation_euler', 2)`;构建时把基准角 `rotation_euler.z` 复位为 0,否则会从被污染角度(如残留 100°)累加
- **Blender 5.2 视口录制(opengl/FFMPEG)输出配置顺序**:必须先 `image_settings.media_type='VIDEO'`,**再** `image_settings.file_format='FFMPEG'`;顺序反了直接报 `'FFMPEG' not found in enum`(VIDEO 之前该枚举项未就绪)
- **驱动命名空间函数持久化(spin 同 bob)**:运行期 `driver_namespace` 映射不落盘,靠 **Register 文本块(源码随文件保存)载入时自动重注册**自愈;或 `scripts/driver-restore/restore_drivers.py` 一键恢复(内置强制重编译),避免重开文件驱动变红
- **Register 自动恢复已实测 100% 生效**:light_off/scroll_speed 文本块勾 Register + Auto Run → 重启后函数自动进命名空间、**全部驱动 is_valid=True 自动恢复**(843 驱动实测 INVALID 0),无需手动操作。文本块模板见 scripts/driver-lights/light_driver.py 与 scripts/glow-scroll-material/scroll_driver.py
- **`Math` 节点的第 3 个输入只有 `MULTIPLY_ADD` 会读** → 想加三路必须**串两个 ADD**,否则第三路被静默丢弃(实测周期算成 174 而非 200);且**未连接的输入默认 0.5 而不是 0**,建完节点要把用不到的口显式清零
- **`image.pixels` 的第 0 行是图的【最底部】** → 拼接触表按行号递增写会**整张上下颠倒**(本项目据此差点下错结论);且 `foreach_set` 每像素 **16 字节**(4 float × 4B),写成 `4*W*H` 报 TypeError
- **视口「材质预览」与 F12 渲染是两套光照** → 判断"用户看不看得见"必须**抓视口**(`bpy.ops.render.opengl(write_still=True, view_context=True)` + `temp_override`);材质预览会用内置 HDRI 而不是场景 world,同一参数实测 **F12 只变 5/255、视口变 86/255**,用 F12 数据会得出"不可见"的错误结论。另:判可见性用 **maxDiff**,别用"变化像素占比"(单边移动的参数 maxDiff 223 而面积仅 0.6%)
- **循环时间轴:时长类参数必须进【相位】** → 只进"周期"不出现在 `u − 参数` 里的参数,在 `f < 周期` 时是**数学恒等变换**,画面逐像素相同(实测 diff 0.0/255),用户拖它整段没反应 = 误报"坏了";详见 skills/blender-radial-pulse-material/SKILL.md §4.2
- **参数只准有一个入口,别做"假控件"** → 把参数再镜像一份到别的 data-block(另一空物体的自定义属性等),它会**能拖、有范围、有说明,但没有任何连线读它** —— 这是"改了参数没效果"最常见的误报来源
- **`driver_add()` 会把表达式自动填成"当时的数值"** → 装完不覆盖 `d.expression` 就等于装了个**常量驱动**,改属性当然纹丝不动(本项目被骗了一整轮)
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
- **★ 独立化必须「先快照、后动手」**:把共享网格数据逐对象 `ob.data = ob.data.copy()` 时,
  **不能一边遍历一边判 `users > 1`** —— 复制一个,那份数据的 users 就掉 1,
  轮到共用同份数据的兄弟对象时 `users == 1` ⇒ 被跳过,实测 118 个对象漏了 28 个。
  正解:先按数据块分组做快照,被共享组里的每个对象都**无条件**复制
  (详见 docs/径向材质多位置部署与时差.md §2.3,脚本 scripts/radial-inward-pulse/make_effect_independent.py)
- **★ 匹配关键词要向用户要全**:本例空对象叫「发射灯效果」「收缩灯效果」,还有一组叫「收缩**射**灯效果」——
  只匹配 发射灯/收缩灯 就会**整组漏掉**(「收缩灯」不是「收缩射灯」的连续子串)。
  按名字圈对象之前,先把实际名字清单打印出来给用户确认
- **★ 带关键帧的材质复制后,action 必须【重建】而不是 copy**:
  `material.copy()` 会带上 `nt.animation_data.action` 且**与原件共用**;
  `action.copy()` + 按名字重绑 `action_slot` **不生效** —— fcurve 在、`fc.evaluate(f)` 也对,
  但节点**评估值冻结**在复制那一刻的帧值。
  正解:`ad.action = None` 丢掉带过来的,再原地 `keyframe_insert` 重建(驱动在 animation_data.drivers,不受影响)
- **★ 播放时差 ≡ 相位偏移(循环周期相同时严格等价)**:
  `相位 = 帧号÷循环周期 + 相位偏移`,令 `相位偏移 = 错位帧数×k ÷ 循环周期` 即等价于用 `帧号+错位×k`。
  内收类**零节点改动**(改控制器属性,注意 UI 上限 1.0 要取 mod 1);
  四段循环类改 TVAL 两个关键帧的【值】(`值 = 帧 + 错位`,斜率不变)。
  ⚠ 相位偏移存的是【圈数】不是【帧数】—— 改循环周期,等效帧错位会跟着变;
  要帧数语义就加 `帧偏移` 参数(相位改成 `(帧号+帧偏移)÷循环周期`)
- **★ 材质 `users==0` 且无 fake user ⇒ 存盘被 Blender 当孤儿清掉**;且**没被任何对象使用的材质
  不进依赖图** ⇒ 读关键帧/驱动的评估值拿到的是**原始存值**。
  「材质没了」「材质不动了」先查这两条,别急着重建;要保留的材质上 `use_fake_user=True`
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
- **⚠️ 验证器的判据必须「取差集 + 精确到本次操作的对象集合」,不能用全场景绝对值**(v1.17.1,同一处病根的两个实例都在验证器第 11 节):
  - **实例①绝对判无**:原先"存在 `users=0` 的 mesh 就 ❌"。真实工程里常已存在历史遗留孤儿(早期删对象留下的数据块) ⇒ **干净操作也必然误报**。实测:某对象 4 槽拆分后 35 项真通过,却被 10 个**拆分前既有**的孤儿(每个仅 26~78 面)判成"❌ 不通过",极具误导。正解:基线记 `orphan_mesh_before` 名单,只把 `orphan_now - orphan_before`(**新增**)判 ❌,交集降级 ℹ️ 提示(存盘时 Blender 本就会丢弃)
  - **实例②全场景口径**:`新增对象数 == 材质槽数-1` 的 `new_objs` 取的是 `set(D.objects) - before_objs`(**全场景**差集)。同一场景**连着拆多个对象**时必然串扰 —— 实测先拆 `水晶走廊_纵向灯`、再拆 `水晶走廊_竖向灯`,回头复验前者看到"新增对象数 **4** != 材质槽数-1 (1)"(把后者新增的 3 个也数进去了)。正解:只数「以 `TARGET + "."` 为前缀」的**本组**新增对象,全场景多出的部分仅作附注(`TARGET + "."` 对"名字互为前缀"的对象安全:`纵向灯` 是 `纵向灯2` 的前缀,但 `纵向灯2.001` 不匹配 `纵向灯.`)
  - **通用心法:凡"存在性 / 计数"检查(`users==0` 孤儿 / 空集合 / 缺贴图 / 新增对象数 / 游离引用),判据都要取差集、且精确到本次操作的对象集合 —— 真实工程状态往往不是干净的初始态,而且操作是连着做的**
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

- **★「恰好 N 条」不能用近似式算**:常数量的判据必须把**每一项**都显式写进公式 —— 径向环数 = `L + 占空比 − 软边占比 − 2×最小可见宽度`(`L = 基准半径/间距`)。只写 `L + 占空比 ≤ N` 会多出第 N+1 条;补了「− 软边」没扣 `2×最小可见宽度` 则仍有约 2% 的相位少一条。**写完必须扫描验证「最小 / 最大 / 恰为 N 的占比」,只看最大值会漏**(详见 docs/径向内收多脉冲材质.md,脚本 scripts/radial-inward-pulse/)
- **★「数几个」必须先问清「在哪条半径上数」**:非圆网格(正方形板)上**内切圆半径**与**角点半径**相差 **√2 ≈ 1.414** —— 按角点定 3 条,圆上只剩 1.55 个周期 ⇒ 只看到 2 条(实测返工)。基准要做成开关并**同时报告两处**的分布
- **★ 驱动只能挂在【Value 节点】的输出上,挂在计算节点(Math/MapRange)的输出插槽上等于没写**:计算节点的输出由它自己的运算决定,驱动会被覆盖 ⇒ 该项恒 0 ⇒ 相位不变 ⇒ **拖时间轴画面完全静止**。**守卫**:逐条驱动检查 `data_path` 目标节点 `type == 'VALUE'`,挂错直接点名;再加一条「帧号响应自检」(`frame_set` 到几帧、读回帧号节点须精确相等)
- **★「亮面面积缩小」与「黑边变粗」是两个【正交】旋钮**:想收紧发光范围要用**径向裁切**(`MapRange(r − 亮面半径, 0..淡出宽度, 1..0)` 乘进掩码),**不是**加宽黑边 —— 混成一个(占空比 0.88→0.60)会把黑边从 24% 涨到 52%,用户下一句必然是「黑边太粗了」
- **★ 读「另一个材质的颜色」不能读 `default_value`**:插槽若**已连线**,`default_value` 只是残留存值(实测读到 `(1,1,1,1)`,而真实配色是一条 ColorRamp 的 6 个色标,全丢)⇒ 必须**顺连线找到真正的来源节点**(ColorRamp 等)再把色标**逐项复制**;色标若铺在 `r∈[0,1]` 而新网格半宽不同,还要按 `r / 色相半径` 归一化,否则超出 1 的部分全被钳到最后一个色标 ⇒ 整面糊成暗红
- **★ 已连线的「计算输出」插槽,Python 读 `default_value` 恒为 0**:只有被**关键帧或驱动器直接写入**的插槽才有可读值(Value 节点输出读得到,`Math`/`MapRange` 的输出读不到)⇒ 核验中间量要改成「**验基准 + 验驱动输入 + 解析式复算**」,别去读中间节点真值
- **★★ 查「谁在读这个参数」必须扫到 `物体数据 → node_tree` 层,否则会双向出事**(2026-09-16 实测):
  驱动器的宿主不止控制物体与材质 —— **Blender 5.x 的灯光/网格数据块自带节点树**,面光灯的同构接入驱动
  全在 `o.data.node_tree.animation_data.drivers`。只扫 `o.animation_data` / `o.data.animation_data` /
  材质节点树会整层漏掉:`面光统一强度` 明明被 7 盏灯的 `发光强度.001` 读着(`expr='st * k'`),
  却被判成"全库零引用 ⇒ 假控件"(**结论完全相反**);更糟的是把 `Z向速度` 改名为 `X向速度` 后,
  漏扫的 7 条驱动全变 **`is_valid=False` 静默失效**(面光灯噪波滚动停摆,UI 上毫无异常)。
  **完整清单**:`o.animation_data` / `o.data.animation_data` / **`o.data.node_tree.animation_data`** /
  `o.modifiers[i].node_group.animation_data` / `materials(+.node_tree)` / `node_groups` / `scenes` /
  `worlds(+.node_tree)`。经验法则:`hasattr(x, "node_tree")` 为真的 data-block 都要往下再扫一层
  (详见 docs/驱动参数化材质维护.md,脚本 scripts/driver-param-maintenance/param_ref_scan.py)
- **★★ 改名/删键之后必须跑「失效体检」,判据是 0 条**:① 全库 `dr.driver.is_valid == False` 计数;
  ② 变量 `data_path` 形如 `["X"]` 但该 ID 已无 `X` 键(正则 `^\["(.+)"\]$` 比对 `id.keys()` ⇒ 悬空引用)。
  两类都是**静默**问题(画面上只表现为"某处不动了"),只有体检能提前抓到
- **删除驱动 / 换轴的顺序铁律**:先 `driver_remove(path, 旧分量)` → 再 `driver_add(path, 新分量)`
  → 重建变量(`id_type` 先于 `id`)→ **★ 显式覆盖 `d.expression`**(`driver_add()` 会把表达式**自动填成
  当时的数值** = 装了个常量驱动)→ 旧分量归零 → **全部驱动重建完之后才删旧属性键**
  (反了会留下指向已删属性的悬空驱动)
- **「关键帧 → 常量」的存档纪律**:删曲线前先打印 `(帧, 值)` 全表 + `interpolation` + `extrapolation`
  + **`fc.evaluate(当前帧)`**(这是唯一回滚依据);**只删目标 `data_path`+`array_index` 那一条 fcurve**
  (同 action 其它曲线必须原样保留);常量取「当前帧所见值」可保证画面不跳变,用户指定值则要回报实际结果值;
  删完打印"动作剩余 fcurves"作证据,并在**另一次请求**里复核
- **三个「index」别混**:① 驱动 FCurve 的**分量索引**(`drivers.find(path, index=2)` /
  `driver_remove(path, 2)` / `driver_add(path, 2)`,向量的 X/Y/Z;`find()` 的 index **必须关键字传参**,
  位置传参报 `TypeError`)② `DriverTarget` 的数组分量(**5.2 无 `.array_index`**,写进 `data_path='location[0]'`)
  ③ `ActionSlot` 的标识(**`.identifier` / `.name_display`** —— 既没有 `.name`,也没有 `.display_name`)
- **`id_properties_ui(k).update(...)` 可全量复制/改写属性 UI**:`as_dict()` 抄下
  `min/max/soft_min/soft_max/default/step/precision/description` 再 `update()` 写进新键 ——
  **给参数改名时描述文案里的轴向要同步改**(如"沿世界 Z"→"沿世界 X");`update()` **不接受 `name`**,
  自定义属性的显示名就是键名本身(逻辑读键处 —— 驱动变量 `targets[0].data_path` —— 必须同步改)
- **同名参数常被多处【同构接入】,换轴必须全搬**:主材质 + 若干面光灯节点树都读同一个速度属性时,
  只搬主材质的分量 ⇒ 两边噪波滚动方向不一致、且漏搬的那批直接失效。判据:
  「主材质与全部灯在同帧的下游插槽读数**逐位相等**」(实测 8 个插槽同时 5.0 / 50.0)
- **几何散布"源隐藏渲染、实例照常"**:想藏掉生成形状的源对象(如星芒的单面源平面),把节点里的 `物体信息(ObjectInfo)` 设 **RELATIVE** 读源 + `源.hide_render=True` / `visible_camera=False`(保留 `hide_viewport=False` 便于调试)。`ObjectInfo` 换 **ORIGINAL 会忽略源的 scale/动画**(控制器参数驱动形同虚设);散布读的是源**评估几何**(depsgraph),藏的是"相机直接渲染"、不拦"被节点组当实例源引用"
- **位置偏移要经 `设置位置` 施加在实例化之前的点上**:先对点 `设置位置(SET_POSITION)` 偏移、再进 `实例化于点上`;直接改 IOP 的 Position/Scale 会被实例基缩放放大、方向错乱
- **SCRIPTED 驱动"声明了变量却没用进表达式"= 参数静默失效**:求值只看表达式文本,变量表装了不用没用。例:源 scale 只写 `a/1000`、`b` 没进式 ⇒ 控制器 `动态缩放` 循环动画对整体大小毫无作用;完整式应 `a/1000 + b/1000`
- **Blender 5.2 `mod.properties.inputs` 不可迭代**:返回 `GeometryNodesInterfaceInputs`,`enumerate(...)` 抛 `TypeError`;读单 socket 用 `.get(名)` / 属性访问
- **不要用 EMPTY 自定义属性驱动几何节点 socket**:5.2 depsgraph 读缓存值(如 288.0)不可靠;量化的 `生成数量` 等直接放节点组接口 / 修改器面板调,实时生效
- **循环三角波关键帧动画**(Slotted Action):一个完整周期进 fcurve + `CYCLES` 循环修饰器铺满帧范围;写路径 `action.layers[0].strips[0].channelbags[0].fcurves`,`FModifierCycles` **无 mode 属性**(默认即正向循环);被驱动属性再用 fcurve 补关键帧时**关键帧值显式覆盖**( `kp.co=(fr,val)`)绕开当前值被驱动干扰,读被驱动值走 depsgraph

- **★ 连续自然降水(下雪/飘落)的统一心法 = `SceneTime → ×1/CYCLE → +随机相位 → FLOORED_MODULO 1 → prog`,位置由 `GROUND + (1-prog)*FALL_SPAN` 线性映射**:`prog∈[0,1)` 均匀铺满整条高度列,**触地瞬间(prog→1)取模回卷到天空** ⇒ 每片循环下落、均匀铺满、无半空消失、无顶部堆积;**别加贴地淡出**(否则雪花半空消失)。相位随机会话 = 初始就铺满全高,不需要"先等落到场"。(详见 docs/雪花下落系统.md §5,脚本 scripts/snowfall-scatter/)
- **★ 几何怪散布宿主变换必须清零**:落雪区高度是相对宿主锚定的(`GROUND` 取地平面世界包围盒底部 Z),宿主若被移动(如实测 Z=-1.47)整个雪区整体移位、**雪埋进地面/顶部够不到天空**;构建脚本强制清零 loc/rot/scale。凡"点阵按世界包围盒算位置再挂到宿主实例化"的模式,宿主必须留在原点
- **★ 随机值共用默认 ID ⇒ 坐标/相位相关(共线/同时落)**:多个 `RandomValue` 想各自独立(相位+X+Y+朝向),必须每个都**显式接 `Index` 作 ID 输入**并给**不同 Seed**(下雪: 29/7/13/401/509);只接 Index 不给独立 seed 仍会相关。同批实例要"各自不同"必须 每域独立随机源
- **★ `'%s' % (tuple)` 陷阱**:单个 `%s` 的右操作数是**三元组**时,Python 把元组当作**多参数解包**,若左边只有一个占位符 ⇒ `TypeError: not all arguments converted during string formatting`。要打印一个坐标元组,必须写成 `% (tuple(...), )`(包成单元素元组)或先 `str()`。`%s` 单占位符对 str 安全、对长度≥2 的 tuple/list 报错
## 约定

- 文档用中文;技巧按"场景 → 做法 → 坑"组织;一坑一篇进 DEVELOPMENT.md
- `skills/` 放**给 AI 助手用的作业规范**(`SKILL.md` + 附件脚本);`scripts/` 放**给人用的脚本包**(README + 脚本);**同一套脚本若两边都有,必须两处同步** —— 目前只有 `blender-scene-cleanup`(→ `scripts/scene-cleanup/`)与 `blender-render-blackout-diagnose`(→ `scripts/blackout-diagnose/`)是两边都有,其余 skill 的脚本只随 skill 自带
- 文档内链接用**相对本文件**的路径;结构改动后跑一次「链接可及性 + 锚点存在性」检查(本地模拟 GitHub 解析)

## 常用命令

- 远程执行:`python send.py <code.py>`(桥脚本在 `scripts/blender-remote-control/`,跨机器可复用;README 含完整说明)
- 验证桥:`netstat -ano | grep 9877`
- 手动改 handle:Graph Editor 选中关键帧按 V

## 详细规则(按需 @引用)

- @docs/技巧速查.md
