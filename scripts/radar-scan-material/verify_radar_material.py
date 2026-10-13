# 独立核验（新请求）：平面「雷达扫描」空间材质
# 1) 结构断言  2) 渲染后读被驱动插槽真值  3) 沿法线正交正视渲染 + 像素级测转角/数条数/验 Y 投射
# 用法: python send.py verify_radar_material.py
import bpy
import math
import os
from mathutils import Vector

OUT_DIR = "C:/radar_check"      # ← 改这里（渲染证据落盘目录，脚本自己建目录）
CHECK_GAIN = 1.0                # 测量用强度（避免过曝把亮度剖面压平 ⇒ argmax 随机）

TAU = 2.0 * math.pi
PLANE, MAT, CTRL = "平面", "平面_雷达扫描", "雷达控制"

scene = bpy.context.scene
ob = bpy.data.objects[PLANE]
mat = bpy.data.materials[MAT]
ctl = bpy.data.objects[CTRL]
nt = mat.node_tree

# ---------- 1. 结构断言 ----------
expect = ['雷达_纹理坐标', '雷达_分离XYZ', '雷达_相位角', '雷达_角度偏置', '雷达_角度U',
          '雷达_时刻', '雷达_有向条数', '雷达_时间项', '雷达_角项', '雷达_相位差', '雷达_相位D',
          '雷达_拖尾包络', '雷达_拖尾曲率', '雷达_头部线', '雷达_半径', '雷达_亮面裁切',
          '雷达_总掩码', '雷达_发光强度', '雷达_颜色', '雷达_BSDF', '雷达_输出']
print("[结构] 节点=%d 连线=%d 缺失=%s" % (len(nt.nodes), len(nt.links),
                                         [n for n in expect if n not in nt.nodes]))
print("[结构] 槽0=%s tex.object=%s" % (ob.material_slots[0].material.name,
                                       nt.nodes['雷达_纹理坐标'].object.name))
drv = nt.animation_data.drivers
print("[结构] 驱动=%d 失效=%s" % (len(drv), [f.data_path for f in drv if not f.driver.is_valid]))
print("[结构] 时间项^1=%s 角项^1=%s  （方向必须只进角项）" % (
    [l.from_node.name for l in nt.links if l.to_node.name == '雷达_时间项' and l.to_socket.name == 'Value'],
    [l.from_node.name for l in nt.links if l.to_node.name == '雷达_角项' and l.to_socket.name == 'Value']))

