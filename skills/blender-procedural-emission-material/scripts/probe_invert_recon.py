# -*- coding: utf-8 -*-
# P61 —— 只读侦察：为「反色」新控件做准备
#   ① 当前材质节点/连线全清单
#   ② 当前 6 条驱动的路径 / 表达式 / 变量绑定
#   ③ 控制器 5 个属性的 UI 元数据（新属性要对齐同样格式）
#   ④ 5.2 里 ShaderNodeMapRange 的插槽名 / 属性（干跑前先摸清 API）
import bpy, json, time

rep = {"t0": time.time()}
MAT = "竖向灯001_噪波滚动发光"
CTRL = "竖向灯001_噪波控制"

mat = bpy.data.materials.get(MAT)
ctl = bpy.data.objects.get(CTRL)
nt = mat.node_tree

# ① 节点 / 连线
rep["nodes"] = [{"name": n.name, "type": n.bl_idname,
                 "label": (n.label or None)} for n in nt.nodes]
rep["links"] = ["%s.%s -> %s.%s" % (l.from_node.name, l.from_socket.name,
                                   l.to_node.name, l.to_socket.name) for l in nt.links]

# ② 驱动
drv = []
ad = nt.animation_data
if ad:
    for fc in ad.drivers:
        d = fc.driver
        drv.append({
            "data_path": fc.data_path,
            "array_index": fc.array_index,
            "expr": d.expression,
            "type": d.type,
            "vars": [{"name": v.name, "type": v.type,
                      "targets": [{"id_type": t.id_type,
                                   "id": (t.id.name if t.id else None),
                                   "data_path": t.data_path} for t in v.targets]}
                     for v in d.variables],
        })
rep["drivers"] = drv
rep["driver_count"] = len(drv)

# ③ 控制器属性元数据
meta = {}
for k in ctl.keys():
    try:
        meta[k] = ctl.id_properties_ui(k).as_dict()
    except Exception as e:
        meta[k] = {"err": repr(e)}
rep["ctrl_meta"] = meta

# ④ MapRange 节点 API 摸底（在临时材质里试，不动真材质）
tmp = bpy.data.materials.new("__P61TMP")
tmp.use_nodes = True
tnt = tmp.node_tree
try:
    mr = tnt.nodes.new('ShaderNodeMapRange')
    rep["maprange"] = {
        "bl_idname": mr.bl_idname,
        "inputs": [{"name": s.name, "type": s.type,
                    "default": (list(s.default_value) if hasattr(s.default_value, "__len__")
                                else s.default_value),
                    "enabled": s.enabled} for s in mr.inputs],
        "outputs": [{"name": s.name, "type": s.type} for s in mr.outputs],
        "props": {p: getattr(mr, p, "<none>") for p in
                  ("interpolation_type", "clamp", "data_type")},
        "has_clamp": hasattr(mr, "clamp"),
        "has_data_type": hasattr(mr, "data_type"),
        "has_interpolation_type": hasattr(mr, "interpolation_type"),
    }
except Exception as e:
    rep["maprange"] = {"err": repr(e)}
# 也摸一下 Math 节点 MULTIPLY_ADD 作为备选
try:
    mn = tnt.nodes.new('ShaderNodeMath')
    mn.operation = 'MULTIPLY_ADD'
    rep["math_madd"] = {"inputs": [s.name for s in mn.inputs],
                        "operation_set": mn.operation}
except Exception as e:
    rep["math_madd"] = {"err": repr(e)}
bpy.data.materials.remove(tmp, do_unlink=True)

# 现状体检
rep["object_count"] = len(bpy.data.objects)
rep["material_count"] = len(bpy.data.materials)
rep["leftover_tmp"] = [m.name for m in bpy.data.materials if m.name.startswith("__P61")]
rep["frame_now"] = bpy.context.scene.frame_current
rep["ctrl_values"] = {k: ctl[k] for k in ctl.keys()}
rep["total_sec"] = round(time.time() - rep["t0"], 2)
print("P61_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("P61_END")
