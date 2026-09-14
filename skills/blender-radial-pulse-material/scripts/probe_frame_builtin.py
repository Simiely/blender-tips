# -*- coding: utf-8 -*-
# A_PROBE —— 定论：「驱动表达式里的内建 frame 变量，在 Blender 5.2 上到底能不能用？」
#
# 仓库里这条说法分裂成两派：
#   说"不可用"：AGENTS.md:41 / docs/驱动式Z轴匀速旋转系统.md:81 / scripts/driver-spin/README.md:70
#               / skills/blender-procedural-emission-material/SKILL.md:184-191
#   说"可用"  ：AGENTS.md:32 / docs/材质参数统一控制器与实时面板.md:79 / docs/技巧速查.md:40,577-581
#
# 本脚本 4 组对照，全部在【主场景的临时物体】上做，做完删净，不碰任何真实数据。
#   A 内建 frame          —— 节点插槽驱动
#   B 内建 frame          —— 对象级驱动（location.z）
#   C frame * 未注册函数() —— 复现"恒为 0"的现象，看 is_valid
#   D frame * 已注册函数() —— 变量是被冤枉的那个
#   E SINGLE_PROP(scene.frame_current) —— 对照（仓库推荐写法）
#
# 判读要点：所有读数都走【求值后的依赖图】，且靠 frame_set() 换帧驱动重算
#          （换帧是依赖图自带的输入变化，不属于"外部 tag"）。
import bpy, json, time

PFX = "__AF"
rep = {"t0": time.time()}
main = bpy.context.scene

# ---------- 清理历史残留 ----------
for o in list(bpy.data.objects):
    if o.name.startswith(PFX):
        try: bpy.data.objects.remove(o, do_unlink=True)
        except Exception: pass
for m in list(bpy.data.materials):
    if m.name.startswith(PFX):
        try: bpy.data.materials.remove(m, do_unlink=True)
        except Exception: pass
for k in [k for k in bpy.app.driver_namespace if k.startswith("__af")]:
    del bpy.app.driver_namespace[k]

# ---------- 造：网格 + 材质 + 控制器 ----------
me = bpy.data.meshes.new(PFX + "MESH")
me.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
me.update()
obj = bpy.data.objects.new(PFX + "OBJ", me)
main.collection.objects.link(obj)

mat = bpy.data.materials.new(PFX + "MAT")
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
mnode = nt.nodes.new('ShaderNodeMath')
mnode.name = "M"
mnode.operation = 'ADD'
outn = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(mnode.outputs[0], outn.inputs[0])
obj.data.materials.append(mat)          # ★ 必须挂到真实物体上，材质才在依赖图里

ctl = bpy.data.objects.new(PFX + "CTL", None)
main.collection.objects.link(ctl)
ctl["v"] = 2.0

def read_node():
    dg = bpy.context.evaluated_depsgraph_get()
    return round(float(mat.evaluated_get(dg).node_tree.nodes["M"].inputs[0].default_value), 4)

def read_obj_z():
    dg = bpy.context.evaluated_depsgraph_get()
    return round(float(obj.evaluated_get(dg).location.z), 4)

def node_drv_valid():
    ad = nt.animation_data
    if not ad or not ad.drivers:
        return None
    try:
        return bool(ad.drivers[0].driver.is_valid)
    except Exception:
        return "ERR"

