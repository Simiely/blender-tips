# -*- coding: utf-8 -*-
"""
按材质合并 —— 复核脚本（**必须另开一次 Blender 进程**）

在合并进程里打的 CHECK_VERTS / CHECK_POLYS 只能证明「内存里的数据对得上」，
**不能证明存出去的文件还能打开**。所以必须重开一次 Blender 加载产物做复核。

v2 起默认**零配置**：直接读 merge_by_material.py 落盘的 merge_result.json 逐组核对。
（读不到 JSON 时退化为通用检查，仍会算总数与收敛性，只是不逐组比。）

运行位置（系统命令行，只读）：
    blender.exe --background --factory-startup "<合并后.blend>" --python verify_merge.py
    # 可选 --json <路径>   指定 merge_result.json（默认 <cwd>/merge_result.json）
    # 可选 --tol 0.001     世界包围盒容差

判据（全部 OK 才算通过）：
    ① 逐组：存活对象在 / 顶点面数一致 / 父级一致 / 世界包围盒偏差 ≤ tol
    ② 被合并掉的原始对象名：一个都不该还在
    ③ 顶点总数、面总数与源文件一致（**独立重算**，不引用分组统计）
    ④ EMPTY 收敛（无子级的 EMPTY = 0）/ 悬空约束 = 0 / 游离对象 = 0
    ⑤ 材质与图片未丢
"""

import bpy, os, sys, json
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
HERE = os.getcwd()
JSONP = os.path.join(HERE, "merge_result.json")
TOL = 1e-3
j = 0
while j < len(argv):
    if argv[j] == "--json" and j + 1 < len(argv):
        JSONP = argv[j + 1]
        j += 2
        continue
    if argv[j] == "--tol" and j + 1 < len(argv):
        TOL = float(argv[j + 1])
        j += 2
        continue
    j += 1

ok = True
FAILLOG = []


def check(label, cond, detail=""):
    global ok
    print("==CHECK_%s==" % label, "OK" if cond else "FAIL " + str(detail))
    if not cond:
        ok = False
        FAILLOG.append("%s %s" % (label, detail))


def wbb(objs_):
    """逐顶点世界空间包围盒（与合并脚本同口径；不要用 bound_box）"""
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


# ---------- 通用统计 ----------
meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.data]
v = sum(len(o.data.vertices) for o in meshes)
p = sum(len(o.data.polygons) for o in meshes)
print("==FILE==", bpy.data.filepath)
print("==BLENDER==", bpy.app.version_string)
print("==MESH_OBJECTS==", len(meshes))
print("==VERTS==", v)
print("==POLYS==", p)
print("==MATERIALS==", len(bpy.data.materials))
print("==IMAGES==", len(bpy.data.images))
print("==EMPTY==", len([o for o in bpy.data.objects if o.type == "EMPTY"]))
print("==JSON==", JSONP if os.path.isfile(JSONP) else "(未找到，只做通用检查)")

# ---------- 读合并报告 ----------
R = None
if os.path.isfile(JSONP):
    with open(JSONP, encoding="utf-8") as f:
        R = json.load(f)

