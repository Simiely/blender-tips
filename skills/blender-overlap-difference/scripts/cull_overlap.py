# -*- coding: utf-8 -*-
"""面级剔除实现 `<TARGET> -= <CUTTER>`（物理去重叠，绕开布尔爆面）。
通过 9877 桥送进运行中的 Blender 执行。

配置块：改 TARGET / CUTTER 即可。CUTTER 全程只读、绝不改动。

规则（保守保留 ⇒ 保证零重叠）：
  1) 与 CUTTER 表面相交的面            → 删   (BVH.overlap)
  2) 其余面形心落在 CUTTER 内部        → 删   (三票制：+法向奇偶 / −法向奇偶 / 最近点法向符号，≥2 票)
  3) 形心离 CUTTER 表面 < EPS_TOUCH    → 删   (数值贴面安全网)
  ⇒ 留下的面整体位于 CUTTER 外部，与 CUTTER 零接触

还原点：隐藏备份对象 __BAK__<TARGET>__（可删）+ 尝试 undo_push。
跑完立刻内联复核 overlap == 0。
"""
import bpy
import bmesh
import json
import time
from mathutils.bvhtree import BVHTree

# ============ 配置 ============
TARGET = "水晶走廊_竖向灯.001"          # 要削的对象
CUTTER = "水晶走廊_竖向灯.002"          # 刀具体（保持完整）
BAK_PREFIX = "__BAK__"
EPS_TOUCH = 1e-4                        # 贴面安全网（局部单位）
MAX_HITS = 64                           # 奇偶射线最大反弹次数
MAKE_BACKUP = True                      # 是否放隐藏备份对象（强烈建议 True）
# ==============================

BAK_NAME = BAK_PREFIX + TARGET + "__"
tgt = bpy.data.objects[TARGET]
cut = bpy.data.objects[CUTTER]
me = tgt.data
report = {"target": TARGET, "cutter": CUTTER}


def stat(o):
    m = o.data
    return {"polys": len(m.polygons), "verts": len(m.vertices), "edges": len(m.edges)}


report["baseline"] = {
    "target": stat(tgt),
    "cutter": stat(cut),
    "uv_layers": [l.name for l in me.uv_layers],
    "has_custom_normals": bool(me.has_custom_normals),
    "slots": [(s.material.name if s.material else None) for s in tgt.material_slots],
    "scene_objects": len(bpy.data.objects),
}

# ---------- 还原点 ----------
if MAKE_BACKUP:
    old = bpy.data.objects.get(BAK_NAME)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    bak = tgt.copy()
    bak.data = tgt.data.copy()
    bak.name = BAK_NAME
    bak.modifiers.clear()
    bak.hide_viewport = True
    bak.hide_render = True
    tgt.users_collection[0].objects.link(bak)
    report["backup_object"] = BAK_NAME
try:
    bpy.ops.ed.undo_push(message="cull %s vs %s" % (TARGET, CUTTER))
    report["undo_push"] = "ok"
except Exception as e:
    report["undo_push"] = "N/A: %s" % e

# ---------- BVH ----------
t0 = time.time()
dg = bpy.context.evaluated_depsgraph_get()
bvh_cut = BVHTree.FromObject(cut, dg)
bvh_tgt = BVHTree.FromObject(tgt, dg)
ov = bvh_tgt.overlap(bvh_cut)
crossing = {p[0] for p in ov}
report["build_and_overlap_s"] = round(time.time() - t0, 2)
report["crossing_faces"] = len(crossing)


def parity_inside(origin, direction, bvh):
    hits = 0
    o = origin.copy()
    loc, n, idx, dist = bvh.ray_cast(o, direction, 1e5)
    while loc is not None and hits < MAX_HITS:
        hits += 1
        o = loc + direction * 1e-4
        loc, n, idx, dist = bvh.ray_cast(o, direction, 1e5)
    return hits % 2 == 1


def inside_votes(center, normal, bvh):
    votes = 0
    if parity_inside(center + normal * 1e-4, normal, bvh):
        votes += 1
    if parity_inside(center - normal * 1e-4, -normal, bvh):
        votes += 1
    loc, n, idx, dist = bvh.find_nearest(center, 1e5)
    if loc is not None and (center - loc).dot(n) < 0:
        votes += 1
    return votes


# ---------- 分类 ----------
t1 = time.time()
delete = set(crossing)
reasons = {"crossing": len(crossing), "inside": 0, "too_close": 0, "degenerate": 0}
for p in me.polygons:
    if p.index in crossing:
        continue
    n = p.normal
    if n.length < 1e-12:
        delete.add(p.index)
        reasons["degenerate"] += 1
        continue
    n = n.normalized()
    c = p.center
    loc, bn, idx, dist = bvh_cut.find_nearest(c, 1e5)
    if loc is not None and dist < EPS_TOUCH:
        delete.add(p.index)
        reasons["too_close"] += 1
        continue
    if inside_votes(c, n, bvh_cut) >= 2:
        delete.add(p.index)
        reasons["inside"] += 1
report["classify_s"] = round(time.time() - t1, 2)
report["reasons"] = reasons
report["delete_total"] = len(delete)

# ---------- 执行（先冻结索引，再统一删）----------
t2 = time.time()
kill_idx = sorted(delete)
bm = bmesh.new()
bm.from_mesh(me)
bm.faces.ensure_lookup_table()
kill = [bm.faces[i] for i in kill_idx if i < len(bm.faces)]
bmesh.ops.delete(bm, geom=kill, context='FACES')
bm.to_mesh(me)
bm.free()
me.update()
report["apply_s"] = round(time.time() - t2, 2)

report["after"] = {
    "target": stat(tgt),
    "cutter": stat(cut),
    "uv_layers": [l.name for l in me.uv_layers],
    "has_custom_normals": bool(me.has_custom_normals),
    "slots": [(s.material.name if s.material else None) for s in tgt.material_slots],
    "scene_objects": len(bpy.data.objects),
}
report["kept_pct"] = round(100.0 * len(me.polygons) / max(1, report["baseline"]["target"]["polys"]), 2)

# ---------- 内联复核 ----------
t3 = time.time()
dg2 = bpy.context.evaluated_depsgraph_get()
ov2 = BVHTree.FromObject(tgt, dg2).overlap(BVHTree.FromObject(cut, dg2))
report["verify_overlap_pairs"] = len(ov2)
report["verify_overlap_target_faces"] = len({p[0] for p in ov2})
report["verify_s"] = round(time.time() - t3, 2)
report["total_s"] = round(time.time() - t0, 2)
report["ok"] = (len(ov2) == 0)

print("CULL_BEGIN")
print(json.dumps(report, ensure_ascii=False, indent=1))
print("CULL_END")
