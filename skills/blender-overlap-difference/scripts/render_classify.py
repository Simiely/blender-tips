# -*- coding: utf-8 -*-
"""render_classify.py — 「动刀前先看见」：把目标件的面按【保留 / 表面相交 / 体积内部】三色渲染出来。

绿 = 保留（整体在刀具体外部）    红 = 与刀具体表面相交    蓝 = 判为落在刀具体体积内部
刀具体用线框套在外面，并额外出一张 x-ray 视角。

为什么必须跑这一步：占比数字会骗人。实测某例报「87~89% 在内部」，双方都以为是「互相插一点」，
渲染出来才发现是「细灯丝穿在珠串里」—— 那 87% 是设计如此。不看图就动刀，必然出事。

依赖：必须走 9877 桥在 Blender 主线程里执行（见 blender-bridge-ops skill）。
桥调用：python bl.py render_classify.py
"""

import bpy
import bmesh
import json
import os
import time
from mathutils import Vector
from mathutils.bvhtree import BVHTree

# ============================ 配置区 ============================
TARGET = "对象A"                 # ← 要判定删/留的对象
CUTTER = "对象B"                 # ← 刀具体
MESH_SOURCE = ""                 # 留空 = 自动：有 __BAK__<TARGET>__ 就用它（未经改动的原网格），否则用 TARGET 当前网格
OUTDIR = r"D:/workbuddy/_overlap_render"
ZOOM_SCALE = 0.35                # 特写正交视野宽度（按对象尺寸调）
OVERVIEW_SCALE = 30.0            # 全景正交视野宽度
RES = 1100
EPS_TOUCH = 1e-4
MAX_HITS = 64

# 相机方向（世界系，相机放在 center + dir*60 处看向 center）
VIEW_ZOOM = (0.55, -0.78, 0.30)
VIEW_OVERVIEW = (0.55, -0.75, 0.35)
# ===============================================================

os.makedirs(OUTDIR, exist_ok=True)
a = bpy.data.objects[TARGET]
b = bpy.data.objects[CUTTER]

if MESH_SOURCE:
    src = bpy.data.objects[MESH_SOURCE]
elif ("__BAK__%s__" % TARGET) in bpy.data.objects:
    src = bpy.data.objects["__BAK__%s__" % TARGET]
    print("MESH_SOURCE 自动取用备份对象 __BAK__%s__（未经改动）" % TARGET)
else:
    src = a
me = src.data

log = {"target": TARGET, "cutter": CUTTER, "mesh_source": src.name, "mesh": me.name}
t0 = time.time()

verts = [v.co.copy() for v in me.vertices]
polys = [tuple(p.vertices) for p in me.polygons]
# 注意：分类在「对象局部坐标」里做，BVH 也必须在同一空间；故对刀具体用 FromObject 前先确认同坐标系。
# 若两者变换不同，需把刀具体顶点变换到 src 的局部空间（此处用 src.matrix_world.inverted() @ b.matrix_world）。
m_b2src = src.matrix_world.inverted() @ b.matrix_world
dg = bpy.context.evaluated_depsgraph_get()
ev = b.evaluated_get(dg)
me_b = ev.to_mesh()
vb = [m_b2src @ v.co for v in me_b.vertices]
pb = [tuple(p.vertices) for p in me_b.polygons]
bvh_b = BVHTree.FromPolygons(vb, pb, all_triangles=False, epsilon=0.0)
ev.to_mesh_clear()

bvh_a = BVHTree.FromPolygons(verts, polys, all_triangles=True)
crossing = {p[0] for p in bvh_a.overlap(bvh_b)}
log["crossing"] = len(crossing)


def parity_inside(origin, direction, bvh):
    hits = 0
    o = origin.copy()
    loc, n, idx, dist = bvh.ray_cast(o, direction, 1e5)
    while loc is not None and hits < MAX_HITS:
        hits += 1
        o = loc + direction * 1e-4
        loc, n, idx, dist = bvh.ray_cast(o, direction, 1e5)
    return hits % 2 == 1


inside = set()
for p in me.polygons:
    if p.index in crossing:
        continue
    n = p.normal
    if n.length < 1e-12:
        inside.add(p.index)
        continue
    n = n.normalized()
    c = p.center
    v = 0
    if parity_inside(c + n * 1e-4, n, bvh_b):
        v += 1
    if parity_inside(c - n * 1e-4, -n, bvh_b):
        v += 1
    loc, bn, idx, dist = bvh_b.find_nearest(c, 1e5)
    if loc is not None and (loc - c).dot(bn) > 0:
        v += 1
    if v >= 2:
        inside.add(p.index)
kept = set(range(len(me.polygons))) - crossing - inside
log["inside"] = len(inside)
log["kept"] = len(kept)
log["total_faces"] = len(me.polygons)
log["kept_pct"] = round(len(kept) / max(1, len(me.polygons)) * 100, 2)

