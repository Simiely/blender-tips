# probe_53.py —— 找出用「新材质」的其它对象（用户自己贴的平面），按各自法线正对渲染
import bpy, os, json, time, math
from mathutils import Vector

WORKDIR = r"C:\path\to\blender_control"   # <<< 改这里
OUT = os.path.join(WORKDIR, "render")
MAT_NAME = "竖向灯001_噪波滚动发光"
CTRL_NAME = "竖向灯001_噪波控制"
STRIP = "水晶走廊_竖向灯.001"
PFX = "__P53"
rep = {"t0": time.time()}


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


nuke()
# 顺手清掉历史残留场景
killed = []
for s in list(bpy.data.scenes):
    if s.name.startswith("__"):
        nm = s.name                      # 先取名字：remove 之后这个引用就失效了
        try:
            bpy.data.scenes.remove(s); killed.append(nm)
        except Exception as e:
            killed.append("%s:ERR %r" % (nm, e))
rep["old_scenes_cleaned"] = killed

mat = bpy.data.materials[MAT_NAME]
ctrl = bpy.data.objects[CTRL_NAME]
main = bpy.context.scene
ORIG_FRAME = main.frame_current
BASE = {"噪波密度": 2.0, "噪波种子": 0.0, "Z向速度": 0.02, "噪波对比度": 5.0, "发光强度": 5.0}

users = []
for o in bpy.data.objects:
    if o.type != 'MESH' or not o.material_slots:
        continue
    if any(s.material is mat for s in o.material_slots):
        users.append(o)
rep["users"] = []
for o in users:
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [p.x for p in bb]; ys = [p.y for p in bb]; zs = [p.z for p in bb]
    rep["users"].append({"name": o.name, "verts": len(o.data.vertices), "polys": len(o.data.polygons),
                         "loc": [round(v, 3) for v in o.location],
                         "rot_deg": [round(math.degrees(v), 1) for v in o.rotation_euler],
                         "scale": [round(v, 3) for v in o.scale],
                         "world_size": [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3),
                                        round(max(zs) - min(zs), 3)],
                         "world_min": [round(min(xs), 3), round(min(ys), 3), round(min(zs), 3)],
                         "world_max": [round(max(xs), 3), round(max(ys), 3), round(max(zs), 3)]})


def face_normal(o):
    """取面积加权平均法线（世界空间）"""
    me = o.data
    n = Vector((0, 0, 0))
    mw3 = o.matrix_world.to_3x3()
    for p in me.polygons:
        n += (mw3 @ p.normal) * p.area
    return n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))


sc = bpy.data.scenes.new(PFX + "_SCENE__")
sc.render.engine = 'CYCLES'
sc.cycles.samples = 24
sc.cycles.use_denoising = False
sc.render.image_settings.file_format = 'PNG'
sc.render.film_transparent = False
sc.render.stamp_font_size = 22
sc.render.stamp_background = (0, 0, 0, 0.75)
sc.render.use_stamp = True
for _f in ("use_stamp_date", "use_stamp_time", "use_stamp_render_time", "use_stamp_frame",
           "use_stamp_frame_range", "use_stamp_camera", "use_stamp_scene", "use_stamp_filename",
           "use_stamp_lens", "use_stamp_marker", "use_stamp_memory", "use_stamp_hostname",
           "use_stamp_sequencer_strip"):
    if hasattr(sc.render, _f):
        setattr(sc.render, _f, False)
sc.render.use_stamp_note = True
sc.render.use_stamp_labels = False
sc.view_settings.view_transform = main.view_settings.view_transform
sc.view_settings.look = main.view_settings.look
sc.view_settings.exposure = main.view_settings.exposure
w2 = bpy.data.worlds.new(PFX + "_WORLD__")
w2.use_nodes = True
_bg = next(n for n in w2.node_tree.nodes if n.type == 'BACKGROUND')
_bg.inputs[0].default_value = (0, 0, 0, 1); _bg.inputs[1].default_value = 0.0
sc.world = w2

cd = bpy.data.cameras.new(PFX + "_CAM__")
cam = bpy.data.objects.new(PFX + "_CAM__", cd)
sc.collection.objects.link(cam); sc.camera = cam; cd.type = 'ORTHO'


def apply(frame, over=None):
    vals = dict(BASE); vals.update(over or {})
    for k, v in vals.items():
        ctrl[k] = float(v)
    ctrl.update_tag(); mat.update_tag(); mat.node_tree.update_tag()
    main.frame_set(frame)
    bpy.context.view_layer.update()


def stats(path):
    img = bpy.data.images.load(path, check_existing=False)
    n = img.size[0] * img.size[1]
    buf = [0.0] * (n * 4); img.pixels.foreach_get(buf); bpy.data.images.remove(img)
    lum = [0.2126 * buf[i * 4] + 0.7152 * buf[i * 4 + 1] + 0.0722 * buf[i * 4 + 2] for i in range(n)]
    return {"min": round(min(lum), 4), "p50": round(sorted(lum)[n // 2], 4), "max": round(max(lum), 4),
            "dark%": round(100.0 * sum(1 for v in lum if v < .05) / n, 2),
            "blown%": round(100.0 * sum(1 for v in lum if v > .95) / n, 2)}


jobs = []
for o in users:
    if o.name == STRIP:
        continue                                  # 灯带已单独出图
    sc.collection.objects.link(o)
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [p.x for p in bb]; ys = [p.y for p in bb]; zs = [p.z for p in bb]
    c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    nrm = face_normal(o)
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) * 1.05
    cd.ortho_scale = max(span, 0.2)
    cam.location = c + nrm * 30
    cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    ar = (max(xs) - min(xs)) / max(max(zs) - min(zs), 1e-6)
    sc.render.resolution_x = 720
    sc.render.resolution_y = max(120, int(720 / max(ar, 0.2)))
    for tag, over in (("c2", {"噪波对比度": 2.0}), ("c5", {}), ("c10", {"噪波对比度": 10.0})):
        apply(1, over)
        sc.render.stamp_note_text = "%s   %s   (face-on, ortho %.2f)" % (o.name, tag, cd.ortho_scale)
        p = os.path.join(OUT, "p53_%s_%s.png" % (o.name.replace(" ", "_"), tag))
        sc.render.filepath = p
        try:
            bpy.ops.render.render(write_still=True, scene=sc.name)
            r = {"obj": o.name, "tag": tag, "path": p, "ok": os.path.exists(p)}
            if os.path.exists(p):
                r.update(stats(p))
            jobs.append(r)
        except Exception as e:
            jobs.append({"obj": o.name, "tag": tag, "error": repr(e)})
    sc.collection.objects.unlink(o)
rep["jobs"] = jobs

# ---- 还原 & 清理 ----
for k, v in BASE.items():
    ctrl[k] = float(v)
ctrl.update_tag(); mat.update_tag(); mat.node_tree.update_tag()
main.frame_set(ORIG_FRAME)
bpy.context.view_layer.update()
try:
    bpy.data.scenes.remove(sc); rep["scene_removed"] = True
except Exception as e:
    rep["scene_removed"] = repr(e)
nuke()
rep["leftover"] = {k: [x.name for x in v if x.name.startswith(PFX)] for k, v in
                   (("objects", bpy.data.objects), ("scenes", bpy.data.scenes),
                    ("worlds", bpy.data.worlds))}
rep["scene_now"] = bpy.context.scene.name
rep["total_sec"] = round(time.time() - rep["t0"], 2)
print("P53_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("P53_END")
