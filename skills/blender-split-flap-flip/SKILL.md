---
name: blender-split-flap-flip
description: 给翻页牌（split-flap / 报刊亭翻页牌 / 机场翻页显示牌）的卡片做批量翻页动画：中缝轴挂接、整数圈落位、斜向波浪相位。当用户要求「翻页牌动起来」「卡片绕中缝翻转」「批量翻页 + 波浪」「翻完要回到初始朝向」时使用。含非受信任文件导致驱动静默失效的绕行方案、弧度换算陷阱、存盘冻结陷阱。
agent_created: true
---

# 分体翻页牌驱动翻页(Split-flap)

## 铁律(绝对不能违反)

1. **先只读体检再动手**。摸清:卡片尺寸/数量、父级层级、有没有动画、轴心在哪。
2. **总转角必须是 360 的整数倍**。半圈(180°)结束是背面朝外 —— 看不到字;
   `360 × N`(默认 3 圈 = 1080°)结束才与初始朝向完全一致。
3. **keep-transform 只补偿一次**。
   `world = pivot.mw @ parent_inverse @ basis`;保持世界不变的做法是
   `parent_inverse = T(center)⁻¹` 且 `basis = 原世界矩阵`。
   **两处都乘 `T⁻¹` = 双重补偿**,卡片会被平移到 `T(-center) @ orig`(实测 bbox 跑到世界原点附近)。
4. **驱动表达式必须返回弧度**。`rotation_euler` 单位是弧度,写 `1080.0` 会被当成 1080 弧度
   (= 61879°),全部卡片歪成随机角度。一律 `radians(1080.0)`。
5. **新建/刚改父级的对象不要回读 `matrix_world`**(可能拿到 basis 或过期值)。
   根级轴的世界变换用 `Matrix.Translation(center)` **解析构造**;只有加载后从未动过的对象读才可信。
6. **保存前必须停到静止帧或跑 `reset_flip_rest.py`**。`bpy.app.handlers` 不写进 .blend,
   存盘会把"当时那一帧的角度"冻结进文件,重开即僵在半翻姿态。
7. **★ 挂父级必须「先 `parent`,再设 `matrix_parent_inverse`」**。
   顺序反了补偿矩阵会被 Blender 重置成单位矩阵,整组多叠一个 `+父级位置` 的位移
   (实测把 35 个轴收进总控时,全部卡片平移 `(-59.44, -15.90, +2.08)`)。
8. **改前快照、改后核验**: 改前记每张卡世界包围盒 min,改后逐张比对,有偏移立刻中止并报告。
   链完整性最强判据:**每张卡的中心严格等于其中缝轴的世界位置**(误差 < 1e-4)。

## 标准作业循环

1. 只读体检(`probe_flip.py`):卡片数、尺寸、父级、残留角度、trust 状态
2. 批量挂轴(`attach_flip_axes.py`):内置快照/核验,位置偏移会中止
3. 呈报:卡片数、静止帧、参数表
4. 调参(`retune_flip.py`):圈数/时长/周期/波浪步长
5. 要整体搬运/复用到别的工程 → `group_under_master.py`:全部轴收进一个**总控 Empty**(放在轴群中心、
   `rotation` 保持 0)+ 单一集合;移动/旋转总控即整体跟随,别的工程 Append 该集合即可
6. 存盘前 `reset_flip_rest.py` → Ctrl+S
7. 不想要了 `detach_flip_axes.py`(卡片自动回到世界原位,因为 basis 就是原世界矩阵)

## 免信任实时方案(★ 本 skill 的核心)

**现象**:SCRIPTED 驱动在非受信任打开的 .blend 里**静默不求值** —— 不报错、不动、看不出来。
判据:`bpy.context.preferences.filepaths.use_scripts_auto_execute == False`
(属性名不是 `use_auto_scripts`)。**运行时把该偏好临时开成 True 也救不活**,
受信任标记在文件加载那一刻就定了(已实证)。

**两条出路**:
- 本次会话实时看效果 → `bpy.app.handlers.frame_change_post` 处理器按公式写 `rotation_euler`
- 长期 → 以受信任方式重开文件(`Reload Trusted`),驱动自动接管

**判活方法**:驱动只写 **evaluated** 数据,必须读
`obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world`;
直接读 `obj.matrix_world` 永远是 0。

## 公式

```
# 角度(弧度)
total = radians(360 * turns)
u = ((frame - delay) % period) / dur
v = total * (3u² - 2u³)   if u < 1   else   total     # smoothstep: 慢起→加速→减速停住
```

- 二次缓动(`u²`)会在到位瞬间**急停**,很假;用 smoothstep
- 相位:`delay = ((列 + 行) % 8) * 2`(同一对角线同时翻,斜向波浪)。
  `% 8` 会让第 0 与第 8 列同步(周期条带,正常);要单一扫过就去掉取模

## 挂接代码(模板)

```python
mw = card.matrix_world.copy()                 # 未动过的对象,可信
center = 卡片世界包围盒中心
pivot = bpy.data.objects.new("FLIP_pivot_x", None)
scene.collection.objects.link(pivot)
pivot.location = center                       # 根级: world == T(center)
card.parent = pivot
card.matrix_parent_inverse = Matrix.Translation(-center)   # 唯一的补偿
card.matrix_basis = mw                                     # 原世界矩阵
```

## 其他已踩坑

- 驱动变量命名避开内置 `frame`(官方警告覆盖内置项未定义行为),用 `fc` / `dl`
- 删驱动用 `fc.data_path`,不是 `fc.driver.data_path`(`AttributeError`)
- 拼表达式时:`%` 格式化要写 `%%`,`.format()` 写 `%`;混用会把 `%%` 留在表达式里变语法错误,
  且因为驱动被屏蔽**不会报错**
- 驱动命名空间有 `radians`(实测可用),没有就 `bpy.app.driver_namespace['radians'] = math.radians`
- 卡片轴心常在角落,必须新建 Empty 当中缝轴;直接转网格会绕角上甩

## 相关

- 传输层:`blender-bridge-ops`
- 文档:`docs/分体翻页牌驱动翻页系统.md`
- 脚本包:`scripts/flip-card/`
