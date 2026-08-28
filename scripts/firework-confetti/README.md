# 粒子系统礼花喷射方案（金纸礼花/Confetti Cannon）

使用 Blender 粒子系统实现持续向上喷射金色纸片的效果，含湍流扰动和碰撞杀死。

## 文件

| 文件 | 用途 |
|------|------|
| `build_firework.py` | 创建完整的礼花系统（含纸片、材质、发射器、粒子、湍流、杀死平面） |
| `sync_emitter.py` | 将发射器同步到发射点空对象的位置和旋转 |

## 用法

### 先决条件

1. 在场景中创建空对象作为发射点，命名如 `发射点，方向Z向_01`
2. 创建空对象 `杀死粒子`，放在粒子应该消失的高度
3. 确保场景使用 Eevee 渲染

### 发送到 Blender

```bash
python send.py build_firework.py
```

### 参数调优

在 build_firework.py 中可修改顶部常量：

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `START_FRAME` | 601 | 开始发射帧 |
| `END_FRAME` | 826 | 停止发射帧 |
| `PARTICLE_COUNT` | 4000 | 粒子总数 |
| `NORMAL_FACTOR` | 24 | 法向(向上)速度 |
| `GRAVITY` | 0.8 | 重力 |
| `DRAG_FACTOR` | 0.3 | 空气阻尼 |
| `BROWNIAN_FACTOR` | 6.0 | 飞行噪波 |
| `TURB_STRENGTH` | 15.0 | 湍流强度 |
| `TURB_SIZE` | 3.0 | 湍流噪波尺寸 |

## 常见问题

### 粒子不显示

切换到 Rendered 视口着色模式。

### 粒子不消失

检查碰撞平面的 `use_particle_kill` 是否为 True，且位置在粒子下方。

### 发射方向不对

发射器平面旋转 `(0, 0, 0)` 时沿 Z 向上。如需匹配发射点空对象角度，运行 `sync_emitter.py`。