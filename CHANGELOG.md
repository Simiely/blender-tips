# CHANGELOG.md

## v1.8.3 · 2026-08-22

- 用户重启实测通过:天空太阳控制重启后自愈,不再断开
- **修正不准确说法**:命名空间函数**源码随 .blend 保存**(文本块 Register),不落盘的只是运行期 `driver_namespace` 映射—靠 Register 文本块载入重注册;依据 Blender 手册 Scripting & Security(Registered Text-Blocks will load on start,受 Auto Run / Trusted Source 控制)
- `docs/天空太阳高度驱动.md` 新增「核心逻辑与要点(官方机制, 重启自愈)」:三前置 = 文本块当前双函数版 + Register + Auto Run
- `scripts/driver-sky/README.md` 顶部加核心逻辑说明
- `AGENTS.md` 修正 bob/spin 命名空间函数持久化两处措辞(源码落盘,映射不落盘)

## v1.8.2 · 2026-08-22

- 实战修复「重启后天空控制断开」:**根因 = .blend 内嵌的 `sky_driver.py` 文本块是旧版**,只注册 `sky_sun_angle`、缺 `sky_sun_elev` → 高度驱动红(Auto Run 正常)。用仓库权威版覆盖文本块 + 保持 Register + 强刷驱动 + Ctrl+S 后,高度/角度均 1:1 恢复
- `scripts/driver-sky/README.md` 排查新增「重启后断开优先看这个」:先核对文本块是否含两个函数,再查命名空间/驱动有效性/Auto Run
- `AGENTS.md` 补坑:重启断开多为内嵌文本块旧版;Scripted 驱动 5.2 无 `d.update()`,强刷用 `d.expression=d.expression`(try/except 兜底)

## v1.8.1 · 2026-08-22

- `docs/天空太阳高度驱动.md` 重构优先序:**命名空间函数版提到最前(默认方案)**,原「数字驱动版」降级为「旧做法,有已知坑」附后;标题改为「天空太阳控制驱动」
- 新增 `scripts/driver-sky/README.md`:**权威脚本目录说明**——`sky_driver.py` 为唯一推荐脚本,旧 `build_sky_sun_driver.py` 标记禁用(会写回常量覆盖 sun 驱动)
- `AGENTS.md` 精简 SINGLE_PROP / sun 驱动那条坑说明,附推荐脚本路径

## v1.8.0 · 2026-08-22

- 新增 `scripts/driver-sky/sky_driver.py`:命名空间函数版天空驱动(`sky_sun_angle` / `sky_sun_elev`),实时读属性,脚本/UI 改值均立即生效
- `docs/天空太阳高度驱动.md` 补充「命名空间函数版(推荐)」小节:含太阳旋转 `sun_rotation`;并记录坑——旧 `build_sky_sun_driver.py` 会把 `sun_elevation` 驱动写回常量导致高度无反应
- `AGENTS.md` 补坑:SINGLE_PROP 读自定义属性脚本内改值不重算、旧重构脚本覆盖驱动 → 用命名空间函数实时读
- `README.md` / `docs/技巧速查.md` #23 更新为「天空太阳控制驱动」
- 来源:9877 工程 260821x05,天空控制 自定义属性(太阳角度/太阳高度)驱动天空纹理

## v1.7.0 · 2026-08-21

- 新增 `docs/输出路径与序列帧输出规范.md`:**输出序列帧路径规范**——相对路径 `//`(工程目录)+ `output/<批次>/` + `#` 帧号占位命名;正确设置顺序 `media_type='IMAGE' → file_format='PNG' → filepath`;`use_file_extension` 自动扩展名;`bpy.path.abspath()` 复核落盘路径
- `README.md` 索引新增 #26 入口
- `AGENTS.md` 补关键坑:media_type 先于 file_format 决定枚举域(镜像 5.2 视口录制 VIDEO 顺序)+ 相对路径规范
- 来源:9877 工程 260821x05 修复主装置,输出改为相对路径 `//output/260821x01/260821x01####.png` 并实测 PNG 序列可行

## v1.6.1 · 2026-08-21

