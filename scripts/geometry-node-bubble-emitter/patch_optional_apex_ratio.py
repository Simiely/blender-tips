import bpy
import json

OUT = r"D:/workbuddy/2026-11-23-17-56-14/bubble_slow_fall_report.json"
PREFIX = "缓降_"


def feed(value, socket):
    if hasattr(value, "is_output"):
        ng.links.new(value, socket)
    else:
        socket.default_value = float(value)


def node(label):
    return ng.nodes.get(label)


def inp(n, key=0):
    return n.inputs[key] if isinstance(key, int) else n.inputs[key]


def out(n, key=0):
    return n.outputs[key] if isinstance(key, int) else n.outputs[key]


def new_node(node_type, label, x, y):
    n = ng.nodes.new(node_type)
    n.label = PREFIX + label
    n.name = PREFIX + label
    n.location = (x, y)
    return n


def math_node(op, label, x, y, a=None, b=None):
    n = new_node("ShaderNodeMath", label, x, y)
    n.operation = op
    if a is not None:
        feed(a, inp(n, 0))
    if b is not None:
        feed(b, inp(n, 1))
    return n


def clear_input(label, key=0):
    sock = inp(node(label), key)
    for link in list(ng.links):
        if link.to_socket == sock:
            ng.links.remove(link)
    return sock


def add_driver(socket, ctrl, prop):
    drv = socket.driver_add("default_value").driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "v"
    var.type = "SINGLE_PROP"
    t = var.targets[0]
    t.id_type = "OBJECT"
    t.id = ctrl
    t.data_path = '["%s"]' % prop
    drv.expression = "v"


def main():
    global ng
    ng = bpy.data.node_groups.get("泡泡发射_GN")
    ctrl = bpy.data.objects.get("泡泡控制")
    scene = bpy.context.scene
    if ng is None or ctrl is None:
        raise RuntimeError("missing node group or controller")

    saved_frame = scene.frame_current
    old_props = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")}

    if "顶点比例" not in ctrl:
        ctrl["顶点比例"] = 0.35
        ui = ctrl.id_properties_ui("顶点比例")
        ui.update(min=0.2, max=0.6, default=0.35,
                  description="高度曲线顶点位置；0.5=对称，越小下落越慢")

    for n in list(ng.nodes):
        if n.label.startswith(PREFIX) or n.name.startswith(PREFIX):
            ng.nodes.remove(n)

    q = out(node("生命周期比例 q"), 0)
    one = out(node("1"), 0)

    apex_node = new_node("ShaderNodeValue", "顶点比例", -3200, 200)
    apex = out(apex_node, 0)
    apex.default_value = float(ctrl["顶点比例"])
    add_driver(apex, ctrl, "顶点比例")

    apex_inv = math_node("SUBTRACT", "下落占比", -2980, 260, one, apex)
    q_up_raw = math_node("DIVIDE", "上升原始", -2980, 140, q, apex)
    q_up_clamp = math_node("MINIMUM", "上升钳制", -2760, 140, out(q_up_raw), one)
    up_part = math_node("MULTIPLY", "上升半段", -2540, 140, out(q_up_clamp), 0.5)

    q_minus = math_node("SUBTRACT", "过顶点时间", -2980, 40, q, apex)
    down_raw = math_node("DIVIDE", "下降原始", -2760, 40, out(q_minus), out(apex_inv))
    down_pos = math_node("MAXIMUM", "下降下限", -2540, 40, out(down_raw), 0.0)
    down_clamp = math_node("MINIMUM", "下降钳制", -2320, 40, out(down_pos), one)
    down_part = math_node("MULTIPLY", "下降半段", -2100, 40, out(down_clamp), 0.5)

    q_z = math_node("ADD", "高度时间", -1880, 100, out(up_part), out(down_part))
    q_z2 = math_node("MULTIPLY", "高度时间平方", -1660, 100, out(q_z), out(q_z))

    pi_sock = clear_input("πq", 0)
    feed(out(q_z), pi_sock)
    fall_sock = clear_input("下落项", 1)
    feed(out(q_z2), fall_sock)

    ctrl.update_tag(refresh={"OBJECT"})
    ng.update_tag()
    bpy.context.view_layer.update()
    scene.frame_set(saved_frame)
    bpy.context.view_layer.update()

    report = {
        "file": bpy.data.filepath,
        "frame_current": scene.frame_current,
        "old_props": old_props,
        "new_props": {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")},
        "node_count": len(ng.nodes),
        "link_count": len(ng.links),
        "new_node_labels": [n.label for n in ng.nodes if n.label.startswith(PREFIX)],
        "changes": [
            "新增顶点比例参数，默认 0.35",
            "高度曲线用分段线性时间重映射：顶点前占 0.5，顶点后占 0.5",
            "只改高度曲线；横向扩散、淡入淡出、随机消散不变",
            "顶点比例 0.5 可恢复原对称曲线；越小下落越慢",
        ],
        "note": "桥只改内存，未保存 .blend",
    }
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_SLOW_FALL_OK")


try:
    main()
except Exception as e:
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump({"error": repr(e), "pass": False}, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_SLOW_FALL_ERROR")
