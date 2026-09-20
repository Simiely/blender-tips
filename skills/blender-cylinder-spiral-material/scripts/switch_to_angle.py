# switch_to_angle.py —— 切到方案 B（按角度，槽 3）
import bpy
ob = bpy.data.objects['滚动效果网格体']
n = 0
for p in ob.data.polygons:
    t = 2 if abs(abs(p.normal.z) - 1.0) < 1e-3 else 3
    if p.material_index != t:
        p.material_index = t; n += 1
ob.active_material_index = 3
print('已切到【按角度】(槽3) | 改动 %d 面 | 槽位=%s'
      % (n, [(i, s.material.name if s.material else None) for i, s in enumerate(ob.material_slots)]))
