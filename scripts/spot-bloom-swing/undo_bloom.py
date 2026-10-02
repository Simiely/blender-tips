# 撤销: 拆掉铰链架构, 把灯挂回定位空对象
# 构建前的默认姿态是「竖直朝上」= rotation_euler (pi, 0, 0);
# 若你构建前是别的姿态, 改下面 RESTORE_ROT
import bpy
import math
from mathutils import Vector

COLLECTION = "动态灯的坐标"
LAMP_PREFIX = "射灯_光"
HINGE_PREFIX = "射灯_铰链"
SPOT_PREFIX = "射灯"
RESTORE_ROT = (math.pi, 0.0, 0.0)   # 竖直朝上
PARAM_PREFIX = "bloom_"

sc = bpy.context.scene

moved = []
for o in list(bpy.data.objects):
    if o.type != 'LIGHT' or not o.name.startswith(LAMP_PREFIX):
        continue
    if o.parent is not None and o.parent.name.startswith(HINGE_PREFIX):
        base_name = o.name.replace(LAMP_PREFIX, SPOT_PREFIX, 1)
        base = bpy.data.objects.get(base_name)
        assert base is not None, "定位空对象缺失: " + base_name
        o.parent = base
        o.location = (0.0, 0.0, 0.0)
        o.rotation_euler = RESTORE_ROT
        moved.append((o.name, base_name))
print("RESTORED_LAMPS", moved)

removed = []
for h in [x for x in bpy.data.objects if x.name.startswith(HINGE_PREFIX)]:
    if h.animation_data:
        for d in list(h.animation_data.drivers):
            h.animation_data.drivers.remove(d)
    removed.append(h.name)
    bpy.data.objects.remove(h, do_unlink=True)
print("REMOVED_HINGES", removed)

for k in [k for k in sc.keys() if k.startswith(PARAM_PREFIX)]:
    del sc[k]
print("REMOVED_PARAMS", PARAM_PREFIX + "*")

bpy.context.view_layer.update()

# 核验: 8 盏应完全一致
lamps = sorted([o for o in bpy.data.objects
                if o.type == 'LIGHT' and o.name.startswith(LAMP_PREFIX)],
               key=lambda o: o.name)
bad = []
for o in lamps:
    dirv = (o.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    upness = dirv.dot(Vector((0.0, 0.0, 1.0)))
    err = (Vector(o.matrix_world.translation) - Vector(o.parent.location)).length \
        if o.parent else 9.9
    print("  ", o.name, "| parent", o.parent.name if o.parent else None,
          "| dir", tuple(round(v, 3) for v in dirv),
          "| up", round(upness, 6), "| 位置误差", round(err, 9))
    if abs(upness - 1.0) > 1e-6 or err > 1e-6:
        bad.append(o.name)
print("BAD", bad)
print("UNDO_DONE", "PASS" if not bad else "FAIL(检查 RESTORE_ROT 是否为构建前姿态)")
