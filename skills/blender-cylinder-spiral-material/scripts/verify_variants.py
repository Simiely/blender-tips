# verify_variants.py —— 两个方案的并列核验（结构 + 驱动 + 互不干扰）
import bpy

VAR = {
 'A 按条数(槽1)': dict(slot=1, mat='滚动效果网格体_滚筒斜纹_按条数', nodes=18, links=20,
                   prop='高度条纹数', dexp='floor(hn + 0.5)', dpath='nodes["高度条纹N"].inputs[1].default_value',
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
# ★ 不写死槽位索引（配置里 SLOT_INDEX/CAP_SLOT 可能调整），按材质名定位
_mats = [s2.material.name if s2.material else None for s2 in ob.material_slots]
chk('端盖材质在槽位里', '滚动效果网格体_端盖黑' in _mats, '%s' % _mats)
_stripe_i = next((i for i, m in enumerate(_mats) if m and '斜纹' in m), None)
chk('条纹材质在槽位里', _stripe_i is not None, '%s' % _mats)
_cap_i = _mats.index('滚动效果网格体_端盖黑') if '滚动效果网格体_端盖黑' in _mats else None
_cap_faces = {p.material_index for p in ob.data.polygons if abs(abs(p.normal.z) - 1.0) < 1e-3}
chk('★ 两个端盖面都指向端盖槽', _cap_i is not None and _cap_faces == {_cap_i},
    '端盖面索引 %s / 端盖槽 %s' % (_cap_faces, _cap_i))
_installed = [k for k, v in VAR.items() if bpy.data.materials.get(v['mat'])]
chk('至少装了一个方案', bool(_installed), '%s' % _installed)
chk('槽位里没有空槽（残留已清）',
    all(s2.material is not None for s2 in ob.material_slots),
    '%s' % [(i, s2.material.name if s2.material else None) for i, s2 in enumerate(ob.material_slots)])

for label, v in VAR.items():
    print('\n--- %s ---' % label)
    mat = bpy.data.materials.get(v['mat'])
    if not (mat and mat.use_nodes):
        print('  SKIP  %s 未安装（只装了另一个方案）' % label)
        continue
    chk('%s 材质存在且 use_nodes' % label, True)
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
chk('★ 侧面全部指向【条纹槽】（不是混着端盖材质）', cur == _stripe_i,
    '侧面面索引=%d / 条纹槽=%s' % (cur, _stripe_i))
print('\n--- 幽灵参数检查（ctrl 上没有节点引用不到的键）---')
for label, v in VAR.items():
    mat = bpy.data.materials.get(v['mat'])
    if not (mat and mat.use_nodes):
        continue
    _u = set()
    for d in (mat.node_tree.animation_data.drivers if mat.node_tree.animation_data else []):
        for var in d.driver.variables:
            if var.type == 'SINGLE_PROP' and var.targets[0].id is ctrl:
                _u.add(var.targets[0].data_path.strip('[]"'))
    # 本方案的面板只应列它自己那套键；ctrl 上其它方案的键也算幽灵（除非另一个方案装着）
    other = [k for k in ctrl.keys() if not k.startswith('_') and k not in _u]
    chk('%s：ctrl 上无本方案用不到的键' % label, not other, '幽灵 %s' % other)

print('\n' + '=' * 58)
print('VERIFY  通过 %d / 失败 %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   FAIL ->', f)
print('结论:', '✅ 全部通过' if not FAIL else '❌ 有失败项')
