# volume-beam-feather · 体积光柱羽化

给射灯（SPOT）做**可见的光柱**：闭合锥体当体积域 + 局部体积材质，
再把**同一个渐变同时接到 `Density` 和 `Emission Strength`**，边缘才会真正羽化。

主题文档见 [docs/体积光柱羽化系统.md](../../docs/体积光柱羽化系统.md)（主题 #47）。

---

## 这个包解决什么

| 问题 | 现象 |
|---|---|
| 真空里看不见光柱 | 纯黑世界下，只有灯没有锥体 → **非零像素 0** |
| 假几何锥边缘硬 | 亮度来自"锥面被照亮"，看到的是两层壳，边缘就是网格边界 |
| 体积锥也还是硬 | 均匀密度的横向亮度 ∝ `2√(R²−d²)`，贴边处导数发散 |
| **加了径向渐变还是硬** | ★ **`Principled Volume` 的 Emission 不受 `Density` 控制** —— 渐变必须同时接 `Emission Strength` |
| 参数没法手动调 | 材质节点不上属性面板 → 用**场景自定义属性 + 驱动器**做滑块 |

---

## 脚本

按顺序跑，每个都能独立执行（`python xxx.py` 或经远程桥 `python bl.py xxx.py <port>`）。

| 脚本 | 作用 |
|---|---|
| `probe_beam.py` | **先探查**：射灯清单与几何签名、已有锥体、材质与驱动器、场景属性 |
| `build_feather_material.py` | 建/重建羽化材质 + 三个**滑块属性** + 三条驱动器 |
| `add_cones_all_lights.py` | 给所有射灯批量建锥，**共享同一份材质**；旧锥体隐藏不删除 |
| `verify_beam.py` | **独立核验**（另跑一次），末尾输出 `VERIFY_RESULT PASS/FAIL` |
| `undo_beam.py` | 撤销：删锥、删材质、删属性；`DRY_RUN=True` 只看不动 |

### 典型流程

```bash
python add_cones_all_lights.py      # 1. 先建锥(此时材质还不存在会报错 → 先跑第 2 步也行)
python build_feather_material.py    # 2. 建材质(读样板锥的 L/R)
#   ↑ 若材质应共享,记得把 add_cones_all_lights.py 的 CONE 材质指回去(默认同名)
python verify_beam.py               # 3. 核验
```

> 更顺的做法：先手工建**一个**样板锥（或在 `add_cones_all_lights.py` 里把
> `MAT_NAME` 指向一个已存在材质），跑 `build_feather_material.py`，
> 再跑 `add_cones_all_lights.py` 批量共享。

---

## 材质链（核心）

```
fall = 长度衰减(z: −L/2…L/2 → 0.05…1.0) × 径向衰减(1 − ρ^p)

ρ = √(x²+y²) / radius(z),   radius(z) = R/2 − R·z/L      ← 锥体局部坐标

Density           ← fall × 浓度
Emission Strength ← fall × 亮度        ★ 少了这条，羽化完全不生效
```

**几何常量 `R` / `L` 是烘焙进材质的**，所以只有当所有灯的
`spot_size` 与 `cutoff_distance` **完全一致**时才能共用一份材质。
`add_cones_all_lights.py` 会在开头检查几何签名，不一致直接中止（不会做错东西）。

---

## 参数（三个滑块）

都在 **Scene → 属性编辑器 → 「场景」标签 → 最底下的「自定义属性」**：

| 属性 | 默认 | 范围 | 说明 |
|---|---|---|---|
| **光锥羽化** | 1.0 | 0.1 ~ 8 | 越小越柔，同时越暗 |
| 光锥浓度 | 0.8 | 0 ~ 3 | 只影响吸收/散射，**不影响自发光亮度** |
| 光锥亮度 | 2.5 | 0 ~ 20 | 主要亮度旋钮 |

实测（近距离 520×520，过渡宽度 = 扫描线上 50%→10% 的像素跨度）：

| 羽化指数 p | 峰值 | 过渡宽度 |
|---|---|---|
| 0.1 | 0.390 | 297 px |
| 0.5 | 0.613 | 277 px |
| 1.0 | — | 260 px |
| 1.5 | — | 250 px |
| 2.5 | — | 239 px |
| 4.0 | — | 230 px |

**羽化越强越暗**（`Emission Strength` 被 `fall` 乘了一遍）→ 用「光锥亮度」补。

---

## 三个必须知道的坑

1. **`Principled Volume` 的 Emission 不受 `Density` 控制**
   实测：`Density` 接 `Value=0.0`（零浓度）画面**依然亮**，而且比 0.8 浓度**更亮**
   （浓度低 → 吸收少 → 自发光累积更多）。只接 Density = 白费。

2. **5.2 里 `nodes.remove()` 之后旧节点引用会失效**
   `out.name` 读出乱码（`UnicodeDecodeError`）、`out.inputs["Volume"]` 抛 `KeyError`，
   更阴的是**链接静默丢失**。本包所有脚本都采用「删完重新遍历取输出节点」的写法。

3. **改自定义属性后依赖图不会自动重算**
   脚本里要 `sc.update_tag()`；**GUI 拖滑块 Blender 会自动打 tag**，所以手上是即时的。
   驱动器求值还有**延迟**：同一次脚本内"改属性→立刻读插槽"读到的是旧值。

---

## 设计选择

- 驱动器用 **`AVERAGE` 型（单变量、无表达式）**，不用 `SCRIPTED`
  —— 后者在非受信任打开的 .blend 里会静默不求值（见主题 45）。
- 锥体只对相机可见（关掉 `visible_shadow / diffuse / glossy / transmission / volume_scatter / volume`），
  **不投影、不影响场景光照**。
- 旧锥体一律**隐藏不删除**，撤销脚本里也保留"恢复显示"开关。
