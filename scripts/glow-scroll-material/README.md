# glow-scroll-material —— 渐变发光滚动材质

把一张**竖图渐变**（上亮下暗）做成自发光材质，并让渐变**竖直匀速滚动**，
滚动速度用一个空物体滑块控制（可打关键帧调速）。

## 场景

- 想给物体一个"灯光渐变 + 流动"的发光效果；
- 渐变方向竖直（和灯光一致：顶部亮、底部暗）；
- 贴图要放大只显示一部分 + 匀速滚动，形成灯光流动动画；
- 滚动速度希望可驱动调节（打关键帧做变速）。

## 用法

```bash
python send.py build_glow_scroll_material.py    # 或 Scripting 工作区 Run Script
```

改脚本顶部 `MAT_NAME`（目标材质）/ `IMG_PATH`（贴图路径）即可。

## 效果

运行后：
- 目标材质重建节点树：`纹理坐标(UV) → 滚动映射 → 渐变贴图 → 原理化BSDF(自发光)`
- 场景出现「贴图滚动控制」空物体，带 `滚动速度` 滑块（默认 0.05 V/帧）
- 贴图竖直放大 2 倍（Mapping Scale Y=0.5），只显示上半部分（顶亮区）
- 匀速滚动：Mapping Location Y 挂驱动 `fr * scroll_speed()`，每帧滚动 0.05
- 悬停 `滚动速度` 按 `I` 打关键帧 → 随时变速

## 参数表

| 常量 | 默认 | 含义 |
|---|---|---|
| `MAT_NAME` | 06 - Default.003 | 要重建的目标材质 |
| `IMG_PATH` | .../001.png | 渐变贴图路径（竖图） |
| `CTRL_NAME` | 贴图滚动控制 | 速度控制空物体 |
| `SPEED_PROP` | 滚动速度 | 速度滑块属性（V/帧） |
| `SPEED_DEFAULT` | 0.05 | 默认速度 |

## 注意（实战踩的坑）

- **5.2 天空/纹理参数可能是节点属性而非 socket**：这里 Mapping 的 Location/Scale 是
  socket（inputs[1]/inputs[3]），但 `TEX_SKY` 的 sun_elevation 等是节点属性——先确认目标。
- **节点驱动存在 node_tree.animation_data**：路径 `nodes["滚动映射"].inputs[1].default_value`，
  不是节点自身（`ShaderNodeMapping` 无 animation_data）。
- **脚本改滚动速度不立即生效**（depsgraph 缓存），但 **UI 手动改/打关键帧正常**。
- **Bridge exec 时 `__name__` 是 `builtins`**：脚本直接调用 `main()`，不用 `__main__` 守卫。
- 运行后 **Ctrl+S** 保存；`scroll_speed` 是命名空间函数，重开文件后驱动可能报红，
  用 restore_drivers.py 或手动 Run Script 恢复。
