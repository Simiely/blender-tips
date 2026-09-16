# -*- coding: utf-8 -*-
"""星芒散射光效系统 · 修复整体缩放驱动
把源『星芒』obj 的 3 条 scale 驱动表达式统一设为「实际大小/1000 + 动态缩放/1000」,
使控制器上的「动态缩放」循环动画也能作用到整体大小(与正确式一致)。
幂等、只改表达式/驱动变量、不动态谱场景几何。经桥执行: send.py [-p PORT] fix_star_scale.py
在改动前会先打印当前表达式供回滚参考。
"""
import bpy

SRC = '星芒'
CTRL = '星芒_控制器'
EXPR = 'a/1000 + b/1000'
A = '实际大小'
B = '动态缩放'


def _ensure_var(d, name, prop):
    for v in d.driver.variables:
        if v.name == name and v.targets:
            return v
    v = d.driver.variables.new()
    v.name = name
    v.type = 'SINGLE_PROP'
    t = v.targets[0]
    t.id_type = 'OBJECT'
    t.id = bpy.data.objects[CTRL]
    t.data_path = '["%s"]' % prop
    return v


def main():
    star = bpy.data.objects.get(SRC)
    ctl = bpy.data.objects.get(CTRL)
    if not star:
        print('未找到源 %s' % SRC)
        return
    if not ctl:
        print('未找到控制器 %s' % CTRL)
        return

    ad = star.animation_data_create()
    print('改动前 scale 驱动表达式:')
    cur = [d.driver.expression for d in ad.drivers if d.data_path == 'scale']
    for e in sorted(set(cur)):
        print('  ', e)

    for idx in (0, 1, 2):
        fc = next((d for d in ad.drivers if d.data_path == 'scale' and d.array_index == idx), None)
        if fc is None:
            fc = ad.drivers.new('scale', index=idx)
        d = fc.driver
        d.type = 'SCRIPTED'
        d.expression = EXPR
        _ensure_var(d, 'a', A)
        _ensure_var(d, 'b', B)
        try:
            d.update()
        except Exception:
            pass
        bpy.context.view_layer.update()

    star.update_tag()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = star.evaluated_get(dg)
    print('改动后 scale 驱动表达式: %s' % EXPR)
    print('改动后(当前帧) 评估 scale=%s' % (tuple(round(s, 6) for s in ev.scale)))
    print('FIX_STAR_SCALE_DONE')


main()