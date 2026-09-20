import bpy
ob = bpy.data.objects['滚动效果网格体']
mw = ob.matrix_world
vs = [mw @ v.co for v in ob.data.vertices]
xs = [v.x for v in vs]; ys = [v.y for v in vs]; zs = [v.z for v in vs]
print('世界包围盒  X [%.4f, %.4f]   Y [%.4f, %.4f]   Z [%.4f, %.4f]'
      % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
cx = (min(xs)+max(xs))/2.0; cy = (min(ys)+max(ys))/2.0
rx = (max(xs)-min(xs))/2.0; ry = (max(ys)-min(ys))/2.0
print('几何轴心 XY = (%.4f, %.4f) | 半径 X=%.4f  Y=%.4f' % (cx, cy, rx, ry))
print('柱高 = %.4f | zmin = %.4f | zmax = %.4f' % (max(zs)-min(zs), min(zs), max(zs)))
c = bpy.data.objects['竖条旋转控制'].location
print('锚点        = (%.4f, %.4f, %.4f)' % (c.x, c.y, c.z))
print('锚点偏差    dx=%+.4f  dy=%+.4f  dz=%+.4f  （应全为 0）'
      % (c.x-cx, c.y-cy, c.z-min(zs)))
print('对象 scale  =', tuple(round(v, 4) for v in ob.scale),
      '| rotation =', tuple(round(v, 4) for v in ob.rotation_euler))
print('修改器      =', [m.type for m in ob.modifiers])
print('顶点数      =', len(ob.data.vertices), '| 面数 =', len(ob.data.polygons))
# 校验：所有侧面顶点到轴心的距离是否恒定（真圆柱）
d = [((v.x-cx)**2 + (v.y-cy)**2) ** 0.5 for v in vs]
import statistics
print('顶点到轴心距离：min=%.4f max=%.4f 标准差=%.6f' % (min(d), max(d), statistics.pstdev(d)))
