# -*- coding: utf-8 -*-
"""
按材质合并网格体 —— 执行脚本 v2（大组加固）

把工程里成千上万个零碎网格，按「材质组合（+ 父级）」相同的原则合并成极少数几个对象，
解决 *对象太多导致 GUI 卡顿* 的根因。典型场景：SketchUp / CAD 导入后的工程。

运行位置（**不是**桥 send.py，是系统命令行）：
    blender.exe --background --factory-startup "<源.blend>" ^
                --python merge_by_material.py -- "<输出.blend>" [--limit N] [要排除的对象名...]

v1 → v2 的四项加固（全部实测踩过，详见 docs/按材质合并为单个网格体.md）：
  ① 两级 join      一次性 join 两千多个对象会 Calloc 整数溢出而崩溃（申请 ~28 GB）
  ② 网格独立化     共享 mesh 数据块 + 多段 join ⇒ 几何被重复计入（该组 1365 → 16597 顶点）
  ③ 风险组判定     跨集合 / 不在视图层 / hide_viewport / 修改器不一致 ⇒ 整组跳过
  ④ 世界包围盒校验 逐顶点精确口径（不能用 bound_box，它是松上界，两侧不等价，必误报）

策略：组内对象数 ≤ ONESHOT_MAX_OBJS 走 v1 的快路径（temp_override 一次性 join，
      **不展开实例**，共享网格在 join 后变孤儿、存盘丢弃，文件不膨胀）；
      超过则先做网格独立化、再两级 join（会展开实例、文件变大，但不会崩）。

参数：
    <输出.blend>        必须有。一律另存，绝不覆盖源文件（脚本内有安全闸）。
    --limit N           只处理前 N 组（按对象数降序），用于先试跑。
    [要排除的对象名...] 可选。会与 <cwd>/exclude.txt 里的名单合并。

输出：
    <cwd>/merge_run.log        实时日志（长任务后台跑时可持续 tail）
    <cwd>/merge_result.json    机器可读结果（前后计数 / 每组偏差 / 跳过清单）
    <cwd>/merge_names.txt      人读名单（哪些合成哪些）
"""

import bpy, collections, time, os, re, sys, json, traceback
import numpy as np

# ==================== 配置项 ====================
# 日志 / 报告落盘位置（默认当前工作目录）
HERE = os.getcwd()
LOG = os.environ.get("MBM_LOG", os.path.join(HERE, "merge_run.log"))
# 排除名单文件：一行一个对象名，# 开头为注释
EXCLUDE_FILE = os.path.join(HERE, "exclude.txt")
# 合并后对象名前缀（取该组第一个材质名）
NAME_PREFIX = "M_"
# 空物体是否清理：SketchUp 组件层级在合并后就失去意义了，默认清掉
PURGE_EMPTY = True

# ---- v2 新增 ----
# 分组键是否含「父级」。True（默认）= 实测口径，保住装置归属，合并后挂回原父级；
# 代价是组数变多、合并后对象数变多（更保守）。False = v1 行为（只按材质+UV）。
GROUP_BY_PARENT = True
# 多材质槽对象是否跳过。False（默认）= v1 行为，按「完整材质列表」分组，多材质槽也能合并；
# True = 用户口径（「一个网格体有多个材质就不参与合并」）。两种都正确，差别在取舍。
SKIP_MULTI_SLOT = False
# 风险组判定：跨集合 / 有成员不在视图层 / hide_viewport / 修改器配置不一致 ⇒ 整组跳过。
SKIP_RISKY = True
# 组内对象数 ≤ 此值走一次性 join（快路径）；超过则独立化 + 两级 join。
ONESHOT_MAX_OBJS = 400
# 两级 join 的单块对象数上限（越大越省调用次数，越接近一次性 join 的溢出风险）
MAX_BATCH_OBJS = 120
# 世界包围盒容差
TOL = 1e-3
# ================================================

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.splitext(bpy.data.filepath)[0] + "_合并.blend"

# ---- 安全闸：绝不覆盖源文件 ----
_src = os.path.normpath(os.path.abspath(bpy.data.filepath or ""))
_out = os.path.normpath(os.path.abspath(OUT))
if _src and _src == _out:
    raise SystemExit("[SAFETY] 输出路径等于源文件，拒绝覆盖。请换个文件名。")

t0 = time.time()

# 实时日志：每行既落盘又 flush 到 stdout。stdout 重定向到文件时是块缓冲，
# 进程崩掉就什么都看不到 —— 所以两边都要写。
PROG = open(LOG, "w", encoding="utf-8", buffering=1)
LOGLINES = []


