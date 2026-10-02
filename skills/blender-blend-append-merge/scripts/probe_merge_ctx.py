# -*- coding: utf-8 -*-
"""合并前的场景上下文：场景相机 / 渲染设置 / 视图层可见性 / EMPTY 骨架 / 集合 exclude。"""
import bpy, os, io, json

WORK = os.environ.get("AMB_WORK", os.getcwd())   # 报告/基线/日志都写这里
TAG = os.environ.get("MC_TAG", "?")
D = bpy.data
sc = bpy.context.scene
vl = bpy.context.view_layer

L = []
def w(s=""):
    L.append(s)

w("== 场景 (tag=%s) ==" % TAG)
w("  filepath      : %s" % D.filepath)
w("  scene name    : %s" % sc.name)
w("  scene camera  : %s" % (sc.camera.name if sc.camera else None))
w("  engine        : %s" % sc.render.engine)
w("  resolution    : %dx%d  %%d=%s" % (sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage))
w("  fps           : %s / %s" % (sc.render.fps, sc.render.fps_base))
w("  frames        : %s - %s" % (sc.frame_start, sc.frame_end))
w("  output        : %s" % sc.render.filepath)
w("  world         : %s" % (sc.world.name if sc.world else None))
w("  unit scale    : %s" % sc.unit_settings.scale_length)

w("")
w("== 对象可见性 ==")
vlset = {o.name for o in vl.objects}
allobj = list(D.objects)
mesh = [o for o in allobj if o.type == "MESH"]
empty = [o for o in allobj if o.type == "EMPTY"]
cam = [o for o in allobj if o.type == "CAMERA"]
w("  对象总数      : %d  (MESH %d / EMPTY %d / CAMERA %d / 其他 %d)"
  % (len(allobj), len(mesh), len(empty), len(cam), len(allobj) - len(mesh) - len(empty) - len(cam)))
w("  在视图层      : %d" % len(vlset))
w("  不在视图层    : %d  %s"
  % (len(allobj) - len(vlset), sorted(n for n in (o.name for o in allobj) if n not in vlset)[:12]))
w("  hide_viewport : %d" % sum(1 for o in allobj if o.hide_viewport))
w("  hide_render   : %d" % sum(1 for o in allobj if o.hide_render))
w("  hide_get()    : %d" % sum(1 for o in allobj if o.hide_get()))
w("  无集合归属    : %d" % sum(1 for o in allobj if len(o.users_collection) == 0))
w("  多重集合归属  : %d" % sum(1 for o in allobj if len(o.users_collection) > 1))
w("  有父级的对象  : %d" % sum(1 for o in allobj if o.parent))
w("  EMPTY 作为父级: %d" % sum(1 for e in empty if len(e.children) > 0))
w("  EMPTY 无子级  : %d" % sum(1 for e in empty if len(e.children) == 0))

w("")
w("== 集合树（exclude / hide_viewport）==")


# 取 exclude：遍历 layer_collection
def lc_map(lc, out, depth=0):
    out[lc.name] = (depth, lc.exclude, lc.hide_viewport)
    for ch in lc.children:
        lc_map(ch, out, depth + 1)

EX = {}
lc_map(vl.layer_collection, EX)
def walk2(c, d=0):
    info = EX.get(c.name)
    w("  " + "  " * d + "%-30s objs=%-6d exclude=%-5s hide_vp=%-5s children=%s"
      % (c.name, len(c.objects), info[1] if info else "?", info[2] if info else "?",
         sorted(x.name for x in c.children)))
    for ch in c.children:
        walk2(ch, d + 1)
for c in sc.collection.children:
    walk2(c)

w("")
w("== 材质/图像 引用口径 ==")
w("  materials total=%d  users>0=%d" % (len(D.materials), sum(1 for m in D.materials if m.users > 0)))
w("  images    total=%d  users>0=%d  packed=%d"
  % (len(D.images), sum(1 for i in D.images if i.users > 0),
     sum(1 for i in D.images if i.packed_file)))
w("  生成型图像(无文件) : %s"
  % sorted(i.name for i in D.images if i.source in ("GENERATED", "VIEWER")))

w("")
w("== 几何规模 ==")
w("  mesh objects=%d  mesh datablocks=%d" % (len(mesh), len(D.meshes)))
w("  verts sum=%d  polys sum=%d"
  % (sum(len(o.data.vertices) for o in mesh), sum(len(o.data.polygons) for o in mesh)))
w("  多实例对象数(users>1) = %d" % sum(1 for o in mesh if o.data.users > 1))
w("  带修改器对象数        = %d" % sum(1 for o in allobj if len(o.modifiers) > 0))

with io.open(os.path.join(WORK, "merge_ctx_%s.txt" % TAG), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("\n".join(L))
