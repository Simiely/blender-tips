# switch_to_count.py —— 切到方案 A（按条数，槽 1）
import bpy
ob = bpy.data.objects['滚动效果网格体']
n = 0
for p in ob.data.polygons:
    t = 2 if abs(abs(p.normal.z) - 1.0) < 1e-3 else 1
    if p.material_index != t:
        p.material_index = t; n += 1
ob.active_material_index = 1
print('已切到【按条数】(槽1) | 改动 %d 面 | 槽位=%s'
      % (n, [(i, s.material.name if s.material else None) for i, s in enumerate(ob.material_slots)]))
