# -*- coding: utf-8 -*-
"""
按材质合并 —— 自测台 · 建场景（冒烟测试第 1 步）

**为什么需要它**：拿 500 MB / 2.4 万对象的真实工程去调试合并脚本，一次就是几分钟、
失败还得从头来。所以先用一个小场景验证逻辑正确性。

场景故意覆盖每一条代码路径：

  v1 原有
    · 不同材质 / 单材质槽 / 多材质槽
    · 带父级的层级（空物体带旋转），验证世界变换是否保得住
    · 非单位缩放 + 随机旋转
    · 一个「应被排除」的对象（KEEP_ME，由命令行排除）

  v2 新增
    · 一大组「对象间**共享** mesh 数据块」（> ONESHOT_MAX_OBJS）→ 走两级 join + 网格独立化
    · 一大组「对象各自**独立** mesh」（> ONESHOT_MAX_OBJS）→ 走两级 join
    · 一组「**跨集合**」的对象 → 应被风险判定整组跳过
    · 一组「**不在视图层**」的对象（躺在被 exclude 的集合里）→ 应被风险判定整组跳过

并把 顶点数 / 面数 / 世界包围盒 / 期望结果 记进 <cwd>/smoke_expected.json 作为判据基线。

运行位置（系统命令行）：
    blender.exe --background --factory-startup --python build_smoke_scene.py
"""

import bpy, json, random, os

random.seed(7)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

N_SHARED = 450      # 共享同一 mesh 数据块的大组
N_INDEP = 500       # 各自独立 mesh 的大组
ONESHOT = 400       # 与 merge_by_material.py 的 ONESHOT_MAX_OBJS 保持一致


def mat(name, col):
    m = bpy.data.materials.new(name)
    m.diffuse_color = col
    return m


def move_to(o, col):
    """把对象从当前所有集合里挪进 col（避免它同时挂在两个集合，撞上「跨集合」判定）"""
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o)


matA = mat("MatA", (1, 0, 0, 1))
matB = mat("MatB", (0, 0, 1, 1))
matC = mat("MatC", (0, 1, 0, 1))
matShared = mat("MatShared", (1, 0.5, 0, 1))
matIndep = mat("MatIndep", (0.5, 0, 1, 1))
matCross = mat("MatCross", (1, 1, 0, 1))
matHidden = mat("MatHidden", (0, 1, 1, 1))

ROOT = bpy.context.scene.collection

empties = []
e1 = bpy.data.objects.new("Empty1", None)
ROOT.objects.link(e1)
e1.location = (5, 3, 2)
e1.rotation_euler = (0.3, 0.2, 0.5)
empties.append(e1)

# ---------- v1 原有：普通组 ----------
boxes_a, boxes_b, multi = [], [], []
for i in range(10):
    bpy.ops.mesh.primitive_cube_add(
        location=(random.uniform(-9, 9), random.uniform(-9, 9), random.uniform(0, 4)))
    o = bpy.context.active_object
    o.rotation_euler = (random.random(), random.random(), random.random())
    o.scale = (random.uniform(0.5, 2), random.uniform(0.5, 2), random.uniform(0.5, 2))
    o.data.materials.append(matA)
    boxes_a.append(o)

for i in range(5):
    bpy.ops.mesh.primitive_uv_sphere_add(
        location=(random.uniform(-9, 9), random.uniform(-9, 9), random.uniform(0, 4)))
    o = bpy.context.active_object
    o.data.materials.append(matB)
    boxes_b.append(o)

for i in range(3):
    bpy.ops.mesh.primitive_cone_add(
        location=(random.uniform(-9, 9), random.uniform(-9, 9), random.uniform(0, 4)))
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