# 最大相交簇作为特写取景中心
e2f = {}
for p in me.polygons:
    for ek in p.edge_keys:
        e2f.setdefault(ek, []).append(p.index)
seen = set()
clusters = []
for f0 in crossing:
    if f0 in seen:
        continue
    stack = [f0]
    seen.add(f0)
    comp = [f0]
    while stack:
        f = stack.pop()
        for ek in me.polygons[f].edge_keys:
            for g in e2f.get(ek, ()):
                if g in crossing and g not in seen:
                    seen.add(g)
                    stack.append(g)
                    comp.append(g)
    clusters.append(comp)
clusters.sort(key=len, reverse=True)
if clusters:
    zoom_c = sum((me.polygons[i].center for i in clusters[0]), Vector()) / len(clusters[0])
    log["max_cluster_faces"] = len(clusters[0])
else:
    zoom_c = sum((p.center for p in me.polygons), Vector()) / max(1, len(me.polygons))
log["cluster_count"] = len(clusters)

# 分类渲染在 src 的局部空间里搭临时对象，用 src.matrix_world 摆到世界
temp_objs = []
temp_meshes = []


def make_subset(name, keep_set, color):
    m = me.copy()
    m.name = name + "_mesh"
    temp_meshes.append(m)
    o = bpy.data.objects.new(name, m)
    o.matrix_world = src.matrix_world.copy()
    o.color = color
    bm = bmesh.new()
    bm.from_mesh(m)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep_set], context='FACES')
    bm.to_mesh(m)
    bm.free()
    m.update()
    temp_objs.append(o)
    return o


make_subset("__CHK_kept__", kept, (0.20, 0.80, 0.32, 1.0))
make_subset("__CHK_ins__", inside, (0.20, 0.45, 0.95, 1.0))
make_subset("__CHK_cross__", crossing, (0.95, 0.25, 0.20, 1.0))

sc = bpy.data.scenes.new("__CHKSCENE__")
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x = RES
sc.render.resolution_y = RES
sc.render.image_settings.file_format = 'PNG'
sc.render.film_transparent = False
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'OBJECT'
sh.show_shadows = False
sh.background_type = 'VIEWPORT'
sh.background_color = (0.10, 0.10, 0.12)

for o in temp_objs:
    sc.collection.objects.link(o)
cd = bpy.data.cameras.new("__chkcam__")
cam = bpy.data.objects.new("__chkcam__", cd)
sc.collection.objects.link(cam)
temp_objs.append(cam)
sc.camera = cam
cd.type = 'ORTHO'
b.color = (0.85, 0.85, 0.88, 1.0)

mw = src.matrix_world
zoom_cw = mw @ zoom_c
all_c = [mw @ p.center for p in me.polygons]
xs = [c.x for c in all_c]; ys = [c.y for c in all_c]; zs = [c.z for c in all_c]
big = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))


def shoot(center_w, scale, direction, path):
    cd.ortho_scale = scale
    d = Vector(direction).normalized()
    cam.location = center_w + d * 60
    cam.rotation_euler = (center_w - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    return os.path.exists(path)


shots = {}
try:
    shots["a_zoom"] = shoot(zoom_cw, ZOOM_SCALE, VIEW_ZOOM, os.path.join(OUTDIR, "A_classify_zoom.png"))
    shots["a_overview"] = shoot(big, OVERVIEW_SCALE, VIEW_OVERVIEW, os.path.join(OUTDIR, "A_classify_overview.png"))
    # 叠上刀具体，开 x-ray
    sc.collection.objects.link(b)
    sh.show_xray = True
    sh.xray_alpha = 0.25
    shots["ab_zoom"] = shoot(zoom_cw, ZOOM_SCALE, VIEW_ZOOM, os.path.join(OUTDIR, "AB_xray_zoom.png"))
    shots["ab_overview"] = shoot(big, OVERVIEW_SCALE, VIEW_OVERVIEW, os.path.join(OUTDIR, "AB_xray_overview.png"))
except Exception as e:
    log["render_error"] = str(e)
log["shots"] = shots

# 清理临时对象/场景（绝不留下 __CHK* 残留）
try:
    sc.collection.objects.unlink(b)
except Exception:
    pass
for o in list(temp_objs):
    try:
        sc.collection.objects.unlink(o)
    except Exception:
        pass
bpy.data.scenes.remove(sc)
for o in temp_objs:
    if o.name in bpy.data.objects:
        bpy.data.objects.remove(o, do_unlink=True)
for m in temp_meshes:
    if m.name in bpy.data.meshes and m.users == 0:
        bpy.data.meshes.remove(m)
log["leftover"] = [o.name for o in bpy.data.objects if o.name.startswith("__CHK")]
log["scenes"] = [s.name for s in bpy.data.scenes]
log["total_s"] = round(time.time() - t0, 2)

print("CLASSIFY_BEGIN")
print(json.dumps(log, ensure_ascii=False, indent=1))
print("CLASSIFY_END")
