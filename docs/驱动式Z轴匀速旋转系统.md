# 驱动式 Z 轴匀速旋转系统(Blender 5.2)

> 给指定空物体加**匀速 Z 轴旋转**驱动:一个控制面板承载 `旋转速度` 滑块(度/帧),
> 所有目标共用,每个目标可独立设定**正向 / 反向**;改速度即时生效,不烘焙关键帧。
> 可复用脚本包见 `scripts/driver-spin/`(含 `spin_driver.py` / `build_spin_drivers.py` / README)。

## 场景

点位模型 / 装置里有几个部件想绕 Z 轴**匀速转**:

- 匀速(不像浮动那样带噪波),但能统一调速,拖滑块立刻变速;
- 多个部件**方向可不同**(一个正转、一个反转),但共用一个速度;
- 方便调试:速度滑块一拖、时间轴一 scrub 立刻看效果,不烘焙关键帧;
- 不需要每个部件单独 K 帧、不需要手写角度表达式。

## 原理(为什么是"实时调速")

**角度 = 基准角(0°) + 当前帧 × 旋转速度(度/帧) × 方向符号**,其中旋转速度来自一个
共享控制面板 `旋转控制` 上的自定义属性 `旋转速度`。

关键点:`spin_speed()` 这个函数**每次驱动求值都去实时读** `旋转速度` 这个属性,
而不是把速度"固化"进表达式。所以:

- 拖 `旋转速度` 滑块 → 下一帧起所有目标立即变快 / 变慢 / 停(设 0);
- 方向由每个目标构建时给定的 `+1 / -1` 决定,表达式里乘方向符号即可;
- 全程无关键帧、无烘焙,纯驱动求值,干净可回退。

### 与浮动系统(bob)的对比

| 维度 | bob(上下浮动) | spin(本系统,匀速旋转) |
|---|---|---|
| 信号 | 两层加权 Perlin 噪波(连续、错动) | 线性 `帧 × 速度`(匀速) |
| 轴向 | `location.z` | `rotation_euler[2]`(Z 欧拉角) |
| 控制面板 | 每集合一个(`运动控制0X`,9 滑块) | 全局一个(`旋转控制`,1 滑块) |
| 方向 | 由噪波符号自然给出 | 每个目标显式 `+1 / -1` |
| 持久化 | `bob_driver.py` 文本块 + Register | `spin_driver.py` 文本块 + Register |

## 做法(可复用脚本)

### 1. 核心函数 `spin_speed()`(注册进驱动命名空间)

完整源码见 `scripts/driver-spin/spin_driver.py`。要点:

```python
def spin_speed():
    ctrl = bpy.data.objects.get('旋转控制')
    if ctrl is None:
        return 1.0
    return float(ctrl.get('旋转速度', 1.0))
bpy.app.driver_namespace['spin_speed'] = spin_speed
```

### 2. 通用构建器 `build_spin_drivers.py`

```python
TARGETS = [
    ('空物体.006_需要旋转', +1),   # (对象名, 方向) +1 正向 / -1 反向
    ('空物体.007_需要旋转', -1),
]
# 每个目标: driver_add('rotation_euler', 2) 挂 Z 旋转驱动
#          表达式 = 0.0 + fr * spin_speed() * DEG2RAD * sign
#          fr 由 SINGLE_PROP 读 scene.frame_current
#          先移除旧 Z 驱动 → 幂等重建;基准角复位为 0
```

运行(经桥或 Scripting 工作区 Run Script):
```bash
python send.py build_spin_drivers.py
```

### 3. 控制面板(实时调)

选中 `旋转控制` 空物体 → 属性面板 → 自定义属性 → `旋转速度`(度/帧,0~20,默认 1.0)。
拖时间轴 / `Alt+A` 播放即可看效果。

## ⚠️ 坑(代码里看不出,全是实战踩的)

- **Z 轴旋转用 `rotation_euler[2]`,不是 `rotation` / `rotation_quaternion`**:直接给 `rotation`(四元数)挂驱动路径会被当四元数读,结果错乱;务必 `driver_add('rotation_euler', 2)`。
- **基准角要复位为 0**:目标若之前被驱动污染过 Z 角(如实战里残留 100°),构建时显式 `rotation_euler.z = 0.0`,否则角度从错误基准累加。脚本在挂驱动前强制复位。
- **`spin_speed()` 不随 .blend 保存**:驱动依赖注册进 `bpy.app.driver_namespace` 的函数,重开文件函数丢失 → 旋转驱动变红。必须用文本块 `spin_driver.py` 勾 Register 持久化,或用 `scripts/driver-restore/restore_drivers.py` 一键恢复。
- **速度用 SINGLE_PROP 读 `scene.frame_current`**:不依赖内置 `frame` 变量(5.x 驱动命名空间默认无 `frame` 键),每帧强制重算,调速即时生效。
- **多个独立速度组**:本包默认一个共享 `旋转控制`;若要两组互不干扰的速度,复制 `spin_driver.py` / `build_spin_drivers.py` 并把 `旋转控制` / `旋转速度` 改名(函数和表达式里同步改)。
- **桥只改内存**:构建完记得 Ctrl+S(尤其 `spin_driver.py` 文本块 + `旋转控制` 面板属性)。

## 验证要点

- 速度 1 → 每帧转 1°,100 帧 = 100°;速度 3 → 100 帧 = 300°;速度 0 → 完全不动(实测精确)。
- 正 / 反目标角度符号相反(一个递增一个递减)。
- 重开文件后跑 `restore_drivers.py`,`spin_speed in namespace` 应为 True,旋转恢复。
