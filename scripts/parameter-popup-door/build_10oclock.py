# bl_10oclock_build.py — 10点钟方向：复用同一控制器驱动右门/左门/角色弹出
import bpy, os, json, datetime

OUT_DIR = r"D:\workbuddy\2026-11-23-17-56-14"
OLD = os.path.join(OUT_DIR, "3oclock_baseline.json")
NEW = os.path.join(OUT_DIR, "10oclock_baseline_now.json")
REPORT = os.path.join(OUT_DIR, "10oclock_anim_build_report.txt")
PARAMS = os.path.join(OUT_DIR, "10oclock_anim_params.json")

with open(OLD, "r", encoding="utf-8") as f:
    old = json.load(f)
with open(NEW, "r", encoding="utf-8") as f:
    now = json.load(f)
old_r = {r["name"]: r for r in old["roots"]["10点钟方向"]["objects"]}
now_r = {r["name"]: r for r in now["objects"]}

R = []
def p(*a):
    R.append(" ".join(str(x) for x in a))

# 控制器必须已存在（3点钟那套）
ctrl = bpy.data.objects.get("3点钟_弹出控制")
if ctrl is None:
    p("!! 控制器 3点钟_弹出控制 不存在，中止")
    raise SystemExit(1)
PROP = "弹出进度"

right = bpy.data.objects["右侧门.001"]
left = bpy.data.objects["左侧门.001"]
char = bpy.data.objects["角色弹出02"]

# 端点：当前(用户刚改)=初始门角/最终角色位；基线=最终门角/初始角色位
r0 = float(now_r["右侧门.001"]["rotation_euler_local"][2])   # 0 初始关门
r1 = float(old_r["右侧门.001"]["rotation_euler_local"][2])   # -2.775074 最终开门
l0 = float(now_r["左侧门.001"]["rotation_euler_local"][2])   # 0
l1 = float(old_r["左侧门.001"]["rotation_euler_local"][2])   # 2.722714
c0 = float(old_r["角色弹出02"]["location_local"][1])         # 31.439859 初始缩回
c1 = float(now_r["角色弹出02"]["location_local"][1])         # 31.018097 最终弹出

# 硬闸：确认当前值确实是初始/最终（防止基线抓错）
assert abs(float(right.rotation_euler[2]) - r0) < 1e-5, "right current mismatch"
assert abs(float(left.rotation_euler[2]) - l0) < 1e-5, "left current mismatch"
assert abs(float(char.location[1]) - c1) < 1e-5, "char current mismatch"

p("=" * 80)
p("10点钟方向 参数驱动构建（复用 %s[%s]）  %s" % (
    ctrl.name, PROP, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
p("=" * 80)
p("端点映射: 右门 %.9f -> %.9f rad" % (r0, r1))
p("          左门 %.9f -> %.9f rad" % (l0, l1))
p("          角色Y %.9f -> %.9f" % (c0, c1))
p("")

def add_driver(obj, path, idx, expr):
    fc = obj.driver_add(path, idx)
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
    return d

expr_right = "%.9f + (%.9f - %.9f)*p/10" % (r0, r1, r0)
expr_left = "%.9f + (%.9f - %.9f)*p/10" % (l0, l1, l0)
expr_char = "%.9f + (%.9f - %.9f)*p/10" % (c0, c1, c0)
# 基线角度是弧度，直接写；不套 radians()（3点钟踩过的坑）
dr = add_driver(right, 'rotation_euler', 2, expr_right)
dl = add_driver(left, 'rotation_euler', 2, expr_left)
dc = add_driver(char, 'location', 1, expr_char)
p("驱动: 右侧门.001 rotZ / 左侧门.001 rotZ / 角色弹出02 locY")
p("  右: %s" % expr_right)
p("  左: %s" % expr_left)
p("  角色: %s" % expr_char)
p("  is_valid: %s / %s / %s" % (dr.is_valid, dl.is_valid, dc.is_valid))

params = {
    "controller": ctrl.name, "prop": PROP,
    "right_z": [r0, r1], "left_z": [l0, l1], "char_y": [c0, c1],
    "expr": {"right": expr_right, "left": expr_left, "char": expr_char},
}
with open(PARAMS, "w", encoding="utf-8") as f:
    json.dump(params, f, ensure_ascii=False, indent=2)
p("")
p("is_dirty=%s  桥只改内存，需 Ctrl+S" % bpy.data.is_dirty)
p("参数 -> " + PARAMS)
txt = "\n".join(R)
with open(REPORT, "w", encoding="utf-8") as f:
    f.write(txt + "\n")
print(txt)
print("=== 10OCLOCK BUILD DONE ===")
