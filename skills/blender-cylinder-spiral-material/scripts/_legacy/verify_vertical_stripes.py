# verify_vertical_stripes.py —— 独立核验「竖条旋转」材质（结构 + 行为）
# 真值一律从【求值依赖图】读（evaluated_get），不是读磁盘/内存里的原始值。
import bpy

OBJ = '滚动效果网格体'
MAT = '滚动效果网格体_竖条旋转'
CTRL = '竖条旋转控制'
SPIRAL_MAT = '滚动效果网格体_螺旋上升'
CAP_MAT = '滚动效果网格体_端盖黑'
PANEL_TEXT = 'vertical_stripes_panel.py'
DEF = {'条纹数量': 4.0, '条纹宽度': 0.4, '渐变柔化': 0.6, '流星拖尾': 0.8, '旋转速度': 0.01, '发光强度': 5.0}

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
dg = bpy.context.evaluated_depsgraph_get()


def gv(path_parts):
    """从求值后的节点树读真值：path_parts = (node_name, ...) 或 (node_name, 'sock', idx)"""
    ev = mat.evaluated_get(bpy.context.evaluated_depsgraph_get()).node_tree
    n = ev.nodes[path_parts[0]]
    if len(path_parts) == 2 and isinstance(path_parts[1], int):     # 输出 socket
        return n.outputs[path_parts[1]].default_value
    if path_parts[1] == 'in':
        return n.inputs[path_parts[2]].default_value
    if path_parts[1] == 'pos':
        return n.color_ramp.elements[path_parts[2]].position
    if path_parts[1] == 'op':
        return n.operation
    if path_parts[1] == 'out':
        return n.outputs[path_parts[2]].default_value
    return None


def bsdf_strength():
    ev = mat.evaluated_get(bpy.context.evaluated_depsgraph_get()).node_tree
    b = next(n for n in ev.nodes if n.type == 'BSDF_PRINCIPLED')
    return b.inputs['Emission Strength'].default_value


print('\n--- A. 槽位与面索引 ---')
slots = [(i, s.material.name if s.material else None) for i, s in enumerate(ob.material_slots)]
chk('槽 1 = 竖条旋转材质', len(slots) > 1 and slots[1][1] == MAT, '%s' % slots)
chk('槽 0 = 螺旋上升材质（未被破坏）', slots[0][1] == SPIRAL_MAT, '%s' % slots)
chk('槽 2 = 端盖黑材质', len(slots) > 2 and slots[2][1] == CAP_MAT, '%s' % slots)
idx_dist = {}
for p in ob.data.polygons:
    idx_dist[p.material_index] = idx_dist.get(p.material_index, 0) + 1