def P(*a):
    s = " ".join(str(x) for x in a)
    line = "[%7.1fs] %s" % (time.time() - t0, s)
    LOGLINES.append(line)
    try:
        PROG.write(line + "\n")
    except Exception:
        pass
    try:
        print("==" + s, flush=True)
    except Exception:
        pass


P("SRC", bpy.data.filepath)
P("OUT", OUT)
P("BLENDER", bpy.app.version_string)

# ---- 排除名单：文件 + 命令行附加 ----
LIMIT = 0
cli_extra = []
i = 1
while i < len(argv):
    if argv[i] == "--limit" and i + 1 < len(argv):
        try:
            LIMIT = int(argv[i + 1])
        except ValueError:
            LIMIT = 0
        i += 2
        continue
    cli_extra.append(argv[i])
    i += 1

EXCLUDE = set()
if os.path.isfile(EXCLUDE_FILE):
    with open(EXCLUDE_FILE, encoding="utf-8") as f:
        for line in f:
            n = line.strip()
            if n and not n.startswith("#"):
                EXCLUDE.add(n)
EXCLUDE.update(a for a in cli_extra if a and not a.endswith(".blend"))
P("EXCLUDE_LIST", sorted(EXCLUDE) if EXCLUDE else "(空)")
P("GROUP_BY_PARENT", GROUP_BY_PARENT, "| SKIP_MULTI_SLOT", SKIP_MULTI_SLOT,
  "| SKIP_RISKY", SKIP_RISKY, "| ONESHOT_MAX_OBJS", ONESHOT_MAX_OBJS)
if LIMIT:
    P("★ 限流模式：只处理前 %d 组（按对象数降序）" % LIMIT)

SMOOTH_RE = re.compile(r"按角度平滑|Smooth by Angle")


def has_smooth(o):
    try:
        return any(SMOOTH_RE.search(m.name) for m in o.modifiers)
    except Exception:
        return False


def mod_sig(o):
    try:
        return tuple(sorted(m.name for m in o.modifiers))
    except Exception:
        return ()


def wbb(objs_):
    """逐顶点世界空间包围盒（min xyz + max xyz）。

    ★ 必须逐顶点算，不能用 obj.bound_box —— 后者是「物体局部包围盒再变换」，
    是松上界，与合并后的口径不等价，必然误报偏差。
    """
    lo = [1e30] * 3
    hi = [-1e30] * 3
    for o in objs_:
        me = o.data
        if me is None:
            continue
        n = len(me.vertices)
        if n == 0:
            continue
        co = np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        q = co.reshape(n, 3).astype(np.float64)
        M = np.array(o.matrix_world, dtype=np.float64)
        w = q @ M[:3, :3].T + M[:3, 3]
        for k in range(3):
            lo[k] = min(lo[k], float(w[:, k].min()))
            hi[k] = max(hi[k], float(w[:, k].max()))
    return lo + hi


def totals():
    v = p = 0
    for o in bpy.data.objects:
        if o.type == "MESH" and o.data:
            v += len(o.data.vertices)
            p += len(o.data.polygons)
    return v, p


def counts():
    objs = list(bpy.data.objects)
    return {
        "objects": len(objs),
        "mesh_objs": sum(1 for o in objs if o.type == "MESH"),
        "empties": sum(1 for o in objs if o.type == "EMPTY"),
        "materials": len(bpy.data.materials),
        # ★ 存盘时 Blender 会 prune 掉 users==0 的孤儿数据块（旧工程里很常见），
        #   所以复核口径必须是「被引用的数量」，不能用总数，否则必然误报「丢了材质」。
        "materials_used": sum(1 for m in bpy.data.materials if m.users > 0),
        "images": len(bpy.data.images),
        "images_used": sum(1 for i in bpy.data.images if i.users > 0),
        "collections": len(bpy.data.collections),
    }


all_meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.data]
meshes = [o for o in all_meshes if o.name not in EXCLUDE]
excluded = [o for o in all_meshes if o.name in EXCLUDE]

# 名单里的名字在工程中不存在 → 告警（多半是手抖写错，静默跳过会埋雷）
missing = sorted(EXCLUDE - {o.name for o in all_meshes})
if missing:
    P("!! 排除名单里有工程中不存在的对象:", missing)

for o in excluded:
    P("EXCLUDED", o.name, "| 顶点", len(o.data.vertices), "| 面", len(o.data.polygons),
      "| 材质", [m.name if m else None for m in o.data.materials])

