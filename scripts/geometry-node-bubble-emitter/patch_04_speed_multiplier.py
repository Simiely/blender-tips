import bpy
import json

OUT = r"D:/workbuddy/2026-11-23-17-56-14/bubble_speed_multiplier_report.json"
PREFIX = "倍率_"


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

    old_props = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")}
    old_frame = scene.frame_current

    ctrl["生命周期"] = 96.0
    if "慢速倍率" not in ctrl:
        ctrl["慢速倍率"] = 2.5

    ui = ctrl.id_properties_ui("生命周期")
    ui.update(min=24.0, max=240.0, default=96.0,
              description="基础生命周期帧数；实际帧数=生命周期×慢速倍率")
    ui = ctrl.id_properties_ui("慢速倍率")
    ui.update(min=0.5, max=6.0, default=2.5,
              description="整体时间倍率；1=原速，2.5=当前慢速，越大越慢")

    for n in list(ng.nodes):
        if n.label.startswith(PREFIX) or n.name.startswith(PREFIX):
            ng.nodes.remove(n)

    slow_node = new_node("ShaderNodeValue", "慢速倍率", -3400, 300)
    slow = out(slow_node, 0)
    slow.default_value = float(ctrl["慢速倍率"])
    add_driver(slow, ctrl, "慢速倍率")

    base_life = out(node("生命周期"), 0)
    eff_node = new_node("ShaderNodeMath", "有效生命周期", -3180, 300)
    eff_node.operation = "MULTIPLY"
    feed(base_life, inp(eff_node, 0))
    feed(slow, inp(eff_node, 1))
    eff_life = out(eff_node, 0)

    for label in ("相位帧", "循环年龄", "生命周期比例 q"):
        sock = clear_input(label, 1)
        feed(eff_life, sock)

    ctrl.update_tag(refresh={"OBJECT"})
    ng.update_tag()
    bpy.context.view_layer.update()
    scene.frame_set(old_frame)
    bpy.context.view_layer.update()

    report = {
        "file": bpy.data.filepath,
        "old_frame": old_frame,
        "frame_current": scene.frame_current,
        "old_props": old_props,
        "new_props": {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")},
        "effective_life": float(ctrl["生命周期"]) * float(ctrl["慢速倍率"]),
        "node_count": len(ng.nodes),
        "link_count": len(ng.links),
        "new_node_labels": [n.label for n in ng.nodes if n.label.startswith(PREFIX)],
        "changes": [
            "生命周期 240 -> 96（基础值）",
            "新增慢速倍率，默认 2.5",
            "相位帧/循环年龄/生命周期比例 均改用 生命周期×慢速倍率",
            "有效生命周期保持 240，当前画面不变",
        ],
        "note": "桥只改内存，未保存 .blend",
    }
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_SPEED_MULTIPLIER_OK")


try:
    main()
except Exception as e:
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump({"error": repr(e), "pass": False}, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_SPEED_MULTIPLIER_ERROR")
