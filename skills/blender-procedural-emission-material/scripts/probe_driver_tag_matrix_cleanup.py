# -*- coding: utf-8 -*-
# P59 —— 收尾：
#   ① 跨请求再看一次"不 tag 到底会不会自己重算"（上一请求把 v 设成 99 却没 tag）
#   ② 把 P58 造的所有临时物体/材质/命名空间函数删干净
#   ③ 确认真实材质与控制器没被动过
import bpy, json, time

PFX = "__P58"
rep = {"t0": time.time()}
main = bpy.context.scene

# ① 跨请求读残余值
try:
    ev = bpy.data.materials[PFX + "MAT_B_sp"].evaluated_get(
        bpy.context.evaluated_depsgraph_get()).node_tree.nodes["V"]
    rep["residual_B_sp"] = round(float(ev.outputs[0].default_value), 4)
except Exception as e:
    rep["residual_B_sp"] = repr(e)
rep["residual_expect"] = "8.0 = 时间流逝也不会自动重算（99.0 才算会自动）"

# ② 清理
removed_o, removed_m = [], []
for o in list(bpy.data.objects):
    if o.name.startswith(PFX):
        removed_o.append(o.name)
        try: bpy.data.objects.remove(o, do_unlink=True)
        except Exception: pass
for m in list(bpy.data.materials):
    if m.name.startswith(PFX):
        removed_m.append(m.name)
        try: bpy.data.materials.remove(m, do_unlink=True)
        except Exception: pass
me_gone = []
for me in list(bpy.data.meshes):
    if me.name.startswith(PFX):
        me_gone.append(me.name)
        try: bpy.data.meshes.remove(me, do_unlink=True)
        except Exception: pass
ns = [k for k in bpy.app.driver_namespace if k.startswith("__p58")]
for k in ns:
    del bpy.app.driver_namespace[k]

bpy.context.view_layer.update()

rep["removed_objects"] = removed_o
rep["removed_materials"] = removed_m
rep["removed_meshes"] = me_gone
rep["removed_ns"] = ns
rep["leftover_objects"] = [o.name for o in bpy.data.objects if o.name.startswith("__P5")]
rep["leftover_materials"] = [m.name for m in bpy.data.materials if m.name.startswith("__P5")]
rep["leftover_ns"] = [k for k in bpy.app.driver_namespace if k.startswith("__p5")]

# ③ 真实材质 / 控制器体检
matname = "竖向灯001_噪波滚动发光"
ctrlname = "竖向灯001_噪波控制"
mt = bpy.data.materials.get(matname)
ct = bpy.data.objects.get(ctrlname)
rep["real_material"] = {
    "exists": mt is not None,
    "nodes": len(mt.node_tree.nodes) if mt else None,
    "drivers": len(mt.node_tree.animation_data.drivers) if (mt and mt.node_tree.animation_data) else 0,
    "nodes_names": sorted(n.name for n in mt.node_tree.nodes) if mt else None,
}
rep["real_ctrl"] = {
    "exists": ct is not None,
    "keys": sorted(k for k in ct.keys()) if ct else None,
    "values": {k: ct[k] for k in ct.keys()} if ct else None,
    "location": list(ct.location) if ct else None,
}
rep["object_count"] = len(bpy.data.objects)
rep["material_count"] = len(bpy.data.materials)
rep["scene_now"] = main.name
rep["frame_now"] = main.frame_current
rep["total_sec"] = round(time.time() - rep["t0"], 2)
print("P59_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("P59_END")