v0, p0 = totals()
bc = counts()
P("BEFORE | 网格对象", len(all_meshes), "→ 参与合并", len(meshes), "| 排除", len(excluded),
  "| 顶点", v0, "| 面", p0, "| 空物体", bc["empties"])

# ---- 1. 分组 ----
# key 带 UV 层名：把带 UV 的和不带 UV 的并进同一组，UV 会被拉平丢失。
# key 带父级（GROUP_BY_PARENT）：导入工程的「同类件」往往按装置分组（实测 83 个铜件
# 分布在 19 个父级下），不带父级会导致装置归属彻底消失、且合并后无处挂回。
groups = collections.defaultdict(list)
skipped_multi = 0
skipped_none = 0
for o in meshes:
    me = o.data
    mats = list(me.materials)
    if SKIP_MULTI_SLOT and len(mats) > 1:
        skipped_multi += 1
        continue
    if len(mats) == 0 or all(m is None for m in mats):
        skipped_none += 1
        continue
    key = (tuple(m.name if m else "<空>" for m in mats),
           tuple(l.name for l in me.uv_layers))
    if GROUP_BY_PARENT:
        key = key + (o.parent.name if o.parent else None,)
    groups[key].append(o)

P("GROUP_COUNT", len(groups),
  "| 跳过：多材质槽", skipped_multi, "/ 无材质", skipped_none)
multi_slot_total = sum(1 for o in meshes if len(o.data.materials) > 1)
if not SKIP_MULTI_SLOT and multi_slot_total:
    P("  注：多材质槽对象 %d 个，当前按「完整材质列表」分组参与合并"
      "（要按用户口径跳过，把 SKIP_MULTI_SLOT 设为 True）" % multi_slot_total)

cand = {k: v for k, v in groups.items() if len(v) > 1}
P("可合并组数", len(cand), "| 覆盖对象", sum(len(v) for v in cand.values()),
  "| 单件组（收益 0，不参与）", sum(1 for v in groups.values() if len(v) == 1))

# ---- 2. 风险组判定 ----
skipped = {}
if SKIP_RISKY:
    vl_names = set(o.name for o in bpy.context.view_layer.objects)   # ★ 先物化，O(n) 一次
    P("视图层对象", len(vl_names), "| 场景对象", len(bpy.data.objects))
    for k, g in cand.items():
        issues = []
        cols = sorted({c.name for o in g for c in o.users_collection})
        if len(cols) > 1:
            issues.append("跨集合:%s" % cols[:3])
        hidden = [o.name for o in g if o.name not in vl_names]
        if hidden:
            issues.append("不在视图层:%s" % hidden[0])
        hv = [o.name for o in g if o.hide_viewport]
        if hv:
            issues.append("hide_viewport:%s" % hv[0])
        sigs = {mod_sig(o) for o in g}
        if len(sigs) > 1 and not all(has_smooth(o) for o in g):
            issues.append("修改器配置不一致:%d 种" % len(sigs))
        if issues:
            skipped[k] = issues
    P("风险判定：硬跳过", len(skipped), "组 /", sum(len(cand[k]) for k in skipped), "个对象")
    cnt = collections.Counter()
    for v in skipped.values():
        for x in v:
            cnt[x.split(":")[0]] += 1
    for a, b in cnt.most_common():
        P("      - %-22s %d 组" % (a, b))

todo = [k for k in cand if k not in skipped]
todo.sort(key=lambda x: -len(cand[x]))
if LIMIT:
    todo = todo[:LIMIT]

# ---- 3. 基线（逐组世界包围盒）----
before_bb = {k: wbb(cand[k]) for k in todo}
expected_drop = sum(len(cand[k]) - 1 for k in todo)
n_two = sum(1 for k in todo if len(cand[k]) > ONESHOT_MAX_OBJS)
P("EXEC_PLAN | 执行组数", len(todo), "| 需两级 join 的组", n_two,
  "| 预计减少对象", expected_drop)
P("TOP10 大组：")
for k in sorted(todo, key=lambda x: -len(cand[x]))[:10]:
    P("      %-38s 父级 %-18s %5d 对象  %9d 顶点"
      % (str(k[0])[:38], str(k[-1] if GROUP_BY_PARENT else "-")[:18],
         len(cand[k]), sum(len(o.data.vertices) for o in cand[k])))

