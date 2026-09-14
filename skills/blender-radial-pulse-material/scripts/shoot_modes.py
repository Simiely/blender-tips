# -*- coding: utf-8 -*-
"""shoot_modes.py — 为 4 种模式各渲染参考图（供技能库 references/ 使用）

流程：对每种模式用 radial_field.py 重建材质并**临时**赋给目标对象 ->
建临时相机渲染 3/4 视角与俯视 -> 最后把每个 mesh 的材质槽与渲染设置全部还原。

⚠️ 会临时改动目标对象的材质槽（结束时还原）。跑完请核对末尾的「场景还原」行。
"""
import io
import os
import re
import sys
import bpy

# NOTE: 路径为模板占位 —— 用前改成你本机的「脚本目录 / 输出目录」。
#       （桥执行环境里 __file__ 不可靠，因此显式定义。）
FIELD = r"C:/Users/2504/.workbuddy/skills/blender-radial-pulse-material/scripts/radial_field.py"
OUT = r"D:/workbuddy/_out_radial"
MODES = ("spot", "ring", "spike", "pulse")
RES, SAMPLES = 480, 48
SHOTS = {"hero": (3.6, -3.6, 2.6), "top": (0.0, 0.0, 7.5)}

log = []
scn = bpy.context.scene
R = scn.render
VS = scn.view_settings

def snap_render():
    return {
        "res_x": R.resolution_x, "res_y": R.resolution_y, "pct": R.resolution_percentage,
        "samples": scn.eevee.taa_render_samples, "filepath": R.filepath,
        "view_transform": VS.view_transform, "camera": scn.camera,
        "frame": scn.frame_current, "film": R.film_transparent,
        "fmt": R.image_settings.file_format, "mode": R.image_settings.color_mode,
        "depth": R.image_settings.color_depth,
        "cam_data": list(bpy.data.cameras),
    }

def snap_scene():
    return {
        "mats": sorted(m.name for m in bpy.data.materials),
        "slots": {o.name: [m.name if m else None for m in o.data.materials]
                  for o in bpy.data.objects if o.type == 'MESH'},
        "objs": sorted(o.name for o in bpy.data.objects),
    }

def restore_scene(s, base_mats):
    for m in [m for m in bpy.data.materials if m.name not in base_mats]:
        bpy.data.materials.remove(m)
    for name, want in s["slots"].items():
        ob = bpy.data.objects.get(name)
        if not ob:
            continue
        me = ob.data
        me.materials.clear()
        for mn in want:
            if mn:
                me.materials.append(bpy.data.materials[mn])
        for poly in me.polygons:
            poly.material_index = 0

def restore_render(s):
    R.resolution_x, R.resolution_y, R.resolution_percentage = s["res_x"], s["res_y"], s["pct"]
    scn.eevee.taa_render_samples = s["samples"]
    R.filepath = s["filepath"]
    VS.view_transform = s["view_transform"]
    scn.camera = s["camera"]
    R.film_transparent = s["film"]
    R.image_settings.file_format = s["fmt"]
    R.image_settings.color_mode = s["mode"]
    R.image_settings.color_depth = s["depth"]
    for c in [c for c in bpy.data.cameras if c not in s["cam_data"]]:
        bpy.data.cameras.remove(c)
    if scn.frame_current != s["frame"]:
        scn.frame_set(s["frame"])

def shot(path, loc, frame):
    cd = bpy.data.cameras.new("_SKILLSHOT")
    cam = bpy.data.objects.new("_SKILLSHOT", cd)
    scn.collection.objects.link(cam)
    cd.lens = 40.0
    cam.location = loc
    # 指向原点：用 track-to 的等价旋向（绕 X 90°，再按镜头方位自转）
    import math
    from mathutils import Vector
    d = Vector((0, 0, 0)) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scn.camera = cam
    scn.frame_set(frame)
    R.filepath = path
    bpy.ops.render.render(write_still=True)
    scn.collection.objects.unlink(cam)      # 注意是 collection.objects，不是 scn.objects
    bpy.data.objects.remove(cam)
    return os.path.getsize(path)

# 开局清残留（上次中途失败可能留下临时相机 / 临时材质）
for ob in [o for o in bpy.data.objects if o.name.startswith("_SKILLSHOT")]:
    bpy.data.objects.remove(ob)
for c in [c for c in bpy.data.cameras if c.name.startswith("_SKILLSHOT")]:
    bpy.data.cameras.remove(c)
for m in [m for m in bpy.data.materials if m.name.startswith("_SKILLTEST")]:
    bpy.data.materials.remove(m)

