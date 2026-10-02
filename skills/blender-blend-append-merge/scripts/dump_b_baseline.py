# -*- coding: utf-8 -*-
"""导出 B 的逐对象基线（世界矩阵 / 父级 / 数据块 / 材质槽 / 修改器），
   供追加后做逐对象守恒比对。只读，不改任何东西。"""
import bpy, os, json, io, time

WORK = os.environ.get("AMB_WORK", os.getcwd())   # 报告/基线/日志都写这里
TAG = os.environ.get("BL_TAG", "B")

t0 = time.time()
D = bpy.data
objs = {}
for o in D.objects:
    mw = o.matrix_world
    objs[o.name] = {
        "t": o.type,
        "d": (o.data.name if o.data else None),
        "du": (o.data.users if o.data else None),
        "p": (o.parent.name if o.parent else None),
        "pi": [round(v, 6) for v in o.matrix_parent_inverse.to_translation()],
        "c": sorted(c.name for c in o.users_collection),
        "m": [s.material.name if s.material else None for s in o.material_slots],
        "mo": [(m.name, m.type, getattr(getattr(m, "node_group", None), "name", None))
               for m in o.modifiers],
        "mw": [round(v, 6) for row in mw for v in row],
        "l": [round(v, 6) for v in o.location],
        "s": [round(v, 6) for v in o.scale],
        "r": [round(v, 6) for v in o.rotation_euler],
        "hv": o.hide_viewport, "hr": o.hide_render,
        "nv": (len(o.data.vertices) if o.type == "MESH" else None),
        "np": (len(o.data.polygons) if o.type == "MESH" else None),
    }

meshes = {m.name: {"u": m.users, "nv": len(m.vertices), "np": len(m.polygons)}
          for m in D.meshes}
mats = {m.name: m.users for m in D.materials}
imgs = {i.name: {"u": i.users, "p": i.packed_file is not None, "s": i.source}
        for i in D.images}
ngs = {g.name: g.users for g in D.node_groups}
cams = {c.name: c.users for c in D.cameras}
colls = {c.name: {"o": sorted(x.name for x in c.objects),
                  "ch": sorted(x.name for x in c.children)} for c in D.collections}

out = {
    "tag": TAG, "filepath": D.filepath,
    "seconds": round(time.time() - t0, 3),
    "sum": {
        "objects": len(objs), "meshes": len(meshes), "materials": len(mats),
        "images": len(imgs), "node_groups": len(ngs), "cameras": len(cams),
        "collections": len(colls),
        "verts": sum(v["nv"] or 0 for v in objs.values()),
        "polys": sum(v["np"] or 0 for v in objs.values()),
        "multi_user_objs": sum(1 for v in objs.values() if (v["du"] or 0) > 1),
        "objs_with_mod": sum(1 for v in objs.values() if v["mo"]),
    },
    "objects": objs, "meshes": meshes, "materials": mats,
    "images": imgs, "node_groups": ngs, "cameras": cams, "collections": colls,
}
p = os.path.join(WORK, "baseline_%s.json" % TAG)
with io.open(p, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)
print("saved", p, os.path.getsize(p), "bytes")
print(json.dumps(out["sum"], ensure_ascii=False, indent=1))
