import bpy
import json
import math

REPORT = r"D:/workbuddy/2026-11-23-17-56-14/bubble_build_report.json"
PARAMS = r"D:/workbuddy/2026-11-23-17-56-14/bubble_params.json"

CTRL_NAME = "泡泡控制"
SRC_NAME = "泡泡_源球"
SYS_NAME = "泡泡发射_系统"
COL_NAME = "泡泡系统"
NG_NAME = "泡泡发射_GN"
MAT_NAME = "泡泡_半透明材质"


def feed(value, socket):
    if hasattr(value, "is_output"):
        ng.links.new(value, socket)
    else:
        socket.default_value = float(value)


def new_node(node_type, label, x, y):
    n = ng.nodes.new(node_type)
    n.label = label
    n.name = label
    n.location = (x, y)
    return n


def out(node, key=0):
    if isinstance(key, int):
        return node.outputs[key]
    return node.outputs[key]


def inp(node, key=0):
    if isinstance(key, int):
        return node.inputs[key]
    return node.inputs[key]


def math_node(op, label, x, y, a=None, b=None):
    n = new_node("ShaderNodeMath", label, x, y)
    n.operation = op
    if a is not None:
        feed(a, inp(n, 0))
    if b is not None:
        feed(b, inp(n, 1))
    return n


def vec_node(op, label, x, y, a=None, b=None):
    n = new_node("ShaderNodeVectorMath", label, x, y)
    n.operation = op
    if a is not None:
        feed(a, inp(n, 0))
    if b is not None:
        feed(b, inp(n, 1))
    return n


def vec_length(label, x, y, vector_socket):
    n = vec_node("LENGTH", label, x, y, vector_socket, None)
    return out(n, "Value")


def combine(label, x, y, xx, yy, zz):
    n = new_node("ShaderNodeCombineXYZ", label, x, y)
    feed(xx, inp(n, "X"))
    feed(yy, inp(n, "Y"))
    feed(zz, inp(n, "Z"))
    return out(n, "Vector")


def separate(label, x, y, vector_socket):
    n = new_node("ShaderNodeSeparateXYZ", label, x, y)
    feed(vector_socket, inp(n, "Vector"))
    return out(n, "X"), out(n, "Y"), out(n, "Z")


def value_node(label, x, y, default, prop=None, ctrl=None):
    n = new_node("ShaderNodeValue", label, x, y)
    s = out(n, 0)
    s.default_value = float(default)
    if prop is not None:
        drv = s.driver_add("default_value").driver
        drv.type = "SCRIPTED"
        var = drv.variables.new()
        var.name = "v"
        var.type = "SINGLE_PROP"
        t = var.targets[0]
        t.id_type = "OBJECT"
        t.id = ctrl
        t.data_path = '["%s"]' % prop
        drv.expression = "v"
    return s


def random_node(label, x, y, seed_socket, id_socket, min_v=0.0, max_v=1.0):
    n = new_node("FunctionNodeRandomValue", label, x, y)
    n.data_type = "FLOAT"
    inp(n, "Min").default_value = float(min_v)
    inp(n, "Max").default_value = float(max_v)
    feed(id_socket, inp(n, "ID"))
    feed(seed_socket, inp(n, "Seed"))
    return out(n, "Value")


def set_prop(ctrl, name, value, min_v, max_v, description):
    ctrl[name] = value
    ui = ctrl.id_properties_ui(name)
    ui.update(min=min_v, max=max_v, default=value, description=description)


def make_material():
    mat = bpy.data.materials.get(MAT_NAME)
    if mat is None:
        mat = bpy.data.materials.new(MAT_NAME)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        for n in nodes:
            if n.type == "BSDF_PRINCIPLED":
                bsdf = n
                break
    if bsdf is not None:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.72, 0.9, 1.0, 1.0)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.12
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = 0.35
        if "Transmission Weight" in bsdf.inputs:
            bsdf.inputs["Transmission Weight"].default_value = 0.35
    if hasattr(mat, "surface_render_method"):
        try:
            mat.surface_render_method = "DITHERED"
        except Exception:
            pass
    elif hasattr(mat, "blend_method"):
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass
    return mat


