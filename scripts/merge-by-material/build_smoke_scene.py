# -*- coding: utf-8 -*-
"""
按材质合并 —— 自测台 · 建场景(冒烟测试第 1 步)

**为什么需要它**:拿 500 MB / 2.4 万对象的真实工程去调试合并脚本,一次就是几分钟、
失败还得从头来。所以先用一个 ~20 对象的小场景验证逻辑正确性。

场景故意包含:不同材质、单/多材质槽、带父级的层级、旋转缩放、一个「应被排除」的对象。
同时把 顶点数 / 面数 / 世界包围盒 / 期望分组数 记进 <cwd>/smoke_expected.json 作为判据基线。

运行位置(系统命令行):
    blender.exe --background --factory-startup --python build_smoke_scene.py
"""

import bpy, json, random, mathutils, os

random.seed(7)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections):
    if c.name != "Collection":
        pass

def mat(name, col):
    m = bpy.data.materials.new(name)
    m.diffuse_color = col
    return m

matA = mat("MatA", (1, 0, 0, 1))
matB = mat("MatB", (0, 0, 1, 1))
matC = mat("MatC", (0, 1, 0, 1))

empties = []
e1 = bpy.data.objects.new("Empty1", None)
bpy.context.scene.collection.objects.link(e1)
e1.location = (5, 3, 2); e1.rotation_euler = (0.3, 0.2, 0.5)
empties.append(e1)

boxes_a, boxes_b, multi = [], [], []
for i in range(10):
    bpy.ops.mesh.primitive_cube_add(location=(random.uniform(-9, 9), random.uniform(-9, 9), random.uniform(0, 4)))
    o = bpy.context.active_object
    o.rotation_euler = (random.random(), random.random(), random.random())
    o.scale = (random.uniform(0.5, 2), random.uniform(0.5, 2), random.uniform(0.5, 2))
    o.data.materials.append(matA)
    boxes_a.append(o)

for i in range(5):
    bpy.ops.mesh.primitive_uv_sphere_add(location=(random.uniform(-9, 9), random.uniform(-9, 9), random.uniform(0, 4)))
    o = bpy.context.active_object
    o.data.materials.append(matB)
    boxes_b.append(o)

for i in range(3):
    bpy.ops.mesh.primitive_cone_add(location=(random.uniform(-9, 9), random.uniform(-9, 9), random.uniform(0, 4)))
    o = bpy.context.active_object
    o.data.materials.append(matB)
    o.data.materials.append(matC)
    for f in o.data.polygons:
        f.material_index = 0 if f.index % 2 == 0 else 1
    multi.append(o)

# 把前 3 个 MatA 立方体挂到空物体下（测试世界变换是否保留）
for o in boxes_a[:3]:
    o.parent = e1

# 特意留一个「不参与合并」的对象，用来验证排除逻辑
bpy.ops.mesh.primitive_plane_add(location=(0, 0, 9))
keep = bpy.context.active_object
keep.name = "KEEP_ME"
keep.data.materials.append(matA)
keep.data.materials.append(matC)

# uv：给 sphere 加 UV 层，cube 不加 —— 测试分组是否把 UV 配置算进去
import bmesh
for o in boxes_b:
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=0)
    bm.to_mesh(o.data); bm.free()

allm = boxes_a + boxes_b + multi + [keep]

def world_bbox(objs):
    mn = [1e9] * 3; mx = [-1e9] * 3
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            for i in range(3):
                mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
    return [round(x, 4) for x in mn], [round(x, 4) for x in mx]

bpy.context.view_layer.update()
mn, mx = world_bbox(allm)
stat = {
    "mesh_objects": len(allm),
    "verts": sum(len(o.data.vertices) for o in allm),
    "polys": sum(len(o.data.polygons) for o in allm),
    "groups_expected": 4,   # MatA / MatB / (MatB,MatC) / 排除对象 KEEP_ME
    "bbox_min": mn, "bbox_max": mx,
    "empties": len(empties),
}
import os
with open(os.path.join(os.getcwd(), "smoke_expected.json"), "w", encoding="utf-8") as f:
    json.dump(stat, f, ensure_ascii=False)
print("==EXPECTED==", json.dumps(stat, ensure_ascii=False))

smoke = os.path.join(os.getcwd(), "smoke_scene.blend")
bpy.ops.wm.save_as_mainfile(filepath=smoke, compress=False)
print("==SAVED_SMOKE==", smoke)
print("==DONE==")
