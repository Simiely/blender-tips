# -*- coding: utf-8 -*-
"""
分体翻页牌 —— 撤销:卡片脱离中缝轴,回到世界原位

原理: 当初挂接时把 card.matrix_basis 设成了卡的**世界矩阵**,
所以解除父级后 world = matrix_basis = 原世界位置,自动回到原位(不需要再补偿)。

同时删除 FLIP_pivots 集合、移除 frame_change 处理器与各轴驱动。
"""
import bpy
from mathutils import Vector

PIVOT_COLL = "FLIP_pivots"

scene = bpy.context.scene
pivots = sorted([o for o in bpy.data.objects if 'flip_delay' in o], key=lambda p: p.name)
print("待撤销轴:", len(pivots))

# 1. 快照(用于核验)
def bbox_min(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return tuple(round(min(c[i] for c in cs), 4) for i in range(3))

cards = []
for p in pivots:
    c = bpy.data.objects.get(p.get("flip_card", "")) if "flip_card" in p else None
    if c:
        cards.append((c, bbox_min(c)))

# 2. 轴角度归零 → 解除父级(Keep Transform 语义: 直接置 parent=None,world = basis)
for p in pivots:
    p.rotation_euler = (0.0, 0.0, 0.0)
for c, _ in cards:
    if c.parent and c.parent.name.startswith("FLIP_pivot"):
        c.parent = None

# 3. 删轴与集合
for p in pivots:
    bpy.data.objects.remove(p, do_unlink=True)
coll = bpy.data.collections.get(PIVOT_COLL)
if coll:
    bpy.data.collections.remove(coll)

# 4. 移除处理器
MARK = "flip_all_cards"
for h in list(bpy.app.handlers.frame_change_post):
    if getattr(h, "__name__", "") == MARK:
        bpy.app.handlers.frame_change_post.remove(h)

# 5. 核验
bad = [(c.name, before, bbox_min(c)) for c, before in cards if bbox_min(c) != before]
print("位置核验:", "全部 PASS (%d 张,回到挂轴前位置)" % len(cards) if not bad else "FAIL → %s" % bad[:5])
print("[DETACH DONE] 轴与集合已清除;卡片已回到场景根下")
