# -*- coding: utf-8 -*-
# P56 —— 钉死一个问题：【临时场景（非活动）渲染】时，依赖「主场景帧」的驱动到底有没有求值？
# 只读 + 建/删一个临时场景；不动材质、不动控制器、不渲图（有渲染但只写两张小图用于佐证）。
import bpy, json, time
from mathutils import Vector

WORKDIR = r"C:/path/to/blender_control"
MAT = "竖向灯001_噪波滚动发光"
PFX = "__P56"
rep = {"t0": time.time()}

for s in list(bpy.data.scenes):
    if s.name.startswith(PFX):
        try: bpy.data.scenes.remove(s)
        except Exception: pass

main = bpy.context.scene
mat = bpy.data.materials[MAT]
plane = bpy.data.objects["平面"]
ORIG = main.frame_current
rep["main"] = main.name
rep["orig_frame"] = ORIG


def read_mapZ(dg):
    nte = mat.evaluated_get(dg).node_tree
    for n in nte.nodes:
        if n.type == 'MAPPING':
            return round(n.inputs[1].default_value[2], 5)
    return None


def read_raw_mapZ():
    for n in mat.node_tree.nodes:
        if n.type == 'MAPPING':
            return round(n.inputs[1].default_value[2], 5)
    return None


seq = []


def snap(tag, dg):
    seq.append({"when": tag, "active_scene": bpy.context.window.scene.name,
                "main_frame": main.frame_current,
                "raw_mapZ": read_raw_mapZ(), "eval_mapZ": read_mapZ(dg)})


# ---------- 1. 活动场景 = main ----------
main.frame_set(1); bpy.context.view_layer.update()
snap("A1 active=main f1", bpy.context.evaluated_depsgraph_get())
main.frame_set(96); bpy.context.view_layer.update()
snap("A2 active=main f96", bpy.context.evaluated_depsgraph_get())

# ---------- 2. 建临时场景并把 plane link 进去，然后切成活动场景 ----------
tmp = bpy.data.scenes.new(PFX + "SC")
tmp.collection.objects.link(plane)
bpy.context.window.scene = tmp
bpy.context.view_layer.update()
snap("B1 active=tmp (main f96)", bpy.context.evaluated_depsgraph_get())
rep["B1_tmp_frame"] = tmp.frame_current

# ---------- 3. 在 tmp 活动的情况下改 main 的帧，再读 tmp 的依赖图 ----------
main.frame_set(1)
bpy.context.view_layer.update()
snap("B2 active=tmp, main.frame_set(1)", bpy.context.evaluated_depsgraph_get())

# ---------- 4. 改 tmp 自己的帧 ----------
tmp.frame_set(96)
bpy.context.view_layer.update()
snap("B3 active=tmp, tmp.frame_set(96)", bpy.context.evaluated_depsgraph_get())
rep["B3_main_frame"] = main.frame_current

# ---------- 5. 回到 main 活动，恢复帧 ----------
bpy.context.window.scene = main
main.frame_set(ORIG)
bpy.context.view_layer.update()
snap("C1 active=main restored", bpy.context.evaluated_depsgraph_get())

rep["seq"] = seq

# ---------- 6. 佐证：在 tmp 场景里渲两帧，看画面是否真的不同 ----------
OUT = WORKDIR + "/render"
camd = bpy.data.cameras.new(PFX + "CAM")
cam = bpy.data.objects.new(PFX + "CAM", camd)
tmp.collection.objects.link(cam); tmp.camera = cam
camd.type = 'ORTHO'
cd = bpy.data.objects["竖向灯001_噪波控制"]
n = Vector((0, -1, 0))
c = Vector((-23.4472, -3.2686, 4.3506))
camd.ortho_scale = 8.359 * 0.98
cam.location = c + n * 30
cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
tmp.render.engine = 'CYCLES'; tmp.cycles.samples = 8
tmp.render.resolution_x = 240; tmp.render.resolution_y = 240
tmp.render.image_settings.file_format = 'PNG'
tmp.render.use_stamp = False
shots = {}
for fr in (1, 96):
    main.frame_set(fr)
    bpy.context.view_layer.update()
    p = "%s/__p56_f%d.png" % (OUT, fr)
    tmp.render.filepath = p
    t1 = time.time()
    bpy.ops.render.render(write_still=True, scene=tmp.name)
    shots[fr] = {"path": p, "sec": round(time.time() - t1, 2)}
rep["shots"] = shots


def lum(p):
    im = bpy.data.images.load(p, check_existing=False)
    n = im.size[0] * im.size[1]
    b = [0.0] * (n * 4); im.pixels.foreach_get(b); bpy.data.images.remove(im)
    return [0.2126 * b[i * 4] + 0.7152 * b[i * 4 + 1] + 0.0722 * b[i * 4 + 2] for i in range(n)]


try:
    l1 = lum(shots[1]["path"]); l2 = lum(shots[96]["path"])
    diff = sum(abs(a - b) for a, b in zip(l1, l2)) / len(l1)
    changed = 100.0 * sum(1 for a, b in zip(l1, l2) if abs(a - b) > 0.02) / len(l1)
    rep["f1_vs_f96"] = {"mean_abs_diff": round(diff, 5), "changed%": round(changed, 2)}
except Exception as e:
    rep["f1_vs_f96"] = {"error": repr(e)}

# ---------- 清理 ----------
bpy.context.window.scene = main
main.frame_set(ORIG)
bpy.context.view_layer.update()
for o in list(bpy.data.objects):
    if o.name.startswith(PFX):
        try: bpy.data.objects.remove(o, do_unlink=True)
        except Exception: pass
for x in list(bpy.data.cameras):
    if x.name.startswith(PFX):
        try: bpy.data.cameras.remove(x)
        except Exception: pass
for s in list(bpy.data.scenes):
    if s.name.startswith(PFX):
        try: bpy.data.scenes.remove(s)
        except Exception: pass
rep["leftover"] = {k: [x.name for x in v if x.name.startswith(PFX)] for k, v in
                   (("objects", bpy.data.objects), ("scenes", bpy.data.scenes), ("cameras", bpy.data.cameras))}
rep["scene_now"] = bpy.context.scene.name
rep["frame_after"] = main.frame_current
rep["total_sec"] = round(time.time() - rep["t0"], 2)
print("P56_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("P56_END")
