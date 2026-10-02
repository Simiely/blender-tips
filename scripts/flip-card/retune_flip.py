# -*- coding: utf-8 -*-
"""
分体翻页牌 —— 调参(驱动与处理器同步)

改完立即生效(处理器本次会话实时;驱动在受信任重开时接管)。
"""
import bpy
import math

# ---------------- CONFIG ----------------
TURNS = 3      # 圈数(整数圈 = 结束回到初始朝向)
DUR = 16       # 单次翻页时长(帧)
PERIOD = 60    # 翻页周期(帧)
# ----------------------------------------

scene = bpy.context.scene
pivots = sorted([o for o in bpy.data.objects if 'flip_delay' in o], key=lambda p: p.name)
print("轴数量:", len(pivots))

TOTAL_DEG = 360.0 * TURNS
for p in pivots:
    p["flip_turns"] = TURNS
    p["flip_dur"] = DUR
    p["flip_period"] = PERIOD

# 驱动(注意 radians!)
EXPR = ("(radians({t}) * (3*(((fc - dl) % {p}) / {d}) ** 2 - 2*(((fc - dl) % {p}) / {d}) ** 3)) "
        "if (((fc - dl) % {p}) < {d}) else radians({t})").format(t=TOTAL_DEG, p=PERIOD, d=DUR)
if 'radians' not in bpy.app.driver_namespace:
    bpy.app.driver_namespace['radians'] = math.radians
for p in pivots:
    for d_ in p.animation_data.drivers:
        d_.driver.expression = EXPR
        d_.driver.is_valid = False
print("驱动表达式:", EXPR)

# 处理器(与驱动同公式)
MARK = "flip_all_cards"
for h in list(bpy.app.handlers.frame_change_post):
    if getattr(h, "__name__", "") == MARK:
        bpy.app.handlers.frame_change_post.remove(h)
ns = {"bpy": bpy, "math": math}
exec(compile("""
def {m}(scene, depsgraph):
    import math
    f = scene.frame_current
    for ob in bpy.data.objects:
        if 'flip_delay' in ob:
            per = int(ob.get('flip_period', 60))
            dur = float(ob.get('flip_dur', 16))
            turns = int(ob.get('flip_turns', 3))
            total = math.radians(360.0 * turns)
            t = (f - int(ob['flip_delay'])) % per
            u = t / dur
            v = total * (3.0*u*u - 2.0*u*u*u) if u < 1.0 else total
            ob.rotation_euler[ob.get('flip_axis', 1)] = v
""".format(m=MARK), "<flip>", "exec"), ns)
bpy.app.handlers.frame_change_post.append(ns[MARK])
print("处理器已重新注册:", MARK)

scene.frame_set(scene.frame_current)   # 触发一次求值
print("[RETUNE DONE] 圈数=%d 时长=%d 周期=%d" % (TURNS, DUR, PERIOD))
