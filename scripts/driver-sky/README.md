# driver-sky —— 天空太阳高度数字驱动

把天空纹理的太阳高度(`sun_elevation`)接到一个控制面板空物体的**数字滑块**上，
对滑块打关键帧即可控制太阳升降动画（单位友好，集中控制）。

## 场景

- 想让天空的太阳高度可调、可做太阳升降动画；
- 直接给 `sun_elevation`（弧度）打关键帧不直观，想要一个「度」为单位的滑块；
- 希望所有动画控制集中在一个空物体上，方便查找和批量管理。

## 用法

```bash
# 在桥环境远程执行(默认端口 9877)
python send.py build_sky_sun_driver.py

# 或直接在 Blender Scripting 工作区 Run Script
```

改脚本顶部常量：

```python
CTRL_NAME = '天空控制'    # 控制面板空物体名
PROP_NAME = '太阳高度'    # 滑块属性(单位: 度)
COL_NAME  = '新对象'      # 控制面板挂载集合
DEFAULT_DEG = 3.0         # 默认太阳高度(度)
```

## 效果

```
SKY_DRIVER_OK expr=elev * 0.017453292519943295
  天空控制.太阳高度=3.0° -> sun_elevation=3.00°
DONE_OK
```

运行后：
- 场景出现空物体「天空控制」，带 `太阳高度` 滑块（-90°~90°）；
- 世界节点树的天空纹理 `sun_elevation` 挂 SCRIPTED 驱动，实时读滑块值（度→弧度）；
- **鼠标悬停「太阳高度」按 `I` 打关键帧**，即可做太阳升降动画。

## 原理

- 太阳高度是天空纹理节点的**属性**（`ShaderNodeTexSky.sun_elevation`），单位弧度；
- 驱动表达式 `elev * DEG2RAD` 把滑块的「度」转成弧度；
- 节点驱动实际存在**节点树**（`node_tree.animation_data`）上，路径 `nodes["天空纹理"].sun_elevation`，不是节点本身。

## 幂等与安全

- **幂等**:已有 `sun_elevation` 驱动先移除再重建；控制面板已存在则复用，重跑无副作用。
- **非破坏**:不修改天空节点的其它参数（sun_rotation / intensity / size 等）。

## 注意

- **脚本内改滑块值可能不立即触发驱动重算**（depsgraph 缓存，SINGLE_PROP 读自定义属性的已知现象），
  但**用户 UI 手动改 / 打关键帧完全正常**。验证逻辑请用打关键帧 + 跨帧方式。
- 桥接环境 `exec` 时 `__name__` 为 `builtins`，脚本直接调用 `main()`，不用 `__main__` 守卫。
- 运行后 **Ctrl+S** 保存工程，控制面板与驱动才会落盘。