if R is not None:
    bt = R.get("before_totals") or {}
    at = R.get("after_totals") or {}
    if bt.get("verts"):
        check("VERTS_VS_BASELINE", v == bt["verts"], "%d -> %d" % (bt["verts"], v))
    if bt.get("polys"):
        check("POLYS_VS_BASELINE", p == bt["polys"], "%d -> %d" % (bt["polys"], p))

    # ① 逐组核对
    nm = R.get("name_map") or {}
    bad_bb, bad_vf, bad_par, lost, resurrect = [], [], [], [], []
    maxdev = 0.0
    for key, x in nm.items():
        o = bpy.data.objects.get(x["merged_into"])
        if o is None or o.type != "MESH":
            lost.append(x["merged_into"])
            continue
        if len(o.data.vertices) != x["verts"] or len(o.data.polygons) != x["faces"]:
            bad_vf.append("%s (%d/%d vs %d/%d)"
                          % (x["merged_into"], len(o.data.vertices), len(o.data.polygons),
                             x["verts"], x["faces"]))
        got_par = o.parent.name if o.parent else None
        if got_par != x.get("parent"):
            bad_par.append("%s: %s -> %s" % (x["merged_into"], x.get("parent"), got_par))
        b0 = x.get("before_wbb")
        if b0:
            dev = max(abs(b0[k] - wbb([o])[k]) for k in range(6))
            maxdev = max(maxdev, dev)
            if dev > TOL:
                bad_bb.append("%s 偏差 %.6f" % (x["merged_into"], dev))
        # ② 被合并掉的原始对象名不该还在
        act = x.get("active_src")
        for n in x.get("from", []):
            if n != act and n in bpy.data.objects:
                resurrect.append(n)

    print("==GROUPS_CHECKED==", len(nm))
    check("GROUP_TARGETS_ALIVE", not lost, lost[:5])
    check("GROUP_VERTS_FACES", not bad_vf, bad_vf[:5])
    check("GROUP_PARENT_KEPT", not bad_par, bad_par[:5])
    check("GROUP_MAX_WBB_DEV", not bad_bb, "%s（最大 %.6f / 容差 %.3f）"
          % (bad_bb[:3], maxdev, TOL))
    print("==MAX_WBB_DEV==", "%.6f" % maxdev)
    check("SOURCE_OBJECTS_GONE", not resurrect, resurrect[:5])

    ac = R.get("after_counts") or {}
    if ac.get("mesh_objs") is not None:
        check("MESH_OBJS_VS_REPORT", len(meshes) == ac["mesh_objs"],
              "%d -> %d" % (ac["mesh_objs"], len(meshes)))
    # ★ 比「被引用」而不是总数：存盘会 prune 掉 users==0 的孤儿数据块，
    #   拿总数比必然误报「丢了材质 / 丢了贴图」。
    mu = sum(1 for m in bpy.data.materials if m.users > 0)
    iu = sum(1 for i in bpy.data.images if i.users > 0)
    if ac.get("materials_used") is not None:
        check("MATERIALS_USED", mu == ac["materials_used"],
              "%d -> %d  (总数 %d -> %d)"
              % (ac["materials_used"], mu, ac.get("materials", -1),
                 len(bpy.data.materials)))
    if ac.get("images_used") is not None:
        check("IMAGES_USED", iu == ac["images_used"],
              "%d -> %d  (总数 %d -> %d)"
              % (ac["images_used"], iu, ac.get("images", -1), len(bpy.data.images)))

# ---------- ④ 收尾检查（与报告无关，任何时候都做）----------
dead = [o.name for o in bpy.data.objects
        if o.type == "EMPTY" and not o.children and not o.children_recursive]
check("EMPTY_CONVERGED", not dead, "仍有 %d 个无子级 EMPTY: %s" % (len(dead), dead[:5]))

badcon = [o.name for o in bpy.data.objects
          if any(not c.is_valid for c in o.constraints)]
check("NO_DANGLING_CONSTRAINTS", not badcon, badcon[:5])

orphan = [o.name for o in bpy.data.objects if not o.users_collection]
check("NO_ORPHAN_OBJECTS", not orphan, orphan[:5])

# ---------- 展示 ----------
print("==NAMES==")
for o in sorted(meshes, key=lambda x: -len(x.data.vertices))[:15]:
    print("   ", o.name, "| 顶点", len(o.data.vertices), "| 面", len(o.data.polygons),
          "| 材质槽", len([m for m in o.data.materials if m]))

if FAILLOG:
    print("==FAILURES==")
    for s in FAILLOG:
        print("   ", s)
print("==VERIFY_RESULT==", "PASS" if ok else "FAIL")
print("==DONE==")
