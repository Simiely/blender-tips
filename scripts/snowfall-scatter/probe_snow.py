# -*- coding: utf-8 -*-
import bpy
import mathutils


def bbox(obj):
    m = obj.matrix_world
    wc = [m @ mathutils.Vector(c) for c in obj.bound_box]
    xs = [c[0] for c in wc]; ys = [c[1] for c in wc]; zs = [c[2] for c in wc]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


for name in ('平面.005', '花瓣雪花_低模'):
    o = bpy.data.objects.get(name)
    if o is None:
        print('[ref] %s 不存在' % name)
        continue
    b = bbox(o)
    print('[ref] %-16s loc=%.2f,%.2f,%.2f  scale=(%.2f,%.2f,%.2f)  Z[%.2f,%.2f]'
          % (name, o.location[0], o.location[1], o.location[2],
             o.scale[0], o.scale[1], o.scale[2], b[4], b[5]))

host = bpy.data.objects.get('下雪_宿主')
if host:
    print('[host] 下雪_宿主 loc=%.2f,%.2f,%.2f' % host.location[:])

for fr in (1, 75, 150):
    bpy.context.scene.frame_set(fr)
    dep = bpy.context.evaluated_depsgraph_get()
    zs = []
    count = 0
    for inst in dep.object_instances:
        if not inst.is_instance:
            continue
        parent = inst.parent
        if parent is None or parent.name != '下雪_宿主':
            continue
        t = inst.matrix_world.translation
        zs.append(t[2]); count += 1
    if zs:
        print('[inst] frame=%3d  n=%d  Z[min=%.2f  avg=%.2f  max=%.2f]'
              % (fr, count, min(zs), sum(zs) / len(zs), max(zs)))