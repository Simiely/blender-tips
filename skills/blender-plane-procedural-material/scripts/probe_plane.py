# -*- coding: utf-8 -*-
# P54 —— 【只读】平面专项侦察：几何 / 朝向 / 纹理坐标在三轴上的冻结情况 / 节点链 / 驱动
# 纯读，不做任何改动。
import bpy, json, math
from mathutils import Vector

WORKDIR = r"C:/path/to/blender_control"
MAT = "竖向灯001_噪波滚动发光"
CTRL = "竖向灯001_噪波控制"

rep = {}
sc = bpy.context.scene
rep["scene"] = sc.name
rep["frame"] = sc.frame_current
rep["engine"] = sc.render.engine
rep["view_transform"] = sc.view_settings.view_transform
rep["object_count"] = len(bpy.data.objects)
rep["scene_count"] = len(bpy.data.scenes)
rep["all_scenes"] = [s.name for s in bpy.data.scenes]

# ---------- 1. 材质使用者 ----------
mat = bpy.data.materials.get(MAT)
rep["mat_found"] = mat is not None
users = []
if mat is not None:
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        for sl in o.material_slots:
            if sl.material is mat:
                mw = o.matrix_world
                mw3 = mw.to_3x3()
                pts = [mw @ v.co for v in o.data.vertices]
                xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
                lo = [min(xs), min(ys), min(zs)]
                hi = [max(xs), max(ys), max(zs)]
                # 面积加权平均法线（世界空间）
                n = Vector((0.0, 0.0, 0.0))
                for p in o.data.polygons:
                    n += (mw3 @ p.normal) * p.area
                n = n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))
                # 局部包围盒
                lpts = [v.co for v in o.data.vertices]
                llo = [min(p[i] for p in lpts) for i in range(3)]
                lhi = [max(p[i] for p in lpts) for i in range(3)]
                users.append({
                    "name": o.name,
                    "verts": len(o.data.vertices),
                    "polys": len(o.data.polygons),
                    "uv_layers": [u.name for u in o.data.uv_layers],
                    "loc": [round(v, 4) for v in o.location],
                    "rot_deg": [round(math.degrees(v), 2) for v in o.rotation_euler],
                    "scale": [round(v, 4) for v in o.scale],
                    "world_min": [round(v, 4) for v in lo],
                    "world_max": [round(v, 4) for v in hi],
                    "world_size": [round(hi[i] - lo[i], 4) for i in range(3)],
                    "local_min": [round(v, 4) for v in llo],
                    "local_max": [round(v, 4) for v in lhi],
                    "normal_world": [round(v, 5) for v in n],
                    "flat_axes": [],          # 世界尺度≈0 的轴
                })
                for i, ax in enumerate("XYZ"):
                    if hi[i] - lo[i] < 1e-6:
                        users[-1]["flat_axes"].append(ax)
rep["users"] = users

# ---------- 2. 纹理坐标在「三轴」上的取值（平面专项核心）----------
# shader 里 tex.object = <控制空物体> ⇒ 采样点 = ctrl.matrix_world^-1 @ obj.matrix_world @ v.co
ctrl = bpy.data.objects.get(CTRL)
rep["ctrl_found"] = ctrl is not None
if ctrl is not None:
    rep["ctrl"] = {
        "loc": [round(v, 6) for v in ctrl.location],
        "rot_deg": [round(math.degrees(v), 6) for v in ctrl.rotation_euler],
        "scale": [round(v, 6) for v in ctrl.scale],
        "is_identity": (ctrl.matrix_world - ctrl.matrix_world.Identity(4)).median_scale < 1e-9,
        "keys": [k for k in ctrl.keys() if not k.startswith("_")],
        "props": {k: ctrl.get(k) for k in ctrl.keys() if not k.startswith("_")},
    }

# 节点链里 tex.object 指向谁
tex_target = None
if mat is not None and mat.use_nodes:
    for n in mat.node_tree.nodes:
        if n.type == 'TEX_COORD':
            ob = n.object
            tex_target = ob.name if ob else None
rep["tex_object"] = tex_target