# 修复上次中断留下的污染：目标对象槽位若为 None 或临时材质，复位成成品组合
# （临时材质被 remove 后，引用它的槽会变成 None；不清掉的话基线快照就是脏的）
FINAL_MODE, FINAL_MAT, FINAL_SRC = "pulse", "FB_Firework_View", "FB_Firework"
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    names = [m.name if m else None for m in o.data.materials]
    if any((n is None) or n.startswith("_SKILLTEST") for n in names):
        o.data.materials.clear()
        for mn in (FINAL_MAT, FINAL_SRC):
            if bpy.data.materials.get(mn):
                o.data.materials.append(bpy.data.materials[mn])
        for poly in o.data.polygons:
            poly.material_index = 0
        log.append("  修复残留: %s 槽位 -> %s" % (
            o.name, [m.name if m else None for m in o.data.materials]))
log.append("已清理残留的临时对象/相机/材质")

RS, SS = snap_render(), snap_scene()
base_mats = set(SS["mats"])
src_code = io.open(FIELD, encoding="utf-8").read()
ok = 0

R.image_settings.file_format = 'PNG'
R.image_settings.color_mode = 'RGB'
R.image_settings.color_depth = '8'
R.film_transparent = False
scn.eevee.taa_render_samples = SAMPLES
R.resolution_percentage = 100

def run_field(mode, material, assign, src=None):
    code = src_code
    code = re.sub(r'"mode":\s*"[a-z]+"', '"mode": "%s"' % mode, code, count=1)
    code = re.sub(r'"material":\s*"[^"]+"', '"material": "%s"' % material, code, count=1)
    code = re.sub(r'"assign":\s*(True|False)', '"assign": %s' % assign, code, count=1)
    code = re.sub(r'"src_material":\s*(None|"[^"]+")',
                  '"src_material": %s' % (('"%s"' % src) if src else 'None'), code, count=1)
    buf, old = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        exec(compile(code, FIELD, "exec"), {"__name__": "__main__"})
        return None, buf.getvalue()
    except Exception as e:
        return "%s: %s" % (type(e).__name__, e), buf.getvalue()
    finally:
        sys.stdout = old

for mode in MODES:
    err, _ = run_field(mode, "_SKILLTEST_%s" % mode, "True", src=None)
    R.resolution_x = R.resolution_y = RES
    if err:
        log.append("MODE=%-6s BUILD ERR %s" % (mode, err))
        continue
    sizes = []
    for tag, loc in SHOTS.items():
        f = 1 if mode in ("spot", "ring", "spike") else 60
        sizes.append("%s=%d" % (tag, shot(os.path.join(OUT, "skill_%s_%s.png" % (mode, tag)), loc, f)))
    log.append("MODE=%-6s %s  nodes=%d" % (
        mode, " ".join(sizes),
        len(bpy.data.materials["_SKILLTEST_%s" % mode].node_tree.nodes)))
    ok += 1

# 再补一组 pulse 的时间序列
err, _ = run_field("pulse", "_SKILLTEST_pulse_t", "True", src=None)
if err:
    log.append("pulse 时序 BUILD ERR %s" % err)
else:
    R.resolution_x = R.resolution_y = 420
    for f in (1, 60, 88, 130, 180, 250):
        sz = shot(os.path.join(OUT, "skill_pulse_f%03d.png" % f), SHOTS["top"], f)
        log.append("  pulse f%3d size=%d" % (f, sz))

# ---------- 收尾：清临时物 + 显式重建成品（保证最终状态 = 用户认可的那版）----------
restore_scene(SS, base_mats)
restore_render(RS)
err, txt = run_field(FINAL_MODE, FINAL_MAT, "True", src=FINAL_SRC)
log.append("显式重建 %s(%s): %s" % (FINAL_MAT, FINAL_MODE, err or "OK"))
if err:
    log.append(txt[-800:])
now = snap_scene()
want_slots = {o.name: [FINAL_MAT, FINAL_SRC]
              for o in bpy.data.objects if o.type == 'MESH'}
slots_ok = all(now["slots"].get(k) == v for k, v in want_slots.items())
mats_ok = set(now["mats"]) == {"FB_Firework", "FB_Firework_View"}
log.append("BUILT=%d/%d" % (ok, len(MODES)))
log.append("最终材质表=%s  %s" % (now["mats"], "OK" if mats_ok else "**FAIL**"))
log.append("最终槽位=%s  %s" % (now["slots"], "OK" if slots_ok else "**FAIL**"))
log.append("render还原: view_transform=%s samples=%d res=%dx%d camera=%s frame=%d" % (
    VS.view_transform, scn.eevee.taa_render_samples, R.resolution_x, R.resolution_y,
    scn.camera.name if scn.camera else None, scn.frame_current))
print("\n".join(log))
