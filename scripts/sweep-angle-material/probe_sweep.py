# -*- coding: utf-8 -*-
# 渐变扫过材质 · UV 方向角 —— 只读侦察(经 9877 桥执行)
# 不改任何数据。先跑这个,再决定要不要 build / verify / maintain。
import bpy

# ═══ 配置(换工程改这里) ═══
PLANE = "平面"
MAT_NAME = "渐变扫过材质"
CTRL_NAME = "渐变控制"
RAMP_NODES = ("颜色渐变_扫过", "颜色渐变_水平")
KNOB_NAMES = ("扫过速度", "扫过角度", "扫过条数", "水平条数", "发光强度")
# ═════════════════════════

C, D, sc = bpy.context, bpy.data, bpy.context.scene

print("=== 场景 ===")
print("文件=%r  引擎=%r  分辨率=%dx%d@%d%%  帧=%d  fps=%s"
      % (D.filepath, sc.render.engine, sc.render.resolution_x, sc.render.resolution_y,
         sc.render.resolution_percentage, sc.frame_current, sc.render.fps))
print("OBJECTS=%r" % [(o.name, o.type) for o in D.objects])
print("MATERIALS=%r" % [(m.name, m.users, m.use_nodes) for m in D.materials])

print("=== 目标网格体 %r ===" % PLANE)
ob = D.objects.get(PLANE)
if ob is None:
    print("!! 找不到 %r" % PLANE)
else:
    mw = ob.matrix_world
    pts = [mw @ v.co for v in ob.data.vertices]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    print("顶点=%d 面=%d  材质槽=%r"
          % (len(ob.data.vertices), len(ob.data.polygons),
             [s.material.name if s.material else None for s in ob.material_slots]))
    print("世界包围盒: X %.4f..%.4f (%.4f) / Y %.4f..%.4f (%.4f) / Z %.4f..%.4f (%.4f)"
          % (min(xs), max(xs), max(xs) - min(xs), min(ys), max(ys), max(ys) - min(ys),
             min(zs), max(zs), max(zs) - min(zs)))
    # 法线轴: 看哪个世界轴的分量占优 ⇒ 那个轴就是"平面的法线",另两个轴构成 UV 平面
    if len(ob.data.polygons):
        acc = [0.0, 0.0, 0.0]
        rot = mw.to_3x3()
        for p in ob.data.polygons:
            n = rot @ p.normal
            for i in range(3):
                acc[i] += n[i]
        k = max(range(3), key=lambda i: abs(acc[i]))
        axis = "XYZ"[k]
        span = {"X": max(xs) - min(xs), "Y": max(ys) - min(ys), "Z": max(zs) - min(zs)}
        other = [a for a in "XYZ" if a != axis]
        print("平均世界法线=(%.4f, %.4f, %.4f) ⇒ 法线轴 = %s" % (acc[0], acc[1], acc[2], axis))
        print("★ 本材质用的是 Generated 坐标:平面张成的那两个轴 %s 就是「UV 平面」"
              " ⇒ 扫过角度 0° 沿其中长度较大的那个轴(两边等长时按 分离XYZ.X 的轴)" % ("/".join(other),))
        print("  轴跨度 X=%.4f Y=%.4f Z=%.4f" % (span["X"], span["Y"], span["Z"]))
    print("自定义属性=%r" % dict(ob.items()))

print("=== 控制器空对象 %r ===" % CTRL_NAME)
ctrl = D.objects.get(CTRL_NAME)
if ctrl is None:
    print("!! 不存在(材质若是「参数挂空对象」那版,就没法调参了)")
else:
    print("type=%s visible_get()=%s hide_render=%s loc=%s"
          % (ctrl.type, ctrl.visible_get(), ctrl.hide_render,
             tuple(round(v, 3) for v in ctrl.location)))
    print("selected=%s  ★ 活动对象=%r"
          % ([o.name for o in C.view_layer.objects if o.select_get()],
             C.view_layer.objects.active.name if C.view_layer.objects.active else None))
    for k in KNOB_NAMES:
        if k in ctrl:
            ui = ctrl.id_properties_ui(k).as_dict()
            print("  %-6s = %-10s soft=[%s, %s] hard=[%s, %s] desc=%r"
                  % (k, ctrl[k], ui.get("soft_min"), ui.get("soft_max"),
                     ui.get("min"), ui.get("max"), ui.get("description")))
        else:
            print("  %-6s !! 缺失" % k)
    extra = [k for k in ctrl.keys() if k not in KNOB_NAMES]
    if extra:
        print("  (额外属性: %r)" % extra)

print("=== 材质 %r ===" % MAT_NAME)
mat = D.materials.get(MAT_NAME)
if mat is None:
    print("!! 不存在")
else:
    nt = mat.node_tree
    print("use_nodes=%s  NODES=%d LINKS=%d  users=%d  fake_user=%s"
          % (mat.use_nodes, len(nt.nodes), len(nt.links), mat.users, mat.use_fake_user))
    for n in nt.nodes:
        extra = ""
        if n.bl_idname == "ShaderNodeMath":
            extra = " op=%s in1=%s" % (n.operation, n.inputs[1].default_value)
        elif n.bl_idname in ("ShaderNodeValue",):
            extra = " val=%.6f" % n.outputs[0].default_value
        elif n.bl_idname == "ShaderNodeValToRGB":
            extra = " stops=%d %r" % (len(n.color_ramp.elements),
                                      [(round(e.position, 3), tuple(round(c, 3) for c in e.color[:3]))
                                       for e in n.color_ramp.elements])
        elif n.bl_idname in ("ShaderNodeMix", "ShaderNodeMixRGB"):
            extra = " data=%s blend=%s" % (getattr(n, "data_type", "-"), n.blend_type)
        print("  %-14s %-28s%s" % (n.name, n.bl_idname, extra))
    print("--- 连线 ---")
    for l in nt.links:
        print("  %s.%s -> %s.%s" % (l.from_node.name, l.from_socket.name,
                                    l.to_node.name, l.to_socket.name))
    print("--- 驱动器 ---")
    drs = list(nt.animation_data.drivers) if nt.animation_data else []
    for f in drs:
        nm = f.data_path[7:].split('"')[0]
        vs = [(v.name, t.id.name if t.id else None, t.data_path)
              for v in f.driver.variables for t in v.targets]
        print("  %-8s type=%-9s valid=%-5s expr=%r" % (nm, f.driver.type, f.driver.is_valid, f.driver.expression))
        print("            vars=%r" % (vs,))
    print("驱动器数=%d" % len(drs))
    if len(drs):
        # ★ is_valid 必须在一次真正的图更新之后才可信
        C.evaluated_depsgraph_get().update()
        bad = [f.data_path for f in drs if not f.driver.is_valid]
        print("强刷新后 INVALID=%d %r" % (len(bad), bad))
    # 是否已经是"角度版"(有 数学_投影 / 角度_余弦)
    ang = ("数学_投影" in nt.nodes and "角度_余弦" in nt.nodes)
    print("★ 版本判定: %s" % ("角度版(UV 方向角)" if ang else "旧版(方向只有 ±1)"))

print("=== 材质被哪些对象使用 ===")
if mat is not None:
    for o in D.objects:
        for i, s in enumerate(o.material_slots):
            if s.material is mat:
                print("  %s 槽%d" % (o.name, i))
print("PROBE_SWEEP_OK")
