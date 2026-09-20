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
| `blender-driver-param-maintenance` | **参数化驱动系统的运维改造**（已建成系统的维护，不是新建）：① `refs` 引用体检 —— 谁在读这个参数（扫描**必须含 `物体数据 → node_tree`**，灯光 Shader Nodetree 层漏扫会双向出事：误判"假控件" / 改名后驱动静默失效）；② `health` 失效体检 —— 全库 `is_valid=False` + 悬空引用，判据 0 条；③ 关键帧 → 常量的存档纪律；④ 改名换轴六步顺序（驱动重建完才删旧键） | [驱动参数化材质维护](../docs/驱动参数化材质维护.md) / [`../scripts/driver-param-maintenance/`](../scripts/driver-param-maintenance/) |
| `blender-cylinder-spiral-material` | **圆柱面螺旋斜条纹发光材质**（滚筒）：斜纹 = 柱面坐标相位取模 `f = u×K − v×N` + `FLOORED_MODULO`；波形走 **Math 域**（`MapRange(SMOOTHSTEP)×2 + MINIMUM`），**不让 ColorRamp 兼职**（后者会参数耦合 / 色标被驱动锁死 / 拖尾被结构卡在 58%）；ColorRamp 零驱动只管颜色。**两套并列调参方案**（按条数 / 按角度，跑哪个装哪个，避免留幽灵参数）；端盖按**法线**单独分槽（否则条纹摊成扇形风车）；**方向以实测标定**（纸面推导曾推反） | [滚筒斜纹材质](../docs/滚筒斜纹材质.md) / [`../scripts/streak-material/`](../scripts/streak-material/) |
| `blender-loop-keyframe-anim` | **给自定义属性批量写「循环三角波关键帧动画」**：一个完整周期进 fcurve + CYCLES 循环修饰器铺满帧范围，贝塞尔自然缓入缓出；含 Slotted Action 正确写入路径、5.x 无 mode 属性、`is_valid=False` 判空、depsgraph 读被驱动值、关键帧值精确写入（绕开属性当前值被驱动干扰） | 传输层 `blender-bridge-ops`；[技巧速查 §3/§4/§5](../docs/技巧速查.md) |

十者是**分层**关系：`blender-bridge-ops` 管「怎么把代码送进正在运行的 Blender」，
其余九个各管一件事：`blender-scene-cleanup` 清理、`blender-render-blackout-diagnose` 查画面不对、
`blender-overlap-difference` 去重叠、`blender-procedural-emission-material` 做程序化发光材质与控件、
`blender-plane-procedural-material` 用平面验收材质、`blender-radial-pulse-material` 做径向距离场脉冲材质、
`blender-inward-pulse-material` 做径向**内收多脉冲**材质（环数恒定的约束解算）、
`blender-driver-param-maintenance` 给**已建成**的参数化系统做维护（引用体检 / 关键帧收敛 / 改名换轴）、
`blender-loop-keyframe-anim` 给自定义属性批量写**循环三角波关键帧动画**（Slotted Action + CYCLES）。
后四者**母 skill 均为 `blender-procedural-emission-material`**（通用机制在那边）；
`blender-driver-param-maintenance` 与之并列，管的是同一套系统的**运维**而非新建；
`blender-loop-keyframe-anim` 是**动画写入类**（继承 bridge 传输层，管关键帧而非材质）；
各 skill 开头均引用 `blender-bridge-ops`。

## 安装

⚠️ **只拷 `skills/` 会留下断链** —— 多数 SKILL.md 用 `../scripts/<包>/` 与 `../docs/<文>.md` 引用同级目录，
所以必须**连同 `scripts/` 与 `docs/` 一起**拷到同一个父目录下（相对路径才成立）。

拷到用户级 skill 目录（Windows，三件套一起拷）：

```powershell
$dst = "$env:USERPROFILE\.workbuddy\skills"
# 1) 10 个技能本体
Copy-Item .\skills\* $dst -Recurse -Force
# 2) 共享脚本包 —— 供 SKILL.md 里的 ../scripts/<包>/ 解析
Copy-Item .\scripts   $dst -Recurse -Force
# 3) 配套文档 —— 供 SKILL.md 里的 ../docs/<文>.md 解析
Copy-Item .\docs      $dst -Recurse -Force
```

装完**务必跑一次断链校验**（下面的脚本会把每个带路径的引用逐一解析）：

```bash
python - <<'PY'
import os, re
SK = os.path.expanduser("~/.workbuddy/skills")
ref = re.compile(r'((?:\.\./)*[A-Za-z0-9_\u4e00-\u9fff-]+(?:/[A-Za-z0-9_\u4e00-\u9fff.-]+)+\.(?:py|md))')
bad = 0
for d in sorted(os.listdir(SK)):
    p = os.path.join(SK, d, "SKILL.md")
    if not os.path.isfile(p): continue
    for r in sorted(set(ref.findall(open(p, encoding="utf-8").read()))):
        if r.startswith("http") or r.startswith("_bridge/"): continue
        if not (os.path.exists(os.path.normpath(os.path.join(os.path.dirname(p), r)))
                or os.path.exists(os.path.normpath(os.path.join(SK, r)))):
            print("MISS", d, "->", r); bad += 1
print("断链:", bad)
PY
```

判据：**断链 = 0**。非 0 说明漏拷了 `scripts/` 或 `docs/`，或 SKILL.md 里的相对层级写错（见下）。

> **相对层级约定（易错）**：从 `skills/<名>/` 出发，正确写法是 **`../scripts/`** 与 **`../docs/`**（一级）。
> 写成 `../../scripts/`（两级）会落到安装根之外，静默断链 —— 本文件早期版本与
> `blender-driver-param-maintenance` / `blender-inward-pulse-material` 两个 SKILL.md 都踩过，已于 2026-09-20 修正。


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
└── blender-driver-param-maintenance/
    ├── SKILL.md                  # 脚本包在 ../scripts/driver-param-maintenance/(与本目录不重复)
    └── (无自带 scripts —— 引用 ../scripts/driver-param-maintenance/)
└── blender-loop-keyframe-anim/
    ├── SKILL.md
    └── scripts/{write_loop_anim.py, verify_loop_anim.py}
```

> 跑 `scripts/` 里的脚本前记得改顶部的 `OUT_DIR`（报告 / 名单 / 基线都写那里），同一 skill 下的脚本要一致。
> 脚本位置有两种约定（**不要混用**）：① **自带** `skills/<名>/scripts/`（如 plane / radius-pulse）；
> ② **引用** `../scripts/<名>/`、skill 目录下不放副本（如 `blender-inward-pulse-material` 与
> `blender-driver-param-maintenance`）—— 后者的脚本**只维护一份**，无需两处同步。
