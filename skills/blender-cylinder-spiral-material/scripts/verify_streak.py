# verify_streak.py —— 独立核验 v3「滚筒斜纹」材质（结构 + 行为）
# 真值一律从【求值依赖图】读（evaluated_get），不是读原始值。
#
# v3 的设计目标（本脚本逐条验证）：
#   · 波形仍在 Math 域 —— MapRange(SMOOTHSTEP) ∩ MapRange(SMOOTHSTEP)
#   · ★ 新增高度项：f = u×K − v'×N（SUBTRACT）⇒ 条纹成 `/` 形
#   · ★ 上升驱动 = +fr * us（实测定标：该符号才让条纹往左上走）
#   · ★ ColorRamp 上一条驱动都没有 ⇒ 用户可以自由加色标
#   · 端盖按法线分到独立纯黑槽
import bpy

OBJ = '滚动效果网格体'
MAT = '滚动效果网格体_竖条旋转'
CTRL = '竖条旋转控制'
SPIRAL_MAT = '滚动效果网格体_螺旋上升'
CAP_MAT = '滚动效果网格体_端盖黑'
PANEL_TEXT = 'streak_panel.py'
DEF = {'条纹数量': 3.0, '高度条纹数': 2.0, '前缘宽度': 0.12, '拖尾起点': 0.22,
       '上升速度': 0.01, '旋转速度': 0.0, '发光强度': 5.0}
DEPRECATED = ('条纹宽度', '渐变柔化', '流星拖尾')
HEIGHT_CONST = 13.6764

PASS, FAIL = [], []