- 新增 `scripts/driver-lights/light_driver.py`、`scripts/glow-scroll-material/scroll_driver.py`:**命名空间函数文本块模板**(勾 Register + Auto Run → 重开文件自动恢复)
- `scripts/driver-restore/restore_drivers.py` EXPR_MAP 补充 light_off / scroll_speed(一键恢复含新函数)
- **实测确认 Register 自动恢复 100% 生效**:light_off/scroll_speed 文本块勾 Register + Auto Run → 重启后函数自动进命名空间、全部驱动 is_valid=True(843 驱动 INVALID 0),无需手动操作
- `AGENTS.md` 更新"恢复后必须强制重编译"适用范围(仅运行中 exec 注册场景;正常重启 Register 自动恢复连带驱动)
- 来源:9877 工程重启验证(打开自动就对)

## v1.6.0 · 2026-08-21

- 新增 `scripts/driver-lights/` 可复用脚本包:**运动网格灯光方案**
  - `build_light_system.py`(给驱动浮动网格轴心加向上/向下双 AREA 灯,分组+跟随驱动+偏移属性+旋转绑定,一键全套,幂等)
  - `README.md`(参数表 / 手动微调 / 5 条实战坑)
- 新增 `scripts/glow-scroll-material/` 可复用脚本包:**渐变发光滚动材质**
  - `build_glow_scroll_material.py`(竖图渐变自发光 + Mapping 放大2倍只显示一半 + Location Y 驱动竖直滚动 + 速度滑块)
  - `README.md`
- 新增 `docs/运动网格灯光方案.md` / `docs/渐变发光滚动材质.md`
- `README.md` / `docs/技巧速查.md` 索引新增 #24 / #25
- `AGENTS.md` 补 3 条关键坑(新建空物体需先 update 再读 matrix_world / 5.2 DriverTarget 无 array_index / 驱动单向主从)
- `DEVELOPMENT.md` 新增 3 篇问题记录(翻倍偏移 / array_index / 循环依赖)
- 来源:9877 工程 5 个主装置 168 灯灯光方案 + 渐变发光滚动材质实战

## v1.5.0 · 2026-08-21

- 新增 `scripts/driver-sky/` 可复用脚本包:**天空太阳高度数字驱动**
  - `build_sky_sun_driver.py`(建「天空控制」空物体 + `太阳高度` 滑块(度),给 `sun_elevation` 挂 SCRIPTED 驱动 度→弧度;幂等可重跑)
  - `README.md`(原理 / 用法 / 坑)
- 新增 `docs/天空太阳高度驱动.md`:5.2 天空纹理参数是节点属性(非 socket) / 节点驱动在 node_tree.animation_data / 打关键帧做太阳升降
- `README.md` 索引新增 #23 / `docs/技巧速查.md` 补 #23
- `AGENTS.md` 补 2 条关键坑(5.2 TEX_SKY 属性驱动 / 节点驱动存 node_tree.animation_data)
- 来源:9877 工程天空纹理(天空控制.太阳高度 滑块, 悬停按 I 打关键帧)

## v1.4.2 · 2026-08-21

- **修正 send.py 不支持端口参数**:`scripts/blender-remote-control/send.py` 新增 `-p/--port`(多 Blender 并存连接非默认端口;AGENTS.md 早已声称支持但代码缺失,现已补上);超时从 120s 提到 300s(长任务如 playblast 更稳)
- **去掉经桥执行脚本的 `__main__` 守卫**:`build_bob_drivers.py` / `build_spin_drivers.py` / `restore_drivers.py` 改为直接调用 `main()`——桥接 exec 时 `__name__='builtins'`,守卫会让脚本静默不执行(只回 OK 无输出)
- **修正 AGENTS.md 过时结论**:5.2 文本块 Register 持久化**实测有效**——`use_module=True`(UI 的 Register 复选框)+ Auto Run Python Scripts → 重开文件自动恢复命名空间函数,无需手动 Run Script(`use_register` 是旧 API 名已移除,但 use_module 仍在)
- **docs/视口预览录制录屏式.md 补坑**:场景相机按帧切换 = 时间轴标记绑定(Bind Camera to Markers),**不要写死 `s.camera`** 否则覆盖标记绑定丢机位切换
- 来源:9877 工程重开验证(Register 自动恢复成功)+ 录屏 v2/v3 实战(写死相机丢机位切换的坑)

## v1.4.1 · 2026-08-21

