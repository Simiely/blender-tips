# -*- coding: utf-8 -*-
"""侦察两个网格体的重叠情况（只读）。
通过 9877 桥送进运行中的 Blender 执行，输出 PROBE_OVL_BEGIN ... END 之间的 JSON。

配置块：改 ROOT / 两对象名即可。
"""
import bpy
import json
import time
from mathutils.bvhtree import BVHTree

# ============ 配置 ============
A_NAME = "水晶走廊_竖向灯.001"   # 目标件（要削的那个）
B_NAME = "水晶走廊_竖向灯.002"   # 刀具体（保持完整的那个）
CLUSTER_TOP = 8                 # 相交簇报告前 N 大
A_STRIDE = 8                    # A 侧内外采样步长
B_STRIDE = 60                   # B 侧内外采样步长
# ==============================

a = bpy.data.objects.get(A_NAME)
b = bpy.data.objects.get(B_NAME)
out = {}

for name, o in ((A_NAME, a), (B_NAME, b)):
    if o is None:
        out[name] = {"exists": False}
        continue
    me = o.data
    mw = o.matrix_world
    out[name] = {
        "exists": True,
        "data": me.name,
        "mesh_users": me.users,
        "verts": len(me.vertices),
        "edges": len(me.edges),
        "polys": len(me.polygons),
        "edge_minus_1_5F": len(me.edges) - 1.5 * len(me.polygons),
        "slots": [(s.material.name if s.material else None) for s in o.material_slots],
        "modifiers": [m.type for m in o.modifiers],
        "parent": (o.parent.name if o.parent else None),
        "collections": [c.name for c in o.users_collection],
        "loc": [round(v, 6) for v in o.location],
        "rot_euler": [round(v, 6) for v in o.rotation_euler],
        "scale": [round(v, 6) for v in o.scale],
        "dims": [round(v, 4) for v in o.dimensions],
        "matrix_is_identity": all(
            abs(mw[i][j] - (1.0 if i == j else 0.0)) < 1e-9
            for i in range(4) for j in range(4)),
    }

if a is None or b is None:
    print("PROBE_OVL_BEGIN")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print("PROBE_OVL_END")
    raise SystemExit

same_xf = all(abs(a.matrix_world[i][j] - b.matrix_world[i][j]) < 1e-9
              for i in range(4) for j in range(4))
out["same_matrix_world"] = bool(same_xf)
out["_note"] = ("两对象 matrix_world 相同 ⇒ BVH 可在同一局部空间直接比较；"
                "不同则本脚本的相交/内外结果无效，需先统一到世界空间。")

dg = bpy.context.evaluated_depsgraph_get()
t0 = time.time()
bvh_a = BVHTree.FromObject(a, dg)
bvh_b = BVHTree.FromObject(b, dg)
out["bvh_build_s"] = round(time.time() - t0, 2)

# ---- 表面穿插：BVH 相交 ----
t1 = time.time()
ov = bvh_a.overlap(bvh_b)
touched = {p[0] for p in ov}
out["surface_intersection"] = {
    "triangle_pairs": len(ov),
    "a_faces_touched": len(touched),
    "a_faces_total": len(a.data.polygons),
    "a_touched_pct": round(100.0 * len(touched) / max(1, len(a.data.polygons)), 2),
    "seconds": round(time.time() - t1, 2),
}


def parity_inside(origin, direction, bvh, max_hits=64):
    hits = 0
    o = origin.copy()
    loc, n, idx, dist = bvh.ray_cast(o, direction, 1e5)
    while loc is not None and hits < max_hits:
        hits += 1
        o = loc + direction * 1e-4
        loc, n, idx, dist = bvh.ray_cast(o, direction, 1e5)
    return hits % 2 == 1


def inside_report(obj, bvh, stride):
    """奇偶法 + 最近点法向符号法，两种独立判据并列"""
    me = obj.data
    ids = list(range(0, len(me.polygons), stride))
    par = neg = pos = 0
    nohit = 0
    for i in ids:
        p = me.polygons[i]
        c = p.center
        n = p.normal
        if n.length < 1e-12:
            continue
        n = n.normalized()
        if parity_inside(c + n * 1e-4, n, bvh):
            par += 1
        loc, bn, idx, dist = bvh.find_nearest(c, 1e5)
        if loc is None:
            nohit += 1
            continue
        if (c - loc).dot(bn) < 0:
            neg += 1
        else:
            pos += 1
    return {
        "sampled": len(ids),
        "inside_by_parity_pct": round(100.0 * par / max(1, len(ids)), 2),
        "inside_by_normal_sign_pct": round(100.0 * neg / max(1, neg + pos), 2),
        "no_nearest_hit": nohit,
    }


out["A_inside_B"] = inside_report(a, bvh_b, A_STRIDE)
out["B_inside_A"] = inside_report(b, bvh_a, B_STRIDE)

# ---- 相交簇聚类（判"一整片"还是"大量小穿插"）----
ma = a.data
e2f = {}
for p in ma.polygons:
    for ek in p.edge_keys:
        e2f.setdefault(ek, []).append(p.index)
seen = set()
clusters = []
for f0 in touched:
    if f0 in seen:
        continue
    stack = [f0]
    seen.add(f0)
    comp = [f0]
    while stack:
        f = stack.pop()
        for ek in ma.polygons[f].edge_keys:
            for g in e2f.get(ek, ()):
                if g in touched and g not in seen:
                    seen.add(g)
                    stack.append(g)
                    comp.append(g)
    clusters.append(comp)

mw = a.matrix_world
cinfo = []
for comp in clusters:
    zs = [(mw @ ma.polygons[i].center).z for i in comp]
    cinfo.append({"faces": len(comp), "z": [round(min(zs), 3), round(max(zs), 3)]})
cinfo.sort(key=lambda c: -c["faces"])
out["overlap_clusters"] = {"count": len(cinfo), "top": cinfo[:CLUSTER_TOP]}
out["elapsed_s"] = round(time.time() - t0, 2)

print("PROBE_OVL_BEGIN")
print(json.dumps(out, ensure_ascii=False, indent=1))
print("PROBE_OVL_END")
