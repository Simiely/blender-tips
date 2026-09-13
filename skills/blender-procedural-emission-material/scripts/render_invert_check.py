# -*- coding: utf-8 -*-
# render_invert_check.py —— 客观验证「反色」控件真的在起作用（像素级）
#
# 判据设计（不靠肉眼）：
#   ① corr(反色=0, 反色=1)  ≈ −1   ⇒ 两张图明暗关系完全颠倒 = 真的反色了
#   ② corr(反色=0, 反色=0)  == 1   ⇒ 零控：同参数渲两次必须逐像素一致（链路无假变化）
#   ③ std(反色=0.5) ≈ 0            ⇒ 反色=0.5 时 MapRange 的 To Min=To Max=0.5
#                                    ⇒ 输出被压成恒定灰（证明 To Min/To Max 真的被驱动读到了）
#   参数刻意选成不饱和（密度0.4 / 对比度2 / 强度0.6 / Standard）⇒ 像素读数是单调的，
#   相关系数才有判别力。
#
# ★ 前提（见 skill blender-plane-procedural-material §5）：
#   dither_intensity = 0（默认 1.0 的抖动会引入假差异）、16-bit、1 采样（纯发光=确定性）
import bpy, os, json, math, time
import numpy as np
from mathutils import Vector

WORKDIR = r"<WORKDIR>"  # <<< 改成你的 blender_control 目录
OUTDIR = os.path.join(WORKDIR, "render")
MAT_NAME = "竖向灯001_噪波滚动发光"
CTRL_NAME = "竖向灯001_噪波控制"
PLANE_NAME = "平面"
PFX = "__IV"
RES = 512
SAMPLES = 1
OVERSCAN = 0.98
VIEW = 'Standard'
TEST = {"噪波密度": 0.4, "噪波种子": 0.0, "Z向速度": 0.0,
        "噪波对比度": 2.0, "发光强度": 0.6, "反色": 0.0}

rep = {"t0": time.time()}
os.makedirs(OUTDIR, exist_ok=True)
mat = bpy.data.materials[MAT_NAME]
ctrl = bpy.data.objects[CTRL_NAME]
main = bpy.context.scene
ORIG_FRAME = main.frame_current
ORIG = {k: float(ctrl.get(k, 0.0)) for k in TEST}


def nuke():
    for s in list(bpy.data.scenes):
        if s.name.startswith(PFX):
            try: bpy.data.scenes.remove(s)
            except Exception: pass
    for o in list(bpy.data.objects):
        if o.name.startswith(PFX):
            try: bpy.data.objects.remove(o, do_unlink=True)
            except Exception: pass
    for w in list(bpy.data.worlds):
        if w.name.startswith(PFX):
            try: bpy.data.worlds.remove(w)
            except Exception: pass
    for c in list(bpy.data.cameras):
        if c.name.startswith(PFX):
            try: bpy.data.cameras.remove(c)
            except Exception: pass


nuke()
plane = bpy.data.objects[PLANE_NAME]
rep["has_invert_node"] = ("反色" in mat.node_tree.nodes
                          and mat.node_tree.nodes["反色"].bl_idname == 'ShaderNodeMapRange')
bpy.context.view_layer.update()


def face_normal(o):
    n = Vector((0, 0, 0))
    mw3 = o.matrix_world.to_3x3()
    for p in o.data.polygons:
        n += (mw3 @ p.normal) * p.area
    return n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))


pbb = [plane.matrix_world @ Vector(c) for c in plane.bound_box]
nrm = face_normal(plane)
xs = [p.x for p in pbb]; ys = [p.y for p in pbb]; zs = [p.z for p in pbb]
cent = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
span_x, span_z = max(xs) - min(xs), max(zs) - min(zs)

sc = bpy.data.scenes.new(PFX + "_SCENE__")
sc.render.engine = 'CYCLES'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = False
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_depth = '16'
sc.render.dither_intensity = 0.0                 # ★ 必须关（默认 1.0 会加 ±1/255 抖动）
sc.render.film_transparent = False
sc.render.use_stamp = False
sc.view_settings.view_transform = VIEW
sc.view_settings.look = 'None'
sc.view_settings.exposure = 0.0
sc.render.filter_size = 0.01                     # 关抗锯齿模糊 ⇒ 图像完全确定
w2 = bpy.data.worlds.new(PFX + "_WORLD__")
w2.use_nodes = True
_bg = next(n for n in w2.node_tree.nodes if n.type == 'BACKGROUND')
_bg.inputs[0].default_value = (0, 0, 0, 1)
_bg.inputs[1].default_value = 0.0
sc.world = w2

