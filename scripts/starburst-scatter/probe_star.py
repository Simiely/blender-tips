# -*- coding: utf-8 -*-
"""星芒散射光效系统 · 只读探查
读取 星芒_效果 集合与相关数据块,输出当前关键状态
(控制器 6 参数 / 源 星芒 修改器与驱动 / 三宿主散布组偏移 / ObjectInfo 空间 / 控制器动画)。
经桥执行: send.py [-p PORT] probe_star.py
"""
import bpy

SRC = '星芒'
CTRL = '星芒_控制器'
HOSTS = [('球心_点云', '星芒_散布_GN_4'), ('球心_点云2', '星芒_散布_GN'),
         ('球心_点云3', '星芒_散布_GN_3')]


def fmt(v, n=4):
    if hasattr(v, '__len__'):
        try:
            return tuple(round(float(x), n) for x in v)
        except Exception:
            return str(v)
    return round(float(v), n)


def main():
    print('==== 控制器 %s 参数 ====' % CTRL)
    ctl = bpy.data.objects.get(CTRL)
    if ctl:
        for k in ['尖角长度', '圆盘半径', '基部半角', '内凹程度', '实际大小', '动态缩放']:
            if k in ctl:
                print('  %-8s = %r' % (k, ctl[k]))
        cad = ctl.animation_data
        if cad and cad.action:
            for layer in getattr(cad.action, 'layers', []):
                for strip in getattr(layer, 'strips', []):
                    for cb in getattr(strip, 'channelbags', []):
                        for fc in getattr(cb, 'fcurves', []):
                            pts = [(round(kp.co[0], 2), round(kp.co[1], 4)) for kp in fc.keyframe_points]
                            mods = [m.type for m in getattr(fc, 'modifiers', [])]
                            print('  action=%s fcurve=%r 关键帧=%s 修饰器=%s' % (
                                cad.action.name, fc.data_path, pts, mods))
    else:
        print('  未找到 %s' % CTRL)

    print()
    print('==== 源 %s 修改器与驱动 ====' % SRC)
    star = bpy.data.objects.get(SRC)
    if star:
        for m in star.modifiers:
            print('  修改器 %-12s type=%s node_group=%s' % (
                m.name, m.type, m.node_group.name if m.node_group else None))
        for d in star.animation_data.drivers:
            print('  driver %-46s expr=%r 变量=%s' % (
                d.data_path, d.driver.expression,
                [(v.name, v.targets[0].data_path) for v in d.driver.variables]))
        print('  位置=%s scale=%s hide_render=%s visible_camera=%s' % (
            fmt(star.location), fmt(star.scale), star.hide_render, star.visible_camera))

    print()
    print('==== 三宿主散布组 偏移(合并XYZ.002) 与 ObjectInfo 空间 ====')
    for host, g in HOSTS:
        ng = bpy.data.node_groups.get(g)
        if not ng:
            print('  [%s] %s 不存在' % (host, g))
            continue
        off = None
        for nd in ng.nodes:
            if nd.type == 'COMBXYZ' and '002' in nd.name:
                wired = any(l.to_node == nd for l in ng.links)
                if not wired:
                    off = (round(float(nd.inputs['X'].default_value), 6),
                           round(float(nd.inputs['Y'].default_value), 6),
                           round(float(nd.inputs['Z'].default_value), 6))
                    break
        ois = [(nd.inputs['Object'].default_value.name if nd.inputs['Object'].default_value else None, nd.transform_space)
               for nd in ng.nodes if nd.type == 'OBJECT_INFO']
        print('  %-10s [%-14s] 偏移合并XYZ.002=%s  ObjectInfo=%s' % (host, g, off, ois))

    print('PROBE_STAR_DONE')


main()