# Agent Skills（给 AI 助手用的作业规范）

本目录收录供 AI 助手（WorkBuddy 等）加载的 **Agent Skill**：每个子目录一个 skill，
内含 `SKILL.md`（带 YAML frontmatter，描述触发条件 + 作业步骤 + 硬约束）与可选的 `scripts/`。

## 和 `../scripts/` 的区别

| 目录 | 面向 | 内容形态 |
|---|---|---|
| `../scripts/` | **人** | 可复用脚本包：README（原理 / 配置项 / 使用步骤 / 实测数据）+ 脚本 |
| `skills/` | **AI 助手** | 作业规范：怎么干、先干什么、什么绝对不能干，并把同一套脚本作为附件带上 |

两者内容**有意重叠**：`skills/` 的价值是让 AI 不必每次重新推演流程与安全闸，直接照着干。
改动脚本时**两处都要同步**（`skills/<名>/scripts/` 与 `../scripts/<名>/`）。

## 清单

| Skill | 作用 | 关联文档 / 脚本包 |
|---|---|---|
| `blender-bridge-ops` | 9877 桥的**传输层作业规范**：客户端封装、120s 上限规避、Blender 5.x Slotted Action、引用判定、删除后引用失效等硬约束 | [技巧速查 §1](../docs/技巧速查.md) / [`../scripts/blender-remote-control/`](../scripts/blender-remote-control/) |
| `blender-scene-cleanup` | 工程**清理类**改造：EMPTY 收敛清理（不动点）、孤儿数据块、空集合、缺失贴图审计与还原 | [空物体收敛清理](../docs/空物体收敛清理.md) / [`../scripts/scene-cleanup/`](../scripts/scene-cleanup/) |
| `blender-render-blackout-diagnose` | **渲染发黑 / 材质不发光**排查：材质覆盖、引擎不读材质、Holdout、输出未连线或改错节点、AgX 压暗等七条路径 | [渲染发黑与材质不发光排查](../docs/渲染发黑与材质不发光排查.md) / [`../scripts/blackout-diagnose/`](../scripts/blackout-diagnose/) |
| `blender-overlap-difference` | 让两个互相穿插的网格体「**物理上不重叠**」——**面级剔除**替代布尔差集（只删目标件伸进刀具体的面，刀具体分毫不动）；含动刀前分类着色预览、三票制内外判定、布尔干跑评估、还原点与 `__BAK__` 撤回、独立核验 | 暂无独立文档，脚本包随 skill 自带 `scripts/`（`cull_overlap.py` / `probe_overlap.py` / `render_classify.py` / `restore_from_backup.py`） |
| `blender-procedural-emission-material` | **世界空间程序化噪波滚动发光材质** + 全套数字控件：不用 UV，标准链 `纹理坐标→Mapping(滚)→噪波4D→ColorRamp(对比度)→×强度→Emission`；含 SINGLE_PROP 驱动、**看门狗定时器**自动刷新、AREA 面光灯节点树同构接入与依赖环铁律 | [渐变发光滚动材质](../docs/渐变发光滚动材质.md) / [材质参数统一控制器与实时面板](../docs/材质参数统一控制器与实时面板.md)（其 §3 刷新结论不完整，见本 skill §6） |
| `blender-plane-procedural-material` | **平面（flat plane）专项**：法线轴零跨度导致的坐标退化、**平面 = 3D 噪声体的一片切片**、把平面当**验收测试卡**出客观读数（暗区占比 / 滚动方向 / 位移的像素级测法） | 母 skill `blender-procedural-emission-material` |
| `blender-radial-pulse-material` | **世界空间径向距离场发光材质**：图案只依赖到**共享中心的距离 r**（和方向 d）⇒ 共心的 XY/XZ/YZ 平面切过去天然同心、交线连续；含五种模式、**四段循环脉冲**（`TVAL≡帧号` 关键帧技巧 + 周期/相位分离：时长类参数只进周期就是空操作）、**空物体自定义属性 + SINGLE_PROP 驱动器**（数据驱动，不写面板）；附 Math 第 3 输入口 / 未连输入默认 0.5 / 接触表行序三个静默陷阱 | 母 skill `blender-procedural-emission-material` |
| `blender-inward-pulse-material` | **径向内收多脉冲**：若干同心亮环从外往内收、无缝循环；核心是**环数恒定的有效窗口公式**（`L + 占空比 − 软边 − 2×最小可见宽度 ≈ N`，缺一项环数就会在 N±1 间跳）与**计数基准的选择**（内切圆 vs 角点，相差 √2）；含亮面裁切把发光限制在圆内、从姊妹材质读 ColorRamp 复制配色、**驱动只能挂 Value 节点**的守卫 | [径向内收多脉冲材质](../docs/径向内收多脉冲材质.md) / [`../scripts/radial-inward-pulse/`](../scripts/radial-inward-pulse/) |