- `scripts/driver-restore/restore_drivers.py` 增强:恢复命名空间函数后,**强制重新赋值驱动表达式**触发驱动重新编译
  - 修复:只 exec 文本块注册函数不够——depsgraph 缓存旧失败状态(`driver.is_valid=False`,求值失败返回 0 → 物体掉到 Z=0 错位);必须重赋值同值表达式强制重算
  - 机制:`EXPR_MAP` 声明 文本块名→函数名,扫描全场景 SCRIPTED 驱动,表达式含该函数的即重赋值
- `AGENTS.md` 补关键坑:恢复函数后必须强制驱动重编译(否则 is_valid 仍 False、物体停 0 位)
- 来源:9877 工程重开后 bob/spin 函数丢失导致主装置01-05 全部错位(Z 掉 0),按此流程修复

## v1.4.0 · 2026-08-21

- 新增 `scripts/make-independent/` 可复用脚本包:**集合内对象数据独立化**
  - `make_independent.py`(遍历指定集合 MESH 对象,`users>1` 的共享网格数据块 `copy()` 成独立副本;材质独立可选;幂等可重跑;无 `__main__` 守卫——桥接 exec `__name__` 为 builtins)
  - `README.md`(场景 / 用法 / 效果示例 / 幂等安全 / 注意)
- 新增 `docs/集合内对象数据独立化.md`:原理(对象与数据块多对一)+ 排查方法 + 做法 + 4 条实战坑
- `README.md` 索引新增 #22(数据独立化)入口
- `docs/技巧速查.md` 索引补 #22
- `AGENTS.md` 补关键坑(桥接 exec `__name__`=builtins / 判断共享用 `users>1` 勿看数据块名)
- `DEVELOPMENT.md` 新增 2 篇问题记录:`__main__` 守卫静默不执行 / linked duplicate 共享数据块联动
- 来源:新工程「补充」集合 43 网格只共享 21 数据块(组7912/7913_GeomAdjust 共引 Mesh.537),独立化后 43/43 各自独立,可安全复制出去

## v1.3.0 · 2026-08-21

- 新增 `scripts/driver-spin/` 可复用脚本包:**驱动式 Z 轴匀速旋转系统**
  - `spin_driver.py`(核心函数 `spin_speed()`,实时读 `旋转速度` 滑块,注册进驱动命名空间;勾 Register 持久化)
  - `build_spin_drivers.py`(通用构建器:建 `旋转控制` 面板 + 给指定目标挂 Z 旋转驱动,可独立设正/反向;幂等可重复运行)
  - `README.md`(原理 / 文件清单 / 使用步骤 / 踩坑 / 调参)
- 新增 `scripts/playblast/` 可复用脚本包:**视口预览录制(录屏式,非全渲染)**
  - `playblast_export.py`(`render.opengl` 从场景相机抓视口画面导出 mp4;顶部可调输出路径/分辨率;含 5.2 输出配置顺序坑)
  - `README.md`
- 新增 `scripts/driver-restore/restore_drivers.py`:重开 .blend 后一键重跑 `bob_driver.py` / `spin_driver.py` 文本块,恢复驱动依赖的命名空间函数(解决 5.2 无 use_register 导致驱动变红)
- 新增 `docs/驱动式Z轴匀速旋转系统.md`(原理 / 与 bob 对比 / 做法 / 6 条实战坑 / 验证)
- 新增 `docs/视口预览录制录屏式.md`(原理 / 用法 / 5 条实战坑 / 调试)
- `README.md` 索引新增 #20(旋转)/ #21(录屏)入口
- `docs/技巧速查.md` 索引补 #20 / #21
- `AGENTS.md` 补关键坑(Z 轴旋转用 rotation_euler[2] / 5.2 视口录制 media_type 顺序 / spin 命名空间函数持久化)
- `DEVELOPMENT.md` 新增 2 篇问题记录:视口录制输出配置顺序 / Z 轴旋转用 rotation_euler + 基准角复位
- 来源:活力之丘点位模型 主装置实战(空物体.006 正向 / 007 反向匀速转 + 相机视角预览导出)

## v1.2.0 · 2026-08-21

- 新增 `scripts/driver-bob/` 可复用脚本包:一组独立网格物体的**丝滑阻尼感上下浮动驱动系统**
  - `bob_driver.py`(核心噪波函数 `bob()`,两层加权混合 Perlin 噪波:全局大波 + 局部错动;注册进驱动命名空间,可勾 Register 持久化)
  - `build_bob_drivers.py`(通用构建器:给指定集合挂 Z 驱动、建独立控制面板空物体、按名排除不动区;幂等可重复运行)
  - `README.md`(原理 / 文件清单 / 使用步骤 / 踩坑 / 调参)
