# 独立核验: 全部重新取引用, 不复用构建时的任何列表
# 判据(三条全过才算成功):
#   1. 位置误差       = 0        (灯没被带走)
#   2. 切向偏离       ≈ 0        (灯锁死在自己的径向平面里)
#   3. 同步帧 8 盏展开角差 = 0   (拍频公式生效)
import bpy
import math
import re
from mathutils import Vector

COLLECTION = "动态灯的坐标"
CENTER_OBJ = "绽放中轴线"
SPOT_PREFIX = "射灯"
LAMP_PREFIX = "射灯_光"
HINGE_PREFIX = "射灯_铰链"
PARAM_PREFIX = "bloom_"
SAMPLE_FRAMES = (0, 120, 300, 600, 601, 900, 1200, 2400)

sc = bpy.context.scene
ctr = bpy.data.objects.get(CENTER_OBJ)
C = Vector(ctr.location)
print("CENTER", tuple(round(v, 4) for v in C))

lamps = sorted([o for o in bpy.data.objects
                if o.type == 'LIGHT' and o.name.startswith(LAMP_PREFIX)],
               key=lambda o: o.name)
assert len(lamps) == 8, "期望 8 盏灯, 实得 %d" % len(lamps)

# 每盏灯的基础几何(从它的定位空对象反推)
base = {}
for o in lamps:
    e = o.parent.parent if (o.parent and o.parent.parent) else o.parent
    assert e is not None, "找不到定位空对象: " + o.name
    d = Vector(e.location) - C
    r_hat = Vector((d.x, d.y, 0.0)).normalized()
    t_hat = Vector((0.0, 0.0, 1.0)).cross(r_hat).normalized()
    d_full = C - Vector(e.location)
    elev = math.atan2(d_full.z, math.hypot(d_full.x, d_full.y))
    base[o.name] = (e, r_hat, t_hat, elev)

print("---- 静态: 位置与层级 ----")
pos_bad = []
for o in lamps:
    e, _, _, _ = base[o.name]
    err = (Vector(o.matrix_world.translation) - Vector(e.location)).length
    ok = err < 1e-6 and o.parent is not None and o.parent.name.startswith(HINGE_PREFIX)
    print("  ", o.name, "| parent", o.parent.name if o.parent else None,
          "| 位置误差", round(err, 9), "| OK", ok)
    if not ok:
        pos_bad.append(o.name)
print("POS_BAD", pos_bad)

print("---- 动态: 逐帧采样 ----")
def sample(f):
    sc.frame_set(f)
    out = []
    for o in lamps:
        e, r_hat, t_hat, elev = base[o.name]
        dirv = (o.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
        a = dirv.dot(-r_hat)
        b = dirv.dot(Vector((0.0, 0.0, 1.0)))
        c = dirv.dot(t_hat)
        ang = math.degrees(math.atan2(b, a)) - math.degrees(elev)
        w = C - Vector(o.matrix_world.translation)
        dist_axis = (w.cross(dirv)).length      # 光线到中轴线的最近距离
        out.append((ang, c, dist_axis))
    return out

orig = sc.frame_current
worst_tan = 0.0
sync_bad = []
for f in SAMPLE_FRAMES:
    res = sample(f)
    angs = [r[0] for r in res]
    tan = max(abs(r[1]) for r in res)
    worst_tan = max(worst_tan, tan)
    spread = max(angs) - min(angs)
    print("  frame", f,
          "| 展开角", [round(x, 2) for x in angs],
          "| 最大-最小", round(spread, 4),
          "| 切向偏离", round(tan, 8),
          "| 光线到中轴", round(min(r[2] for r in res), 4), "~", round(max(r[2] for r in res), 4))
sc.frame_set(orig)

# 同步帧判据
sync_f = int(sc[PARAM_PREFIX + "sync_frame"])
res = sample(sync_f)
angs = [r[0] for r in res]
sync_spread = max(angs) - min(angs)
print("SYNC_FRAME", sync_f, "| 展开角差", round(sync_spread, 8),
      "| 同步时展开角", round(angs[0], 3))
print("FRAME_RESTORED", sc.frame_current)
print("VERDICT",
      "PASS" if (not pos_bad and worst_tan < 1e-5 and sync_spread < 1e-3) else "FAIL")
print("VERIFY_DONE")