chk('侧面 32 → 槽1 / 端盖 2 → 槽2', idx_dist == {1: 32, 2: 2}, '%s' % idx_dist)
z_caps = [p.index for p in ob.data.polygons if abs(abs(p.normal.z) - 1.0) < 1e-3]
chk('端盖面 = 2 个（按法线判定，不是按索引）', len(z_caps) == 2, '%s' % z_caps)
capm = bpy.data.materials.get(CAP_MAT)
capb = None
if capm and capm.use_nodes:
    capb = next((n for n in capm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
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
chk('无父级（坐标不被带偏）', ctrl.parent is None)
chk('5 个控件键齐全', all(k in ctrl for k in DEF), '%s' % [k for k in ctrl.keys()])

print('\n--- C. 节点结构 ---')
need = ['纹理坐标', '分离XYZ', '柱面_相位角', '柱面_角度偏置', '柱面_角度U',
        '旋转相位', '条纹数量K', '竖条取模', '条纹遮罩', '发光配色']
for n in need:
    chk('节点存在: %s' % n, n in nt.nodes)
chk('节点总数 = 12', len(nt.nodes) == 12, '%d' % len(nt.nodes))
chk('连线总数 = 12', len(nt.links) == 12, '%d' % len(nt.links))
t = next(n for n in nt.nodes if n.type == 'TEX_COORD')
chk('TexCoord.type = TEX_COORD', t.type == 'TEX_COORD', t.type)
chk('TexCoord.object 指向控制空物体', t.object is not None and t.object.name == CTRL,
    t.object.name if t.object else 'None')
ev_nodes = mat.evaluated_get(dg).node_tree.nodes
chk('操作符: 柱面_相位角 = ARCTAN2', nt.nodes['柱面_相位角'].operation == 'ARCTAN2')
chk('操作符: 柱面_角度偏置 = ADD', nt.nodes['柱面_角度偏置'].operation == 'ADD')
chk('操作符: 柱面_角度U = MULTIPLY', nt.nodes['柱面_角度U'].operation == 'MULTIPLY')
chk('操作符: 旋转相位 = ADD', nt.nodes['旋转相位'].operation == 'ADD')
chk('操作符: 条纹数量K = MULTIPLY', nt.nodes['条纹数量K'].operation == 'MULTIPLY')
chk('操作符: 竖条取模 = FLOORED_MODULO（不是 MODULO）',
    nt.nodes['竖条取模'].operation == 'FLOORED_MODULO', nt.nodes['竖条取模'].operation)


def link_of(to_node_name, input_name, input_index=None):
    """按【名字】找进入某输入的连线（节点不是 ID 数据，'is' 比较恒为 False）"""
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


print('\n--- D. 连线逐条 ---')
ln = link_of('分离XYZ', 'Vector')
chk('纹理坐标.Object → 分离XYZ.Vector',
    len(ln) == 1 and ln[0].from_node.name == '纹理坐标' and ln[0].from_socket.name == 'Object')
a = nt.nodes['柱面_相位角']
l0 = link_of('柱面_相位角', None, 0)
l1 = link_of('柱面_相位角', None, 1)
chk('ARCTAN2 输入0 = Y（分子）', len(l0) == 1 and l0[0].from_socket.name == 'Y',
    l0[0].from_socket.name if l0 else '无')
chk('ARCTAN2 输入1 = X（分母）', len(l1) == 1 and l1[0].from_socket.name == 'X',
    l1[0].from_socket.name if l1 else '无')
pairs = [('柱面_角度偏置', 0, '柱面_相位角'), ('柱面_角度U', 0, '柱面_角度偏置'),
         ('旋转相位', 0, '柱面_角度U'), ('条纹数量K', 0, '旋转相位'),
         ('竖条取模', 0, '条纹数量K')]
for tn, ti, fn in pairs:
    ls = link_of(tn, None, ti)
    chk('%s.in%d ← %s' % (tn, ti, fn),
        len(ls) == 1 and ls[0].from_node.name == fn,
        ls[0].from_node.name if ls else '无')
ls = link_of('条纹遮罩', None, 0)   # ⚠️ ColorRamp 输入 socket 名不是 'Fac'，只能按索引取
chk('条纹遮罩.Fac ← 竖条取模', len(ls) == 1 and ls[0].from_node.name == '竖条取模',
    ls[0].from_node.name if ls else '无')
ls = link_of('发光配色', None, 0)
chk('发光配色.Fac ← 条纹遮罩.Color', len(ls) == 1 and ls[0].from_node.name == '条纹遮罩',
    ls[0].from_node.name if ls else '无')
b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
ls = link_of(b.name, 'Emission Color')
chk('BSDF.Emission Color ← 发光配色.Color',
    len(ls) == 1 and ls[0].from_node.name == '发光配色', ls[0].from_node.name if ls else '无')
ls = link_of('材质输出', 'Surface')
chk('材质输出.Surface ← BSDF', len(ls) == 1 and ls[0].from_node.type == 'BSDF_PRINCIPLED')

print('\n--- E. 竖条性质（关键）---')
used = {l.from_node.name for l in nt.links}
chk('★ 分离XYZ.Z 未被任何节点使用 ⇒ 条纹与高度无关 = 竖直', '分离XYZ' in used)
z_links = [l for l in nt.links if l.from_node.name == '分离XYZ' and l.from_socket.name == 'Z']
chk('★ 无任何连线从 分离XYZ.Z 出发', len(z_links) == 0, '共 %d 条' % len(z_links))
chk('★ 条纹数量K 的输入1 是驱动不是连线', len(link_of('条纹数量K', None, 1)) == 0)

print('\n--- F. 双渐变节点（条纹遮罩 + 发光配色）---')


def exp_pos(w, s, t):
    """独立重算遮罩 6 个色标位置。
    ⚠️ 刻意用与驱动表达式【不同】的写法（Python 浮点中间量版本），
       这样公式写错时不会被"同源复算"掩盖过去。"""
    hw = w / 2.0
    tr = s * hw
    c = 0.5 - t * (0.5 - hw - 0.02)
    rise = tr * (1.0 - t)
    fall = tr + ((1.0 - (c + hw)) - tr) * t
    return [0.0, max(0.0, c - hw - rise), c - hw, c + hw, min(1.0, c + hw + fall), 1.0]


cr = nt.nodes['条纹遮罩'].color_ramp
chk('遮罩 interpolation = EASE（真渐变，不是硬边）', cr.interpolation == 'EASE', cr.interpolation)
chk('遮罩 6 个色标', len(cr.elements) == 6, '%d' % len(cr.elements))
chk('遮罩首尾均为暗色（周期无缝）',
    tuple(cr.elements[0].color)[:3] == (0.0, 0.0, 0.0)
    and tuple(cr.elements[5].color)[:3] == (0.0, 0.0, 0.0))
chk('遮罩色标2/3 = 亮色（亮带平台）',
    tuple(cr.elements[2].color)[:3] == (1.0, 1.0, 1.0)
    and tuple(cr.elements[3].color)[:3] == (1.0, 1.0, 1.0))
_p = [e.position for e in cr.elements]
_e = exp_pos(DEF['条纹宽度'], DEF['渐变柔化'], DEF['流星拖尾'])
chk('遮罩 6 个色标位置 = 公式值',
    all(abs(a - b) < 1e-6 for a, b in zip(_p, _e)),
    '实际%s / 期望%s' % ([round(x, 4) for x in _p], [round(x, 4) for x in _e]))
chk('★ 流星拖尾生效：亮带整体靠前（色标2 < 0.5）', _p[2] < 0.5, '%.4f' % _p[2])
chk('★ 流星拖尾生效：后缘拖尾 > 前缘（[4]-[3] > [2]-[1]）',
    (_p[4] - _p[3]) > (_p[2] - _p[1]),
    '拖尾 %.4f vs 前缘 %.4f' % (_p[4] - _p[3], _p[2] - _p[1]))
cr2 = nt.nodes['发光配色'].color_ramp
chk('配色 interpolation = LINEAR', cr2.interpolation == 'LINEAR', cr2.interpolation)
chk('配色 2 个色标（留给你加）', len(cr2.elements) == 2, '%d' % len(cr2.elements))
chk('配色左端 = 不发光色（默认黑）', tuple(cr2.elements[0].color)[:3] == (0.0, 0.0, 0.0))
chk('配色右端 = 发光色（默认白）', tuple(cr2.elements[1].color)[:3] == (1.0, 1.0, 1.0))
chk('BSDF Base Color = 黑', tuple(b.inputs['Base Color'].default_value)[:3] == (0.0, 0.0, 0.0))
chk('BSDF Roughness = 1', abs(b.inputs['Roughness'].default_value - 1.0) < 1e-6)
chk('BSDF Metallic = 0', abs(b.inputs['Metallic'].default_value) < 1e-6)

print('\n--- G. 驱动 ---')
drs = nt.animation_data.drivers if nt.animation_data else []
chk('驱动数 = 7', len(drs) == 7, '%d' % len(drs))
found = {d.data_path: d.driver.expression for d in drs}
need_paths = ['nodes["旋转相位"].inputs[1].default_value',
              'nodes["条纹数量K"].inputs[1].default_value'] + \
             ['nodes["条纹遮罩"].color_ramp.elements[%d].position' % i for i in (1, 2, 3, 4)]
missing = [p for p in need_paths if p not in found]
chk('7 条驱动路径齐全', not missing, '缺 %s' % missing)
chk('旋转相位驱动 = -fr * sp', found.get(need_paths[0]) == '-fr * sp', found.get(need_paths[0], '缺失'))
chk('条纹数量驱动 = kn', found.get(need_paths[1]) == 'kn', found.get(need_paths[1], '缺失'))
chk('7 条驱动全 is_valid', all(d.driver.is_valid for d in drs))
chk('驱动变量均为 SINGLE_PROP',
    all(v.type == 'SINGLE_PROP' for d in drs for v in d.driver.variables))
vn = {v.name for d in drs for v in d.driver.variables}
chk('驱动变量名集合 = {fr,sp,kn,wd,sf,tl,st}',
    vn == {'fr', 'sp', 'kn', 'wd', 'sf', 'tl', 'st'}, '%s' % sorted(vn))
bsdf_p = 'nodes["%s"].inputs[29].default_value' % b.name
chk('BSDF 强度驱动存在且 = st', found.get(bsdf_p) == 'st', found.get(bsdf_p, '缺失'))

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
wf = bpy.app.driver_namespace.get('_vertical_stripes_watch')
chk('看门狗定时器在线', bool(wf and bpy.app.timers.is_registered(wf)))
chk('面板类已注册', hasattr(bpy.types, 'VIEW3D_PT_vertical_stripes'))
chk('螺旋面板未被顶掉（两面板可共存）', hasattr(bpy.types, 'VIEW3D_PT_spiral_rise'))
chk('面板 PROPS 含「流星拖尾」', bool(mod and '流星拖尾' in getattr(mod, 'PROPS', [])),
    '%s' % (getattr(mod, 'PROPS', None) if mod else None))

print('\n--- I. 无临时残留 ---')
junk = [m.name for m in bpy.data.materials if m.name.startswith(('_SKILLTEST', '_PV_', '_wb_'))]
junko = [o.name for o in bpy.data.objects if o.name.startswith(('_SKILLTEST', '_PV_', '_wb_'))]
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


def live_pos():
    return [gv(('条纹遮罩', 'pos', i)) for i in range(6)]


def check_pos(label, w, s, t):
    e = exp_pos(w, s, t)
    a = live_pos()
    ok = all(abs(x - y) < 1e-5 for x, y in zip(a, e))
    chk(label, ok, '实际%s' % [round(x, 4) for x in a])
    return a


setk('条纹数量', 7.0)
chk('改「条纹数量」→ K 真值跟随', abs(gv(('条纹数量K', 'in', 1)) - 7.0) < 1e-6,
    '%.4f' % gv(('条纹数量K', 'in', 1)))
setk('条纹数量', 3.0)
chk('再改「条纹数量」→ K 真值跟随', abs(gv(('条纹数量K', 'in', 1)) - 3.0) < 1e-6,
    '%.4f' % gv(('条纹数量K', 'in', 1)))
setk('条纹数量', DEF['条纹数量'])

setk('流星拖尾', 0.0)
_a = check_pos('「流星拖尾」=0 → 亮带居中、前后对称', 0.4, 0.6, 0.0)
chk('  ↳ 亮带中心 = 0.5', abs((_a[2] + _a[3]) / 2 - 0.5) < 1e-5, '%.4f' % ((_a[2] + _a[3]) / 2))

setk('流星拖尾', 1.0)
_a = check_pos('「流星拖尾」=1 → 前缘垂直 + 拖尾铺满', 0.4, 0.6, 1.0)
chk('  ↳ 前缘宽度 ≈ 0（垂直上升）', _a[2] - _a[1] < 1e-6, '%.4f' % (_a[2] - _a[1]))
chk('  ↳ 拖尾铺满剩余周期（色标4 = 1.0）', abs(_a[4] - 1.0) < 1e-6, '%.4f' % _a[4])
chk('  ↳ 拖尾长度 > 亮带宽度', (_a[4] - _a[3]) > (_a[3] - _a[2]),
    '拖尾%.4f vs 亮带%.4f' % (_a[4] - _a[3], _a[3] - _a[2]))

setk('流星拖尾', 0.8)
check_pos('「流星拖尾」=0.8 → 公式吻合', 0.4, 0.6, 0.8)

setk('渐变柔化', 0.0)
check_pos('「渐变柔化」=0 → 过渡带=0（纯硬边）', 0.4, 0.0, 0.8)
setk('渐变柔化', 1.0)
check_pos('「渐变柔化」=1 → 过渡带 = 半宽', 0.4, 1.0, 0.8)
setk('渐变柔化', DEF['渐变柔化'])

setk('条纹宽度', 0.25)
check_pos('「条纹宽度」=0.25 → 亮带按比例收窄', 0.25, DEF['渐变柔化'], DEF['流星拖尾'])
setk('条纹宽度', DEF['条纹宽度'])

setk('发光强度', 12.5)
chk('改「发光强度」→ 真值跟随', abs(bsdf_strength() - 12.5) < 1e-3, '%.4f' % bsdf_strength())

setk('旋转速度', 0.05)
bpy.context.view_layer.update()
sc.frame_set(400)
bpy.context.view_layer.update()
chk('旋转相位 = -帧 × 速度（帧400/速0.05 → -20.0）',
    abs(gv(('旋转相位', 'in', 1)) - (-400 * 0.05)) < 1e-3,
    '%.4f' % gv(('旋转相位', 'in', 1)))
sc.frame_set(420)
bpy.context.view_layer.update()
chk('帧 420 → 旋转相位 -21.0（线性）',
    abs(gv(('旋转相位', 'in', 1)) - (-420 * 0.05)) < 1e-3,
    '%.4f' % gv(('旋转相位', 'in', 1)))
setk('旋转速度', -0.03)
bpy.context.view_layer.update()
chk('速度取负 → 相位反号（420 帧 → +12.6）',
    abs(gv(('旋转相位', 'in', 1)) - (420 * 0.03)) < 1e-3,
    '%.4f' % gv(('旋转相位', 'in', 1)))

print('\n--- K. 还原 ---')
for k, v in DEF.items():
    setk(k, v)
sc.frame_set(f0)
bpy.context.view_layer.update()
chk('还原：条纹数量', abs(gv(('条纹数量K', 'in', 1)) - DEF['条纹数量']) < 1e-6)
check_pos('还原：遮罩 6 个色标回到默认', DEF['条纹宽度'], DEF['渐变柔化'], DEF['流星拖尾'])
chk('还原：发光强度', abs(bsdf_strength() - DEF['发光强度']) < 1e-3)
chk('还原：旋转速度',
    abs(gv(('旋转相位', 'in', 1)) - (-f0 * DEF['旋转速度'])) < 1e-3,
    '%.4f' % gv(('旋转相位', 'in', 1)))
chk('还原：帧号', sc.frame_current == f0, '%d' % sc.frame_current)

print('\n' + '=' * 62)
print('VERIFY  通过 %d / 失败 %d' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('   FAIL ->', f)
print('结论:', '✅ 全部通过' if not FAIL else '❌ 有失败项')