cd = bpy.data.cameras.new(PFX + "_CAM__")
cam = bpy.data.objects.new(PFX + "_CAM__", cd)
sc.collection.objects.link(cam)
sc.camera = cam
cd.type = 'ORTHO'
cd.ortho_scale = max(max(span_x, span_z) * OVERSCAN, 0.05)
cam.location = cent + nrm * 30.0
cam.rotation_euler = (cent - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.resolution_x = RES
sc.render.resolution_y = max(64, int(round(RES * span_z / max(span_x, 1e-6))))
sc.collection.objects.link(plane)                # ★ 额外 link，别动主场景归属
rep["camera"] = {"ortho_scale": round(cd.ortho_scale, 4),
                 "resolution": [sc.render.resolution_x, sc.render.resolution_y],
                 "view_transform": VIEW, "samples": SAMPLES, "dither": sc.render.dither_intensity}


def apply(over):
    vals = dict(TEST)
    vals.update(over or {})
    for k, v in vals.items():
        ctrl[k] = float(v)
    ctrl.update_tag(); mat.update_tag(); mat.node_tree.update_tag()
    main.frame_set(1)
    bpy.context.view_layer.update()


def render_to(name):
    p = os.path.join(OUTDIR, "iv_%s.png" % name)
    sc.render.filepath = p                        # ★ 必须先设路径，否则静默不写盘
    bpy.ops.render.render(write_still=True, scene=sc.name)   # ★ 必须显式指定场景，否则渲到活动场景
    return p


def load_lum(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    n = w * h
    buf = np.empty(n * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    b = buf.reshape(n, 4).astype(np.float64)
    lum = 0.2126 * b[:, 0] + 0.7152 * b[:, 1] + 0.0722 * b[:, 2]
    return lum


def stats(a):
    n = a.size
    return {"min": round(float(a.min()), 4), "p50": round(float(np.median(a)), 4),
            "max": round(float(a.max()), 4),
            "mean": round(float(a.mean()), 4), "std": round(float(a.std()), 5),
            "dark%": round(100.0 * float((a < 0.05).sum()) / n, 2),
            "blown%": round(100.0 * float((a > 0.95).sum()) / n, 2)}


JOBS = [("inv0", {"反色": 0.0}), ("inv1", {"反色": 1.0}),
        ("inv0_null", {"反色": 0.0}), ("inv05", {"反色": 0.5})]
data, rows = {}, []
for nm, over in JOBS:
    apply(over)
    p = render_to(nm)
    dg = bpy.context.evaluated_depsgraph_get()
    et = mat.evaluated_get(dg).node_tree


    def _ev(sock):
        for s in et.nodes["反色"].inputs:
            if s.name == sock and s.type == 'VALUE':
                return round(float(s.default_value), 4)
        return None


    a = load_lum(p)
    data[nm] = a
    rows.append({"job": nm, "over": over, "file": os.path.basename(p),
                 "evaluated_To_Min": _ev('To Min'), "evaluated_To_Max": _ev('To Max'),
                 **stats(a)})
rep["jobs"] = rows

corr = lambda A, B: round(float(np.corrcoef(A, B)[0, 1]), 5)
rep["corr_inv0_vs_inv1"] = corr(data["inv0"], data["inv1"])
rep["corr_inv0_vs_inv0null"] = corr(data["inv0"], data["inv0_null"])
rep["files_differ_inv0_vs_inv1"] = bool(abs(data["inv0"] - data["inv1"]).max() > 0.05)

V = {}
V["反色0 vs 反色1 强负相关 (≈ -1 ⇒ 明暗颠倒)"] = rep["corr_inv0_vs_inv1"] < -0.9
V["零控: 同参数渲两次逐像素一致 (corr > 0.9999)"] = rep["corr_inv0_vs_inv0null"] > 0.9999
V["反色0.5 → 输出被压成恒定灰 (std ≈ 0)"] = rows[3]["std"] < 0.002
V["反色0 有正常明暗起伏 (std > 0.02)"] = rows[0]["std"] > 0.02
V["反色1 也有明暗起伏 (不是被压平)"] = rows[1]["std"] > 0.02
V["驱动真值: 反色0 → To 0/1 ；反色1 → To 1/0"] = (
    rows[0]["evaluated_To_Min"] == 0.0 and rows[0]["evaluated_To_Max"] == 1.0
    and rows[1]["evaluated_To_Min"] == 1.0 and rows[1]["evaluated_To_Max"] == 0.0)
V["驱动真值: 反色0.5 → To 0.5/0.5"] = (
    abs(rows[3]["evaluated_To_Min"] - 0.5) < 1e-6 and abs(rows[3]["evaluated_To_Max"] - 0.5) < 1e-6)
rep["checks"] = V
rep["all_ok"] = all(V.values())

# ---------- 复原 ----------
for k, v in ORIG.items():
    ctrl[k] = float(v)
ctrl.update_tag(); mat.update_tag(); mat.node_tree.update_tag()
main.frame_set(ORIG_FRAME)
bpy.context.view_layer.update()
nuke()
rep["restored"] = {k: float(ctrl[k]) for k in ORIG}
rep["leftover"] = {"scenes": [s.name for s in bpy.data.scenes if s.name.startswith(PFX)],
                   "objects": [o.name for o in bpy.data.objects if o.name.startswith(PFX)]}
rep["object_count"] = len(bpy.data.objects)
rep["scene_now"] = bpy.context.scene.name
rep["total_sec"] = round(time.time() - rep["t0"], 2)
print("IV_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("IV_END")