os.makedirs(OUT_DIR, exist_ok=True)
snap = {
    'engine': scene.render.engine, 'rx': scene.render.resolution_x, 'ry': scene.render.resolution_y,
    'rp': scene.render.resolution_percentage, 'fp': scene.render.filepath,
    'ff': scene.render.image_settings.file_format, 'cm': scene.render.image_settings.color_mode,
    'ft': scene.render.film_transparent, 'vt': scene.view_settings.view_transform,
    'dith': scene.render.dither_intensity, 'frame': scene.frame_current,
    'cy': scene.cycles.samples, 'hidden': {o.name: o.hide_render for o in bpy.data.objects},
}
prop_old = {k: ctl[k] for k in ("扫描条数", "拖尾长度", "扫描方向", "扫描速度", "发光强度")}
cam = None
try:
    engines = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    eevee = next((e for e in engines if 'EEVEE' in e), None)
    scene.render.engine = eevee or 'CYCLES'
    if not eevee:
        scene.cycles.samples = 8
    scene.render.resolution_x = scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'   # 别用 AgX，会把对比压平
    scene.render.dither_intensity = 0.0
    for o in bpy.data.objects:
        o.hide_render = (o.name != PLANE)

    mw = ob.matrix_world
    pts = [mw @ v.co for v in ob.data.vertices]
    center = Vector([sum(p[i] for p in pts) / len(pts) for i in range(3)])
    span = max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3))
    normal = (mw.to_3x3() @ Vector((0, 0, 1))).normalized()
    half = span / 2.0

    cam_data = bpy.data.cameras.new("__雷达核验相机__")
    cam = bpy.data.objects.new("__雷达核验相机__", cam_data)
    scene.collection.objects.link(cam)
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = span * 0.98
    loc = center + normal * 30.0
    cam.location = loc
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (center - loc).to_track_quat('-Z', 'Y')
    scene.camera = cam
    print("[渲染] 引擎=%s ortho=%.4f 法线=(%.2f,%.2f,%.2f) 半宽=%.4f" %
          (scene.render.engine, cam_data.ortho_scale, *normal, half))

    def render(frame, tag):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        scene.render.filepath = OUT_DIR + "/" + tag
        bpy.ops.render.render(write_still=True)
        return OUT_DIR + "/" + tag + ".png"

    def profile(path, r_frac, N=720):
        """按 u 采样一圈亮度：X = r·cos(2πu−π)、Z = r·sin(2πu−π)（与材质里的 atan2 反演一致）"""
        img = bpy.data.images.load(path, check_existing=False)
        W, H = img.size
        px = img.pixels[:]
        ppm = W / cam_data.ortho_scale
        r = r_frac * half
        vals = []
        for i in range(N):
            u = i / N
            ang = TAU * u - math.pi
            ix = int(round(W / 2 + r * math.cos(ang) * ppm))
            iy = int(round(H / 2 + r * math.sin(ang) * ppm))
            lum = 0.0
            if 0 <= ix < W and 0 <= iy < H:
                o = (iy * W + ix) * 4
                lum = (px[o] + px[o + 1] + px[o + 2]) / 3.0
            vals.append((u, lum))
        bpy.data.images.remove(img)
        mx = max(v for _, v in vals)
        mn = min(v for _, v in vals)
        peak_u = max(vals, key=lambda t: t[1])[0]
        return peak_u, mx, mn, vals

    def count_peaks(vals):
        mx = max(v for _, v in vals)
        mn = min(v for _, v in vals)
        thr = mn + 0.6 * (mx - mn)
        flags = [v > thr for _, v in vals]
        runs, n = 0, len(flags)
        for i in range(n):
            if flags[i] and not flags[i - 1]:
                runs += 1
        return runs, thr

    # --- A. 单条（count=1，拖尾 90°）：头角可无歧义测 ---
    ctl["扫描条数"], ctl["拖尾长度"], ctl["扫描方向"] = 1.0, 90.0, 1.0
    ctl["发光强度"] = CHECK_GAIN
    ctl.update_tag()
    bpy.context.view_layer.update()

    p1 = render(1, "one_f001")
    t1 = nt.nodes['雷达_时刻'].outputs[0].default_value
    p2 = render(31, "one_f031")
    t2 = nt.nodes['雷达_时刻'].outputs[0].default_value
    u1, mx1, mn1, _ = profile(p1, 0.65)
    u2, mx2, mn2, _ = profile(p2, 0.65)

    fps, speed = scene.render.fps, ctl["扫描速度"]
    exp_deg = 30.0 / fps * speed
    meas = ((u2 - u1) % 1.0) * 360.0
    if meas > 180.0:
        meas -= 360.0
    print("[驱动真值] 时刻 f1=%.5f f31=%.5f（期望 %.5f / %.5f）" %
          (t1, t2, 1 / fps * speed / 360.0, 31 / fps * speed / 360.0))
    print("[测量·单条] 头部 u f1=%.4f f31=%.4f | 亮度区间 f1=[%.3f,%.3f] f31=[%.3f,%.3f]" %
          (u1, u2, mn1, mx1, mn2, mx2))
    print("[测量·单条] 期望转角=%+.2f°  实测=%+.2f°  误差=%.2f°" % (exp_deg, meas, abs(exp_deg - meas)))

    # --- B. 反向（方向=-1）应朝相反方向转 ---
    ctl["扫描方向"] = -1.0
    ctl.update_tag()
    bpy.context.view_layer.update()
    q1 = render(1, "rev_f001")
    q2 = render(31, "rev_f031")
    v1, _, _, _ = profile(q1, 0.65)
    v2, _, _, _ = profile(q2, 0.65)
    rm = ((v2 - v1) % 1.0) * 360.0
    if rm > 180.0:
        rm -= 360.0
    print("[测量·反向] 实测转角=%+.2f°（期望 ≈ %+.2f°）" % (rm, -exp_deg))

    # --- C. 参考外观（用户默认 5 条 / 129° / 正向） ---
    ctl["扫描条数"], ctl["拖尾长度"], ctl["扫描方向"] = 5.0, 129.0, 1.0
    ctl["发光强度"] = 2.0
    ctl.update_tag()
    bpy.context.view_layer.update()
    r1 = render(1, "ref_f001")
    render(31, "ref_f031")
    _, rmx, rmn, rvals = profile(r1, 0.65)
    runs, thr = count_peaks(rvals)
    print("[测量·5条] 亮度区间=[%.3f,%.3f] 阈值=%.3f 数到的亮峰数=%d（期望 5）" %
          (rmn, rmx, thr, runs))

    # --- D. Y 轴投射验证：沿 Y 平移平面，正交投影下画面应逐像素不变 ---
    import hashlib
    ctl["扫描条数"], ctl["拖尾长度"], ctl["扫描方向"] = 1.0, 120.0, 1.0
    ctl.update_tag()
    bpy.context.view_layer.update()
    a = render(7, "yproj_y0")
    oy0 = ob.location.y
    ob.location.y = oy0 + 2.0
    bpy.context.view_layer.update()
    b = render(7, "yproj_ymov")
    ob.location.y = oy0
    bpy.context.view_layer.update()
    with open(a, 'rb') as fa, open(b, 'rb') as fb:
        ha, hb = hashlib.md5(fa.read()).hexdigest(), hashlib.md5(fb.read()).hexdigest()
    print("[测量·Y投射] 平面沿世界 Y 平移 2m：%s vs %s ⇒ %s" %
          (ha[:10], hb[:10], "逐像素一致（图案与 Y 无关）" if ha == hb else "不一致（异常！）"))

    print("[外观] 参考帧: %s/ref_f001.png  ref_f031.png（含单条/反向/Y投射 共 9 张）" % OUT_DIR)
finally:
    for k, v in prop_old.items():
        ctl[k] = v
    ctl.update_tag()
    if cam is not None:
        scene.camera = None
        bpy.data.objects.remove(cam, do_unlink=True)
    scene.render.engine = snap['engine']
    scene.render.resolution_x, scene.render.resolution_y = snap['rx'], snap['ry']
    scene.render.resolution_percentage = snap['rp']
    scene.render.filepath = snap['fp']
    scene.render.image_settings.file_format = snap['ff']
    scene.render.image_settings.color_mode = snap['cm']
    scene.render.film_transparent = snap['ft']
    scene.view_settings.view_transform = snap['vt']
    scene.render.dither_intensity = snap['dith']
    scene.cycles.samples = snap['cy']
    for o in bpy.data.objects:
        if o.name in snap['hidden']:
            o.hide_render = snap['hidden'][o.name]
    scene.frame_set(snap['frame'])
    bpy.context.view_layer.update()
    print("[还原] 引擎/相机/渲染/参数已复原 | 材质已挂回=%s | 残留异常隐藏=%s" % (
        ob.material_slots[0].material.name,
        [o.name for o in bpy.data.objects if o.hide_render != snap['hidden'].get(o.name)]))
