# bl_10oclock_verify.py — 10点钟方向独立核验（depsgraph 求值，另起请求）
import bpy, os, json

OUT_DIR = r"D:\workbuddy\2026-11-23-17-56-14"
PARAMS = os.path.join(OUT_DIR, "10oclock_anim_params.json")
REPORT = os.path.join(OUT_DIR, "10oclock_anim_verify_report.txt")
with open(PARAMS, "r", encoding="utf-8") as f:
    P = json.load(f)

R = []
def p(*a):
    R.append(" ".join(str(x) for x in a))

scn = bpy.context.scene
ctrl = bpy.data.objects[P["controller"]]
right = bpy.data.objects["右侧门.001"]
left = bpy.data.objects["左侧门.001"]
char = bpy.data.objects["角色弹出02"]
PROP = P["prop"]

p("=" * 84)
p("10点钟方向 独立核验  |  %s" % bpy.data.filepath)
p("=" * 84)

p("[结构] 复用控制器 %s[%s]" % (ctrl.name, PROP))
p("  参数关键帧: %s" % [
    (int(k.co[0]), round(float(k.co[1]), 4))
    for layer in ctrl.animation_data.action.layers
    for strip in layer.strips
    for cb in strip.channelbags
    for fc in cb.fcurves
    if fc.data_path == '["%s"]' % PROP
    for k in fc.keyframe_points])
for nm, obj, path, idx in (
    ("右门.001 rotZ", right, 'rotation_euler', 2),
    ("左门.001 rotZ", left, 'rotation_euler', 2),
    ("角色弹出 locY", char, 'location', 1)):
    fcs = [d for d in obj.animation_data.drivers
           if d.data_path == path and d.array_index == idx]
    if fcs:
        d = fcs[0].driver
        v = d.variables[0] if d.variables else None
        t = v.targets[0] if v else None
        p("  %-16s valid=%s expr=%s target=%s" % (
            nm, d.is_valid, d.expression,
            t.id.name if (t and t.id) else "-"))
    else:
        p("  %-16s *** 无驱动 ***" % nm)
p("")

def ev(obj, dg):
    return obj.evaluated_get(dg)

def deg(rad):
    return rad * 180.0 / 3.141592653589793

rows = []
p("[逐帧求值]")
for fr in (1, 25, 50, 75, 100):
    scn.frame_set(fr)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    pv = float(ev(ctrl, dg)[PROP])
    rz_r = float(ev(right, dg).rotation_euler[2])
    rz_l = float(ev(left, dg).rotation_euler[2])
    cy = float(ev(char, dg).location[1])
    rows.append((fr, pv, rz_r, rz_l, cy))
    p("  frame %3d p=%6.3f | 右=%8.4f rad (%8.3f°) 左=%8.4f rad (%8.3f°) | 角色Y=%10.5f" % (
        fr, pv, rz_r, deg(rz_r), rz_l, deg(rz_l), cy))

p("")
p("[端点判定]")
tol = 2e-3
r0, r1 = P["right_z"]; l0, l1 = P["left_z"]; c0, c1 = P["char_y"]
f1, f100 = rows[0], rows[-1]
checks = [
    ("帧1 p=0", abs(f1[1]) < tol),
    ("帧100 p=10", abs(f100[1] - 10) < tol),
    ("右门 帧1=初始", abs(f1[2] - r0) < tol),
    ("右门 帧100=最终", abs(f100[2] - r1) < tol),
    ("左门 帧1=初始", abs(f1[3] - l0) < tol),
    ("左门 帧100=最终", abs(f100[3] - l1) < tol),
    ("角色 帧1=缩回", abs(f1[4] - c0) < tol),
    ("角色 帧100=弹出", abs(f100[4] - c1) < tol),
    ("右门单调", all(rows[i][2] >= rows[i+1][2] - 1e-6 for i in range(4))),
    ("左门单调", all(rows[i][3] <= rows[i+1][3] + 1e-6 for i in range(4))),
    ("角色单调(递减)", all(rows[i][4] >= rows[i+1][4] - 1e-6 for i in range(4))),
]
for label, ok in checks:
    p("  %-18s %s" % (label, "OK" if ok else "*** FAIL ***"))

p("")
p("[子对象跟随]")
for fr in (1, 100):
    scn.frame_set(fr)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    p("  frame %d:" % fr)
    for nm in ("Rectangle202", "Rectangle207", "对象910"):
        w = bpy.data.objects[nm].evaluated_get(dg).matrix_world.translation
        p("    %-14s world=(%.4f, %.4f, %.4f)" % (nm, w.x, w.y, w.z))

# 同步性：3点钟与10点钟同一 p 值
p("")
p("[同步性] 同一参数驱动两组")
for fr in (1, 50, 100):
    scn.frame_set(fr)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    p3 = float(ev(ctrl, dg)[PROP])
    r3 = float(bpy.data.objects["右侧门"].evaluated_get(dg).rotation_euler[2])
    r10 = float(right.evaluated_get(dg).rotation_euler[2])
    c3 = float(bpy.data.objects["角色伸出"].evaluated_get(dg).location[1])
    c10 = float(char.evaluated_get(dg).location[1])
    p("  frame %3d p=%5.2f | 右门3=%7.4f 右门10=%7.4f | 角色3Y=%9.2f 角色10Y=%9.4f" % (
        fr, p3, r3, r10, c3, c10))

scn.frame_set(1)
p("")
p("失败项: %d" % sum(1 for _, ok in checks if not ok))
p("is_dirty=%s" % bpy.data.is_dirty)
txt = "\n".join(R)
with open(REPORT, "w", encoding="utf-8") as f:
    f.write(txt + "\n")
print(txt)
print("=== 10OCLOCK VERIFY DONE ===")