# ---- 4. 逐组合并 ----
name_map = {}
failed = []
ok_n = 0
bpy.ops.object.select_all(action="DESELECT")
for gi, k in enumerate(todo):
    g = list(cand[k])
    parent_name = k[-1] if GROUP_BY_PARENT else None
    A = next((o for o in g if has_smooth(o)), max(g, key=lambda o: len(o.modifiers)))
    A = A if A in g else g[0]
    P(">>> [%d/%d] %s @ %s  对象 %d  顶点 %d"
      % (gi + 1, len(todo), str(k[0])[:44], parent_name or "<无父级>",
         len(g), sum(len(o.data.vertices) for o in g)))
    try:
        b0 = before_bb[k]
        world = {o.name: o.matrix_world.copy() for o in g}

        # ① 摘父级：把世界变换烧进对象自身（保住世界位置），只 update 一次
        for o in g:
            if o.parent is not None:
                o.parent = None
                o.matrix_world = world[o.name]
        bpy.context.view_layer.update()

        if len(g) > ONESHOT_MAX_OBJS:
            # ②a 大组路径 —— 网格数据独立化 + 两级 join
            # ★ 独立化是必需的：组内 136 个对象共享同一 mesh 数据块时，任何「多段 join」
            #   都会把该 mesh 在**整个工程里**的全部实例几何重复计入
            #   （137 组本该 1365 顶点，分段后变 15637，偏差 1.69）。独立化后 1365 ✅
            ndup = 0
            for o in g:
                if o.data.users > 1:
                    o.data = o.data.copy()
                    ndup += 1
            if ndup:
                P("     独立化网格 %d 个" % ndup)
            order = [A] + [o for o in g if o is not A]
            chunks = [order[j:j + MAX_BATCH_OBJS]
                      for j in range(0, len(order), MAX_BATCH_OBJS)]
            bpy.ops.object.select_all(action="DESELECT")
            prev = []
            inter = []
            for ch in chunks:
                for o in prev:
                    try:
                        o.select_set(False)
                    except Exception:
                        pass
                prev = list(ch)
                for o in ch:
                    o.select_set(True)
                bpy.context.view_layer.objects.active = ch[0]
                bpy.ops.object.join()
                M = bpy.context.view_layer.objects.active
                inter.append(M)
                prev = [M]
            if len(inter) > 1:
                for o in prev:
                    try:
                        o.select_set(False)
                    except Exception:
                        pass
                for o in inter:
                    o.select_set(True)
                bpy.context.view_layer.objects.active = inter[0]
                bpy.ops.object.join()
            result = bpy.context.view_layer.objects.active
            bpy.ops.object.select_all(action="DESELECT")
            P("     两级 join：%d 块 → 1（%d 次 join 调用）"
              % (len(chunks), len(chunks) + (1 if len(inter) > 1 else 0)))
        else:
            # ②b 快路径 —— temp_override 一次性 join，不碰全局选中、不展开实例
            with bpy.context.temp_override(selected_editable_objects=g, active_object=A):
                bpy.ops.object.join()
            result = A

        # ③ 挂回原父级（恢复世界矩阵）
        if parent_name:
            par = bpy.data.objects.get(parent_name)
            if par is not None:
                result.parent = par
                result.matrix_world = world[A.name]
        bpy.context.view_layer.update()

        # ④ 世界包围盒校验
        b1 = wbb([result])
        dev = max(abs(b0[j] - b1[j]) for j in range(6))
        good = dev <= TOL

        base = k[0][0] if k[0] else "无材质"
        nm = (NAME_PREFIX + base)[:55]
        n, c = nm, 1
        while n in bpy.data.objects:
            n = nm + ".%03d" % c
            c += 1
        result.name = n

        name_map["%s @ %s" % (k[0], parent_name or "<无父级>")] = {
            "merged_into": n, "n_from": len(g), "dev": dev, "ok": good,
            "parent": parent_name, "verts": len(result.data.vertices),
            "faces": len(result.data.polygons),
            "from": [o for o in world.keys()],
            "active_src": A.name,
            "before_wbb": b0, "after_wbb": b1,
        }
        if not good:
            failed.append(n)
            P("     !! 偏差 %.6f > 容差 %.3f  %s" % (dev, TOL, n))
        else:
            ok_n += 1
            P("     OK  %d→1  偏差 %.6f  顶点 %d  面 %d  →  %s"
              % (len(g), dev, len(result.data.vertices),
                 len(result.data.polygons), n))
    except Exception:
        failed.append("%s @ %s" % (k[0], parent_name))
        P("     !! 失败:", traceback.format_exc().splitlines()[-1])
    if (gi + 1) % 20 == 0:
        P("  …… 进度 %d/%d  已用时 %.0f 秒" % (gi + 1, len(todo), time.time() - t0))

P("MERGE_OK", ok_n, "| FAILED", len(failed))

