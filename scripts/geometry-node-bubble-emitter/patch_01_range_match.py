import bpy
import json

OUT = r"D:/workbuddy/2026-11-23-17-56-14/bubble_optimize_report.json"
PREFIX = "优化_"


def feed(value, socket):
    if hasattr(value, "is_output"):
        ng.links.new(value, socket)
    else:
        socket.default_value = float(value)


def node(label):
    return ng.nodes.get(label)


def inp(n, key=0):
    if isinstance(key, int):
        return n.inputs[key]
    return n.inputs[key]


def out(n, key=0):
    if isinstance(key, int):
        return n.outputs[key]
    return n.outputs[key]


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
    n = node(label)
    if n is None:
        raise RuntimeError("missing node: " + label)
    sock = inp(n, key)
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

    old_props = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")}

    if "范围匹配" not in ctrl:
        ctrl["范围匹配"] = 1.0
        ui = ctrl.id_properties_ui("范围匹配")
        ui.update(min=0.0, max=1.0, default=1.0,
                  description="0=按发射口扩散，1=匹配泡泡范围正圆")

    for n in list(ng.nodes):
        if n.label.startswith(PREFIX) or n.name.startswith(PREFIX):
            ng.nodes.remove(n)

    frame = out(node("场景帧"), "Frame")
    start = out(node("起始帧"), 0)
    phase_frames = out(node("相位帧"), 0)
    smooth = out(node("扩散缓动"), 0)
    emit_x = out(node("发射口 XYZ"), "X")
    emit_y = out(node("发射口 XYZ"), "Y")
    center_x = out(node("圆心X"), 0)
    center_y = out(node("圆心Y"), 0)
    allowed_r = out(node("允许半径"), 0)
    spread = out(node("扩散"), 0)
    sqrt_u = out(node("sqrt(随机强度)"), 0)
    cos_a = out(node("cos(角度)"), 0)
    sin_a = out(node("sin(角度)"), 0)
    one = out(node("1"), 0)

    birth_frame = math_node("ADD", "出生帧", -2200, 200, start, phase_frames)
    birth_threshold = math_node("SUBTRACT", "出生阈值", -1980, 200, out(birth_frame), 0.5)
    born = math_node("GREATER_THAN", "已出生", -1760, 200, frame, out(birth_threshold))
    inst = node("实例化泡泡")
    clear_input("实例化泡泡", "Selection")
    feed(out(born), inp(inst, "Selection"))

    v_match_node = new_node("ShaderNodeValue", "范围匹配", -2200, -40)
    v_match = out(v_match_node, 0)
    v_match.default_value = float(ctrl["范围匹配"])
    add_driver(v_match, ctrl, "范围匹配")

    inv_match = math_node("SUBTRACT", "反向匹配", -1980, -40, one, v_match)
    old_r = math_node("MULTIPLY", "旧目标半径", -1980, -140, spread, sqrt_u)
    new_r = math_node("MULTIPLY", "新目标半径", -1980, -240, allowed_r, sqrt_u)
    old_part = math_node("MULTIPLY", "旧半径权重", -1760, -140, out(old_r), out(inv_match))
    new_part = math_node("MULTIPLY", "新半径权重", -1760, -240, out(new_r), v_match)
    target_r = math_node("ADD", "目标半径", -1540, -190, out(old_part), out(new_part))

    emit_x_part = math_node("MULTIPLY", "发射口中心权重", -1980, -360, emit_x, out(inv_match))
    center_x_part = math_node("MULTIPLY", "圆心X权重", -1980, -440, center_x, v_match)
    mix_center_x = math_node("ADD", "混合中心X", -1760, -400, out(emit_x_part), out(center_x_part))
    emit_y_part = math_node("MULTIPLY", "发射口中心权重Y", -1980, -520, emit_y, out(inv_match))
    center_y_part = math_node("MULTIPLY", "圆心Y权重", -1980, -600, center_y, v_match)
    mix_center_y = math_node("ADD", "混合中心Y", -1760, -560, out(emit_y_part), out(center_y_part))

    endpoint_dx = math_node("MULTIPLY", "终点偏移X", -1320, -140, cos_a, out(target_r))
    endpoint_dy = math_node("MULTIPLY", "终点偏移Y", -1320, -240, sin_a, out(target_r))
    endpoint_x = math_node("ADD", "终点X", -1100, -140, out(mix_center_x), out(endpoint_dx))
    endpoint_y = math_node("ADD", "终点Y", -1100, -240, out(mix_center_y), out(endpoint_dy))

    to_end_x = math_node("SUBTRACT", "到终点X", -880, -140, out(endpoint_x), emit_x)
    to_end_y = math_node("SUBTRACT", "到终点Y", -880, -240, out(endpoint_y), emit_y)
    move_x = math_node("MULTIPLY", "X位移", -660, -140, out(to_end_x), smooth)
    move_y = math_node("MULTIPLY", "Y位移", -660, -240, out(to_end_y), smooth)
    x_interp = math_node("ADD", "插值X", -440, -140, emit_x, out(move_x))
    y_interp = math_node("ADD", "插值Y", -440, -240, emit_y, out(move_y))

    sock_x = clear_input("相对圆心X", 0)
    feed(out(x_interp), sock_x)
    sock_y = clear_input("相对圆心Y", 0)
    feed(out(y_interp), sock_y)

    ctrl.update_tag(refresh={"OBJECT"})
    ng.update_tag()
    bpy.context.view_layer.update()
    scene.frame_set(60)
    bpy.context.view_layer.update()

    report = {
        "file": bpy.data.filepath,
        "frame_current_set": scene.frame_current,
        "old_props": old_props,
        "new_props": {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")},
        "node_count": len(ng.nodes),
        "link_count": len(ng.links),
        "new_node_labels": [n.label for n in ng.nodes if n.label.startswith(PREFIX)],
        "changes": [
            "按出生帧=起始帧+随机相位*生命周期做逐泡泡显隐",
            "新增范围匹配参数：0=旧发射口扩散，1=匹配泡泡范围正圆",
            "保留原有边界钳制作为安全兜底",
        ],
        "note": "桥只改内存，未保存 .blend",
    }
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_OPTIMIZE_OK")


try:
    main()
except Exception as e:
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump({"error": repr(e), "pass": False}, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_OPTIMIZE_ERROR")
