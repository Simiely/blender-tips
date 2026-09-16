# -*- coding: utf-8 -*-
"""下雪动态系统 · 独立核验器
逐项核对关键不变量,输出 通过/失败 清单。
不修改场景(只读 + depsgraph 评估)。经桥执行: send.py [-p PORT] verify_snow.py
"""
import bpy
import mathutils

HOST = '下雪_宿主'
SNOW = '花瓣雪花_低模'
PLANE = '平面.005'
GROUP = '下雪_GN'
COLL = '下雪_系统'
N_EXPECT = 250 * 200       # 50000
FALL_SPAN = 30.0


def check(name, ok, detail=''):
    print('%s %-40s %s' % ('[PASS]' if ok else '[FAIL]', name, detail))
    return ok


def main():
    ok_all = True

    host = bpy.data.objects.get(HOST)
    ok_all &= check('宿主 %s 存在' % HOST, host is not None)
    if host:
        ok_all &= check('宿主为 EMPTY(承载 GN 修改器)', host.type == 'EMPTY', 'type=%s' % host.type)
        ok_all &= check('宿主变换清零', tuple(round(v, 4) for v in host.location) == (0.0, 0.0, 0.0)
                        and tuple(round(v, 4) for v in host.scale) == (1.0, 1.0, 1.0),
                        'loc=%s' % (tuple(round(v, 3) for v in host.location),))
        gn = next((m for m in host.modifiers if m.type == 'NODES' and m.node_group and m.node_group.name == GROUP), None)
        ok_all &= check('宿主带 NODES 修改器 %s' % GROUP, gn is not None)
        ok_all &= check('宿主修改器视口开启', gn is not None and gn.show_viewport)

    snow = bpy.data.objects.get(SNOW)
    ok_all &= check('源 %s 存在' % SNOW, snow is not None)
    if snow:
        ok_all &= check('源 hide_render=True', snow.hide_render, '实际=%s' % snow.hide_render)
        ok_all &= check('源 hide_viewport=True', snow.hide_viewport, '实际=%s' % snow.hide_viewport)
        ok_all &= check('源 visible_camera=False', getattr(snow, 'visible_camera', True) is False)

    coll = bpy.data.collections.get(COLL)
    ok_all &= check('集合 %s 存在' % COLL, coll is not None)
    if coll:
        members = [o.name for o in coll.objects]
        for n in (HOST, SNOW, PLANE):
            ok_all &= check('集合含 %s' % n, n in members, '成员=%s' % members[:6])

    ng = bpy.data.node_groups.get(GROUP)
    ok_all &= check('节点组 %s 存在' % GROUP, ng is not None)
    if ng:
        rel = sum(1 for nd in ng.nodes if nd.type == 'OBJECT_INFO' and getattr(nd, 'transform_space', '') == 'RELATIVE')
        ok_all &= check('%s ObjectInfo 用 RELATIVE' % GROUP, rel >= 1, 'RELATIVE数=%d' % rel)
        grid = next((nd for nd in ng.nodes if nd.type == 'MESH_GRID'), None)
        if grid:
            ok_all &= check('栅格 %s×%s=%d' % (250, 200, N_EXPECT),
                            int(grid.inputs['Vertices X'].default_value) == 250
                            and int(grid.inputs['Vertices Y'].default_value) == 200,
                            '实际=%sx%s' % (grid.inputs['Vertices X'].default_value, grid.inputs['Vertices Y'].default_value))
        fmod = any(nd.type == 'MATH' and getattr(nd, 'operation', '') == 'FLOORED_MODULO' for nd in ng.nodes)
        ok_all &= check('%s 含 FLOORED_MODULO(循环回卷)' % GROUP, fmod)

    # 实例核验(取 3 帧抽样)
    ok = True
    for fr in (1, 75, 150):
        bpy.context.scene.frame_set(fr)
        dep = bpy.context.evaluated_depsgraph_get()
        n = 0
        attrs = []
        for inst in dep.object_instances:
            if not inst.is_instance:
                continue
            if inst.parent is None or inst.parent.name != HOST:
                continue
            n += 1
            attrs.append(inst.matrix_world.translation)
        if len(attrs) == 0:
            ok_all &= check('frame=%d 实例>0' % fr, False, '无实例')
            return ok_all
        zs = [t[2] for t in attrs]
        ok &= n == N_EXPECT
        ok &= abs(min(zs) - (-1.30)) < 0.2 and abs(max(zs) - (-1.30 + FALL_SPAN)) < 0.2
        print('  ℹ️ frame=%d 实例=%d  Z[%.2f, %.2f]' % (fr, n, min(zs), max(zs)))
    ok_all &= check('实例数 == %d(3帧)' % N_EXPECT, ok,
                    '上面 ℹ️ 每帧一致且 Z 贴地[~-1.3, ~28.7] 才通过')

    print()
    print('VERIFY_RESULT=%s' % ('ALL_PASS' if ok_all else 'HAS_FAIL'))


main()