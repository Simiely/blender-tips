# -*- coding: utf-8 -*-
"""probe_63 v2: 「黑底零星白点」可行性侦察。
1) mathutils 3D fBm 采样 Fac 分布分位数（统计上等价于 4D 固定 W）。
2) 隔离临时场景试渲 4 个候选 ColorRamp 顶部窗口，量白点占比。
   —— 临时场景配方同 render_nz_preview（主场景渲染设置全程不碰）；
      新场景 file_format 默认 PNG，绕开 5.2「视频模式场景拒改图片格式」的 RNA 限制。
   色标驱动 mute → 手写窗口 → 渲完 unmute + 还原位置 + 还原控件值。
"""
import json
import os

CTRL = "竖向灯001_噪波控制"
MAT = "竖向灯001_噪波滚动发光"
WORKDIR = r"<WORKDIR>"  # <<< 改成你的 blender_control 目录
OUTDIR = os.path.join(WORKDIR, "render")

import bpy
from mathutils import noise, Vector, Quaternion

rep = {"step": "probe_63_sparse_white_recon_v2"}

# ---------- 1) fBm 分布采样（不改场景） ----------
def fbm3(x, y, z, detail=2.0):
    amp, freq, s = 1.0, 1.0, 0.0
    n = max(0, int(detail))
    for i in range(n):
        s += amp * noise.noise(Vector((x * freq, 7.3 * freq, z * freq)))
        amp *= 0.5
        freq *= 2.0
    return s * 0.5 + 0.5

import random
random.seed(7)
N = 200000
vals = sorted(fbm3(random.uniform(0, 20), 0.0, random.uniform(0, 20)) for _ in range(N))
def pct(p):
    return round(vals[int(p * (N - 1))], 4)
rep["fac_dist"] = {"min": pct(0.0), "p50": pct(0.5), "p80": pct(0.8), "p90": pct(0.9),
                   "p95": pct(0.95), "p98": pct(0.98), "p99": pct(0.99),
                   "p995": pct(0.995), "max": pct(1.0)}
rep["white_frac_above"] = {"T>%.2f" % T: round(sum(1 for v in vals if v > T) / N, 5)
                           for T in (0.60, 0.62, 0.65, 0.68, 0.70, 0.72, 0.75)}

# ---------- 2) 隔离临时场景试渲 ----------
obj = bpy.data.objects.get(CTRL)
mat = bpy.data.materials[MAT]
nt = mat.node_tree
nodes = {n.name: n for n in nt.nodes}
ramp = nodes["对比度"]
e0, e1 = ramp.color_ramp.elements[0], ramp.color_ramp.elements[1]
plane = bpy.data.objects.get("平面")
rep["plane_found"] = plane is not None

orig_pos = (e0.position, e1.position)
orig_frame = bpy.context.scene.frame_current
ORIG_PROPS = {k: obj.get(k) for k in ("噪波密度", "噪波种子", "Z向速度",
                                      "噪波对比度", "发光强度", "反色")}
muted_fcs = []
ts = None
tworld = None
tcam = None

def aim_faceon(cam, cam_data, plane):
    nrm = (plane.matrix_world.to_quaternion() @ Vector((0, 0, 1))).normalized()
    center = plane.matrix_world.translation
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = max(plane.dimensions) * 0.98
    cam.location = center + nrm * 30.0
    q = (-nrm).to_track_quat('-Z', 'Y')          # -Z 指向平面
    up = q @ Vector((0, 1, 0))
    wz = Vector((0, 0, 1))
    axis = up.cross(wz)
    if axis.length > 1e-9:                        # 把 local +Y 转到世界 +Z
        q = Quaternion(axis.normalized(), up.angle(wz)) @ q
    cam.rotation_euler = q.to_euler()

