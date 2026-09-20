# verify_variants.py —— 两个方案的并列核验（结构 + 驱动 + 互不干扰）
import bpy

VAR = {
 'A 按条数(槽1)': dict(slot=1, mat='滚动效果网格体_滚筒斜纹_按条数', nodes=18, links=20,
                   prop='高度条纹数', dexp='hn', dpath='nodes["高度条纹N"].inputs[1].default_value',
                   panel='streak_count_panel.py', cls='VIEW3D_PT_streak_count', watch='_streak_count_watch',
                   extra=[]),
 'B 按角度(槽3)': dict(slot=3, mat='滚动效果网格体_滚筒斜纹_按角度', nodes=22, links=25,
                   prop='斜角', dexp='ang', dpath='nodes["斜角_弧度"].inputs[0].default_value',
                   panel='streak_angle_panel.py', cls='VIEW3D_PT_streak_angle', watch='_streak_angle_watch',
                   extra=['斜角_弧度', '斜角_正切', 'N_分子', 'N_计算']),
}
PASS, FAIL = [], []
def chk(n, c, d=''):
    (PASS if c else FAIL).append(n)
    print('  %s  %s%s' % ('PASS' if c else 'FAIL', n, ('   [%s]' % d) if d else ''))

ob = bpy.data.objects['滚动效果网格体']
ctrl = bpy.data.objects['竖条旋转控制']
print('槽位:', [(i, s.material.name if s.material else None) for i, s in enumerate(ob.material_slots)])
chk('槽 0 = 螺旋上升（保留）', ob.material_slots[0].material.name == '滚动效果网格体_螺旋上升')
chk('槽 2 = 端盖黑（共用）', ob.material_slots[2].material.name == '滚动效果网格体_端盖黑')
chk('两个方案材质同时存在（互不覆盖）',
    ob.material_slots[1].material.name == VAR['A 按条数(槽1)']['mat']
    and ob.material_slots[3].material.name == VAR['B 按角度(槽3)']['mat'])

for label, v in VAR.items():
    print('\n--- %s ---' % label)
    mat = bpy.data.materials.get(v['mat'])
    chk('%s 材质存在且 use_nodes' % label, bool(mat and mat.use_nodes))
    if not (mat and mat.use_nodes):
        continue
    nt = mat.node_tree
    chk('  节点 %d / 连线 %d' % (v['nodes'], v['links']),
        len(nt.nodes) == v['nodes'] and len(nt.links) == v['links'],
        '%d / %d' % (len(nt.nodes), len(nt.links)))
    for nm in ('螺旋合成', '相位取模', '前缘上升', '拖尾衰减', '波形合成', '发光配色', '高度条纹N'):
        chk('  节点 %s 存在' % nm, nm in nt.nodes)
    for nm in v['extra']:
        chk('  斜角链节点 %s 存在' % nm, nm in nt.nodes)
    chk('  螺旋合成 = SUBTRACT（/ 形）', nt.nodes['螺旋合成'].operation == 'SUBTRACT')
    chk('  波形在 Math 域（前缘/拖尾 = SMOOTHSTEP）',
        nt.nodes['前缘上升'].interpolation_type == 'SMOOTHSTEP'
        and nt.nodes['拖尾衰减'].interpolation_type == 'SMOOTHSTEP')
    drs = nt.animation_data.drivers if nt.animation_data else []
    found = {d.data_path: d.driver.expression for d in drs}
    chk('  驱动 7 条且全 valid', len(drs) == 7 and all(d.driver.is_valid for d in drs), '%d' % len(drs))
    chk('  ★ 上升偏移 = fr * us（实测定标）',
        found.get('nodes["上升偏移"].inputs[1].default_value') == 'fr * us')
    chk('  ★ 本方案的特征驱动 %s = %s' % (v['dpath'].split('"')[1], v['dexp']),
        found.get(v['dpath']) == v['dexp'], found.get(v['dpath'], '缺失'))
    chk('  ★★ ColorRamp 零驱动', not any('color_ramp' in d.data_path for d in drs))
    chk('  配色 2 色标（端点钉在 0/1）',
        len(nt.nodes['发光配色'].color_ramp.elements) == 2)
    chk('  控件键「%s」在 ctrl 上' % v['prop'], v['prop'] in ctrl)
    txt = bpy.data.texts.get(v['panel'])
    chk('  文本块 %s 在 + use_module' % v['panel'], bool(txt and txt.use_module))
    chk('  面板类 %s 已注册' % v['cls'], hasattr(bpy.types, v['cls']))
    wf = bpy.app.driver_namespace.get(v['watch'])
    chk('  看门狗 %s 在线' % v['watch'], bool(wf and bpy.app.timers.is_registered(wf)))

z = [p for p in ob.data.polygons if abs(abs(p.normal.z) - 1.0) < 1e-3]
chk('端盖面 = 2 个', len(z) == 2)
cur = ob.data.polygons[0].material_index
chk('★ 当前显示的是【单一个】方案（不是混合）', cur in (1, 3),
    '面索引=%d ⇒ %s' % (cur, '按条数' if cur == 1 else '按角度'))
print('\n' + '=' * 58)
print('VERIFY  通过 %d / 失败 %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   FAIL ->', f)
print('结论:', '✅ 全部通过' if not FAIL else '❌ 有失败项')
