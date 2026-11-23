# bl_3oclock_fix_expr.py — 修复门驱动表达式：基线值本就是弧度，去掉 radians()
import bpy, os, json

OUT_DIR = r"D:\workbuddy\2026-11-23-17-56-14"
PARAMS = os.path.join(OUT_DIR, "3oclock_anim_params.json")
with open(PARAMS, "r", encoding="utf-8") as f:
    P = json.load(f)

r0, r1 = P["right_z"]
l0, l1 = P["left_z"]
expr_right = "%.9f + (%.9f - %.9f)*p/10" % (r0, r1, r0)
expr_left = "%.9f + (%.9f - %.9f)*p/10" % (l0, l1, l0)

for nm, expr in (("右侧门", expr_right), ("左侧门", expr_left)):
    obj = bpy.data.objects[nm]
    found = False
    for d in obj.animation_data.drivers:
        if d.data_path == 'rotation_euler' and d.array_index == 2:
            d.driver.expression = expr
            found = True
            print("FIX %-8s -> %s  valid=%s" % (nm, expr, d.is_valid))
    if not found:
        print("!! %s driver not found" % nm)

P["expr"]["right"] = expr_right
P["expr"]["left"] = expr_left
with open(PARAMS, "w", encoding="utf-8") as f:
    json.dump(P, f, ensure_ascii=False, indent=2)
print("=== FIX EXPR DONE ===")
