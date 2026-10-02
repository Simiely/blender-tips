# -*- coding: utf-8 -*-
"""把 smoke_B 的顶层集合追加进 smoke_A，实测 append 的全部语义。
   环境变量：
     SMK_ROUTE = op | lib      （wm.append operator / bpy.data.libraries.load）
     SMK_REUSE = 0 | 1         （仅 op 路线有效：do_reuse_local_id）
   结果写 smoke/append_report_<route>.txt + .json
"""
import bpy, os, json, time, io, sys

WORK = os.environ.get("AMB_WORK", os.getcwd())   # 报告/基线/日志都写这里
ROUTE = os.environ.get("SMK_ROUTE", "op")
REUSE = os.environ.get("SMK_REUSE", "0") == "1"
SRC = os.path.join(WORK, "smoke_B.blend")
TARGET = "SKP Imported Data"

L = []
def w(s=""):
    L.append(s)


def snap():
    D = bpy.data
    o = {}
    for ob in D.objects:
        o[ob.name] = {
            "type": ob.type,
            "data": (ob.data.name if ob.data else None),
            "data_users": (ob.data.users if ob.data else None),
            "parents": ([ob.parent.name] if ob.parent else []),
            "children": sorted(c.name for c in ob.children),
            "colls": sorted(c.name for c in ob.users_collection),
            "mods": [(m.name, getattr(getattr(m, "node_group", None), "name", None))
                     for m in ob.modifiers],
            "mats": [s.material.name if s.material else None for s in ob.material_slots],
            "hide_viewport": ob.hide_viewport,
            "loc": [round(v, 4) for v in ob.matrix_world.translation],
        }
    return {
        "objects": o,
        "collections": {c.name: sorted(x.name for x in c.objects) for c in D.collections},
        "coll_children": {c.name: sorted(x.name for x in c.children) for c in D.collections},
        "materials": {m.name: m.users for m in D.materials},
        "meshes": {m.name: m.users for m in D.meshes},
        "images": {i.name: (i.users, i.packed_file is not None) for i in D.images},
        "worlds": {x.name: x.users for x in D.worlds},
        "node_groups": {g.name: g.users for g in D.node_groups},
        "cameras": {c.name: c.users for c in D.cameras},
        "scene_world": (bpy.context.scene.world.name if bpy.context.scene.world else None),
        "top_children": sorted(c.name for c in bpy.context.scene.collection.children),
        "filepath": D.filepath,
    }


t0 = time.time()
before = snap()
w("== 载入底文件 ==")
w("  base      : %s" % before["filepath"])
w("  objects=%d meshes=%d mats=%d imgs=%d colls=%d worlds=%d ngroup=%d"
  % (len(before["objects"]), len(before["meshes"]), len(before["materials"]),
     len(before["images"]), len(before["collections"]), len(before["worlds"]),
     len(before["node_groups"])))
w("  top children: %s" % before["top_children"])
w("  scene.world : %s" % before["scene_world"])
w("")

props = [p.identifier for p in bpy.ops.wm.append.get_rna_type().properties]
w("== wm.append 可用参数 ==")
w("  %s" % props)
w("")

t_imp = time.time()
if ROUTE == "op":
    kw = {}
    for k, v in (("instance_collections", False), ("instance_objects", False),
                 ("set_fake", False), ("use_recursive", False),
                 ("do_reuse_local_id", REUSE)):
        if k in props:
            kw[k] = v
    w("== 路线 op：bpy.ops.wm.append ==")
    w("  kwargs = %s" % kw)
    r = bpy.ops.wm.append(filepath=os.path.join(SRC, "Collection", TARGET),
                          directory=SRC + os.sep + "Collection" + os.sep,
                          filename=TARGET, **kw)
    w("  return = %s" % list(r))
else:
    w("== 路线 lib：bpy.data.libraries.load(link=False) ==")
    with bpy.data.libraries.load(SRC, link=False) as (df, dt):
        w("  源文件顶层 collections: %s" % df.collections[:10])
        dt.collections = [TARGET]
    w("  取回 collections: %s"
      % [c.name if c else None for c in dt.collections])
    linked = []
    for c in dt.collections:
        if c and c.name not in [x.name for x in bpy.context.scene.collection.children]:
            bpy.context.scene.collection.children.link(c)
            linked.append(c.name)
    w("  手动 link 进场景顶层: %s" % linked)

t_imp_done = time.time()
after = snap()
w("")
w("== 耗时 ==")
w("  append 本体 : %.3f s" % (t_imp_done - t_imp))
w("  合计        : %.3f s" % (t_imp_done - t0))
w("")