八者是**分层**关系：`blender-bridge-ops` 管「怎么把代码送进正在运行的 Blender」，
其余七个各管一件事：`blender-scene-cleanup` 清理、`blender-render-blackout-diagnose` 查画面不对、
`blender-overlap-difference` 去重叠、`blender-procedural-emission-material` 做程序化发光材质与控件、
`blender-plane-procedural-material` 用平面验收材质、`blender-radial-pulse-material` 做径向距离场脉冲材质、
`blender-inward-pulse-material` 做径向**内收多脉冲**材质（环数恒定的约束解算）。
后三者**母 skill 均为 `blender-procedural-emission-material`**（通用机制在那边）；
各 skill 开头均引用 `blender-bridge-ops`。

## 安装

拷到用户级 skill 目录（Windows）：

```powershell
$dst = "$env:USERPROFILE\.workbuddy\skills"
Copy-Item .\blender-bridge-ops    $dst -Recurse -Force
Copy-Item .\blender-scene-cleanup $dst -Recurse -Force
Copy-Item .\blender-render-blackout-diagnose $dst -Recurse -Force
Copy-Item .\blender-overlap-difference $dst -Recurse -Force
Copy-Item .\blender-procedural-emission-material $dst -Recurse -Force
Copy-Item .\blender-plane-procedural-material $dst -Recurse -Force
Copy-Item .\blender-radial-pulse-material $dst -Recurse -Force
Copy-Item .\blender-inward-pulse-material $dst -Recurse -Force
```

拷完目录结构应为：

```
~/.workbuddy/skills/
├── blender-bridge-ops/SKILL.md
├── blender-scene-cleanup/
│   ├── SKILL.md
│   └── scripts/{purge_empties.py, verify_purge.py, snapshot_baseline.py}
├── blender-render-blackout-diagnose/
│   ├── SKILL.md
│   └── scripts/diagnose_blackout.py
├── blender-overlap-difference/
│   ├── SKILL.md
│   └── scripts/{cull_overlap.py, probe_overlap.py, render_classify.py, restore_from_backup.py}
├── blender-procedural-emission-material/
│   ├── SKILL.md
│   └── scripts/{build_noise_scroll.py, verify_noise_scroll.py, verify_lights.py, restore_lights.py, ...}
├── blender-plane-procedural-material/
│   ├── SKILL.md
│   └── scripts/{plane_testcard.py, probe_plane.py, probe_threshold_e2e.py, ...}
└── blender-radial-pulse-material/
    ├── SKILL.md
    └── scripts/{radial_field.py, cycle_pulse.py, verify_field.py, self_test.py, shoot_modes.py}
└── blender-inward-pulse-material/
    ├── SKILL.md                  # 脚本包在 ../scripts/radial-inward-pulse/(与本目录不重复)
    └── (无自带 scripts —— 引用 ../scripts/radial-inward-pulse/)
```

> 跑 `scripts/` 里的脚本前记得改顶部的 `OUT_DIR`（报告 / 名单 / 基线都写那里），同一 skill 下的脚本要一致。
> 后三个 skill 的脚本**只随 skill 自带**（`../scripts/` 下暂无对应脚本包），暂不需要两处同步。
