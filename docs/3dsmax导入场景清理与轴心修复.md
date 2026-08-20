# 3ds Max 导入场景清理与轴心修复

> 来源:260820x03.blend 实战(11,961 对象 / 4,073 动画对象 / 3ds Max 导入 / Blender 5.2)
> 覆盖:缺失数据诊断 → 空物体清理 → 轴心安全修复(翻车教训) → 动画清理(保留相机) → 5.2 API 坑

## 一、缺失数据诊断(保存提示"缺材质")

**场景**:Blender 保存文件时弹"缺失"警告,但材质槽看着都正常。

**做法**:五查——①空材质槽(material is None) ②外部库引用(material.library) ③**图片文件缺失**(遍历 bpy.data.images,未打包且 filepath 磁盘不存在) ④动画 action 引用 ⑤约束 target 断裂。

**坑**:
- 最常被误当"缺材质"的是 **③图片文件缺失**:3ds Max 的 .fbm 贴图目录路径带旧机器绝对路径(`C:\Users\Administrator\Desktop\xxx.fbm\`),必然失效
- 修复:断开 Image Texture 节点 `node.image=None` → `bpy.data.images.remove(img, do_unlink=True)`
- `remove()` 后立即访问 `img.name` 报 `ReferenceError: StructRNA has been removed`——先存名字字符串

## 二、空物体清理(两类垃圾)

1. **完全孤立空物体**:无子对象/无动画/无自定义属性/无约束修改器 + user_map 无 Scene/Collection 之外引用 → 删(典型:创建未改名的 `Untitled.001~498`)
2. **3ds Max 元数据残留**:EMPTY 且自定义属性 ⊆ `{MaxHandle, NodePropParameters, MaxWireColor, MaxRange, MaxGroupID}` + 无其他内容 → 删(`组*` 组辅助、`3d66-Event/DisplayParticles/RenderParticles/Birth/Position_Object/speed` 粒子辅助、`Camera*.Target`)

**坑**:`bpy.data.user_map()` 在 5.2 返回 `dict{block: set}`——可遍历,切片报 `'set' object is not subscriptable`。

## 三、轴心修复(核心,翻车教训)

**场景**:选中对象操作"没效果"——旋转绕远处点转、对齐数值与视觉不符。

**根因**:3ds Max 导入对象**全部带非单位缩放(实测 0.006~0.594)+ 全部带旋转,部分负缩放(镜像)**。对这种对象直接 `origin_set` 位置会跳变(负缩放包围盒方向都反)。

**安全流程**(单对象验证 bbox 中心/顶点世界位移 = 0):
```
① bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)  # 烘焙旋转缩放,视觉不变
② bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')          # 轴心归位
```

**跳过条件**:
- **multi-user 网格**(`obj.data.users > 1`):transform_apply 报 `Cannot apply to a multi user`;需先 `obj.data = obj.data.copy()` 独立网格再处理(复制后原网格成 orphan)
- **有动画对象**:跳过(或连动画曲线一起平移,复杂)
- 动画**空引用**(action 的该对象 slot 无实际 fcurve,导入残留)→ 可直接安全处理

**验证**:处理前后 bbox 世界中心与顶点世界位置位移 ≈ 0;处理后轴心偏移(几何中心-原点) < 0.01。

## 四、动画清理(保留相机动画变体)

**场景**:3ds Max 导入产生 4000+ 动画对象(共享一个 Take 001 action),实际无用;但**相机动画(位置/角度 + data 级焦距/景深)要保留**。

**做法**:
1. 逐对象静态化当前变换:记录 `matrix_world` → `animation_data_clear()` → 恢复 `matrix_basis`(有父级乘 `parent.matrix_world.inverted()`)——防止对象跳到属性面板值
2. 保留:**CAMERA 类型对象** 与 **camera data**(`bpy.data.cameras` 的 animation_data)的动画
3. 删 orphan action:先 `use_fake_user=False`,再 `users==0` 才 `remove()`

**坑**:
- action 可能被 **Camera data 块**引用(users=1)——只清对象动画后 action 删不掉,需清 data 级动画
- `animation_data_clear()` 是 API 调用,**不进 undo 栈**;`bpy.data.actions.remove()` 同理 → 删了只能重开文件恢复,操作前确认保留名单

## 五、Blender 5.2 API 坑速记

| API | 变化 / 替代 |
|---|---|
| `obj.apply_transform()` | 不存在 → `bpy.ops.object.transform_apply(location=, rotation=, scale=)` |
| `action.fcurve_find` / `ActionSlot.fcurves` | 不存在 → `fcurve_ensure_for_datablock(obj, path, index=i)` 后判空;遍历 slot 用 `slot.identifier` 区分(OB对象/CA相机数据) |
| `bpy.context.undo` | 5.2 已移除 |
| `obj.lock_get()` | 不存在 → 用 `obj.hide_select` |
| 桥内 `bpy.ops.ed.undo()` | 可能 poll 失败(context incorrect),撤回走循环 undo 或重开文件 |
