# -*- coding: utf-8 -*-
"""probe_64: 端到端验证新控件 亮区阈值 —— 真实驱动链（不 mute），临时场景渲染。
渲 2 张（T=0.70 / T=0.75，其余用用户当前值），渲完恢复用户值。"""
import json, os, bpy
from mathutils import Vector, Quaternion

rep = {"step": "probe_64_threshold_e2e"}
CTRL, MAT = "竖向灯001_噪波控制", "竖向灯001_噪波滚动发光"
OUTDIR = r"<WORKDIR>\\render"  # <<< 改成你的 blender_control\\render
KEYS = ("噪波密度", "噪波种子", "Z向速度", "噪波对比度", "亮区阈值", "发光强度", "反色")

obj = bpy.data.objects[CTRL]
mat = bpy.data.materials[MAT]
nt = mat.node_tree
plane = bpy.data.objects.get("平面")
ORIG = {k: obj.get(k) for k in KEYS}
rep["orig"] = {k: round(float(v), 4) for k, v in ORIG.items()}

ts = tw = tcam = None
try:
    def set_props(**kw):
        for k, v in kw.items():
            obj[k] = float(v)
        obj.update_tag(); mat.update_tag(); nt.update_tag()
        bpy.context.view_layer.update()

    ts = bpy.data.scenes.new("__P64__")
    ts.collection.objects.link(plane)
    ts.render.engine = 'CYCLES'
    ts.cycles.samples = 16
    ts.cycles.use_denoising = False
    ts.render.image_settings.file_format = 'PNG'
    ts.render.resolution_x = 640; ts.render.resolution_y = 640
    ts.render.resolution_percentage = 100
    main = bpy.context.scene
    ts.view_settings.view_transform = main.view_settings.view_transform
    ts.view_settings.look = main.view_settings.look
    ts.view_settings.exposure = main.view_settings.exposure
    tw = bpy.data.worlds.new("__p64w__")
    tw.use_nodes = True
    bg = next(n for n in tw.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs[0].default_value = (0, 0, 0, 1); bg.inputs[1].default_value = 0.0
    ts.world = tw
    tcam = bpy.data.objects.new("__p64cam__", bpy.data.cameras.new("__p64cam__"))
    ts.collection.objects.link(tcam); ts.camera = tcam
    nrm = (plane.matrix_world.to_quaternion() @ Vector((0, 0, 1))).normalized()
    ctr = plane.matrix_world.translation
    tcam.data.type = 'ORTHO'
    tcam.data.ortho_scale = max(plane.dimensions) * 0.98
    tcam.location = ctr + nrm * 30.0
    q = (-nrm).to_track_quat('-Z', 'Y')
    up = q @ Vector((0, 1, 0)); wz = Vector((0, 0, 1))
    ax = up.cross(wz)
    if ax.length > 1e-9:
        q = Quaternion(ax.normalized(), up.angle(wz)) @ q
    tcam.rotation_euler = q.to_euler()
    ts.frame_set(1)

    jobs = []
    for i, T in enumerate((0.70, 0.75)):
        set_props(亮区阈值=T, 噪波对比度=20.0, 反色=0.0)
        p = os.path.join(OUTDIR, "p64b_T%.2f.png" % T)
        ts.render.filepath = p
        bpy.ops.render.render(write_still=True, scene=ts.name)
        img = bpy.data.images.load(p)
        px = img.pixels[:]
        br = tot = 0
        for j in range(0, len(px), 28):
            tot += 1
            if px[j] > 0.5:
                br += 1
        jobs.append({"T": T, "bright%": round(100.0 * br / tot, 2),
                     "file": os.path.basename(p)})
        bpy.data.images.remove(img)
    rep["jobs"] = jobs
finally:
    for k, v in ORIG.items():
        if v is not None:
            obj[k] = v
    obj.update_tag(); mat.update_tag(); nt.update_tag()
    if plane and ts:
        ts.collection.objects.unlink(plane)
    if tcam:
        cd = tcam.data
        bpy.data.objects.remove(tcam, do_unlink=True)
        if cd: bpy.data.cameras.remove(cd)
    if tw: bpy.data.worlds.remove(tw)
    if ts: bpy.data.scenes.remove(ts)
    bpy.context.view_layer.update()

after = {k: obj.get(k) for k in KEYS}
rep["restore_ok"] = all(abs(float(after[k]) - float(v)) < 1e-6 for k, v in ORIG.items())
rep["scenes"] = [s.name for s in bpy.data.scenes if s.name.startswith("__P")]
print("P64_BEGIN" + json.dumps(rep, ensure_ascii=False) + "P64_END")
