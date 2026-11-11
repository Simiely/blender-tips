# -*- coding: utf-8 -*-
"""
body_dive_param.py —— 刹车点头（车身俯仰）+ 强度滑块 + 间隙实测

用途:
  MODE='setup'     建/重建:控制_车身 上的 点头曲线(关键帧) + 点头强度(滑块)，
                   删掉车身自己的 rotation 关键帧，改为驱动 dive*k
  MODE='clearance' 只读:扫不同强度下【轮胎表面 → 车身曲面】最近距离，找穿模上限

要点:
  * Blender 里一个属性不能既有关键帧又被驱动 ⇒ 必须拆成 曲线属性 + 强度属性
  * 自定义属性的 min/max 会【真的钳制取值】，不只是限制滑块 ⇒ 内部曲线属性范围要留宽
  * 强度是【相对系数】 ⇒ 改了基准曲线的峰值，滑块 max 必须按新基准重量一遍
  * 非等比 scale 下动 rotation 是安全的（子级 matrix_parent_inverse 里的 S⁻¹ 会抵消），
    但要保距校验证伪；动 scale 会立刻拉开车身
  * 采样轮胎顶点必须【每帧重新取世界坐标】，否则量出假穿模

经桥执行:
  python bl.py body_dive_param.py
"""

import bpy
from mathutils import Vector

# ============================== CONFIG ==============================
MODE = 'setup'                     # 'setup' | 'clearance'
BODY = "绑定_车身"
ROOT = "绑定_车辆根"
CTRL_NAME = "控制_车身"
COLL_NAME = "绑定_主控"
PROP_CURVE = "点头曲线"
PROP_K = "点头强度"

# (帧, 值)。负值 = 车头下压。曲线形状，与强度无关
KEYS = [
    (88.0, 0.0),
    (92.0, 0.0),
    (96.0, -0.0100),      # 峰值：× 强度 0.65 ⇒ -0.37°
    (101.0, 0.0045),      # 回弹过冲
    (105.0, 0.0),         # 必须与速度曲线终点一致，否则末帧构图偏
    (112.0, 0.0),
]
DEFAULT_K = 0.65
K_MAX = 3.0                       # 实测 3.0 == -1.72°，间隙仍有 1.78 cm
K_SOFT_MAX = 1.5
CURVE_RANGE = 0.10                # 内部曲线属性的 min/max 对称留宽，别设 0 上限
WHEEL = "绑定_轮_右前"              # clearance 模式测这条轮胎
# ====================================================================


def iter_fcurves(ad):
    a = ad.action
    slot = getattr(ad, "action_slot", None)
    for layer in a.layers:
        for strip in layer.strips:
            bags = getattr(strip, "channelbags", None) or []
            for cb in bags:
                if slot is not None and getattr(cb, "slot", None) is not None and cb.slot != slot:
                    continue
                for fc in cb.fcurves:
                    yield cb, fc


def body_corners(body):
    pts = []
    for ch in body.children:
        if ch.type != 'MESH':
            continue
        m = ch.matrix_world
        for c in ch.bound_box:
            pts.append(m @ Vector(c))
    return pts


def nose_z(body):
    pts = body_corners(body)
    minx = min(p.x for p in pts)
    return min(p.z for p in pts if p.x <= minx + 0.20)


def tire_pts(wheel, step=20):
    out = []
    meshes = [c for c in wheel.children if c.type == 'MESH'] or [wheel]
    for m in meshes:
        mw = m.matrix_world
        vs = m.data.vertices
        for i in range(0, len(vs), step):
            out.append(mw @ vs[i].co)
    return out


def min_gap(body, pts):
    best = 1e9
    for o in body.children:
        if o.type != 'MESH':
            continue
        inv = o.matrix_world.inverted()
        mw = o.matrix_world
        for p in pts:
            ok, loc, nor, idx = o.closest_point_on_mesh(inv @ p)
            if ok:
                d = (mw @ loc - p).length
                if d < best:
                    best = d
    return best


