# dispersion-glass —— 水晶色散材质

四片 Glass（红/绿/蓝/白）用 `Add Shader` 相加，用 `Light Path.Transmission Depth` 当 `Mix Shader` 系数
切开「表面 / 内部」，再用「噪波 → 三段 ColorRamp」控三片彩色玻璃的粗糙度。
效果：通透水晶 + 边缘细密彩虹彩边，接近真实钻石火彩。

## 场景

- 想要通透水晶/宝石 + 边缘彩色色散，但 **5.2 没有原生色散参数**（`Principled` / `Glass BSDF` 都没有 Dispersion）；
- 三片纯 RGB 玻璃直加时本体容易发暗、或被内反射染浑；
- 希望表面大部分保持通透，只有噪波峰值处磨砂，形成"干净玻璃 + 局部彩斑"。

## 用法

```bash
python send.py build_dispersion_glass.py     # 桥（改内存，不存盘）
```

或 Scripting 工作区打开本文件 → Run Script。会套到**当前选中**的网格对象上（没选中则套到所有网格）。
参数都在文件顶部常量里：三片玻璃的 IOR、噪波 Scale/Detail/Roughness、色带黑标位置。

## 节点结构（13 节点 / 14 连线）

```
纹理坐标.Object → 映射(恒等) → 噪波(15/15/1/2/0) → 颜色渐变(0.000黑 / 0.459黑 / 1.000白)
                                                      ├→ 红 Glass(1.450).Roughness
                                                      ├→ 绿 Glass(1.500).Roughness
                                                      └→ 蓝 Glass(1.550).Roughness

Add(绿,蓝) → Add(该结果,红) → Mix.Shader1
白 Glass(1.500, Rough 0, 不接色带) → Mix.Shader2
Light Path.Transmission Depth → Mix.Fac → Material Output
```

## ★ 三条必须守住的

1. **色带是三段，不是两段。** `0.000 黑 → 0.459 黑 → 1.000 白`。写成 `0 黑 → 0.459 白` 会让噪波
   ≥0.459 全部输出白 = 粗糙度 1，半个表面糊死，渲出来是一颗**磨砂白瓷**（实测彩色面积 0.0%）。
   只改这一个色标位置，彩色面积从 0.0% 涨到 37.1%。
2. **`Transmission Depth` 接 `Mix Shader.Fac`。** 接错到噪波向量上等于让内反射深度扰动粗糙度，机制完全不同。
3. **`Add Shader` 是能量相加。** 四片叠加 = 两倍亮度（实测 0.90 严重过曝），偏亮场景可把四片颜色按 1/2 缩放。

## 实测

| 材质 | 彩色面积 | 色相数 | 亮度 |
|---|---|---|---|
| 本材质（三段色带） | 37.1% | 3 | 0.49 |
| 同上但两段色带 | 0.0% | 2 | 0.85（磨砂白） |
| 同上但不接光程切换 | 0.0% | 1 | 0.90（过曝白） |

## 出处

https://www.youtube.com/watch?v=RMXZJw7Fu9g 《Dispersion glass material in Blender》，
按 5.2 实测校正（教程为旧版 Blender，`Combine HSV` / `RGB Curves` 在 5.2 均已改名或移除）。
完整说明见 [docs/水晶色散材质.md](../../docs/水晶色散材质.md)。
