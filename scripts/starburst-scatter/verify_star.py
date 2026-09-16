# -*- coding: utf-8 -*-
"""星芒散射光效系统 · 独立核验器
逐项核对关键不变量,输出 通过/失败 清单。
不修改场景(只读 + depsgraph 评估)。经桥执行: send.py [-p PORT] verify_star.py
"""
import bpy

SRC = '星芒'
CTRL = '星芒_控制器'
EXPECT_OFFSET = {
    '星芒_散布_GN': (-0.0065, -0.0076, 0.0),
    '星芒_散布_GN_3': (-0.0065, 0.0, -0.0076),
    '星芒_散布_GN_4': (-0.0065, 0.0076, 0.0),
}


def check(name, ok, detail=''):
    print('%s %-36s %s' % ('[PASS]' if ok else '[FAIL]', name, detail))
    return ok


def main():
    ok_all = True
    ok_all &= check('控制器存在', bpy.data.objects.get(CTRL) is not None)
    ctl = bpy.data.objects.get(CTRL)
    if ctl:
        params = ['尖角长度', '圆盘半径', '基部半角', '内凹程度', '实际大小', '动态缩放']
        missing = [p for p in params if p not in ctl]
        ok_all &= check('控制器 6 参数齐全', not missing, '缺: %s' % missing if missing else '')
        cad = ctl.animation_data
        cyc = False
        if cad and cad.action:
            for layer in getattr(cad.action, 'layers', []):
                for strip in getattr(layer, 'strips', []):
                    for cb in getattr(strip, 'channelbags', []):
                        for fc in getattr(cb, 'fcurves', []):
                            if 'CYCLES' in [m.type for m in getattr(fc, 'modifiers', [])]:
                                cyc = True
        ok_all &= check('控制器动态缩放 CYCLES 动画', cyc, cad.action.name if cyc and cad and cad.action else '')

    star = bpy.data.objects.get(SRC)
    ok_all &= check('源 %s 存在' % SRC, star is not None)
    if star:
        ok_all &= check('源 hide_render=True', star.hide_render, '实际=%s' % star.hide_render)
        ok_all &= check('源 未隐藏视口', not star.hide_viewport, 'hide_viewport=%s' % star.hide_viewport)
        gn_mod = next((m for m in star.modifiers if m.node_group and m.node_group.name == '星芒_GN'), None)
        ok_all &= check('源带 星芒_GN 修改器', gn_mod is not None)
        expr_ok = True
        if star.animation_data:
            sd = [d for d in star.animation_data.drivers if d.data_path == 'scale']
            for d in sd:
                if not d.driver.expression.startswith('a/1000'):
                    expr_ok = False
            ok_all &= check('源 scale 驱动 3 条且含 实际大小/1000', len(sd) == 3 and expr_ok,
                            'expr=%s' % (sorted({d.driver.expression for d in sd}) if sd else '无驱动'))
            shape_ok = all(any(d.data_path == 'modifiers["星芒_GN"].properties.inputs.Socket_%d.value' % i
                               for d in star.animation_data.drivers) for i in range(4))
            ok_all &= check('源 4 条形状驱动 Socket_0..3', shape_ok)

    for g, expected in EXPECT_OFFSET.items():
        ng = bpy.data.node_groups.get(g)
        ok_all &= check('节点组 %s 存在' % g, ng is not None)
        if ng:
            off = None
            nrel = 0
            for nd in ng.nodes:
                if nd.type == 'COMBXYZ' and '002' in nd.name:
                    if not any(l.to_node == nd for l in ng.links):
                        off = (round(float(nd.inputs['X'].default_value), 6),
                            round(float(nd.inputs['Y'].default_value), 6),
                            round(float(nd.inputs['Z'].default_value), 6))
                if nd.type == 'OBJECT_INFO' and nd.transform_space == 'RELATIVE':
                    nrel += 1
            ok_all &= check('%s ObjectInfo 用 RELATIVE' % g, nrel >= 2, 'RELATIVE数=%d' % nrel)
            ok_all &= check('%s 位置偏移正确' % g, off == expected, '实际=%s' % (off,))

    vl = bpy.context.view_layer
    ok_all &= check('material_override 为空(发光不被覆盖)', vl.material_override is None)
    ok_all &= check('渲染引擎 Eevee', bpy.context.scene.render.engine == 'BLENDER_EEVEE',
                    bpy.context.scene.render.engine)

    print()
    print('VERIFY_RESULT=%s' % ('ALL_PASS' if ok_all else 'HAS_FAIL'))
    return 0 if ok_all else 1


main()