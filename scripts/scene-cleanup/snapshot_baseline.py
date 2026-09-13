# snapshot_baseline.py — 清理前基线快照（在 purge 之前跑）
# 产出 cleanup_baseline.json，供 verify_purge.py 做前后对比
import bpy, os, json

# !! 必须改：与 purge_empties.py / verify_purge.py 保持一致
OUT_DIR = r"C:\path\to\workdir"
OUT = os.path.join(OUT_DIR, "cleanup_baseline.json")

objs = list(bpy.data.objects)
children = {}
parent_has_nonempty_child = set()     # 避免用 ob.children（对全场景是 O(n^2)）
for o in objs:
    if o.parent is not None:
        nm = o.parent.name
        children[nm] = children.get(nm, 0) + 1
        if o.type != 'EMPTY':
            parent_has_nonempty_child.add(nm)

emp = [o for o in objs if o.type == 'EMPTY']
data = {
    "filepath": bpy.data.filepath,
    "total": len(objs),
    "empty": len(emp),
    "empty_no_child": sum(1 for o in emp if children.get(o.name, 0) == 0),
    "non_empty": len(objs) - len(emp),
    "mesh": sum(1 for o in objs if o.type == 'MESH'),
    "camera": sum(1 for o in objs if o.type == 'CAMERA'),
    "light": sum(1 for o in objs if o.type == 'LIGHT'),
    "curve": sum(1 for o in objs if o.type == 'CURVE'),
    "parented_to_empty": sum(1 for o in objs if o.parent is not None and o.parent.type == 'EMPTY'),
    "empties_with_nonempty_child": sum(1 for o in emp if o.name in parent_has_nonempty_child),
    "materials": len(bpy.data.materials),
    "images": len(bpy.data.images),
    "actions": len(bpy.data.actions),
    "node_groups": len(bpy.data.node_groups),
    "collections": len(bpy.data.collections),
    "scenes": len(bpy.data.scenes),
    "orphan_materials": sum(1 for m in bpy.data.materials if m.users == 0),
    "orphan_images": sum(1 for i in bpy.data.images if i.users == 0),
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("baseline -> " + OUT)
for k, v in data.items():
    print("  %-28s %s" % (k, v))
print("=== SNAPSHOT_BASELINE DONE ===")
