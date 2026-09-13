# 渲染发黑 / 材质不发光 —— 诊断脚本包

一句话：**"我给了发光材质，渲染还是黑的"** —— 用这个脚本一次打全七条路径，直接给出头号嫌疑。

配套文档：[`docs/渲染发黑与材质不发光排查.md`](../../docs/渲染发黑与材质不发光排查.md)

## 为什么需要它

这类问题 90% **不在材质节点里**。而人（和 AI）的直觉都是"去节点树里找"，
于是会在一个完全正确、但**根本没被使用**的材质上折腾半天。

最典型的两层原因叠加：

```
第 1 层：View Layer 有个 material_override  →  全场景材质被替换，你改什么都不生效
第 2 层：材质里有 2 个 BSDF，你把发光设在了【没接输出】的那个上  →  真正生效的是另一个
```

只查一层就会得出错误结论。所以脚本的设计目标不是"查得深"，而是**一次打全、不漏层**。

## 文件

| 文件 | 说明 |
|---|---|
| `diagnose_blackout.py` | 诊断脚本本体，通过 9877 桥发送执行 |

## 使用

1. 确认桥在跑（Blender → Scripting → Run `blender_bridge.py`，看到 `[Bridge v2] BRIDGE READY`）
2. 把 `diagnose_blackout.py` 拷到工作目录，按需改顶部两个配置项
3. 发送：

```powershell
& python.exe .\bl.py .\diagnose_blackout.py
```

结果落在 `diagnose_blackout.py.out`（本机 PowerShell 不回传 stdout，`bl.py` 会代为落盘）。

## 配置项

| 变量 | 默认 | 说明 |
|---|---|---|
| `TARGET` | `""` | 填对象名（支持子串匹配）做对象级体检；留空只做全场景扫描 |
| `MAX_LIST` | `40` | 每个清单最多打印条数，避免大工程刷屏 |

## 输出分区

| 区 | 内容 |
|---|---|
| A | 引擎 / `view_transform` / `look` / `exposure` / `film_transparent`（含自动告警：Workbench 不读材质、AgX 压暗） |
| B | 所有 view layer 的 `material_override` + Workbench `color_type` / `single_color` |
| C | 全场景材质健康度：① `use_nodes=False` ② 输出未连通 ③ 输出直连 `Transparent BSDF` ④ **假发光节点** ⑤ 多 BSDF 只连一个 ⑥ 多 `OUTPUT_MATERIAL` |
| D | 对象级：类型 / 父子 / 可见性 / **Holdout** / 光线可见性 / slots / 材质树完整连线 |
| E | **结论区**：按实际扫描结果给出"头号嫌疑 + 建议动作" |

## 实测数据

真实工程（22315 对象 / 236 材质 / Blender 5.2 / Cycles）：

| 项 | 值 |
|---|---|
| 单次全场景扫描耗时 | **0.05 s** |
| material_override | 命中（用户已手动清除） |
| 假发光节点 | 命中 1 个（`Emission Strength=100` 未接输出） |
| 多 BSDF 只连一个 | 命中 1 个材质 |

耗时主要在材质树遍历，与材质数线性相关。**不要在脚本里遍历 Action 的 fcurve** ——
那是分钟级操作，会撞桥的 120 s 上限（见 `docs/技巧速查.md` §1）。

## 已知坑

- **脚本文件不能带 BOM**：Windows PowerShell 5.1 的 `Set-Content -Encoding UTF8` 会写入 BOM，
  桥端直接 `SyntaxError: invalid non-printable character U+FEFF`。
  请用 `open(path, 'w', encoding='utf-8')` 写文件，或让编辑器不写 BOM
- **`indirect_only` 等旧属性在 5.x 可能不存在**：脚本用 `getattr(..., 'n/a')` 兜底，打印 `n/a` 属正常
- **`mat.diffuse_color` 与节点树结果无关**：那是视口颜色，不要拿它当"材质没生效"的依据