- 新增 `docs/驱动式上下浮动噪声系统.md`:完整原理(连续信号映射 → 丝滑/阻尼感来源)+ 两层结构 + 做法代码 + 7 条实战坑
- `README.md` 索引新增 #19 入口
- `docs/技巧速查.md` 索引补 #18(3ds Max 独立文档)+ #19(驱动浮动独立文档)
- `AGENTS.md` 更新文档基线 + 补充关键坑(5.2 驱动无 SELF 类型 → use_self / 自定义属性显示名即键 / 改名后旧驱动陈旧需 driver.update / 命名空间函数不随文件保存 / 基准位置幂等)
- `DEVELOPMENT.md` 新增 5 篇问题记录:驱动变量类型无 SELF / 自定义属性显示名即键 / 改名后旧驱动陈旧 / bob 不随文件保存 / 基准位置误覆盖
- 来源:活力之丘点位模型 主装置01~05 实战(84 个运动网格,各集合独立控制面板,控件默认参数已调好)

## v1.1.0 · 2026-08-21

- 新增 `docs/3dsmax导入场景清理与轴心修复.md`:3ds Max 导入场景完整清理工作流——缺失数据诊断(五查,fbm 贴图路径失效)/ 空物体清理(孤立 + MaxHandle 元数据残留)/ **轴心安全修复(先 transform_apply 烘焙旋转缩放再 origin_set,multi-user 网格先 copy,负缩放翻车教训)** / 动画清理(静态化防跳位,保留相机对象 + camera data 动画) / 5.2 API 坑速记(apply_transform→ops、fcurve_find 不存在、user_map 返回 set、undo 栈限制)
- `README.md` 索引新增 #18 入口
- `AGENTS.md` 更新文档基线 + 补充关键坑(轴心安全流程 / 5.2 API 变化 / 清动画先静态化)
- 来源:260820x03.blend 实战(11,961 对象 3ds Max 导入,缺贴图警告 + 4165 空物体 + 轴心偏移 + 4083 动画对象)

## v1.0.0 · 2026-08-20

- 新增 `docs/材质与驱动规范.md`:灯光材质系统**完整操作手册**——材质命名规范(灯组前缀独立块) / 圆柱投影公式 / 按位置适配(TexCoord+VNorm 必改) / 驱动速度控制(对象级+材质节点级) / 三大坑(Object坐标不旋转, inputs[N], FLOORED_MODULO) / 三分法灰度 / 打组挂载规范 / 快速复用清单
- `README.md` 索引新增"材质与驱动规范"入口
- 来源:灯1/灯4/灯6 多灯组实战(滚筒材质复制 + 按位置修正 + 命名隔离)

## v0.9.0 · 2026-08-19

- `docs/技巧速查.md` 新增 §17:圆柱贴图与理发店滚筒——圆柱投影(u=atan2角度, v=高度归一化) + 螺旋条纹 f=u×K+v×N + FLOORED_MODULO 无缝循环 + 条纹角度公式 + **Object 坐标只跟随平移不跟随旋转** + **材质 driver 路径必须 inputs[N] 数字索引**
- `DEVELOPMENT.md` 新增 2 篇:Object 坐标不跟随旋转+材质 driver 路径 / 条纹底部裁剪(FLOORED_MODULO)
- `AGENTS.md` 更新基线 + 关键坑
- 来源:灯1 理发店滚筒实战(圆柱条纹 + 驱动速度控制 rot_speed/up_speed)

## v0.8.1 · 2026-08-19

- `docs/技巧速查.md` §16 更新为**最小色标结构**:每平台只留 2 端点色标,边界 0/1 删除靠外推,色标数从 13 → 6(三色);通用公式补"最少色标数 = 颜色数 × 2"
- 来源:灯1 三色循环渐变实战精简(6 色标与 13 色标效果等价)

## v0.8.0 · 2026-08-19

