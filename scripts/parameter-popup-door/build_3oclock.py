# bl_3oclock_anim_build.py — 3点钟方向：控制器参数(0-10)驱动门旋转 + 角色弹出
import bpy, os, json, datetime

OUT_DIR = r"D:\workbuddy\2026-11-23-17-56-14"
BASELINE = os.path.join(OUT_DIR, "3oclock_baseline.json")
REPORT = os.path.join(OUT_DIR, "3oclock_anim_build_report.txt")
PARAMS = os.path.join(OUT_DIR, "3oclock_anim_params.json")

R = []
def p(*a):
    R.append(" ".join(str(x) for x in a))

with open(BASELINE, "r", encoding="utf-8") as f:
    base = json.load(f)

def getrec(name):
    for r in base["roots"]["3点钟方向"]["objects"]:
        if r["name"] == name:
            return r
    raise RuntimeError("baseline missing " + name)

# 基线（19:21）= 最终态的门角 + 初始态的角色位置
b_right_z = float(getrec("右侧门")["rotation_euler_local"][2])
b_left_z = float(getrec("左侧门")["rotation_euler_local"][2])
b_char_y = float(getrec("角色伸出")["location_local"][1])

# 当前场景（用户改后）= 初始态的门角 + 最终态的角色位置
right = bpy.data.objects["右侧门"]
left = bpy.data.objects["左侧门"]
char = bpy.data.objects["角色伸出"]
root = bpy.data.objects["3点钟方向"]
cur_right_z = float(right.rotation_euler[2])
cur_left_z = float(left.rotation_euler[2])
cur_char_y = float(char.location[1])
cur_char_x = float(char.location[0])
cur_char_z = float(char.location[2])

# 安全闸：控制器不能已存在
if bpy.data.objects.get("3点钟_弹出控制") is not None:
    p("!! 控制器已存在，中止")
    raise SystemExit(1)

p("=" * 80)
p("3点钟方向 参数驱动构建  " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
p("=" * 80)
p("数据映射（参数 0=初始 / 10=最终）:")
p("  右侧门 rotZ : %.9f -> %.9f" % (cur_right_z, b_right_z))
p("  左侧门 rotZ : %.9f -> %.9f" % (cur_left_z, b_left_z))
p("  角色 locY   : %.9f -> %.9f" % (b_char_y, cur_char_y))
p("  角色 locX/Z : 保持 %.9f / %.9f" % (cur_char_x, cur_char_z))
p("")

# ---- 1. 建控制器 ----
ctrl = bpy.data.objects.new("3点钟_弹出控制", None)
bpy.context.scene.collection.objects.link(ctrl)
ctrl.empty_display_type = 'SPHERE'
ctrl.empty_display_size = 0.15
ctrl.location = root.location.copy()
PROP = "弹出进度"
ctrl[PROP] = 0.0
ctrl.id_properties_ui(PROP).update(
    min=0.0, max=10.0, soft_min=0.0, soft_max=10.0,
    description="0=初始(门关/角色缩) 10=最终(门开/角色弹出)")
p("控制器: %s loc=%s prop=%s[0,10]" % (
    ctrl.name, [round(float(x), 6) for x in ctrl.location], PROP))

# ---- 2. 参数打关键帧 (帧1=0, 帧100=10) ----
ctrl[PROP] = 0.0
ctrl.keyframe_insert(data_path='["%s"]' % PROP, frame=1)
ctrl[PROP] = 10.0
ctrl.keyframe_insert(data_path='["%s"]' % PROP, frame=100)
# 直接构造精确关键帧坐标（绕开求值干扰）
fc_ctrl = None
ad = ctrl.animation_data
for layer in ad.action.layers:
    for strip in layer.strips:
        for cb in strip.channelbags:
            for fc in cb.fcurves:
                if fc.data_path == '["%s"]' % PROP:
                    fc_ctrl = fc
if fc_ctrl is None:
    raise RuntimeError("controller fcurve not found")
kps = fc_ctrl.keyframe_points
for i, (fr, val) in enumerate([(1.0, 0.0), (100.0, 10.0)]):
    kps[i].co = (float(fr), float(val))
    kps[i].interpolation = 'BEZIER'
fc_ctrl.update()
p("参数关键帧: %s" % [(int(k.co[0]), k.co[1], k.interpolation) for k in kps])

# ---- 3. 挂三条驱动 ----
def add_driver(obj, data_path, idx, expr):
    fc = obj.driver_add(data_path, idx)
    d = fc.driver
    d.type = 'SCRIPTED'
    v = d.variables.new()
    v.name = 'p'
    v.type = 'SINGLE_PROP'
    t = v.targets[0]
    t.id_type = 'OBJECT'
    t.id = ctrl
    t.data_path = '["%s"]' % PROP
    d.expression = expr
    return fc, d

expr_right = "radians(%.9f + (%.9f - %.9f)*p/10)" % (cur_right_z, b_right_z, cur_right_z)
expr_left = "radians(%.9f + (%.9f - %.9f)*p/10)" % (cur_left_z, b_left_z, cur_left_z)
expr_char = "%.9f + (%.9f - %.9f)*p/10" % (b_char_y, cur_char_y, b_char_y)

# 基准角不动：表达式输出绝对角度，驱动直接覆盖该通道
fcr, dr = add_driver(right, 'rotation_euler', 2, expr_right)
fcl, dl = add_driver(left, 'rotation_euler', 2, expr_left)
fcc, dc = add_driver(char, 'location', 1, expr_char)
p("驱动: 右侧门 rotZ / 左侧门 rotZ / 角色 locY  ->  SINGLE_PROP 控制器[%s]" % PROP)
p("  右侧门 expr: %s" % expr_right)
p("  左侧门 expr: %s" % expr_left)
p("  角色   expr: %s" % expr_char)
p("")

# ---- 4. 保存参数供核验 ----
params = {
    "prop": PROP,
    "controller": ctrl.name,
    "frame_start": 1, "frame_end": 100,
    "right_z": [cur_right_z, b_right_z],
    "left_z": [cur_left_z, b_left_z],
    "char_y": [b_char_y, cur_char_y],
    "char_xz": [cur_char_x, cur_char_z],
    "expr": {"right": expr_right, "left": expr_left, "char": expr_char},
}
with open(PARAMS, "w", encoding="utf-8") as f:
    json.dump(params, f, ensure_ascii=False, indent=2)

p("is_dirty=%s  桥只改内存，需 Ctrl+S" % bpy.data.is_dirty)
p("参数 -> " + PARAMS)
txt = "\n".join(R)
with open(REPORT, "w", encoding="utf-8") as f:
    f.write(txt + "\n")
print(txt)
print("=== 3OCLOCK ANIM BUILD DONE ===")