def mkd_node(expr, props=()):
    """props = [('v','OBJECT',ctl,'["v"]'), ...] 先建变量、后写 expression"""
    nt.animation_data_clear()
    nt.animation_data_create()
    fc = nt.nodes["M"].inputs[0].driver_add('default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    for nm, idt, tid, dp in props:
        v = d.variables.new()
        v.name = nm
        v.type = 'SINGLE_PROP'
        t = v.targets[0]
        t.id_type = idt
        t.id = tid
        t.data_path = dp
    d.expression = expr
    fc.update()
    return fc

# ---------- A：内建 frame（节点插槽驱动）----------
mkd_node("frame")
main.frame_set(7);  a7 = read_node()
main.frame_set(30); a30 = read_node()
main.frame_set(1);  a1 = read_node()
rep["A_node_builtin_frame"] = {"f7": a7, "f30": a30, "f1": a1,
                               "valid": node_drv_valid(),
                               "verdict": "OK" if abs(a30 - 30.0) < 1e-3 else "FAIL"}

# ---------- B：内建 frame（对象级驱动）----------
try:
    obj.driver_remove('location', 2)
except Exception:
    pass
fc2 = obj.driver_add('location', 2)
d2 = fc2.driver
d2.type = 'SCRIPTED'
d2.expression = "frame * 0.1"
fc2.update()
main.frame_set(10); b10 = read_obj_z()
main.frame_set(40); b40 = read_obj_z()
main.frame_set(1)
try:
    bvalid = bool(fc2.driver.is_valid)
except Exception:
    bvalid = "ERR"
rep["B_object_builtin_frame"] = {"f10_expected_1.0": b10, "f40_expected_4.0": b40,
                                 "valid": bvalid,
                                 "verdict": "OK" if abs(b40 - 4.0) < 1e-3 else "FAIL"}
obj.driver_remove('location', 2)
obj.location = (0.0, 0.0, 0.0)

# ---------- C：frame * 未注册函数()  —— 复现"恒为 0" ----------
c_err = None
try:
    mkd_node("frame * __af_missing()")
    main.frame_set(30); c30 = read_node()
    main.frame_set(60); c60 = read_node()
    rep["C_builtin_times_missing_ns"] = {"f30": c30, "f60": c60,
                                         "valid": node_drv_valid()}
except Exception as e:
    rep["C_builtin_times_missing_ns"] = {"error": repr(e)[:200]}

# ---------- D：frame * 已注册函数() ----------
bpy.app.driver_namespace["__af_ns"] = (lambda: 3.0)
try:
    mkd_node("frame * __af_ns()")
    main.frame_set(30); d30 = read_node()
    main.frame_set(60); d60 = read_node()
    rep["D_builtin_times_registered_ns"] = {"f30_expected_90": d30, "f60_expected_180": d60,
                                            "valid": node_drv_valid(),
                                            "verdict": "OK" if abs(d60 - 180.0) < 1e-3 else "FAIL"}
except Exception as e:
    rep["D_builtin_times_registered_ns"] = {"error": repr(e)[:200]}

# ---------- E：SINGLE_PROP → scene.frame_current（仓库推荐写法）----------
try:
    mkd_node("fr * v", props=[("fr", 'SCENE', main, "frame_current"),
                              ("v", 'OBJECT', ctl, '["v"]')])
    main.frame_set(30); e30 = read_node()
    main.frame_set(60); e60 = read_node()
    rep["E_single_prop_frame_current"] = {"f30_expected_60": e30, "f60_expected_120": e60,
                                          "valid": node_drv_valid(),
                                          "verdict": "OK" if abs(e60 - 120.0) < 1e-3 else "FAIL"}
except Exception as e:
    rep["E_single_prop_frame_current"] = {"error": repr(e)[:200]}

# ---------- 清理 ----------
nt.animation_data_clear()
bpy.context.view_layer.update()
for o in list(bpy.data.objects):
    if o.name.startswith(PFX):
        try: bpy.data.objects.remove(o, do_unlink=True)
        except Exception: pass
for m in list(bpy.data.materials):
    if m.name.startswith(PFX):
        try: bpy.data.materials.remove(m, do_unlink=True)
        except Exception: pass
for k in [k for k in bpy.app.driver_namespace if k.startswith("__af")]:
    del bpy.app.driver_namespace[k]

main.frame_set(1)
rep["leftover_objects"] = [o.name for o in bpy.data.objects if o.name.startswith(PFX)]
rep["leftover_materials"] = [m.name for m in bpy.data.materials if m.name.startswith(PFX)]
rep["leftover_ns"] = [k for k in bpy.app.driver_namespace if k.startswith("__af")]
rep["blender"] = bpy.app.version_string
rep["total_sec"] = round(time.time() - rep["t0"], 2)
print("A_PROBE_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("A_PROBE_END")