- `docs/技巧速查.md` 新增 §16:循环渐变色(ColorRamp 三色自然循环)——4 层逻辑(N 等分对称/同色连标平台/删过渡中点/首尾同色无缝)+ 共享材质 Mapping 偏移驱动 + 换色通用公式(等分数=颜色数×4)
- `DEVELOPMENT.md` 新增 1 篇问题记录:ColorRamp 渐变"抖"(EASE 插值 + 过渡区多余色标)
- `AGENTS.md` 更新文档基线 + 补充关键坑
- 来源:灯1_灯光变化 150 灯体三色渐变波实战(#7F4800/#E5BF91/#E5A145 循环)

## v0.7.0 · 2026-08-19

- `docs/技巧速查.md` 新增 §15:挂载(parent)/轴心(origin)操作的位置保持——**Blender 5.x parent 后 matrix_parent_inverse 不自动设置导致世界位置翻倍**,正确流程(空对象先定位→挂载→手动 mpi),轴心/原点操作注意事项
- `DEVELOPMENT.md` 新增 1 篇问题记录:parent 赋值后子对象世界位置翻倍(743+743=1486,mpi 不自动设置)
- `AGENTS.md` 更新文档基线 + 补充关键坑
- 来源:灯1 集合 385 对象按材质打组(可搭鸭134530→灯1_可搭鸭 150,其他→灯1_其他 235)+ 渐变空对象 107,手动 mpi 后全部位置保持

## v0.6.0 · 2026-08-18

- `docs/技巧速查.md` 新增 §14:大场景去重优化(重复网格合并为实例)——检测(类型分布/同基础名/完整指纹/抽检) + 合并(对象重定向→删冗余块) + 实测效果(9,079→3,803 数据块,-58%)
- `DEVELOPMENT.md` 新增 2 篇问题记录:send.py 大任务超时误报(桥实际执行完,重跑验证) / 重复网格合并指纹陷阱(材质+UV 必须纳入指纹,抽检真几何)
- `AGENTS.md` 更新文档基线 + 补充关键坑
- 来源:里巷点位模型 260818.blend(63,233 对象)优化实战,合并后对象数不变、材质 100% 保留

## v0.5.0 · 2026-08-18

- `docs/技巧速查.md` 新增 §10~§13:
  - §10 时间轴整体前移(关键帧+标记+frame_end 批量平移,负帧保护,先备份)
  - §11 关键帧小数帧(.5帧)检测与修复(round() 掩盖问题 + 吸附到整数帧,段间距校验)
  - §12 首尾帧交换与反转关键帧真相(**Blender 没有"反转关键帧"菜单,用关键帧→镜像→沿时间轴关于当前帧**;附官方文档链接)
  - §13 时间轴标记管理(增删移 + 中文菜单 + 远程操作)
- `DEVELOPMENT.md` 新增 4 篇问题记录:round() 掩盖小数帧 / 同 exec 缓存旧值 / Reverse Keyframes 不存在 / 平移负帧
- `AGENTS.md` 更新文档基线 + 补充关键坑(反转=镜像、小数帧检测、slotted action 读取路径)
- 来源:活力之丘点位模型 260815x02.blend 时间轴前移 + 小数帧修复 + 标记清理实战(10 相机、13,542 对象)

## v0.4.0 · 2026-08-17

- `docs/技巧速查.md` §9 新增:渲染白膜(材质覆盖,非破坏性)——View Layer `material_override` + 白膜材质 + 天空光补连;索引表补全 §7/§8/§9
- `DEVELOPMENT.md` 新增 1 篇问题记录:0 灯光场景白膜渲染靠天空光 / Sky Texture 未连接 Background
- 来源:CAD 大场景(50186 对象)白膜渲染实战(材质覆盖 + Cycles GPU + 天空纹理;Base Color 0.6 防过亮)

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

## v0.2.3 · 2026-08-17

- §8 扩充"查看每帧渲染用时"详细版:中文菜单路径、输出格式解读(累计时间/单帧换算)、命令行日志统计、F12 vs Ctrl+F12 差异

## v0.3.0 · 2026-08-17

- 新增 `scripts/blender-remote-control/` 可复用脚本包(跨机器):
  - `blender_bridge.py`(桥 v2,端口 9877,主线程执行)
  - `send.py`(发送客户端,纯标准库无依赖)
  - `example_probe.py`(通用示例:探查相机及关键帧,兼容 4.x/5.x Slotted Action API)
  - `README.md`(原理 / 环境核对清单 / 使用步骤 / 踩坑 / 常见问题)
- `docs/技巧速查.md` §1 更新:脚本位置改为指向仓库内可复用包