if ctrl is not None and mat is not None:
    cinv = ctrl.matrix_world.inverted()
    coord_dump = []
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        if not any(sl.material is mat for sl in o.material_slots):
            continue
        cps = [cinv @ (o.matrix_world @ v.co) for v in o.data.vertices]
        if not cps:
            continue
        comp = []
        for i, ax in enumerate("XYZ"):
            vals = [round(p[i], 4) for p in cps]
            lo, hi = min(vals), max(vals)
            comp.append({
                "axis": ax,
                "min": round(lo, 4),
                "max": round(hi, 4),
                "span": round(hi - lo, 4),
                "frozen": (hi - lo) < 1e-4,
            })
        # 局部归一化（Generated 会给出的样子，平面专项参考）
        lpts = [v.co for v in o.data.vertices]
        llo = [min(p[i] for p in lpts) for i in range(3)]
        lhi = [max(p[i] for p in lpts) for i in range(3)]
        gen = []
        for i, ax in enumerate("XYZ"):
            d = lhi[i] - llo[i]
            gen.append({"axis": ax, "span_local": round(d, 5),
                        "note": "degenerate(0..1 无意义)" if d < 1e-6 else "0..1 归一"})
        coord_dump.append({
            "object": o.name,
            "object_coord_axes": comp,
            "frozen_axis": [c["axis"] for c in comp if c["frozen"]],
            "generated_axes": gen,
            "sample_corner_vectors": [[round(x, 4) for x in p] for p in cps[:4]],
        })
    rep["coord_dump"] = coord_dump

# ---------- 3. 节点链 + 驱动 ----------
if mat is not None and mat.use_nodes:
    nt = mat.node_tree
    rep["nodes"] = [{"name": n.name, "type": n.type, "label": n.label} for n in nt.nodes]
    rep["links"] = ["%s.%s -> %s.%s" % (l.from_node.name, l.from_socket.name,
                                        l.to_node.name, l.to_socket.name)
                    for l in nt.links]
    drv = []
    if nt.animation_data:
        for fc in nt.animation_data.drivers:
            d = fc.driver
            drv.append({
                "dpath": fc.data_path,
                "arr": fc.array_index,
                "expr": d.expression,
                "type": d.type,
                "vars": json.loads(json.dumps([
                    {"n": v.name, "t": v.type,
                     "targets": [{"id": t.id_type, "dp": t.data_path} for t in v.targets]}
                    for v in d.variables], ensure_ascii=False)),
            })
    rep["drivers"] = drv
    rep["driver_count"] = len(drv)
    for n in nt.nodes:
        if n.type == 'VALTORGB':
            rep["ramp"] = {
                "node": n.name,
                "interp": n.color_ramp.interpolation,
                "elements": [{"pos": round(e.position, 4),
                              "color": [round(c, 4) for c in e.color]}
                             for e in n.color_ramp.elements],
            }
    # 求值后的真值
    dg = bpy.context.evaluated_depsgraph_get()
    nte = mat.evaluated_get(dg).node_tree
    ev = {}
    for n in nte.nodes:
        if n.type == 'MAPPING':
            ev["mapping_loc"] = [round(v, 5) for v in n.inputs[1].default_value]
            ev["mapping_scale"] = [round(v, 5) for v in n.inputs[3].default_value]
        if n.type == 'TEX_NOISE':
            ev["noise_w"] = round(n.inputs[1].default_value, 5)
            ev["noise_scale"] = round(n.inputs[2].default_value, 5)
            ev["noise_detail"] = round(n.inputs[3].default_value, 5)
        if n.type == 'VALTORGB':
            ev["ramp_positions"] = [round(e.position, 5) for e in n.color_ramp.elements]
        if n.type == 'MATH' and n.operation == 'MULTIPLY':
            ev["mult"] = round(n.inputs[1].default_value, 5)
    rep["evaluated"] = ev
    # BSDF 发光插槽是否已连线
    for n in nte.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            rep["emission_linked"] = n.inputs['Emission Strength'].is_linked
            rep["emission_id"] = {i: s.name for i, s in enumerate(n.inputs)}
rep["total_sec"] = 0.0

print("P54_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("P54_END")
