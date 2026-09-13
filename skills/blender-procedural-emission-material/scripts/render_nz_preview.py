# NOTE: 路径为模板占位 —— 使用前把 WORKDIR 改成本机实际的「脚本/输出目录」。
#       (桥执行环境里 __file__ 不可靠，因此显式定义。)
WORKDIR = r"C://path//to//blender_control"   # <<< 改这里
# render_nz_preview.py — 渲染「噪波滚动发光」标准链效果预览
#
# ⚠️ 驱动求值的两个硬约束（实测）：
#   1) 材质必须挂在**已被某个活动场景使用**的物体上，否则驱动不参与依赖图求值
#      —— 这里目标对象本来就在主场景里，把它额外 link 进临时场景即可，不要新建物体；
#   2) 帧变量 fr = SINGLE_PROP → 主场景 frame_current，
#      所以换帧要调 bpy.context.scene.frame_set()（主场景），不是临时场景的。
import bpy, os, json, time
from mathutils import Vector

TARGET = "水晶走廊_竖向灯.001"
CTRL_NAME = "竖向灯001_噪波控制"
MAT_NAME = "竖向灯001_噪波滚动发光"
OUTDIR = r"C:\path\to\blender_control\render"   # <<< 改这里
SAMPLES = 24
os.makedirs(OUTDIR, exist_ok=True)

obj = bpy.data.objects[TARGET]
ctrl = bpy.data.objects[CTRL_NAME]
mat = bpy.data.materials[MAT_NAME]
main = bpy.context.scene
ORIG_FRAME = main.frame_current
BASE = {"噪波密度": 2.0, "噪波种子": 0.0, "Z向速度": 0.02, "噪波对比度": 5.0, "发光强度": 5.0}

mw = obj.matrix_world
xs, ys, zs = [], [], []
for v in obj.data.vertices:
    p = mw @ v.co
    xs.append(p.x); ys.append(p.y); zs.append(p.z)
X0, X1 = min(xs), max(xs); Y0, Y1 = min(ys), max(ys); Z0, Z1 = min(zs), max(zs)
ctr = Vector(((X0 + X1) / 2, (Y0 + Y1) / 2, (Z0 + Z1) / 2))

sc = bpy.data.scenes.new("__NZ2PREVIEW__")
sc.collection.objects.link(obj)
sc.render.engine = 'CYCLES'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = False
sc.render.image_settings.file_format = 'PNG'
sc.render.film_transparent = False
sc.render.use_stamp = True
for _f in ("use_stamp_date", "use_stamp_time", "use_stamp_render_time", "use_stamp_frame",
           "use_stamp_frame_range", "use_stamp_camera", "use_stamp_scene", "use_stamp_filename",
           "use_stamp_lens", "use_stamp_marker", "use_stamp_memory", "use_stamp_hostname",
           "use_stamp_sequencer_strip"):
    if hasattr(sc.render, _f):
        setattr(sc.render, _f, False)
sc.render.use_stamp_note = True
sc.render.use_stamp_labels = False
sc.render.stamp_font_size = 22
sc.render.stamp_background = (0, 0, 0, 0.75)
sc.view_settings.view_transform = main.view_settings.view_transform
sc.view_settings.look = main.view_settings.look
sc.view_settings.exposure = main.view_settings.exposure
w = bpy.data.worlds.new("__nz2world__")
w.use_nodes = True
_bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
_bg.inputs[0].default_value = (0, 0, 0, 1)
_bg.inputs[1].default_value = 0.0
sc.world = w

cd = bpy.data.cameras.new("__nz2cam__")
cam = bpy.data.objects.new("__nz2cam__", cd)
sc.collection.objects.link(cam); sc.camera = cam; cd.type = 'ORTHO'


def aim(center, ortho):
    cd.ortho_scale = ortho
    cam.location = Vector(center) + Vector((0, 1, 0)) * 40
    cam.rotation_euler = (Vector(center) - cam.location).to_track_quat('-Z', 'Y').to_euler()


def apply(frame, over=None):
    vals = dict(BASE)
    vals.update(over or {})
    for k, v in vals.items():
        ctrl[k] = float(v)
    ctrl.update_tag(); mat.update_tag(); mat.node_tree.update_tag()
    main.frame_set(frame)                 # ← 主场景换帧（fr 变量读的是这里）
    bpy.context.view_layer.update()
    return vals