def setup():
    body = bpy.data.objects[BODY]
    sc = bpy.context.scene

    # 1) 控制器
    ctrl = bpy.data.objects.get(CTRL_NAME)
    if ctrl is None:
        coll = bpy.data.collections.get(COLL_NAME)
        ctrl = bpy.data.objects.new(CTRL_NAME, None)
        ctrl.empty_display_type = 'PLAIN_AXES'
        ctrl.empty_display_size = 1.2
        ctrl.show_in_front = True
        ctrl.hide_render = True
        ctrl.location = (0.0, 0.0, 1.5)
        (coll or sc.collection).objects.link(ctrl)
        print("已建", CTRL_NAME)

    # 2) 两个属性
    ctrl[PROP_CURVE] = 0.0
    ctrl.id_properties_ui(PROP_CURVE).update(
        min=-CURVE_RANGE, max=CURVE_RANGE, description="刹车点头曲线（关键帧驱动，不要手改）")
    if PROP_K not in ctrl.keys():
        ctrl[PROP_K] = float(DEFAULT_K)
    ctrl.id_properties_ui(PROP_K).update(
        min=0.0, max=K_MAX, soft_min=0.0, soft_max=K_SOFT_MAX,
        description="刹车点头强度（相对系数）。基准峰值见曲线，改基准后要重量间隙")

    # 3) 曲线关键帧
    for cb, fc in list(iter_fcurves(ctrl.animation_data)) if ctrl.animation_data else []:
        if fc.data_path == '["%s"]' % PROP_CURVE:
            cb.fcurves.remove(fc)
    for f, v in KEYS:
        ctrl[PROP_CURVE] = v
        ctrl.keyframe_insert('["%s"]' % PROP_CURVE, frame=f)
    ctrl[PROP_CURVE] = 0.0
    for cb, fc in iter_fcurves(ctrl.animation_data):
        if fc.data_path == '["%s"]' % PROP_CURVE:
            for k in fc.keyframe_points:
                k.interpolation = 'BEZIER'
                k.handle_left_type = 'AUTO_CLAMPED'
                k.handle_right_type = 'AUTO_CLAMPED'
            fc.update()

    # 4) 摘掉车身自己的 rotation 曲线，改驱动
    for cb, fc in list(iter_fcurves(body.animation_data)) if body.animation_data else []:
        if fc.data_path == "rotation_euler" and fc.array_index == 1:
            cb.fcurves.remove(fc)
    body.rotation_euler[1] = 0.0
    for fc in list(body.animation_data.drivers) if body.animation_data else []:
        if fc.data_path == "rotation_euler" and fc.array_index == 1:
            body.animation_data.drivers.remove(fc)
    drv = body.driver_add("rotation_euler", 1)
    d = drv.driver
    d.type = 'SCRIPTED'
    d.expression = "dive * k"
    while d.variables:
        d.variables.remove(d.variables[0])
    for name, prop in (("dive", PROP_CURVE), ("k", PROP_K)):
        v = d.variables.new()
        v.name = name
        v.type = 'SINGLE_PROP'
        v.targets[0].id = ctrl
        v.targets[0].data_path = '["%s"]' % prop
    assert d.is_valid, "驱动无效"
    print("驱动 dive*k valid=%s" % d.is_valid)

    # 5) 保距校验：旋转必须不改变几何尺度
    sc.frame_set(int(KEYS[2][0]))
    ctrl.update_tag()
    bpy.context.view_layer.update()
    pts = body_corners(body)
    i = max(range(len(pts)), key=lambda n: -pts[n].x)
    j = max(range(len(pts)), key=lambda n: pts[n].x)
    d0 = (pts[i] - pts[j]).length
    a0 = body.rotation_euler[1]
    ctrl[PROP_K] = 0.0
    ctrl.update_tag()
    bpy.context.view_layer.update()
    pts2 = body_corners(body)
    d1 = (pts2[i] - pts2[j]).length
    ctrl[PROP_K] = float(DEFAULT_K)
    ctrl.update_tag()
    bpy.context.view_layer.update()
    print("保距校验: 有角度 %.6f m / 归零 %.6f m  差 %.2e（应≈0，否则被拉伸）" % (d0, d1, d0 - d1))

    print("峰值角 %.3f° @ f%d，强度 %.2f ⇒ 实际 %.3f°" % (
        KEYS[2][1] * 57.29578, KEYS[2][0], DEFAULT_K, KEYS[2][1] * DEFAULT_K * 57.29578))
    sc.frame_set(88)
    ctrl.update_tag()
    bpy.context.view_layer.update()
    z_rest = nose_z(body)
    sc.frame_set(int(KEYS[2][0]))
    ctrl.update_tag()
    bpy.context.view_layer.update()
    z_dive = nose_z(body)
    print("车头 z: 静止 %.4f → 峰值 %.4f（下沉 %.2f cm）" % (z_rest, z_dive, (z_rest - z_dive) * 100))
    print("SETUP DONE —— 另起一次请求做 clearance / 核验")


def clearance():
    sc = bpy.context.scene
    body = bpy.data.objects[BODY]
    ctrl = bpy.data.objects[CTRL_NAME]
    wheel = bpy.data.objects[WHEEL]
    peak_frame = int(KEYS[2][0])

    print("强度    角度      车头z     轮胎→车身间隙")
    for k in (0.0, 0.65, 1.0, 2.0, 3.0):
        ctrl[PROP_K] = float(k)
        ctrl.update_tag()
        sc.frame_set(peak_frame)
        ctrl.update_tag()
        bpy.context.view_layer.update()
        print("  %.2f  %+6.2f°   %.4f   %.4f m" % (
            k, body.rotation_euler[1] * 57.29578, nose_z(body), min_gap(body, tire_pts(wheel))))
    ctrl[PROP_K] = float(DEFAULT_K)
    ctrl.update_tag()
    bpy.context.view_layer.update()
    print("已还原强度 %.2f" % DEFAULT_K)


if MODE == 'clearance':
    clearance()
else:
    setup()
