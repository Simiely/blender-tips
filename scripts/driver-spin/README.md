# 驱动式 Z 轴匀速旋转系统(跨项目复用包)

给指定空物体加**匀速 Z 轴旋转**驱动:一个控制面板承载 `旋转速度` 滑块(度/帧),
所有目标共用,每个目标可独立设定**正向 / 反向**;改速度即时生效,不烘焙关键帧。

适用: 想让某些装置 / 标志牌 / 转盘绕 Z 轴匀速转、又能统一调速的场景
(如两个反向旋转的部件,一个正转一个反转,共用一个速度滑块)。

## 文件清单

| 文件 | 作用 | 运行位置 |
|---|---|---|
| `spin_driver.py` | **核心函数** `spin_speed()`:实时读控制面板的 `旋转速度`,注册进驱动命名空间;勾 Register 可随 .blend 打开自动恢复 | **Blender 内部**(Scripting 工作区运行) |
| `build_spin_drivers.py` | **通用构建器**:建控制面板、给指定目标挂 Z 旋转驱动(可设方向);可重复运行(幂等) | 外部,配合桥 `send.py` 或直接 Run Script |
| `../docs/驱动式Z轴匀速旋转系统.md` | 完整原理 / 参数说明 / 踩坑 | 阅读 |
| `../driver-restore/restore_drivers.py` | 重开 .blend 后一键恢复 bob/spin 命名空间函数 | 阅读 / 运行 |

## 运动原理(一句话)

每个目标的 Z 旋转角 = `基准角(0°) + 当前帧 × 旋转速度(度/帧) × 方向`。
速度是**实时读取**的(每次驱动求值都去读控制面板属性),所以拖滑块立刻变速,
不需要重跑脚本、不需要烘焙关键帧。

## 环境要求

- Blender 5.2(实测);桥远程执行见 `scripts/blender-remote-control/`
- `spin_speed()` 依赖 `bpy.data.objects['旋转控制']['旋转速度']`,不依赖第三方模块

## 使用步骤

### 1. 注册 spin_speed 函数(每台机器 / 每次重启 Blender 跑一次)

Blender → Scripting → 文本编辑器 **Open** `spin_driver.py` → **Run Script**(Alt+P)。
可勾 **Register**(文本编辑器右上角)让下次打开 .blend 自动运行。

> ⚠️ `spin_speed()` **不随 .blend 文件保存**。若打开文件后旋转驱动变红,跑一次
> `spin_driver.py` 即可;或勾 Register + 开启「偏好设置 → 自动运行 Python 脚本」免手动。
> 更省事:用 `scripts/driver-restore/restore_drivers.py` 一键恢复。

### 2. 构建驱动(指定你的目标)

编辑 `build_spin_drivers.py` 顶部的 `TARGETS` 列表(默认已是实战示例):
```python
TARGETS = [
    ('空物体.006_需要旋转', +1),   # (对象名, 方向) +1 正向 / -1 反向
    ('空物体.007_需要旋转', -1),
]
```
然后通过桥运行(或直接在 Scripting 工作区 Run Script):
```bash
python send.py build_spin_drivers.py
```

- 自动新建一个**控制面板空物体** `旋转控制`,承载 `旋转速度` 滑块(0~20,默认 1.0 度/帧)
- **可重复运行**:已有 Z 旋转驱动的目标先移除再重建,基准角永远复位为 0°

### 3. 调参(实时)

选中 `旋转控制` 空物体 → 右侧属性面板 → 底部 **自定义属性** → `旋转速度`(度/帧):
拖时间轴 / `Alt+A` 播放即可看效果;想停就设 0。

## 注意事项(踩过的坑)

1. **Z 轴旋转用的是 `rotation_euler[2]`(欧拉角 Z 分量),不是 `rotation` / `rotation_quaternion`**:
   直接给 `rotation`(四元数)挂驱动路径会被当四元数读,结果错乱;务必 `driver_add('rotation_euler', 2)`。
2. **基准角要复位为 0**:目标物体若之前被驱动污染过 Z 角(如残留 100°),构建时显式 `rotation_euler.z = 0.0`,
   否则角度从错误基准累加。本脚本在挂驱动前强制复位。
3. **驱动变量类型无 `SELF`(Blender 5.x)**:与 bob 同理,本脚本只读控制面板(共享对象),不涉及自身属性,故无需 use_self。
4. **`spin_speed()` 不随文件保存**:必须靠文本块 `spin_driver.py` + Register 持久化,否则下次打开驱动变红。
5. **速度用 SINGLE_PROP 读 `scene.frame_current`**:不依赖内置 `frame` 变量(5.x 驱动命名空间默认无 `frame` 键),每帧强制重算。
6. 桥只改内存,**记得 Ctrl+S**(尤其是 `spin_driver.py` 文本块 + `旋转控制` 面板属性)。

## 调试建议

- 想正反转互换 → 把该目标 TARGETS 里的 `+1` / `-1` 对调后重跑
- 想不同目标用不同速度 → 复制一份逻辑各自建独立控制面板(把 `旋转控制` / `旋转速度` 改名)
- 打开文件发现旋转不动/变红 → 跑 `scripts/driver-restore/restore_drivers.py`