def stats(path):
    img = bpy.data.images.load(path, check_existing=False)
    n = img.size[0] * img.size[1]
    buf = [0.0] * (n * 4)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    lum = [0.2126 * buf[i * 4] + 0.7152 * buf[i * 4 + 1] + 0.0722 * buf[i * 4 + 2] for i in range(n)]
    return {"min": round(min(lum), 4), "p50": round(sorted(lum)[n // 2], 4), "max": round(max(lum), 4),
            "dark%": round(100.0 * sum(1 for v in lum if v < .05) / n, 2),
            "blown%": round(100.0 * sum(1 for v in lum if v > .95) / n, 2)}


def diff(a, b):
    ia = bpy.data.images.load(a, check_existing=False)
    ib = bpy.data.images.load(b, check_existing=False)
    n = ia.size[0] * ia.size[1]
    ba = [0.0] * (n * 4); bb = [0.0] * (n * 4)
    ia.pixels.foreach_get(ba); ib.pixels.foreach_get(bb)
    bpy.data.images.remove(ia); bpy.data.images.remove(ib)
    ch = sum(1 for i in range(n) if max(abs(ba[i * 4 + c] - bb[i * 4 + c]) for c in range(3)) > 0.02)
    return round(100.0 * ch / n, 2)


zoom_center = Vector(((X0 + X1) / 2 + 1.6, ctr.y, (Z0 + Z1) / 2))
OV, ZC, ZOOM = tuple(ctr), tuple(zoom_center), 3.35

JOBS = [
    ("nz2_00_overview", 1,   {},                       OV, 27.0, (1200, 300),
     "OVERVIEW  strip 26.4x3.1m  (look along +Y)"),
    ("nz2_01_base_f1",  1,   {},                       ZC, ZOOM, (480, 480),
     "BASE  ctr5  f1     black+white blobs"),
    ("nz2_02_f121",     121, {},                       ZC, ZOOM, (480, 480),
     "BASE  ctr5  f121   = f1 shifted in Z (scroll)"),
    ("nz2_03_c2",       1,   {"噪波对比度": 2.0},        ZC, ZOOM, (480, 480),
     "CTR 2    flatter / washed out"),
    ("nz2_04_c10",      1,   {"噪波对比度": 10.0},       ZC, ZOOM, (480, 480),
     "CTR 10   near hard on/off"),
    ("nz2_05_seed7",    1,   {"噪波种子": 7.0},          ZC, ZOOM, (480, 480),
     "SEED 7   different pattern"),
    ("nz2_06_density6", 1,   {"噪波密度": 6.0},          ZC, ZOOM, (480, 480),
     "DENS 6   finer blobs"),
    ("nz2_07_c5_s20",   1,   {"发光强度": 20.0},         ZC, ZOOM, (480, 480),
     "STR 20   brighter highlights"),
]

log = []
t0 = time.time()
for name, frame, over, center, ortho, res, label in JOBS:
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.stamp_note_text = label
    aim(center, ortho)
    vals = apply(frame, over)
    p = os.path.join(OUTDIR, name + ".png")
    sc.render.filepath = p
    t1 = time.time()
    try:
        bpy.ops.render.render(write_still=True, scene=sc.name)
        rec = {"name": name, "frame": frame, "params": over, "ok": os.path.exists(p),
               "path": p, "sec": round(time.time() - t1, 2)}
        if os.path.exists(p):
            rec.update(stats(p))
        log.append(rec)
    except Exception as e:
        log.append({"name": name, "error": repr(e)})

DIFF = {}
for a, b in (("nz2_01_base_f1", "nz2_02_f121"), ("nz2_03_c2", "nz2_01_base_f1"),
             ("nz2_04_c10", "nz2_01_base_f1"), ("nz2_05_seed7", "nz2_01_base_f1"),
             ("nz2_06_density6", "nz2_01_base_f1"), ("nz2_07_c5_s20", "nz2_01_base_f1")):
    try:
        DIFF["%s vs %s" % (a, b)] = diff(os.path.join(OUTDIR, a + ".png"), os.path.join(OUTDIR, b + ".png"))
    except Exception as e:
        DIFF["%s vs %s" % (a, b)] = repr(e)

# ---- 还原 ----
for k, v in BASE.items():
    ctrl[k] = float(v)
ctrl.update_tag(); mat.update_tag(); mat.node_tree.update_tag()
main.frame_set(ORIG_FRAME)
bpy.context.view_layer.update()

sc.collection.objects.unlink(obj)
bpy.data.scenes.remove(sc)
bpy.data.objects.remove(cam, do_unlink=True)
for x in list(bpy.data.worlds):
    if x.name.startswith("__nz2"):
        bpy.data.worlds.remove(x)

print("NZ2_PREVIEW_BEGIN")
print(json.dumps({
    "bbox": [[round(v, 3) for v in (X0, Y0, Z0)], [round(v, 3) for v in (X1, Y1, Z1)]],
    "zoom_center": [round(v, 3) for v in zoom_center], "zoom_span": ZOOM, "samples": SAMPLES,
    "jobs": log, "diff": DIFF, "total_sec": round(time.time() - t0, 2),
    "leftover_objects": [o.name for o in bpy.data.objects if o.name.startswith("__nz2")],
    "leftover_worlds": [x.name for x in bpy.data.worlds if x.name.startswith("__nz2")],
    "leftover_scenes": [s.name for s in bpy.data.scenes if s.name.startswith("__")],
    "scene": bpy.context.scene.name,
    "frame_after": bpy.context.scene.frame_current, "frame_expected": ORIG_FRAME,
    "ctrl_after": {k: ctrl.get(k) for k in BASE},
}, ensure_ascii=False, indent=1))
print("NZ2_PREVIEW_END")
