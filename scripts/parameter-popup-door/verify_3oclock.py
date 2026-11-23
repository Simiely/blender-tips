# bl_3oclock_anim_verify.py — 独立核验（另起请求，走 depsgraph 求值）
import bpy, os, json

OUT_DIR = r"D:\workbuddy\2026-11-23-17-56-14"
PARAMS = os.path.join(OUT_DIR, "3oclock_anim_params.json")
REPORT = os.path.join(OUT_DIR, "3oclock_anim_verify_report.txt")
with open(PARAMS, "r", encoding="utf-8") as f:
    P = json.load(f)

R = []
def p(*a):
    R.append(" ".join(str(x) for x in a))

scn = bpy.context.scene
ctrl = bpy.data.objects[P["controller"]]
right = bpy.data.objects["右侧门"]
left = bpy.data.objects["左侧门"]
char = bpy.data.objects["角色伸出"]

p("=" * 84)
p("3点钟方向 参数驱动独立核验  |  %s" % bpy.data.filepath)
p("=" * 84)

# 1. 结构检查
p("[结构]")
p("  控制器 %s prop=%s=%s" % (ctrl.name, P["prop"], float(ctrl[P["prop"]])))
p("  参数关键帧: %s" % [
    (int(k.co[0]), round(float(k.co[1]), 4))
    for layer in ctrl.animation_data.action.layers
    for strip in layer.strips
    for cb in strip.channelbags
    for fc in cb.fcurves
    if fc.data_path == '["%s"]' % P["prop"]
    for k in fc.keyframe_points])
for nm, obj, path, idx in (
    ("右侧门 rotZ", right, 'rotation_euler', 2),
    ("左侧门 rotZ", left, 'rotation_euler', 2),
    ("角色 locY", char, 'location', 1)):
    fcs = [d for d in obj.animation_data.drivers
           if d.data_path == path and d.array_index == idx]
    if fcs:
        d = fcs[0].driver
        v = d.variables[0] if d.variables else None
        tgt = v.targets[0] if v else None
        p("  %-14s driver expr=%s valid=%s var=%s target=%s.%s" % (
            nm, d.expression, d.is_valid,
            v.name if v else "-",
            tgt.id.name if (tgt and tgt.id) else "-",
            tgt.data_path if tgt else "-"))
    else:
        p("  %-14s *** 无驱动 ***" % nm)
p("")

# 2. 逐帧求值（depsgraph）
p("[逐帧求值 · evaluated_get]")
def ev(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return obj.evaluated_get(dg)

def deg(rad):
    return rad * 180.0 / 3.141592653589793

rows = []
for fr in (1, 25, 50, 75, 100):
    scn.frame_set(fr)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    pv = float(ev(ctrl)[P["prop"]])
    rz_r = float(ev(right).rotation_euler[2])
    rz_l = float(ev(left).rotation_euler[2])
    cy = float(ev(char).location[1])
    rows.append((fr, pv, rz_r, rz_l, cy))
    p("  frame %3d  p=%6.3f | 右门=%8.4f rad (%8.3f°) 左门=%8.4f rad (%8.3f°) | 角色Y=%11.4f" % (
        fr, pv, rz_r, deg(rz_r), rz_l, deg(rz_l), cy))

# 3. 端点到位判定
p("")
p("[端点判定]")
tolerance = 2e-3
r0, r1 = P["right_z"]
l0, l1 = P["left_z"]
c0, c1 = P["char_y"]
f1, f50, f100 = rows[0], rows[2], rows[4]
checks = [
    ("帧1   参数=0", abs(f1[1] - 0.0) < tolerance),
    ("帧100 参数=10", abs(f100[1] - 10.0) < tolerance),
    ("右门 帧1 =初始", abs(f1[2] - r0) < tolerance),
    ("右门 帧100=最终", abs(f100[2] - r1) < tolerance),
    ("左门 帧1 =初始", abs(f1[3] - l0) < tolerance),
    ("左门 帧100=最终", abs(f100[3] - l1) < tolerance),
    ("角色 帧1 =缩回", abs(f1[4] - c0) < tolerance),
    ("角色 帧100=弹出", abs(f100[4] - c1) < tolerance),
    ("单调 右门", all(rows[i][2] >= rows[i+1][2] - 1e-6 for i in range(4))),
    ("单调 左门", all(rows[i][3] <= rows[i+1][3] + 1e-6 for i in range(4))),
    ("单调 角色", all(rows[i][4] >= rows[i+1][4] - 1e-6 for i in range(4))),
]
for label, ok in checks:
    p("  %-20s %s" % (label, "OK" if ok else "*** FAIL ***"))

# 4. 子对象跟随 + 世界包围盒
p("")
p("[子对象跟随 · 世界坐标]")
for fr in (1, 100):
    scn.frame_set(fr)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    r_eval = right.evaluated_get(dg)
    l_eval = left.evaluated_get(dg)
    c_eval = char.evaluated_get(dg)
    p("  frame %d:" % fr)
    for nm, e in (("Line041", bpy.data.objects["Line041"]),
                  ("Line009", bpy.data.objects["Line009"]),
                  ("对象710", bpy.data.objects["对象710"])):
        w = e.evaluated_get(dg).matrix_world.translation
        p("    %-10s world=(%.4f, %.4f, %.4f)" % (nm, w.x, w.y, w.z))
    rw = r_eval.matrix_world.translation
    lw = l_eval.matrix_world.translation
    cw = c_eval.matrix_world.translation
    p("    门轴心 world 右=(%.4f,%.4f,%.4f) 左=(%.4f,%.4f,%.4f)" % (
        rw.x, rw.y, rw.z, lw.x, lw.y, lw.z))
    p("    角色轴心 world=(%.4f,%.4f,%.4f)" % (cw.x, cw.y, cw.z))

# 恢复帧1
scn.frame_set(1)
p("")
p("失败项: %d" % sum(1 for _, ok in checks if not ok))
p("is_dirty=%s" % bpy.data.is_dirty)
txt = "\n".join(R)
with open(REPORT, "w", encoding="utf-8") as f:
    f.write(txt + "\n")
print(txt)
print("=== 3OCLOCK ANIM VERIFY DONE ===")
