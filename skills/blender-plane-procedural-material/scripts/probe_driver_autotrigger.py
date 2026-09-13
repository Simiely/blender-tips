# -*- coding: utf-8 -*-
# P57 —— 决定性实验：让驱动"改属性即自动重算"的正确写法
#   对照 4 种策略：①命名空间函数 ②命名空间函数+几种 tag ③SINGLE_PROP 声明依赖边(不 tag)
#   另外验证驱动表达式里 max()/min() 是否可用（ColorRamp 下界夹 0 需要它）
#   全部在【主场景】里的临时物体上做（材质必须被求值），做完删净。
import bpy, json, time
from mathutils import Vector

PFX = "__P57"
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
for k in [k for k in bpy.app.driver_namespace if k.startswith("__p57")]:
    del bpy.app.driver_namespace[k]

# ---------- 造：物体 + 材质 + 控制器（全部在主场景里）----------
me = bpy.data.meshes.new(PFX + "MESH")
me.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
me.update()
obj = bpy.data.objects.new(PFX + "OBJ", me)
main.collection.objects.link(obj)

mat = bpy.data.materials.new(PFX + "MAT")
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)                       # 清空，自己建
mnode = nt.nodes.new('ShaderNodeMath')
mnode.name = "M"; mnode.operation = 'ADD'
outn = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(mnode.outputs[0], outn.inputs[0])
obj.data.materials.append(mat)               # ★ 必须挂到真实物体上，材质才在依赖图里

ctl = bpy.data.objects.new(PFX + "CTL", None)
main.collection.objects.link(ctl)
for k, v in (("x", 0.0), ("y", 0.0), ("z", 0.0)):
    ctl[k] = float(v)

bpy.app.driver_namespace["__p57_x"] = (lambda: float(ctl.get("x", 0.0)))
bpy.app.driver_namespace["__p57_y"] = (lambda: float(ctl.get("y", 0.0)))


def read():
    dg = bpy.context.evaluated_depsgraph_get()
    v = mat.evaluated_get(dg).node_tree.nodes["M"].inputs[0].default_value
    return round(float(v), 4)


def read_raw():
    return round(float(nt.nodes["M"].inputs[0].default_value), 4)


def mkd(name, expr, use_single=None):
    """use_single = ('x', 'OBJECT', ctl) 时加 SINGLE_PROP 变量"""
    nt.animation_data_clear()
    nt.animation_data_create()
    fc = nt.nodes["M"].inputs[0].driver_add('default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    d.expression = expr
    if use_single:
        prop, idt, tid = use_single
        v = d.variables.new()
        v.name = 'v'
        v.type = 'SINGLE_PROP'
        t = v.targets[0]
        t.id_type = idt
        t.id = tid
        t.data_path = '["%s"]' % prop
    fc.update()
    return {"name": name, "expr": expr, "single_prop": bool(use_single)}


rows = []
# ---- 策略 A：命名空间函数（无变量）----
mkd("A_ns", "__p57_x()")
ctl["x"] = 11.0                                    # 只改属性，不做任何 tag
bpy.context.view_layer.update()
rows.append({"tag": "A 命名空间函数 / 改属性不 tag", "read": read(), "raw": read_raw()})

ctl["x"] = 12.0
bpy.context.view_layer.update()
rows.append({"tag": "A + view_layer.update()", "read": read(), "raw": read_raw()})

ctl["x"] = 13.0
ctl.update_tag()
bpy.context.view_layer.update()
rows.append({"tag": "A + ctl.update_tag()", "read": read(), "raw": read_raw()})

ctl["x"] = 14.0
ctl.update_tag(); mat.update_tag(); nt.update_tag()
bpy.context.view_layer.update()
rows.append({"tag": "A + 三重 tag", "read": read(), "raw": read_raw()})

# ---- 策略 B：SINGLE_PROP 声明依赖边 ----
mkd("B_single", "v", ('x', 'OBJECT', ctl))
ctl["x"] = 21.0                                    # 只改属性，不 tag
bpy.context.view_layer.update()
rows.append({"tag": "B SINGLE_PROP / 改属性不 tag", "read": read(), "raw": read_raw()})

ctl["x"] = 22.0
bpy.context.view_layer.update()
rows.append({"tag": "B SINGLE_PROP / 再改一次不 tag", "read": read(), "raw": read_raw()})

# ---- 策略 C：表达式里能否用 max / min / abs ----
fnres = {}
for nm, ex in (("max", "max(0.0, v - 5.0)"), ("min", "min(v, 3.0)"),
               ("abs", "abs(v - 20.0)"), ("clamp_like", "max(0.0, min(1.0, v))")):
    try:
        mkd("C_" + nm, ex, ('x', 'OBJECT', ctl))
        ctl["x"] = 26.0
        bpy.context.view_layer.update()
        fnres[nm] = {"expr": ex, "read": read(), "error": None}
    except Exception as e:
        fnres[nm] = {"expr": ex, "error": repr(e)}
rep["expr_functions"] = fnres

# ---- 策略 D：两条变量（帧 + 速度）能否同时用 ----
try:
    mkd("D_two", "fr * v", ('x', 'OBJECT', ctl))
    d = nt.animation_data.drivers[0].driver
    v2 = d.variables.new(); v2.name = 'fr'; v2.type = 'SINGLE_PROP'
    t2 = v2.targets[0]; t2.id_type = 'SCENE'; t2.id = main; t2.data_path = 'frame_current'
    nt.animation_data.drivers[0].update()
    ctl["x"] = 0.5
    main.frame_set(10)
    bpy.context.view_layer.update()
    rep["two_vars"] = {"expr": "fr * v", "frame": main.frame_current, "read": read()}
    main.frame_set(1)
except Exception as e:
    rep["two_vars"] = {"error": repr(e)}

rep["matrix"] = rows

# ---------- 清理 ----------
nt.animation_data_clear()
bpy.context.view_layer.update()
if mat.users == 0:
    pass
for o in list(bpy.data.objects):
    if o.name.startswith(PFX):
        try: bpy.data.objects.remove(o, do_unlink=True)
        except Exception: pass
for m in list(bpy.data.materials):
    if m.name.startswith(PFX):
        try: bpy.data.materials.remove(m, do_unlink=True)
        except Exception: pass
for k in [k for k in bpy.app.driver_namespace if k.startswith("__p57")]:
    del bpy.app.driver_namespace[k]
rep["leftover"] = {k: [x.name for x in v if x.name.startswith(PFX)] for k, v in
                   (("objects", bpy.data.objects), ("materials", bpy.data.materials))}
rep["leftover_ns"] = [k for k in bpy.app.driver_namespace if k.startswith("__p57")]
rep["real_mat_untouched"] = {
    "nodes": len(bpy.data.materials["竖向灯001_噪波滚动发光"].node_tree.nodes),
    "drivers": len(bpy.data.materials["竖向灯001_噪波滚动发光"].node_tree.animation_data.drivers)
    if bpy.data.materials["竖向灯001_噪波滚动发光"].node_tree.animation_data else 0}
rep["object_count"] = len(bpy.data.objects)
rep["total_sec"] = round(time.time() - rep["t0"], 2)
print("P57_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("P57_END")
