# 只读侦察：目标「平面」网格体的变换 / 尺寸 / 朝向 / 材质槽
# 用法: python send.py probe_plane.py   （只读，不改工程）
import bpy
from mathutils import Vector

TARGET = "平面"

ob = bpy.data.objects.get(TARGET)
print("found %s: %s | type: %s" % (TARGET, ob is not None, getattr(ob, "type", None)))
if ob:
    print("name:", ob.name)
    print("dimensions:", tuple(round(v, 4) for v in ob.dimensions))
    print("location:", tuple(round(v, 4) for v in ob.location))
    print("rotation_euler(deg):", tuple(round(v * 57.29578, 3) for v in ob.rotation_euler))
    print("scale:", tuple(round(v, 4) for v in ob.scale))
    print("法线(local Z -> world) =",
          tuple(round(v, 4) for v in (ob.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()))
    me = ob.data
    print("verts:", len(me.vertices), "polys:", len(me.polygons))
    print("mesh name:", me.name, "users:", me.users)
    print("material_slots:", [s.material.name if s.material else None for s in ob.material_slots])
    print("has_anim:", bool(ob.animation_data and ob.animation_data.action))
    print("collections:", [c.name for c in ob.users_collection])
    # 世界坐标包围盒（逐顶点，别用 bound_box × matrix_world —— 见 AGENTS.md 包围盒口径坑）
    pts = [ob.matrix_world @ v.co for v in me.vertices]
    print("world center:",
          tuple(round(sum(p[i] for p in pts) / len(pts), 4) for i in range(3)))
    print("面内半宽 X / Z:",
          round((max(p.x for p in pts) - min(p.x for p in pts)) / 2, 4),
          round((max(p.z for p in pts) - min(p.z for p in pts)) / 2, 4))

print("--- 场景中所有名字含「平面」的对象 ---")
for o in bpy.data.objects:
    if "平面" in o.name:
        print(" ", o.name, o.type, tuple(round(v, 3) for v in o.dimensions))

print("--- 现有材质名 ---")
for m in bpy.data.materials:
    print(" ", m.name, "use_nodes:", m.use_nodes)
