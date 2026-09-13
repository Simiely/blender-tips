# -*- coding: utf-8 -*-
# P58 —— 决定性实验（干净版）：改自定义属性后，驱动到底要什么 tag 才会重算？
#
# P57 的矩阵有个陷阱：它反复用【同一个材质 datablock】换驱动，
#   而换完驱动后没有强制重算 ⇒ 读到的 evaluated 副本还是【上一个驱动】的结果（脏读）。
#   ⇒ B 行（SINGLE_PROP）全部读出 14.0，等于没测到。
#
# 本实验：两种驱动类型各用【一个专属新材质】，每个采样点【只施加一种 tag】，逐点读。
# 全部挂在主场景里的真实物体上（材质必须在被求值的依赖图里），做完删净。
import bpy, json, time

PFX = "__P58"
rep = {"t0": time.time()}
main = bpy.context.scene


def wipe():
    for o in list(bpy.data.objects):
        if o.name.startswith(PFX):
            try: bpy.data.objects.remove(o, do_unlink=True)
            except Exception: pass
    for m in list(bpy.data.materials):
        if m.name.startswith(PFX):
            try: bpy.data.materials.remove(m, do_unlink=True)
            except Exception: pass
    for k in [k for k in bpy.app.driver_namespace if k.startswith("__p58")]:
        del bpy.app.driver_namespace[k]


wipe()


def make_case(tag_name, use_single):
    """造一组：控制器空物体 + 平面物体 + 材质 + 一条驱动。返回操控用的句柄 dict。"""
    me = bpy.data.meshes.new(PFX + "MESH_" + tag_name)
    me.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
    me.update()
    obj = bpy.data.objects.new(PFX + "OBJ_" + tag_name, me)
    main.collection.objects.link(obj)

    mat = bpy.data.materials.new(PFX + "MAT_" + tag_name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    vnode = nt.nodes.new('ShaderNodeValue')       # 输出一个纯数值
    vnode.name = "V"
    outn = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(vnode.outputs[0], outn.inputs[0])
    obj.data.materials.append(mat)               # ★ 必须挂到真实物体上

    ctl = bpy.data.objects.new(PFX + "CTL_" + tag_name, None)
    main.collection.objects.link(ctl)
    ctl["v"] = 0.0

    nt.animation_data_create()
    fc = vnode.outputs[0].driver_add('default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    if use_single:
        var = d.variables.new()
        var.name = 'v'
        var.type = 'SINGLE_PROP'
        t = var.targets[0]
        t.id_type = 'OBJECT'; t.id = ctl; t.data_path = '["v"]'
        d.expression = 'v'
    else:
        fn = "__p58_ns_" + tag_name
        bpy.app.driver_namespace[fn] = (lambda c=ctl: float(c.get("v", 0.0)))
        d.expression = fn + '()'
    fc.update()
    return {"obj": obj, "mat": mat, "nt": nt, "vnode": vnode, "ctl": ctl, "objname": obj.name}


def read(case):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = case["mat"].evaluated_get(dg).node_tree.nodes["V"]
    return round(float(ev.outputs[0].default_value), 4)


def run_case(tag_name, use_single):
    case = make_case(tag_name, use_single)
    ctl, mat, nt = case["ctl"], case["mat"], case["nt"]
    rows = []

    def step(label, value, tagfn=None, post=None):
        ctl["v"] = float(value)
        if tagfn is not None:
            tagfn()
        if post is not None:
            post()
        rows.append({"step": label, "set": value, "read": read(case),
                     "ok_expected": value})

    # 基线：三重 tag 强制一次完整求值
    def triple():
        ctl.update_tag(); mat.update_tag(); nt.update_tag(); bpy.context.view_layer.update()
    step("基线 v=1 + 三重 tag", 1.0, triple)

    # ★ 核心问题：改属性【不 tag】，只 view_layer.update()
    step("v=2 【不 tag】+ view_layer.update()", 2.0, None, bpy.context.view_layer.update)

    # 只 tag 控制器
    step("v=3 + ctl.update_tag()", 3.0,
         lambda: ctl.update_tag(), bpy.context.view_layer.update)

    # 只 tag 材质
    step("v=4 + mat.update_tag()", 4.0,
         lambda: mat.update_tag(), bpy.context.view_layer.update)

    # 只 tag 节点树
    step("v=5 + nt.update_tag()", 5.0,
         lambda: nt.update_tag(), bpy.context.view_layer.update)

    # depsgraph.update()
    def dgu():
        bpy.context.evaluated_depsgraph_get().update()
    step("v=6 + depsgraph.update()", 6.0, dgu)

    # frame_set(同一帧)
    def fs():
        main.frame_set(main.frame_current)
    step("v=7 + frame_set(同帧)", 7.0, fs, bpy.context.view_layer.update)

    # 三重 tag 兜底
    step("v=8 + 三重 tag", 8.0, triple)

    return {"case": tag_name, "use_single_prop": use_single, "rows": rows}


rep["A_namespace_function"] = run_case("A_ns", False)
rep["B_single_prop"] = run_case("B_sp", True)

# ---------- 顺带：属性变更后【什么都不做】，交给时间（看门狗关不掉，但本实验物体不在它的名单里）----------
ctl = bpy.data.objects[PFX + "CTL_B_sp"]
ctl["v"] = 99.0
rep["time_only_setup"] = {"v": 99.0, "note": "本请求内不 tag 不 update，下一次请求再看"}
rep["time_only_read_now"] = None
try:
    rep["time_only_read_now"] = round(float(
        bpy.data.materials[PFX + "MAT_B_sp"].evaluated_get(
            bpy.context.evaluated_depsgraph_get()).node_tree.nodes["V"].outputs[0].default_value), 4)
except Exception as e:
    rep["time_only_read_now"] = repr(e)

rep["object_count"] = len(bpy.data.objects)
rep["scene_now"] = main.name
print("P58_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("P58_END")