# ---- 5. 清理空物体（迭代到稳定，而不是只删一轮「当前无子级」的）----
removed = 0
if PURGE_EMPTY:
    for _ in range(30):
        dead = [o for o in bpy.data.objects
                if o.type == "EMPTY" and not o.children and not o.children_recursive]
        if not dead:
            break
        for o in dead:
            bpy.data.objects.remove(o, do_unlink=True)
        removed += len(dead)
P("EMPTIES_REMOVED", removed)

# ---- 6. 几何守恒校验（独立重算总数，不依赖分组统计）----
v1, p1 = totals()
ac = counts()
P("AFTER | 网格对象", ac["mesh_objs"], "| 顶点", v1, "| 面", p1, "| 空物体", ac["empties"])
P("CHECK_VERTS", "一致" if v0 == v1 else "!! 不一致 %d -> %d" % (v0, v1))
P("CHECK_POLYS", "一致" if p0 == p1 else "!! 不一致 %d -> %d" % (p0, p1))
# 非 EMPTY 对象数：合并把 expected_drop 个 MESH 并进了存活对象
ne_b = bc["objects"] - bc["empties"]
ne_a = ac["objects"] - ac["empties"]
ne_exp = ne_b - expected_drop
P("CHECK_NONEMPTY_OBJS", "一致" if ne_a == ne_exp else
  "!! 期望 %d 实际 %d" % (ne_exp, ne_a))
dmesh = bc["mesh_objs"] - ac["mesh_objs"]
P("CHECK_MESH_DROP", "一致" if dmesh == expected_drop else
  "!! 期望减少 %d 实际减少 %d" % (expected_drop, dmesh))
for tag in ("materials", "images"):
    P("CHECK_%s" % tag.upper(), "一致" if bc[tag] == ac[tag] else
      "!! %d -> %d" % (bc[tag], ac[tag]))

devs = [x["dev"] for x in name_map.values()]
maxdev = max(devs) if devs else 0.0
P("MAX_WBB_DEV", "%.6f" % maxdev, "| 容差 %.3f" % TOL,
  "| 超差组", len(failed))

# ---- 7. 另存 ----
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
P("SAVING...")
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=True,
                            check_existing=False, copy=False)
P("SAVED", OUT, "%.1f MB" % (os.path.getsize(OUT) / 1024 / 1024))

# ---- 8. 结果落盘 ----
res = {
    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    "src": bpy.data.filepath, "out": OUT,
    "blender": bpy.app.version_string,
    "config": {"GROUP_BY_PARENT": GROUP_BY_PARENT, "SKIP_MULTI_SLOT": SKIP_MULTI_SLOT,
               "SKIP_RISKY": SKIP_RISKY, "ONESHOT_MAX_OBJS": ONESHOT_MAX_OBJS,
               "MAX_BATCH_OBJS": MAX_BATCH_OBJS, "TOL": TOL},
    "before_counts": bc, "after_counts": ac,
    "before_totals": {"verts": v0, "polys": p0},
    "after_totals": {"verts": v1, "polys": p1},
    "expected_object_drop": expected_drop,
    "groups_candidates": len(cand), "groups_skipped": len(skipped),
    "groups_done": len(name_map), "groups_failed": failed,
    "max_wbb_dev": maxdev, "tolerance": TOL,
    "skipped_detail": ["%s @ %s  (%d 个: %s)"
                       % (str(k[0]), k[-1] if GROUP_BY_PARENT else "-",
                          len(cand[k]), "; ".join(skipped[k])[:200])
                       for k in sorted(skipped, key=lambda x: -len(cand[x]))],
    "name_map": name_map,
}
with open(os.path.join(HERE, "merge_result.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)

with open(os.path.join(HERE, "merge_names.txt"), "w", encoding="utf-8", newline="\n") as f:
    f.write("按材质合并名单  共 %d 组（材质 @ 父级 → 存活对象）\n%s\n\n"
            % (len(name_map), "=" * 70))
    for k, x in sorted(name_map.items(), key=lambda kv: -kv[1]["n_from"]):
        f.write("%s\n  → %s   （%d 个合成 1 个，偏差 %.6f，顶点 %d）\n\n"
                % (k, x["merged_into"], x["n_from"], x["dev"], x["verts"]))
    f.write("\n%s\n跳过的组（保持原样）\n%s\n\n" % ("=" * 70, "=" * 70))
    for s in res["skipped_detail"]:
        f.write("  %s\n" % s)
P("RESULT", os.path.join(HERE, "merge_result.json"))
P("ELAPSED", "%.1f 秒" % (time.time() - t0))
P("DONE")
