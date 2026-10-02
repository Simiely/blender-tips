# -*- coding: utf-8 -*-
"""
分体翻页牌 —— 把所有中缝轴收进一个「总控 Empty」+ 单一集合

用途:
  1. 移动/旋转总控 ⇒ 整组翻页效果整体搬运(逐张实测同量跟随)
  2. 全部对象(master + 轴 + 卡片)收进一个集合 ⇒ 其他工程 File > Append 该集合即可复用

关键:
  ★ 必须先 `p.parent = master`,**再**设 `matrix_parent_inverse` ——
    顺序反了会被 Blender 重置成单位矩阵,整组多叠一个 +总控位置 的位移(实测 35 张全飞)
"""
import bpy
from mathutils import Vector, Matrix

# ---------------- CONFIG ----------------
MASTER_NAME = "翻页牌_总控"
COLL_NAME = "翻页牌动态"
# ----------------------------------------

scene = bpy.context.scene
vl = bpy.context.view_layer

pivots = sorted([o for o in bpy.data.objects if 'flip_delay' in o], key=lambda p: p.name)
cards = [bpy.data.objects.get(p["flip_card"]) for p in pivots
         if "flip_card" in p and bpy.data.objects.get(p["flip_card"])]
print("轴数量:", len(pivots), "| 卡片数:", len(cards))

def bbox_min(o):
    cs = [o.matrix_world @ Vector(v) for v in o.bound_box]
    return tuple(round(min(c[i] for c in cs), 4) for i in range(3))

snap = {c.name: bbox_min(c) for c in cards}

# 1. 总控放在轴群中心
pts = [Vector(p.matrix_world.translation) for p in pivots]
center = Vector((sum(v.x for v in pts)/len(pts),
                 sum(v.y for v in pts)/len(pts),
                 sum(v.z for v in pts)/len(pts)))

old = bpy.data.objects.get(MASTER_NAME)
if old:
    bpy.data.objects.remove(old, do_unlink=True)
master = bpy.data.objects.new(MASTER_NAME, None)
scene.collection.objects.link(master)
master.location = center
master.rotation_euler = (0.0, 0.0, 0.0)      # 保持无旋转,轴的本地 Y 才等于世界 Y
master.empty_display_type = 'ARROWS'
master.empty_display_size = 0.30

# 2. ★ 先 parent 后设补偿(唯一的一次)
T = Matrix.Translation(center)
for p in pivots:
    p.parent = master
    p.matrix_parent_inverse = T.inverted()
vl.update()

# 3. 收进单一集合
coll = bpy.data.collections.get(COLL_NAME) or bpy.data.collections.new(COLL_NAME)
if coll.name not in [c.name for c in scene.collection.children]:
    scene.collection.children.link(coll)
for o in [master] + pivots + cards:
    for c in list(o.users_collection):
        if c.name != COLL_NAME:
            c.objects.unlink(o)
    if o.name not in coll.objects:
        coll.objects.link(o)
oldc = bpy.data.collections.get("FLIP_pivots")
if oldc and len(oldc.objects) == 0:
    bpy.data.collections.remove(oldc)
vl.update()

# 4. 核验
bad = [(c.name, snap[c.name], bbox_min(c)) for c in cards if bbox_min(c) != snap[c.name]]
print("挂接后位置核验:", "全部 PASS (%d 张零位移)" % len(cards) if not bad else "FAIL → %s" % bad[:3])

# 5. 实测整体跟随
before = bbox_min(cards[0])
master.location = center + Vector((1.0, 0.0, 0.5))
vl.update()
delta = tuple(round(bbox_min(cards[0])[i] - before[i], 4) for i in range(3))
master.location = center
vl.update()
print("移动总控 (+1,0,+0.5) → 卡片位移", delta, "|", "OK" if delta == (1.0, 0.0, 0.5) else "异常")
print("总控子级数:", len(master.children), "| 集合对象数:", len(coll.all_objects))
print("[GROUP DONE] 移动/旋转 %s 即可整体搬运;其他工程 Append 集合 %s 复用" % (MASTER_NAME, COLL_NAME))