try:
    # 控件值：密度 6（用户当前）、强度 5、不滚动、不反色
    obj["噪波密度"] = 6.0
    obj["噪波种子"] = 11.34
    obj["Z向速度"] = 0.0
    obj["发光强度"] = 5.0
    obj["反色"] = 0.0
    obj["噪波对比度"] = 1.0
    for o in (obj, mat):
        o.update_tag()
    nt.update_tag()
    bpy.context.view_layer.update()

    # mute 色标驱动，手动写窗口
    for fc in nt.animation_data.drivers:
        if "color_ramp" in fc.data_path:
            fc.mute = True
            muted_fcs.append(fc)

    # 临时场景
    ts = bpy.data.scenes.new("__P63__")
    ts.collection.objects.link(plane)
    ts.render.engine = 'CYCLES'
    ts.cycles.samples = 16
    ts.cycles.use_denoising = False
    ts.render.image_settings.file_format = 'PNG'
    ts.render.resolution_x = 640
    ts.render.resolution_y = 640
    ts.render.resolution_percentage = 100
    ts.render.film_transparent = False
    main = bpy.context.scene
    ts.view_settings.view_transform = main.view_settings.view_transform
    ts.view_settings.look = main.view_settings.look
    ts.view_settings.exposure = main.view_settings.exposure
    tworld = bpy.data.worlds.new("__p63world__")
    tworld.use_nodes = True
    _bg = next(n for n in tworld.node_tree.nodes if n.type == 'BACKGROUND')
    _bg.inputs[0].default_value = (0, 0, 0, 1)
    _bg.inputs[1].default_value = 0.0
    ts.world = tworld
    tcam = bpy.data.objects.new("__p63cam__", bpy.data.cameras.new("__p63cam__"))
    ts.collection.objects.link(tcam)
    ts.camera = tcam
    aim_faceon(tcam, tcam.data, plane)
    ts.frame_set(1)

    CANDS = [(0.60, 0.65), (0.64, 0.68), (0.68, 0.71), (0.71, 0.74)]
    jobs = []
    for i, (lo, hi) in enumerate(CANDS):
        e0.position, e1.position = lo, hi
        nt.update_tag()
        bpy.context.view_layer.update()
        ts.render.filepath = os.path.join(OUTDIR, "p63_win%d.png" % i)
        bpy.ops.render.render(write_still=True, scene=ts.name)
        img = bpy.data.images.load(ts.render.filepath)
        px = img.pixels[:]
        bright = tot = 0
        for j in range(0, len(px), 28):           # 抽样 1/7 像素
            tot += 1
            if px[j] > 0.5:
                bright += 1
        jobs.append({"win": [lo, hi], "bright%": round(100.0 * bright / tot, 2),
                     "file": "p63_win%d.png" % i})
        bpy.data.images.remove(img)
    rep["render_jobs"] = jobs
finally:
    # 还原
    e0.position, e1.position = orig_pos
    for fc in muted_fcs:
        fc.mute = False
    for k, v in ORIG_PROPS.items():
        if v is not None:
            obj[k] = v
    for o in (obj, mat):
        o.update_tag()
    nt.update_tag()
    if plane and ts:
        ts.collection.objects.unlink(plane)
    if tcam:
        cam_data_ref = tcam.data
        bpy.data.objects.remove(tcam, do_unlink=True)
        if cam_data_ref:
            bpy.data.cameras.remove(cam_data_ref)
    if tworld:
        bpy.data.worlds.remove(tworld)
    if ts:
        bpy.data.scenes.remove(ts)
    bpy.context.scene.frame_set(orig_frame)
    bpy.context.view_layer.update()

after = {k: obj.get(k) for k in ORIG_PROPS}
rep["restore_ok"] = all(abs(float(after[k]) - float(v)) < 1e-6
                        for k, v in ORIG_PROPS.items() if v is not None)
rep["ramp_restored"] = (abs(e0.position - orig_pos[0]) < 1e-6
                        and abs(e1.position - orig_pos[1]) < 1e-6)
rep["drivers_unmuted"] = all(not fc.mute for fc in nt.animation_data.drivers)
rep["leftover_scenes"] = [s.name for s in bpy.data.scenes if s.name.startswith("__P")]
rep["object_count"] = len(bpy.data.objects)

print("P63_BEGIN" + json.dumps(rep, ensure_ascii=False) + "P63_END")
