# -*- coding: utf-8 -*-
"""深查指定对象（游离对象）：位置/尺寸/几何/材质/父子/可见性/是否被引用。"""
import bpy, os, io

WORK = os.environ.get("AMB_WORK", os.getcwd())   # 报告/基线/日志都写这里
D = bpy.data
NAMES = [n for n in os.environ.get("STRAY", "").split("|") if n]

L = []
def w(s=""):
    L.append(s)

for n in NAMES:
    o = D.objects.get(n)
    w("=" * 70)
    if o is None:
        w("  %s  << 不存在 >>" % n)
        continue
    w("  name   : %s" % o.name)
    w("  type   : %s   data=%s" % (o.type, o.data.name if o.data else None))
    w("  colls  : %s" % sorted(c.name for c in o.users_collection))
    w("  parent : %s" % (o.parent.name if o.parent else None))
    w("  children(%d): %s" % (len(o.children), sorted(c.name for c in o.children)[:10]))
    w("  loc(world center): %s" % [round(v, 3) for v in o.matrix_world.translation])
    w("  dimensions       : %s" % [round(v, 3) for v in o.dimensions])
    w("  scale            : %s" % [round(v, 4) for v in o.scale])
    w("  hide_viewport=%s hide_render=%s hide_get=%s  visible=%s"
      % (o.hide_viewport, o.hide_render, o.hide_get(), o.visible_get()))
    w("  modifiers: %s" % [(m.name, m.type) for m in o.modifiers])
    if o.type == "MESH":
        me = o.data
        w("  verts=%d polys=%d  data.users=%d" % (len(me.vertices), len(me.polygons), me.users))
        w("  materials: %s" % [m.name if m else None for m in me.materials])
        bb = [tuple(round(x, 3) for x in c) for c in o.bound_box]
        w("  local bound_box: %s" % bb)
        w("  uv_layers: %s  color_attrs: %s"
          % ([l.name for l in me.uv_layers],
             [a.name for a in getattr(me, "color_attributes", []) or []]))
    # 是否被谁引用（父级/约束/驱动/修改器）
    as_parent = [c.name for c in D.objects if c.parent is o]
    w("  被当作父级的对象: %d %s" % (len(as_parent), sorted(as_parent)[:10]))
    users = []
    for c in D.collections:
        if o.name in [x.name for x in c.objects]:
            users.append(c.name)
    w("  集合归属(list): %s" % users)

w("")
w("== 全场景 mesh 对象总数（含游离）: %d =="
  % sum(1 for o in D.objects if o.type == "MESH"))

with io.open(os.path.join(WORK, "stray_detail.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("\n".join(L))