def chk(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  %s  %s%s' % ('PASS' if cond else 'FAIL', name, ('   [%s]' % detail) if detail else ''))


ob = bpy.data.objects.get(OBJ)
mat = bpy.data.materials.get(MAT)
ctrl = bpy.data.objects.get(CTRL)
chk('目标对象存在', ob is not None)
chk('材质存在且 use_nodes', bool(mat and mat.use_nodes))
chk('控制空物体存在', ctrl is not None)
if not (ob and mat and mat.use_nodes and ctrl):
    print('X 前置条件不足，终止')
    raise SystemExit(1)

nt = mat.node_tree


def ev_tree():
    return mat.evaluated_get(bpy.context.evaluated_depsgraph_get()).node_tree


def gv(node_name, idx):
    return ev_tree().nodes[node_name].inputs[idx].default_value


def bsdf_strength():
    b = next(n for n in ev_tree().nodes if n.type == 'BSDF_PRINCIPLED')
    return b.inputs['Emission Strength'].default_value


print('\n--- A. 槽位与面索引 ---')
slots = [(i, s.material.name if s.material else None) for i, s in enumerate(ob.material_slots)]
chk('槽 1 = 滚筒斜纹材质', len(slots) > 1 and slots[1][1] == MAT, '%s' % slots)
chk('槽 0 = 螺旋上升材质（未被破坏）', slots[0][1] == SPIRAL_MAT, '%s' % slots)
chk('槽 2 = 端盖黑材质', len(slots) > 2 and slots[2][1] == CAP_MAT, '%s' % slots)
idx_dist = {}
for p in ob.data.polygons:
    idx_dist[p.material_index] = idx_dist.get(p.material_index, 0) + 1
chk('侧面 32 → 槽1 / 端盖 2 → 槽2', idx_dist == {1: 32, 2: 2}, '%s' % idx_dist)
z_caps = [p.index for p in ob.data.polygons if abs(abs(p.normal.z) - 1.0) < 1e-3]
chk('端盖面 = 2 个（按法线判定）', len(z_caps) == 2, '%s' % z_caps)
capm = bpy.data.materials.get(CAP_MAT)
capb = next((n for n in capm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) \
    if (capm and capm.use_nodes) else None
chk('端盖材质 = 纯黑不发光、不反光',
    bool(capb and tuple(capb.inputs['Emission Color'].default_value)[:3] == (0.0, 0.0, 0.0)
         and abs(capb.inputs['Emission Strength'].default_value) < 1e-6
         and tuple(capb.inputs['Base Color'].default_value)[:3] == (0.0, 0.0, 0.0)))

print('\n--- B. 锚点空物体 ---')
chk('位置 = 柱轴心/底面中心',
    all(abs(a - b) < 1e-4 for a, b in zip(ctrl.location, (30.9216, 2.8832, -1.1444))),
    '%s' % (tuple(round(v, 4) for v in ctrl.location),))
chk('rotation = 0', all(abs(v) < 1e-6 for v in ctrl.rotation_euler))
chk('scale = 1', all(abs(v - 1.0) < 1e-6 for v in ctrl.scale))
chk('无父级', ctrl.parent is None)
chk('7 个控件键齐全', all(k in ctrl for k in DEF), '%s' % sorted(k for k in ctrl.keys()))
chk('旧版废弃控件已清理', not any(k in ctrl for k in DEPRECATED),
    '残留 %s' % [k for k in DEPRECATED if k in ctrl])

print('\n--- C. 节点结构（v3 = 高度项 + Math 域波形）---')
EXPECT = {
    '纹理坐标': 'ShaderNodeTexCoord',
    '分离XYZ': 'ShaderNodeSeparateXYZ',
    '柱面_相位角': 'ShaderNodeMath',
    '柱面_角度偏置': 'ShaderNodeMath',
    '柱面_角度U': 'ShaderNodeMath',
    '柱面_高度V': 'ShaderNodeMath',
    '旋转相位': 'ShaderNodeMath',
    '条纹数量K': 'ShaderNodeMath',
    '上升偏移': 'ShaderNodeMath',
    '高度条纹N': 'ShaderNodeMath',
    '螺旋合成': 'ShaderNodeMath',
    '相位取模': 'ShaderNodeMath',
    '前缘上升': 'ShaderNodeMapRange',
    '拖尾衰减': 'ShaderNodeMapRange',
    '波形合成': 'ShaderNodeMath',
    '发光配色': 'ShaderNodeValToRGB',
}
for n, bl in EXPECT.items():
    node = nt.nodes.get(n)
    chk('节点 %s (%s)' % (n, bl.replace('ShaderNode', '')), bool(node and node.bl_idname == bl),
        node.bl_idname if node else '缺失')
chk('节点总数 = 18', len(nt.nodes) == 18, '%d' % len(nt.nodes))
chk('连线总数 = 20', len(nt.links) == 20, '%d' % len(nt.links))
t = next(n for n in nt.nodes if n.type == 'TEX_COORD')
chk('TexCoord.object → 控制空物体', t.object is not None and t.object.name == CTRL,
    t.object.name if t.object else 'None')

print('\n--- D. 连线逐条（按名字比，节点不是 ID 数据）---')


def link_of(to_node_name, input_name=None, input_index=None):
    out = []
    for l in nt.links:
        if l.to_node.name != to_node_name:
            continue
        if input_index is not None:
            if list(l.to_node.inputs).index(l.to_socket) == input_index:
                out.append(l)
        elif l.to_socket.name == input_name:
            out.append(l)
    return out


PAIRS = [
    ('分离XYZ', 0, '纹理坐标'),
    ('柱面_相位角', 0, '分离XYZ'),
    ('柱面_相位角', 1, '分离XYZ'),
    ('柱面_角度偏置', 0, '柱面_相位角'),
    ('柱面_角度U', 0, '柱面_角度偏置'),
    ('柱面_高度V', 0, '分离XYZ'),
    ('旋转相位', 0, '柱面_角度U'),
    ('条纹数量K', 0, '旋转相位'),
    ('上升偏移', 0, '柱面_高度V'),
    ('高度条纹N', 0, '上升偏移'),
    ('螺旋合成', 0, '条纹数量K'),
    ('螺旋合成', 1, '高度条纹N'),
    ('相位取模', 0, '螺旋合成'),
    ('前缘上升', 0, '相位取模'),
    ('拖尾衰减', 0, '相位取模'),
    ('波形合成', 0, '前缘上升'),
    ('波形合成', 1, '拖尾衰减'),
    ('发光配色', 0, '波形合成'),
]
for tn, ti, fn in PAIRS:
    ls = link_of(tn, input_index=ti)
    chk('%s.in%d ← %s' % (tn, ti, fn),
        len(ls) == 1 and ls[0].from_node.name == fn,
        ls[0].from_node.name if ls else '无')
ls = link_of('分离XYZ', input_name='Vector')
chk('分离XYZ.Vector ← 纹理坐标.Object',
    len(ls) == 1 and ls[0].from_socket.name == 'Object')
l0, l1 = link_of('柱面_相位角', input_index=0), link_of('柱面_相位角', input_index=1)
chk('ARCTAN2 输入0 = Y（分子）', len(l0) == 1 and l0[0].from_socket.name == 'Y',
    l0[0].from_socket.name if l0 else '无')
chk('ARCTAN2 输入1 = X（分母）', len(l1) == 1 and l1[0].from_socket.name == 'X',
    l1[0].from_socket.name if l1 else '无')
b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
ls = link_of(b.name, input_name='Emission Color')
chk('BSDF.Emission Color ← 发光配色.Color',
    len(ls) == 1 and ls[0].from_node.name == '发光配色',
    ls[0].from_node.name if ls else '无')
ls = link_of('材质输出', input_name='Surface')
chk('材质输出.Surface ← BSDF', len(ls) == 1 and ls[0].from_node.type == 'BSDF_PRINCIPLED')

print('\n--- E. 螺旋合成与波形构造 ---')
chk('★ 螺旋合成 = SUBTRACT（u×K − v×N ⇒ 条纹是 / 形）',
    nt.nodes['螺旋合成'].operation == 'SUBTRACT', nt.nodes['螺旋合成'].operation)
chk('柱面_高度V = MULTIPLY（z × 1/柱高）', nt.nodes['柱面_高度V'].operation == 'MULTIPLY')
chk('高度V 系数 = 1/柱高', abs(nt.nodes['柱面_高度V'].inputs[1].default_value
                                - 1.0 / HEIGHT_CONST) < 1e-9,
    '%.8f' % nt.nodes['柱面_高度V'].inputs[1].default_value)
chk('上升偏移 = ADD', nt.nodes['上升偏移'].operation == 'ADD')
chk('高度条纹N = MULTIPLY', nt.nodes['高度条纹N'].operation == 'MULTIPLY')
chk('相位取模 = FLOORED_MODULO（负偏移时不裁条纹）',
    nt.nodes['相位取模'].operation == 'FLOORED_MODULO', nt.nodes['相位取模'].operation)
chk('波形合成 = MINIMUM（取包络）', nt.nodes['波形合成'].operation == 'MINIMUM',
    nt.nodes['波形合成'].operation)
rise, fall = nt.nodes['前缘上升'], nt.nodes['拖尾衰减']
chk('前缘上升 interpolation = SMOOTHSTEP', rise.interpolation_type == 'SMOOTHSTEP',
    rise.interpolation_type)
chk('拖尾衰减 interpolation = SMOOTHSTEP', fall.interpolation_type == 'SMOOTHSTEP',
    fall.interpolation_type)
chk('两个 MapRange 都 clamp 开启', bool(rise.clamp) and bool(fall.clamp))
chk('前缘 From = (0, 前缘宽度)', abs(rise.inputs[1].default_value) < 1e-6
    and abs(rise.inputs[2].default_value - DEF['前缘宽度']) < 1e-6,
    'From %.4f..%.4f' % (rise.inputs[1].default_value, rise.inputs[2].default_value))
chk('前缘 To = (0, 1)', abs(rise.inputs[3].default_value) < 1e-6
    and abs(rise.inputs[4].default_value - 1.0) < 1e-6)
chk('拖尾 From = (拖尾起点, 1)', abs(fall.inputs[1].default_value - DEF['拖尾起点']) < 1e-6
    and abs(fall.inputs[2].default_value - 1.0) < 1e-6,
    'From %.4f..%.4f' % (fall.inputs[1].default_value, fall.inputs[2].default_value))
chk('拖尾 To = (1, 0)', abs(fall.inputs[3].default_value - 1.0) < 1e-6
    and abs(fall.inputs[4].default_value) < 1e-6)
chk('★ 拖尾长度 = 1 − 拖尾起点 = %.2f' % (1 - DEF['拖尾起点']),
    abs((1 - DEF['拖尾起点']) - 0.78) < 1e-9)

print('\n--- F. 颜色节点（★ 完全交给用户）---')
cr = nt.nodes['发光配色'].color_ramp
chk('配色 ColorRamp 共 2 个色标（用户可自由加）', len(cr.elements) == 2, '%d' % len(cr.elements))
chk('配色左端 = 不发光色，位置 = 0',
    abs(cr.elements[0].position) < 1e-9 and tuple(cr.elements[0].color)[:3] == (0.0, 0.0, 0.0))
chk('配色右端 = 发光色，位置 = 1',
    abs(cr.elements[1].position - 1.0) < 1e-9 and tuple(cr.elements[1].color)[:3] == (1.0, 1.0, 1.0))
chk('BSDF Base Color = 黑', tuple(b.inputs['Base Color'].default_value)[:3] == (0.0, 0.0, 0.0))
chk('BSDF Roughness = 1', abs(b.inputs['Roughness'].default_value - 1.0) < 1e-6)
chk('BSDF Metallic = 0', abs(b.inputs['Metallic'].default_value) < 1e-6)

print('\n--- G. 驱动 ---')
drs = nt.animation_data.drivers if nt.animation_data else []
found = {d.data_path: d.driver.expression for d in drs}
chk('驱动数 = 7', len(drs) == 7, '%d' % len(drs))
NEED = {
    'nodes["旋转相位"].inputs[1].default_value': '-fr * sp',
    'nodes["上升偏移"].inputs[1].default_value': 'fr * us',
    'nodes["条纹数量K"].inputs[1].default_value': 'kn',
    'nodes["高度条纹N"].inputs[1].default_value': 'hn',
    'nodes["前缘上升"].inputs[2].default_value': 'fe',
    'nodes["拖尾衰减"].inputs[1].default_value': 'ts',
}
for p, e in NEED.items():
    chk('驱动 %s = %s' % (p.split('"')[1], e), found.get(p) == e, found.get(p, '缺失'))
chk('★ 上升偏移用【正号】（实测定标：负号会让条纹往右下）',
    found.get('nodes["上升偏移"].inputs[1].default_value') == 'fr * us',
    found.get('nodes["上升偏移"].inputs[1].default_value', '缺失'))
chk('7 条驱动全 is_valid', all(d.driver.is_valid for d in drs))
chk('驱动变量均为 SINGLE_PROP', all(v.type == 'SINGLE_PROP' for d in drs for v in d.driver.variables))
vn = {v.name for d in drs for v in d.driver.variables}
chk('驱动变量名集合 = {fr,sp,us,kn,hn,fe,ts,st}',
    vn == {'fr', 'sp', 'us', 'kn', 'hn', 'fe', 'ts', 'st'}, '%s' % sorted(vn))
bsdf_p = 'nodes["%s"].inputs[29].default_value' % b.name
chk('BSDF 强度驱动 = st', found.get(bsdf_p) == 'st', found.get(bsdf_p, '缺失'))
chk('★★ ColorRamp 上【没有任何】驱动（核心目标）',
    not any('color_ramp' in d.data_path for d in drs),
    '%s' % [d.data_path for d in drs if 'color_ramp' in d.data_path])

print('\n--- H. 面板 / 文本块 ---')
txt = bpy.data.texts.get(PANEL_TEXT)
chk('Register 文本块存在', txt is not None)
chk('文本块 use_module == True', bool(txt and txt.use_module))
mod = None
try:
    mod = txt.as_module()
except Exception as e:
    print('   as_module 失败:', repr(e))
chk('文本块可作模块加载', mod is not None)
wf = bpy.app.driver_namespace.get('_streak_watch')
chk('看门狗定时器在线', bool(wf and bpy.app.timers.is_registered(wf)))
chk('面板类已注册', hasattr(bpy.types, 'VIEW3D_PT_streak'))
chk('面板类 bl_category = 滚筒斜纹',
    bool(mod and hasattr(mod, 'VIEW3D_PT_streak')
         and mod.VIEW3D_PT_streak.bl_category == '滚筒斜纹'),
    mod.VIEW3D_PT_streak.bl_category if mod and hasattr(mod, 'VIEW3D_PT_streak') else None)
chk('面板 PROPS 与 v3 控件一致',
    bool(mod and getattr(mod, 'PROPS', None) ==
         ['条纹数量', '高度条纹数', '前缘宽度', '拖尾起点', '上升速度', '旋转速度', '发光强度']),
    '%s' % (getattr(mod, 'PROPS', None) if mod else None))
chk('旧 v1 面板类未复活', not hasattr(bpy.types, 'VIEW3D_PT_vertical_stripes'))

print('\n--- I. 无临时残留 ---')
junk = [m.name for m in bpy.data.materials if m.name.startswith(('_SKILLTEST', '_PV_', '_wb_', '__probe'))]
junko = [o.name for o in bpy.data.objects if o.name.startswith(('_SKILLTEST', '_PV_', '_wb_', '__probe'))]
chk('无临时材质残留', not junk, '%s' % junk)
chk('无临时对象残留', not junko, '%s' % junko)

print('\n--- J. 行为断言（改控件 → 从求值图读真值）---')
sc = bpy.context.scene
f0 = sc.frame_current


def setk(k, v):
    """⚠️ 只改 IDProperty 不会让依赖图失效 ⇒ 必须手动 tag ctrl + mat + node_tree 三处。"""
    ctrl[k] = v
    ctrl.update_tag()
    mat.update_tag()
    if mat.node_tree:
        mat.node_tree.update_tag()
    bpy.context.view_layer.update()


setk('前缘宽度', 0.35)
chk('改「前缘宽度」→ 前缘 From Max 跟随', abs(gv('前缘上升', 2) - 0.35) < 1e-6,
    '%.4f' % gv('前缘上升', 2))
setk('前缘宽度', 0.05)
chk('再改「前缘宽度」→ 跟随', abs(gv('前缘上升', 2) - 0.05) < 1e-6, '%.4f' % gv('前缘上升', 2))

setk('拖尾起点', 0.6)
chk('改「拖尾起点」→ 拖尾 From Min 跟随（拖尾 = 0.40）',
    abs(gv('拖尾衰减', 1) - 0.6) < 1e-6, '拖尾 %.2f' % (1 - gv('拖尾衰减', 1)))
setk('拖尾起点', 0.05)
chk('拖尾起点 → 0.05（拖尾 95%）', abs(1 - gv('拖尾衰减', 1) - 0.95) < 1e-6)
chk('★ 两个形状参数互不干扰：改拖尾不影响前缘',
    abs(gv('前缘上升', 2) - 0.05) < 1e-6, '前缘仍 %.4f' % gv('前缘上升', 2))

setk('条纹数量', 7.0)
chk('改「条纹数量」→ K 跟随', abs(gv('条纹数量K', 1) - 7.0) < 1e-6, '%.4f' % gv('条纹数量K', 1))
setk('高度条纹数', 5.0)
chk('改「高度条纹数」→ N 跟随', abs(gv('高度条纹N', 1) - 5.0) < 1e-6, '%.4f' % gv('高度条纹N', 1))
chk('★ K / N 相互独立（改 N 不动 K）', abs(gv('条纹数量K', 1) - 7.0) < 1e-6)

setk('上升速度', 0.03)
bpy.context.view_layer.update()
sc.frame_set(400)
bpy.context.view_layer.update()
chk('上升偏移 = +帧 × 速度（帧400/速0.03 → +12.0）',
    abs(gv('上升偏移', 1) - (400 * 0.03)) < 1e-3, '%.4f' % gv('上升偏移', 1))
sc.frame_set(420)
bpy.context.view_layer.update()
chk('帧 420 → +12.6（线性）', abs(gv('上升偏移', 1) - (420 * 0.03)) < 1e-3,
    '%.4f' % gv('上升偏移', 1))
setk('上升速度', -0.02)
bpy.context.view_layer.update()
chk('速度取负 → 偏移反号（420 帧 → −8.4）',
    abs(gv('上升偏移', 1) - (-420 * 0.02)) < 1e-3, '%.4f' % gv('上升偏移', 1))

setk('旋转速度', 0.05)
bpy.context.view_layer.update()
chk('旋转相位 = −帧 × 速度（帧420 → −21.0）',
    abs(gv('旋转相位', 1) - (-420 * 0.05)) < 1e-3, '%.4f' % gv('旋转相位', 1))

setk('发光强度', 12.5)
chk('改「发光强度」→ 真值跟随', abs(bsdf_strength() - 12.5) < 1e-3, '%.4f' % bsdf_strength())

print('\n--- K. 还原 ---')
for k, v in DEF.items():
    setk(k, v)
sc.frame_set(f0)
bpy.context.view_layer.update()
chk('还原：条纹数量', abs(gv('条纹数量K', 1) - DEF['条纹数量']) < 1e-6)
chk('还原：高度条纹数', abs(gv('高度条纹N', 1) - DEF['高度条纹数']) < 1e-6)
chk('还原：前缘宽度', abs(gv('前缘上升', 2) - DEF['前缘宽度']) < 1e-6)
chk('还原：拖尾起点', abs(gv('拖尾衰减', 1) - DEF['拖尾起点']) < 1e-6)
chk('还原：上升偏移', abs(gv('上升偏移', 1) - (f0 * DEF['上升速度'])) < 1e-3,
    '%.4f' % gv('上升偏移', 1))
chk('还原：旋转相位', abs(gv('旋转相位', 1) - (-f0 * DEF['旋转速度'])) < 1e-3)
chk('还原：发光强度', abs(bsdf_strength() - DEF['发光强度']) < 1e-3)
chk('还原：帧号', sc.frame_current == f0, '%d' % sc.frame_current)
chk('还原：配色色标仍为 2 个', len(nt.nodes['发光配色'].color_ramp.elements) == 2)

print('\n' + '=' * 62)
print('VERIFY  通过 %d / 失败 %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   FAIL ->', f)
print('结论:', '✅ 全部通过' if not FAIL else '❌ 有失败项')