new_obj = sorted(set(after["objects"]) - set(before["objects"]))
w("== 新来的对象 %d 个 ==" % len(new_obj))
for n in new_obj:
    o = after["objects"][n]
    w("  %-24s %-7s mesh=%-18s users=%s  colls=%s  parent=%s  children=%s"
      % (n, o["type"], o["data"], o["data_users"], o["colls"], o["parents"], o["children"]))
w("")

w("== 新来的集合 ==")
newc = sorted(set(after["collections"]) - set(before["collections"]))
for n in newc:
    w("  %-26s objects=%s  children=%s"
      % (n, after["collections"][n], after["coll_children"][n]))
w("  top children after: %s" % after["top_children"])
w("  top children 变化   : %s"
  % sorted(set(after["top_children"]) - set(before["top_children"])))
w("")

w("== 同名实体是否被复用 ==")
for kind in ("materials", "meshes", "images", "worlds", "node_groups", "cameras"):
    b, a = before[kind], after[kind]
    common = sorted(set(b) & set(a))
    newk = sorted(set(a) - set(b))
    w("  [%s] 同名 %d 个 -> 引用端变化：%s" % (kind, len(common), ""))
    for n in common:
        tag = "复用" if a[n] > b[n] else "未变"
        w("      %-22s users %s -> %s   %s" % (n, b[n], a[n], tag))
    w("      新增条目: %s" % (newk if newk else "（无）"))
w("")

w("== 关键语义判据 ==")
def find_new_of(base):
    return [n for n in new_obj if n.startswith(base)]

w("  1) 材质同名内容相同 -> %s"
  % ("复用同一份（无 .001）" if "M_shared.001" not in after["materials"]
     else "复制出 M_shared.001（出现重复材质）"))
ghost = find_new_of("G-物体")
w("  2) 对象同名 -> A 的 G-物体 仍在: %s ; 追加来的: %s ; 其材质槽=%s"
  % ("G-物体" in after["objects"], ghost,
     [after["objects"][g]["mats"] for g in ghost]))
w("  3) 修改器依赖 -> %s ; 新对象修改器=%s"
  % (after["node_groups"], [after["objects"][g]["mods"] for g in ghost]))
shared = find_new_of("G-共享")
w("  4) 多实例 mesh -> %d 个对象: %s"
  % (len(shared), [(n, after["objects"][n]["data"], after["objects"][n]["data_users"])
                   for n in shared]))
w("     仍共用同一份: %s"
  % (len({after["objects"][n]["data"] for n in shared}) == 1))
child = find_new_of("G-子01")
for c in child:
    w("  5) 父级链 -> %s.parent=%s  (期望 G-空B)"
      % (c, after["objects"][c]["parents"]))
    par = after["objects"][c]["parents"]
    if par and par[0] in after["objects"]:
        w("     父对象位置=%s  子世界位置=%s"
          % (after["objects"][par[0]]["loc"], after["objects"][c]["loc"]))
cams = find_new_of("Cam: 场景号1")
w("  6) 相机同名 -> 追加后为 %s ; 相机总数 %d -> %d"
  % (cams, len(before["cameras"]), len(after["cameras"])))
w("  7) 世界 -> A 的 world 引用 %s -> %s ; 世界条目 %s"
  % (before["scene_world"], after["scene_world"], sorted(after["worlds"])))
w("  8) 底色文件的世界指纹未被替换: %s"
  % (before["scene_world"] == after["scene_world"]))

res = {"route": ROUTE, "reuse": REUSE, "seconds": round(t_imp_done - t_imp, 3),
       "new_objects": new_obj, "new_collections": newc,
       "before_counts": {k: len(before[k]) for k in
                         ("objects", "meshes", "materials", "images",
                          "collections", "worlds", "node_groups", "cameras")},
       "after_counts": {k: len(after[k]) for k in
                        ("objects", "meshes", "materials", "images",
                         "collections", "worlds", "node_groups", "cameras")}}
with io.open(os.path.join(WORK, "append_report_%s.txt" % ROUTE), "w",
             encoding="utf-8") as f:
    f.write("\n".join(L))
with io.open(os.path.join(WORK, "snap_before.json"), "w", encoding="utf-8") as f:
    json.dump(before, f, ensure_ascii=False, indent=1)
with io.open(os.path.join(WORK, "snap_after_%s.json" % ROUTE), "w", encoding="utf-8") as f:
    json.dump(after, f, ensure_ascii=False, indent=1)

outp = os.path.join(WORK, "smoke_out_%s.blend" % ROUTE)
bpy.ops.wm.save_as_mainfile(filepath=outp)
w("")
w("SAVED: %s" % outp)
print("\n".join(L))
