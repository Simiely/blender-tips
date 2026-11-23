import bpy
import json

OUT = r"D:/workbuddy/2026-11-23-17-56-14/bubble_fade_kill_report.json"
PREFIX = "修复_"


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


def random_node(label, x, y, seed_socket, id_socket, min_v, max_v):
    n = new_node("FunctionNodeRandomValue", label, x, y)
    n.data_type = "FLOAT"
    inp(n, "Min").default_value = float(min_v)
    inp(n, "Max").default_value = float(max_v)
    feed(id_socket, inp(n, "ID"))
    feed(seed_socket, inp(n, "Seed"))
    return out(n, "Value")


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


def smooth_step(t, label, x, y, one):
    t2 = math_node("MULTIPLY", label + "_sq", x, y, t, t)
    two_t = math_node("MULTIPLY", label + "_2t", x, y - 80, t, 2.0)
    three = math_node("SUBTRACT", label + "_3minus", x + 180, y - 80, one, out(two_t))
    return math_node("MULTIPLY", label + "_smooth", x + 360, y, out(t2), out(three))


def main():
    global ng
    ng = bpy.data.node_groups.get("泡泡发射_GN")
    ctrl = bpy.data.objects.get("泡泡控制")
    scene = bpy.context.scene
    if ng is None or ctrl is None:
        raise RuntimeError("missing node group or controller")

    old_props = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")}

    if "下落消散" not in ctrl:
        ctrl["下落消散"] = 0.35
        ui = ctrl.id_properties_ui("下落消散")
        ui.update(min=0.0, max=1.0, default=0.35,
                  description="下落阶段随机提前消散的比例，0=不消散")

    for n in list(ng.nodes):
        if n.label.startswith(PREFIX) or n.name.startswith(PREFIX):
            ng.nodes.remove(n)

    q = out(node("生命周期比例 q"), 0)
    born = out(node("优化_已出生"), 0)
    one = out(node("1"), 0)
    seed = out(node("种子"), 0)
    bubble_id = out(node("泡泡ID"), "Index")
    orig_scale = out(node("泡泡缩放"), 0)

    v_kill_node = new_node("ShaderNodeValue", "下落消散", -2800, 200)
    v_kill = out(v_kill_node, 0)
    v_kill.default_value = float(ctrl["下落消散"])
    add_driver(v_kill, ctrl, "下落消散")

    seed_d = math_node("ADD", "种子D", -2580, 320, seed, 53)
    seed_q = math_node("ADD", "种子Q", -2580, 220, seed, 67)
    r_kill = random_node("随机消散判定", -2360, 320, out(seed_d), bubble_id, 0.0, 1.0)
    r_death_q = random_node("随机死亡点", -2360, 220, out(seed_q), bubble_id, 0.55, 0.95)

    kill_flag = math_node("LESS_THAN", "消散标记", -2140, 320, r_kill, v_kill)
    death_span = math_node("SUBTRACT", "死亡跨度", -2140, 220, one, r_death_q)
    kill_part = math_node("MULTIPLY", "消散提前量", -1920, 270, out(kill_flag), out(death_span))
    death_q = math_node("SUBTRACT", "死亡比例", -1700, 270, one, out(kill_part))

    q_visible = math_node("LESS_THAN", "未死亡", -1480, 320, q, out(death_q))
    visible = math_node("MULTIPLY", "最终可见", -1260, 320, born, out(q_visible))
    clear_input("实例化泡泡", "Selection")
    feed(out(visible), inp(node("实例化泡泡"), "Selection"))

    fade_len = new_node("ShaderNodeValue", "淡隐长度", -2800, -60)
    fade_socket = out(fade_len, 0)
    fade_socket.default_value = 0.08

    in_raw = math_node("DIVIDE", "淡入原始", -2580, -60, q, fade_socket)
    in_clamp = math_node("MINIMUM", "淡入钳制", -2360, -60, out(in_raw), one)
    fade_in = smooth_step(out(in_clamp), "淡入", -2140, -60, one)

    remain = math_node("SUBTRACT", "剩余寿命", -2580, -180, out(death_q), q)
    out_raw = math_node("DIVIDE", "淡出原始", -2360, -180, out(remain), fade_socket)
    out_hi = math_node("MINIMUM", "淡出上限", -2140, -180, out(out_raw), one)
    out_lo = math_node("MAXIMUM", "淡出钳制", -1920, -180, out(out_hi), 0.0)
    fade_out = smooth_step(out(out_lo), "淡出", -1700, -180, one)

    fade = math_node("MULTIPLY", "淡隐系数", -1260, -60, out(fade_in), out(fade_out))
    final_scale = math_node("MULTIPLY", "最终缩放", -1040, -60, orig_scale, out(fade))

    for axis in ("X", "Y", "Z"):
        sock = clear_input("缩放向量", axis)
        feed(out(final_scale), sock)

    ctrl.update_tag(refresh={"OBJECT"})
    ng.update_tag()
    bpy.context.view_layer.update()
    scene.frame_set(150)
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
            "出生与死亡两端按生命周期比例 0.08 做平滑缩放淡入淡出",
            "下落阶段 q>0.55 按随机阈值提前消散，消散比例由下落消散控制",
            "消散不是硬删除：死亡点附近同样平滑缩小到 0",
            "保留起始帧门控、范围匹配、边界钳制",
        ],
        "note": "桥只改内存，未保存 .blend",
    }
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_FADE_KILL_OK")


try:
    main()
except Exception as e:
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump({"error": repr(e), "pass": False}, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_FADE_KILL_ERROR")