def main():
    global ng
    scene = bpy.context.scene
    emitter = bpy.data.objects.get("发射口")
    area = bpy.data.objects.get("泡泡范围")
    if emitter is None:
        raise RuntimeError("missing object: 发射口")
    if area is None or area.type != "MESH":
        raise RuntimeError("missing mesh: 泡泡范围")

    for name in (CTRL_NAME, SRC_NAME, SYS_NAME):
        old = bpy.data.objects.get(name)
        if old is not None:
            bpy.data.objects.remove(old, do_unlink=True)
    old_ng = bpy.data.node_groups.get(NG_NAME)
    if old_ng is not None:
        bpy.data.node_groups.remove(old_ng)

    col = bpy.data.collections.get(COL_NAME)
    if col is None:
        col = bpy.data.collections.new(COL_NAME)
        scene.collection.children.link(col)

    ctrl = bpy.data.objects.new(CTRL_NAME, None)
    col.objects.link(ctrl)
    ctrl.empty_display_type = "SPHERE"
    ctrl.empty_display_size = 0.8
    ctrl.location = (
        float(emitter.matrix_world.translation.x),
        float(emitter.matrix_world.translation.y),
        float(emitter.matrix_world.translation.z) + 1.0,
    )

    params = [
        ("泡泡数量", 360, 60, 1200, "实例泡泡数量"),
        ("泡泡半径", 0.16, 0.05, 0.5, "单个泡泡半径"),
        ("扩散半径", 4.1, 0.5, 4.4, "相对发射口的最大水平扩散"),
        ("上升高度", 4.5, 1.0, 9.0, "泡泡相对发射口的抬升"),
        ("生命周期", 96.0, 24.0, 240.0, "单个泡泡循环帧数"),
        ("起始帧", 1.0, 0.0, 500.0, "发射起始帧"),
        ("随机种子", 1, 0, 999, "随机相位和方向种子"),
        ("边界余量", 0.15, 0.02, 0.8, "泡泡与边界的安全留白"),
    ]
    for name, val, lo, hi, desc in params:
        set_prop(ctrl, name, val, lo, hi, desc)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1.0, location=(0, 0, 0))
    src = bpy.context.object
    src.name = SRC_NAME
    src.data.name = SRC_NAME + "_Mesh"
    src.hide_render = True
    src.hide_set(True)
    src.data.materials.clear()
    src.data.materials.append(make_material())
    for c in list(src.users_collection):
        c.objects.unlink(src)
    col.objects.link(src)

    mesh = bpy.data.meshes.new(SYS_NAME + "_Mesh")
    system = bpy.data.objects.new(SYS_NAME, mesh)
    col.objects.link(system)
    system.location = (0, 0, 0)
    system.rotation_euler = (0, 0, 0)
    system.scale = (1, 1, 1)

    ng = bpy.data.node_groups.new(NG_NAME, "GeometryNodeTree")
    if hasattr(ng, "is_modifier"):
        ng.is_modifier = True
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    v_count = value_node("数量", -1600, 900, 360, "泡泡数量", ctrl)
    v_radius = value_node("半径", -1600, 820, 0.16, "泡泡半径", ctrl)
    v_spread = value_node("扩散", -1600, 740, 4.1, "扩散半径", ctrl)
    v_rise = value_node("上升", -1600, 660, 4.5, "上升高度", ctrl)
    v_life = value_node("生命周期", -1600, 580, 96, "生命周期", ctrl)
    v_start = value_node("起始帧", -1600, 500, 1, "起始帧", ctrl)
    v_seed = value_node("种子", -1600, 420, 1, "随机种子", ctrl)
    v_margin = value_node("边界余量", -1600, 340, 0.15, "边界余量", ctrl)
    v_pi = value_node("PI", -1600, 260, math.pi)
    v_three = value_node("3", -1600, 180, 3.0)
    v_eps = value_node("EPS", -1600, 100, 0.0001)
    v_one = value_node("1", -1600, 20, 1.0)

    emit_info = new_node("GeometryNodeObjectInfo", "发射口位置", -1600, -100)
    emit_info.inputs["Object"].default_value = emitter
    if hasattr(emit_info, "transform_space"):
        emit_info.transform_space = "RELATIVE"
    emit_x, emit_y, emit_z = separate("发射口 XYZ", -1380, -100, out(emit_info, "Location"))

    area_info = new_node("GeometryNodeObjectInfo", "泡泡范围几何", -1600, -260)
    area_info.inputs["Object"].default_value = area
    area_info.inputs["As Instance"].default_value = False
    if hasattr(area_info, "transform_space"):
        area_info.transform_space = "RELATIVE"
    bbox = new_node("GeometryNodeBoundBox", "范围包围盒", -1380, -260)
    feed(out(area_info, "Geometry"), inp(bbox, "Geometry"))
    amin_x, amin_y, amin_z = separate("范围 Min", -1160, -340, out(bbox, "Min"))
    amax_x, amax_y, amax_z = separate("范围 Max", -1160, -180, out(bbox, "Max"))

    sum_x = math_node("ADD", "X min+max", -1160, -420, amin_x, amax_x)
    sum_y = math_node("ADD", "Y min+max", -1160, -500, amin_y, amax_y)
    center_x = math_node("MULTIPLY", "圆心X", -940, -340, out(sum_x), 0.5)
    center_y = math_node("MULTIPLY", "圆心Y", -940, -420, out(sum_y), 0.5)
    size_x = math_node("SUBTRACT", "范围宽", -940, -180, amax_x, amin_x)
    size_y = math_node("SUBTRACT", "范围高", -940, -260, amax_y, amin_y)
    min_side = math_node("MINIMUM", "min(宽,高)", -940, -340, out(size_x), out(size_y))
    half_min = math_node("MULTIPLY", "半宽高取小", -720, -220, out(min_side), 0.5)
    radius_less_bubble = math_node("SUBTRACT", "半径减泡泡", -720, -140, out(half_min), v_radius)
    limit_radius = math_node("SUBTRACT", "允许半径", -500, -220, out(radius_less_bubble), v_margin)
    floor_plus_radius = math_node("ADD", "地面加半径", -940, -60, amin_z, v_radius)
    end_z = math_node("ADD", "落地Z", -720, -60, out(floor_plus_radius), v_margin)
    drop = math_node("SUBTRACT", "下落量", -500, -60, emit_z, out(end_z))

    index = new_node("GeometryNodeInputIndex", "泡泡ID", -1600, -520)
    seed_a = math_node("ADD", "种子A", -1380, -520, v_seed, 11)
    seed_u = math_node("ADD", "种子B", -1380, -600, v_seed, 23)
    seed_s = math_node("ADD", "种子C", -1380, -680, v_seed, 37)
    r_phase = random_node("随机相位", -1160, -520, out(seed_a), out(index, "Index"), 0, 1)
    r_angle = random_node("随机角度", -1160, -600, out(seed_u), out(index, "Index"), 0, 2 * math.pi)
    r_u = random_node("随机强度", -1160, -680, out(seed_s), out(index, "Index"), 0, 1)
    r_size = random_node("随机大小", -1160, -760, out(seed_s), out(index, "Index"), 0.75, 1.25)

    scene_time = new_node("GeometryNodeInputSceneTime", "场景帧", -1600, -860)
    t0 = math_node("SUBTRACT", "帧减起始", -1380, -860, out(scene_time, "Frame"), v_start)
    phase_sec = math_node("MULTIPLY", "相位帧", -1160, -860, r_phase, v_life)
    t1 = math_node("SUBTRACT", "帧减相位", -940, -860, out(t0), out(phase_sec))
    age = math_node("FLOORED_MODULO", "循环年龄", -720, -860, out(t1), v_life)
    q = math_node("DIVIDE", "生命周期比例 q", -500, -860, out(age), v_life)

    q2 = math_node("MULTIPLY", "q²", -280, -940, out(q), out(q))
    two_q = math_node("MULTIPLY", "2q", -500, -940, out(q), 2.0)
    three_minus = math_node("SUBTRACT", "3-2q", -280, -1020, v_three, out(two_q))
    smooth = math_node("MULTIPLY", "扩散缓动", -60, -980, out(q2), out(three_minus))
    piq = math_node("MULTIPLY", "πq", -500, -1100, out(q), v_pi)
    sinpiq = math_node("SINE", "sin(πq)", -280, -1100, out(piq))

    sqrt_u = math_node("SQRT", "sqrt(随机强度)", -280, -760, r_u)
    r_base = math_node("MULTIPLY", "扩散基值", -60, -760, v_spread, out(sqrt_u))
    r_final = math_node("MULTIPLY", "当前扩散半径", 160, -760, out(r_base), out(smooth))

    cos_a = math_node("COSINE", "cos(角度)", -60, -600, r_angle)
    sin_a = math_node("SINE", "sin(角度)", -60, -680, r_angle)
    dx = math_node("MULTIPLY", "水平偏移X", 160, -600, out(cos_a), out(r_final))
    dy = math_node("MULTIPLY", "水平偏移Y", 160, -680, out(sin_a), out(r_final))
    x_raw = math_node("ADD", "原始X", 380, -600, emit_x, out(dx))
    y_raw = math_node("ADD", "原始Y", 380, -680, emit_y, out(dy))

    rise_term = math_node("MULTIPLY", "上升项", 160, -1080, v_rise, out(sinpiq))
    drop_term = math_node("MULTIPLY", "下落项", 380, -940, out(drop), out(q2))
    z_mid = math_node("ADD", "发射Z加上升", 380, -1080, emit_z, out(rise_term))
    z_raw = math_node("SUBTRACT", "原始Z", 600, -1020, out(z_mid), out(drop_term))

    ddx = math_node("SUBTRACT", "相对圆心X", 600, -600, out(x_raw), out(center_x))
    ddy = math_node("SUBTRACT", "相对圆心Y", 600, -680, out(y_raw), out(center_y))
    ddx2 = math_node("MULTIPLY", "dx²", 820, -600, out(ddx), out(ddx))
    ddy2 = math_node("MULTIPLY", "dy²", 820, -680, out(ddy), out(ddy))
    dist2 = math_node("ADD", "距离²", 1040, -640, out(ddx2), out(ddy2))
    dist = math_node("SQRT", "距离", 1260, -640, out(dist2))
    dist_safe = math_node("MAXIMUM", "距离下限", 1480, -640, out(dist), v_eps)
    ratio = math_node("DIVIDE", "边界比例", 1700, -640, out(limit_radius), out(dist_safe))
    ratio_clamped = math_node("MINIMUM", "比例钳制", 1920, -640, out(ratio), v_one)
    scaled_dx = math_node("MULTIPLY", "钳制后dx", 2140, -600, out(ddx), out(ratio_clamped))
    scaled_dy = math_node("MULTIPLY", "钳制后dy", 2140, -680, out(ddy), out(ratio_clamped))
    x_final = math_node("ADD", "最终X", 2360, -600, out(center_x), out(scaled_dx))
    y_final = math_node("ADD", "最终Y", 2360, -680, out(center_y), out(scaled_dy))

    pos = combine("最终位置", 2580, -760, out(x_final), out(y_final), out(z_raw))
    bubble_size = math_node("MULTIPLY", "泡泡缩放", 2360, -940, v_radius, r_size)
    scale_vec = combine("缩放向量", 2580, -940, out(bubble_size), out(bubble_size), out(bubble_size))

    line = new_node("GeometryNodeMeshLine", "生成泡泡点", 2580, -180)
    line.mode = "OFFSET"
    feed(v_count, inp(line, "Count"))
    inp(line, "Start Location").default_value = (0.0, 0.0, 0.0)
    inp(line, "Offset").default_value = (0.0, 0.0, 0.0)

    src_info = new_node("GeometryNodeObjectInfo", "源球实例", 2580, -1120)
    src_info.inputs["Object"].default_value = src
    src_info.inputs["As Instance"].default_value = True
    if hasattr(src_info, "transform_space"):
        src_info.transform_space = "ORIGINAL"

    set_pos = new_node("GeometryNodeSetPosition", "设置泡泡位置", 2820, -180)
    feed(out(line, "Mesh"), inp(set_pos, "Geometry"))
    feed(pos, inp(set_pos, "Position"))

    instance = new_node("GeometryNodeInstanceOnPoints", "实例化泡泡", 3060, -760)
    feed(out(set_pos, "Geometry"), inp(instance, "Points"))
    feed(out(src_info, "Geometry"), inp(instance, "Instance"))
    feed(scale_vec, inp(instance, "Scale"))

    group_out = new_node("NodeGroupOutput", "输出", 3060, -760)
    feed(out(instance, "Instances"), inp(group_out, "Geometry"))

    mod = system.modifiers.new("泡泡发射", "NODES")
    mod.node_group = ng

    scene.frame_current = 48

    report = {
        "file": bpy.data.filepath,
        "scene": scene.name,
        "frame_current_set": scene.frame_current,
        "created": {
            "controller": CTRL_NAME,
            "source": SRC_NAME,
            "system": SYS_NAME,
            "collection": COL_NAME,
            "node_group": NG_NAME,
        },
        "params": {p[0]: p[1] for p in params},
        "node_count": len(ng.nodes),
        "link_count": len(ng.links),
        "emitter_unchanged": {
            "location": [round(float(v), 6) for v in emitter.matrix_world.translation],
            "rotation": [round(float(v), 6) for v in emitter.rotation_euler],
            "scale": [round(float(v), 6) for v in emitter.scale],
        },
        "area_unchanged": {
            "location": [round(float(v), 6) for v in area.matrix_world.translation],
            "rotation": [round(float(v), 6) for v in area.rotation_euler],
            "scale": [round(float(v), 6) for v in area.scale],
        },
        "note": "桥只改内存，未保存 .blend",
    }

    with open(REPORT, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    with open(PARAMS, "w", encoding="utf-8") as fp:
        json.dump(report["params"], fp, ensure_ascii=False, indent=2)
    print("BUBBLE_BUILD_OK")


try:
    main()
except Exception as e:
    with open(REPORT, "w", encoding="utf-8") as fp:
        json.dump({"error": repr(e)}, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_BUILD_ERROR")