# ---------- v2 新增 ①：共享 mesh 数据块的大组 ----------
bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0))
proto = bpy.context.active_object
proto.data.materials.append(matShared)
shared_mesh = proto.data
proto.name = "SharedPrototype"
# ★ 必须把它也挪进 ROOT：primitive_add 会放进当时的活动集合（"Collection"），
#   而其余成员挂在 scene.collection —— 不同集合会让整组被「跨集合」判定跳过。
move_to(proto, ROOT)
shared_objs = [proto]
for i in range(N_SHARED - 1):
    o = bpy.data.objects.new("Shared_%03d" % i, shared_mesh)   # ★ 同一个 mesh 数据块
    ROOT.objects.link(o)
    o.location = ((i % 30) * 0.2, (i // 30) * 0.2, 12)
    o.scale = (1.5, 1.5, 1.5)
    shared_objs.append(o)
assert all(o.data is shared_mesh for o in shared_objs)
assert shared_mesh.users >= N_SHARED, shared_mesh.users

# ---------- v2 新增 ②：各自独立 mesh 的大组 ----------
bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0))
p2 = bpy.context.active_object
p2_mesh = p2.data
indep_objs = []
for i in range(N_INDEP):
    m = p2_mesh.copy()            # ★ 每个对象一份独立 mesh 数据块
    m.materials.append(matIndep)
    o = bpy.data.objects.new("Indep_%03d" % i, m)
    ROOT.objects.link(o)
    o.location = ((i % 25) * 0.2, (i // 25) * 0.2, 20)
    indep_objs.append(o)
bpy.data.objects.remove(p2, do_unlink=True)

# ---------- v2 新增 ③：跨集合的一组 ----------
colA = bpy.data.collections.new("CrossA")
colB = bpy.data.collections.new("CrossB")
ROOT.children.link(colA)
ROOT.children.link(colB)
cross_objs = []
for i, col in enumerate((colA, colB)):
    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(i * 0.5, 0, 30))
    o = bpy.context.active_object
    o.name = "Cross_%d" % i
    o.data.materials.append(matCross)
    move_to(o, col)
    cross_objs.append(o)

# ---------- v2 新增 ④：不在视图层的一组（集合被 exclude）----------
colHid = bpy.data.collections.new("HiddenCol")
ROOT.children.link(colHid)
hidden_objs = []
for i in range(2):
    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(i * 0.5, 0, 40))
    o = bpy.context.active_object
    o.name = "Hidden_%d" % i
    o.data.materials.append(matHidden)
    move_to(o, colHid)
    hidden_objs.append(o)
lc = bpy.context.view_layer.layer_collection.children["HiddenCol"]
lc.exclude = True      # ★ 集合被排除 ⇒ 里面的对象不在 view_layer.objects 里

# ---------- 基线 ----------
allm = boxes_a + boxes_b + multi + [keep] + shared_objs + indep_objs \
    + cross_objs + hidden_objs


def world_bbox(objs):
    mn = [1e9] * 3
    mx = [-1e9] * 3
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
    return [round(x, 4) for x in mn], [round(x, 4) for x in mx]


bpy.context.view_layer.update()
# ★ 只统计**视图层内**的对象：躺在 excluded 集合里的对象，depsgraph 根本不会去求值，
#   它们的 matrix_world 停在旧值（常常就是局部坐标），拿它算包围盒两边口径不等价。
vl_names = {o.name for o in bpy.context.view_layer.objects}
mn, mx = world_bbox([o for o in allm if o.name in vl_names])

# 期望：合并后剩下的 mesh 对象数
#   原场景按「材质 + 父级」= 4 组(MatA无父级 / MatA@Empty1 / MatB / MatB+MatC)
#   + KEEP_ME(排除) + 共享大组 1 + 独立大组 1 + 跨集合组 2(跳过) + 视图层外组 2(跳过)
groups_expected = 4 + 1 + 1 + 1 + len(cross_objs) + len(hidden_objs)
# 合并后应保留的 EMPTY：Empty1（M_MatA.001 挂在它下面）
empties_expected = 1

stat = {
    "note": "带父级分组的期望（merge_by_material.py v2 默认 GROUP_BY_PARENT=True）",
    "mesh_objects_before": len(allm),
    "mesh_objects": groups_expected,
    "groups_expected": groups_expected,
    "verts": sum(len(o.data.vertices) for o in allm),
    "polys": sum(len(o.data.polygons) for o in allm),
    "bbox_min": mn,
    "bbox_max": mx,
    "empties_before": len(empties),
    "empties": empties_expected,
    "excluded": ["KEEP_ME"],
    "large_groups": {"shared": N_SHARED, "indep": N_INDEP, "oneshot_max": ONESHOT},
    "risky_kept": {o.name: [len(o.data.vertices), len(o.data.polygons)]
                   for o in cross_objs + hidden_objs},
}
with open(os.path.join(os.getcwd(), "smoke_expected.json"), "w",
          encoding="utf-8", newline="\n") as f:
    json.dump(stat, f, ensure_ascii=False, indent=1)
print("==EXPECTED==", json.dumps(stat, ensure_ascii=False))

smoke = os.path.join(os.getcwd(), "smoke_scene.blend")
bpy.ops.wm.save_as_mainfile(filepath=smoke, compress=False)
print("==SAVED_SMOKE==", smoke)
print("==DONE==")
