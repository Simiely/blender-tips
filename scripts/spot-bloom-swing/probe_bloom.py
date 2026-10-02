# 探查: 灯环几何 / 中轴位置 / 起始线仰角 / 灯当前状态
# 改动前先跑这个, 把实际名字与几何打印出来确认, 别靠猜
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

sc = bpy.context.scene
col = bpy.data.collections.get(COLLECTION)
print("COL", col.name, "objects", len(col.objects))

ctr = bpy.data.objects.get(CENTER_OBJ)
C = Vector(ctr.location)
print("CENTER", repr(ctr.name), tuple(round(v, 4) for v in C))

pat = re.compile(r"^%s(\.\d{3})?$" % re.escape(SPOT_PREFIX))
empties = [o for o in col.objects if o.type == 'EMPTY' and pat.match(o.name)]
print("SPOT_EMPTIES", len(empties), [o.name for o in empties])

print("---- 灯环几何 ----")
for o in sorted(empties, key=lambda x: math.atan2(x.location.y - C.y, x.location.x - C.x)):
    d = Vector(o.matrix_world.translation) - C
    horiz = math.hypot(d.x, d.y)
    print("  ", repr(o.name),
          "| 水平距轴", round(horiz, 4),
          "| 高差 dz", round(d.z, 4),
          "| 起始线仰角", round(math.degrees(math.atan2(-d.z, horiz)), 3), "度",
          "| 方位角", round(math.degrees(math.atan2(d.y, d.x)), 2),
          "| rot", tuple(round(math.degrees(v), 3) for v in o.rotation_euler),
          "| scale", tuple(round(v, 4) for v in o.scale))
    if not all(abs(v - 1.0) < 1e-9 for v in o.scale):
        print("     ⚠ 非单位缩放: 挂父子会传递缩放")

print("---- 灯对象 ----")
lamps = sorted([o for o in bpy.data.objects
                if o.type == 'LIGHT' and o.name.startswith(LAMP_PREFIX)],
               key=lambda o: o.name)
print("LAMP_COUNT", len(lamps))
for o in lamps:
    chain = []
    p = o.parent
    while p:
        chain.append(p.name)
        p = p.parent
    dirv = (o.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    print("  ", o.name,
          "| world", tuple(round(v, 3) for v in o.matrix_world.translation),
          "| dir", tuple(round(v, 3) for v in dirv),
          "| 链", " -> ".join(chain) if chain else "(无父级)",
          "| rot", tuple(round(math.degrees(v), 2) for v in o.rotation_euler))

print("---- 铰链 ----")
hinges = [o for o in bpy.data.objects if o.name.startswith(HINGE_PREFIX)]
print("HINGE_COUNT", len(hinges))
for h in hinges:
    nd = len(h.animation_data.drivers) if h.animation_data else 0
    print("  ", h.name, "| parent", h.parent.name if h.parent else None,
          "| drivers", nd,
          "| rot", tuple(round(math.degrees(v), 3) for v in h.rotation_euler))

print("---- 场景参数 ----")
print("  frame", sc.frame_start, "->", sc.frame_end, "| current", sc.frame_current)
print("  ", {k: sc[k] for k in sc.keys() if k.startswith(PARAM_PREFIX)})
print("PROBE_DONE")
