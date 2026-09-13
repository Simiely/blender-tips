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

三者是**分层**关系：`blender-bridge-ops` 管「怎么把代码送进正在运行的 Blender」，
`blender-scene-cleanup` 管「清理这件事怎么做」、`blender-render-blackout-diagnose` 管「画面不对怎么查」，
后两者开头即引用前者。

## 安装

拷到用户级 skill 目录（Windows）：

```powershell
$dst = "$env:USERPROFILE\.workbuddy\skills"
Copy-Item .\blender-bridge-ops    $dst -Recurse -Force
Copy-Item .\blender-scene-cleanup $dst -Recurse -Force
Copy-Item .\blender-render-blackout-diagnose $dst -Recurse -Force
```

拷完目录结构应为：

```
~/.workbuddy/skills/
├── blender-bridge-ops/SKILL.md
├── blender-scene-cleanup/
│   ├── SKILL.md
│   └── scripts/{purge_empties.py, verify_purge.py, snapshot_baseline.py}
└── blender-render-blackout-diagnose/
    ├── SKILL.md
    └── scripts/diagnose_blackout.py
```

> 跑 `scripts/` 里的脚本前记得改顶部的 `OUT_DIR`（报告 / 名单 / 基线都写那里），三个脚本要一致。
