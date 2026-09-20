# verify_spiral_rise.py — 独立核验：螺旋上升材质（结构 + 行为）
# 规则：驱动真值一律走【求值后的依赖图】；改控件后主动 tag 再读，最后还原默认值。
import bpy, json, math

TARGET_OBJ = '滚动效果网格体'
MAT_NAME = '滚动效果网格体_螺旋上升'
CTRL_NAME = '螺旋上升控制'
PANEL_TEXT = 'spiral_rise_panel.py'
NODES = ['纹理坐标', '分离XYZ', '柱面_相位角', '柱面_角度偏置', '柱面_角度U',
         '柱面_高度V', '上升偏移', '环绕圈数K', '高度条纹N', '螺旋合成', '螺旋取模',
         '条纹', '原理化 BSDF', '材质输出']
DEF = {'环绕圈数': 3.0, '高度条纹': 2.0, '条纹宽度': 0.35, '上升速度': 0.02, '发光强度': 5.0}

ok, bad = [], []


def chk(name, cond, detail=''):
    (ok if cond else bad).append(name)
    print('  %s %-46s %s' % ('PASS' if cond else 'FAIL', name, detail))


def tag_all(ctrl, mat):
    ctrl.update_tag()
    mat.update_tag()
    mat.node_tree.update_tag()
    bpy.context.view_layer.update()


def eval_nt(mat):
    dg = bpy.context.evaluated_depsgraph_get()
    return mat.evaluated_get(dg).node_tree


ob = bpy.data.objects.get(TARGET_OBJ)
mat = bpy.data.materials.get(MAT_NAME)
ctrl = bpy.data.objects.get(CTRL_NAME)

print('=' * 74)
print('一、结构')
print('=' * 74)
chk('对象存在', ob is not None)
chk('材质存在', mat is not None)
chk('控制空物体存在', ctrl is not None)
if not (ob and mat and ctrl):
    print('致命缺失，终止'); raise SystemExit

chk('材质已指派到槽0', len(ob.material_slots) > 0 and ob.material_slots[0].material is mat,
    '槽0=%s' % (ob.material_slots[0].material.name if ob.material_slots and ob.material_slots[0].material else 'None'))
chk('锚点 rotation 全 0', all(abs(v) < 1e-6 for v in ctrl.rotation_euler), str(tuple(ctrl.rotation_euler)))
chk('锚点 scale 全 1', all(abs(v - 1.0) < 1e-6 for v in ctrl.scale), str(tuple(ctrl.scale)))
chk('锚点无父级', ctrl.parent is None)
chk('锚点在柱轴上且位于底面',
    abs(ctrl.location.x - 30.9216) < 1e-3 and abs(ctrl.location.y - 2.8832) < 1e-3
    and abs(ctrl.location.z - (-1.1444)) < 1e-3,
    str(tuple(round(v, 4) for v in ctrl.location)))
chk('对象自身未被改动(34面)', len(ob.data.polygons) == 34, '%d 面' % len(ob.data.polygons))

nt = mat.node_tree
names = {n.name for n in nt.nodes}
missing = [n for n in NODES if n not in names]
chk('14 个节点齐全', not missing, '缺=%s' % missing)
chk('无 ColorRamp 之外的多余 MapRange', not any(n.type == 'MAP_RANGE' for n in nt.nodes))
chk('无残留图像纹理', not any(n.type == 'TEX_IMAGE' for n in nt.nodes))
chk('无残留 Separate/Combine 拼接' , not any(n.type == 'COMBINE_XYZ' for n in nt.nodes))

tex = next((n for n in nt.nodes if n.type == 'TEX_COORD'), None)
chk('TexCoord.object 指向控制空物体', tex is not None and tex.object is ctrl,
    'tex.object=%s' % (tex.object.name if tex and tex.object else 'None'))

# 连线逐条断言
want_links = {
    ('纹理坐标', 'Object', '分离XYZ', 'Vector'),
    ('分离XYZ', 'Y', '柱面_相位角', 'Value'),
    ('分离XYZ', 'X', '柱面_相位角', 'Value'),
    ('柱面_相位角', 'Value', '柱面_角度偏置', 'Value'),
    ('柱面_角度偏置', 'Value', '柱面_角度U', 'Value'),
    ('分离XYZ', 'Z', '柱面_高度V', 'Value'),
    ('柱面_高度V', 'Value', '上升偏移', 'Value'),
    ('柱面_角度U', 'Value', '环绕圈数K', 'Value'),
    ('上升偏移', 'Value', '高度条纹N', 'Value'),
    ('环绕圈数K', 'Value', '螺旋合成', 'Value'),
    ('高度条纹N', 'Value', '螺旋合成', 'Value'),
    ('螺旋合成', 'Value', '螺旋取模', 'Value'),
    ('螺旋取模', 'Value', '条纹', 'Factor'),
}
have = {(l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name) for l in nt.links}
miss_link = want_links - have
chk('13 条关键连线逐条吻合', not miss_link, '缺=%s' % sorted(miss_link))
chk('条纹色 → BSDF Emission Color',
    any(l.from_node.name == '条纹' and l.to_node.name == '原理化 BSDF'
        and l.to_socket.name == 'Emission Color' for l in nt.links))
chk('BSDF → 材质输出',
    any(l.from_node.type == 'BSDF_PRINCIPLED' and l.to_node.type == 'OUTPUT_MATERIAL' for l in nt.links))
chk('Emission Strength 未被连线(驱动可读真值)',
    not next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Emission Strength'].is_linked)

# 遍历顺序检查（柱面_相位角 的分子/分母）
# ⚠️ 节点不是 ID 数据，bpy 每次访问会返回新的 wrapper ⇒ 必须比 name，不能用 `is`
atan = nt.nodes['柱面_相位角']
src_of = {}
for l in nt.links:
    if l.to_node.name == '柱面_相位角':
        src_of[list(atan.inputs).index(l.to_socket)] = l.from_socket.name
chk('ARCTAN2 输入 (in0 = Y 分子, in1 = X 分母)',
    src_of.get(0) == 'Y' and src_of.get(1) == 'X', str(src_of))
chk('角度偏置 = π', abs(nt.nodes['柱面_角度偏置'].inputs[1].default_value - math.pi) < 1e-6)
chk('u 归一化 = 1/2π', abs(nt.nodes['柱面_角度U'].inputs[1].default_value - 1.0 / (2 * math.pi)) < 1e-6)
chk('v 归一化 = 1/柱高', abs(nt.nodes['柱面_高度V'].inputs[1].default_value - 1.0 / 13.6764) < 1e-6)
chk('取模用 FLOORED_MODULO', nt.nodes['螺旋取模'].operation == 'FLOORED_MODULO',
    nt.nodes['螺旋取模'].operation)

ramp = nt.nodes['条纹'].color_ramp
chk('ColorRamp = 3 个色标', len(ramp.elements) == 3, '%d 个' % len(ramp.elements))
chk('ColorRamp 元素0 在 0 且为暗色',
    abs(ramp.elements[0].position) < 1e-6 and tuple(ramp.elements[0].color)[:3] == (0.0, 0.0, 0.0),
    str(tuple(ramp.elements[0].color)[:3]))
chk('ColorRamp 元素2 在 1 且为亮色',
    abs(ramp.elements[2].position - 1.0) < 1e-6 and tuple(ramp.elements[2].color)[:3] == (1.0, 1.0, 1.0))
# ★ 极性：只有 CONSTANT 才能得到「暗底 + 亮条」；LINEAR 会整段渐变到白 ⇒ 全亮
chk('ColorRamp 插值 = CONSTANT（暗底成立的前提）', ramp.interpolation == 'CONSTANT',
    ramp.interpolation)
chk('暗区在亮区之前（元素0 暗 / 元素1 亮）',
    tuple(ramp.elements[0].color)[:3] == (0.0, 0.0, 0.0)
    and tuple(ramp.elements[1].color)[:3] == (1.0, 1.0, 1.0))

# 驱动清单
drv = {d.data_path: d for d in (nt.animation_data.drivers if nt.animation_data else [])}
want_drv = {
    'nodes["上升偏移"].inputs[1].default_value',
    'nodes["环绕圈数K"].inputs[1].default_value',
    'nodes["高度条纹N"].inputs[1].default_value',
    'nodes["条纹"].color_ramp.elements[1].position',
}
chk('节点树上的 4 条驱动齐全', want_drv <= set(drv), '缺=%s' % sorted(want_drv - set(drv)))
chk('全部驱动 is_valid', all(d.driver.is_valid for d in drv.values()),
    str({p: d.driver.is_valid for p, d in drv.items()}))
chk('无残留指向已删节点的驱动',
    all(('nodes["%s"]' % p.split('nodes["')[1].split('"]')[0]) in
        ['nodes["%s"]' % n for n in names] for p in drv))
chk('上升驱动 = -fr * us（正速度=上升）',
    drv.get('nodes["上升偏移"].inputs[1].default_value') is not None
    and drv['nodes["上升偏移"].inputs[1].default_value'].driver.expression.replace(' ', '') == '-fr*us',
    drv.get('nodes["上升偏移"].inputs[1].default_value').driver.expression
    if 'nodes["上升偏移"].inputs[1].default_value' in drv else 'missing')
# 驱动变量必须是 SINGLE_PROP（有依赖边），不是命名空间函数
varts = []
for p, d in drv.items():
    for v in d.driver.variables:
        varts.append((p.split(']')[0][-8:], v.name, v.type,
                      v.targets[0].id_type if v.targets else None))
chk('所有驱动变量均为 SINGLE_PROP（有依赖边）',
    all(t == 'SINGLE_PROP' for _, _, t, _ in varts), str(varts[:6]))

txt = bpy.data.texts.get(PANEL_TEXT)
chk('Register 文本块存在', txt is not None)
chk('文本块 use_module == True', bool(txt and txt.use_module))
mod = None
try:
    mod = txt.as_module()
except Exception as e:
    print('   as_module 失败:', repr(e))
chk('文本块可作模块加载', mod is not None)
# 看门狗：as_module() 可能重载模块产生【新的函数对象】，
# 所以不能拿这里的 mod._watch 去问 —— 必须读 register() 存下的那个引用
_wfn = bpy.app.driver_namespace.get('_spiral_rise_watch')
chk('看门狗定时器在线',
    _wfn is not None and bool(bpy.app.timers.is_registered(_wfn)),
    'is_registered=%s' % (bpy.app.timers.is_registered(_wfn) if _wfn else None))
chk('参数面板类已注册', hasattr(bpy.types, 'VIEW3D_PT_spiral_rise'))
chk('面板类别名 = 螺旋上升',
    getattr(getattr(bpy.types, 'VIEW3D_PT_spiral_rise', None), 'bl_category', None) == '螺旋上升')

print()
print('=' * 74)
print('二、行为（改控件 → 主动 tag → 从求值依赖图读回真值）')
print('=' * 74)
sc = bpy.context.scene
sc.frame_set(sc.frame_current)
tag_all(ctrl, mat)


def gv(path):
    n = eval_nt(mat)
    return n.nodes[path[0]].color_ramp.elements[path[2]].position if len(path) == 3 \
        else n.nodes[path[0]].inputs[path[1]].default_value


def bsdf_strength():
    n = next(x for x in eval_nt(mat).nodes if x.type == 'BSDF_PRINCIPLED')
    return n.inputs['Emission Strength'].default_value


# 基线（默认值下的真实求值）
f0 = sc.frame_current
base_rise = gv(('上升偏移', 1))
chk('基线：上升偏移 = -帧 × 上升速度',
    abs(base_rise - (-f0 * DEF['上升速度'])) < 1e-4,
    '%.4f (期望 %.4f)' % (base_rise, -f0 * DEF['上升速度']))
chk('基线：环绕圈数K = 默认', abs(gv(('环绕圈数K', 1)) - DEF['环绕圈数']) < 1e-6,
    '%.3f' % gv(('环绕圈数K', 1)))
chk('基线：高度条纹N = 默认', abs(gv(('高度条纹N', 1)) - DEF['高度条纹']) < 1e-6,
    '%.3f' % gv(('高度条纹N', 1)))
chk('基线：条纹色标1 = 1 - 宽度',
    abs(gv(('条纹', None, 1)) - (1.0 - DEF['条纹宽度'])) < 1e-6,
    '%.4f' % gv(('条纹', None, 1)))
chk('基线：发光强度 = 默认', abs(bsdf_strength() - DEF['发光强度']) < 1e-4,
    '%.4f' % bsdf_strength())

# 逐项改
ctrl['环绕圈数'] = 3.0; tag_all(ctrl, mat)
chk('环绕圈数 2→3', abs(gv(('环绕圈数K', 1)) - 3.0) < 1e-6, '%.3f' % gv(('环绕圈数K', 1)))
ctrl['高度条纹'] = 4.0; tag_all(ctrl, mat)
chk('高度条纹 1→4', abs(gv(('高度条纹N', 1)) - 4.0) < 1e-6, '%.3f' % gv(('高度条纹N', 1)))
ctrl['条纹宽度'] = 0.3; tag_all(ctrl, mat)
chk('条纹宽度 0.5→0.3 ⇒ 色标1 = 0.7', abs(gv(('条纹', None, 1)) - 0.7) < 1e-5,
    '%.4f' % gv(('条纹', None, 1)))
ctrl['发光强度'] = 12.0; tag_all(ctrl, mat)
chk('发光强度 5→12', abs(bsdf_strength() - 12.0) < 1e-4, '%.4f' % bsdf_strength())
ctrl['上升速度'] = 0.05; tag_all(ctrl, mat)
sc.frame_set(425); tag_all(ctrl, mat)
chk('上升速度 0.05 @帧425 ⇒ -3.0', abs(gv(('上升偏移', 1)) - (-425 * 0.05)) < 1e-4,
    '%.4f (期望 %.4f)' % (gv(('上升偏移', 1)), -425 * 0.05))
ctrl['上升速度'] = -0.05; tag_all(ctrl, mat)
chk('上升速度 -0.05 @帧425 ⇒ +3.0（反向）', abs(gv(('上升偏移', 1)) - (425 * 0.05)) < 1e-4,
    '%.4f' % gv(('上升偏移', 1)))

# 还原默认
for k, v in DEF.items():
    ctrl[k] = v
sc.frame_set(f0); tag_all(ctrl, mat)
chk('还原：环绕圈数', abs(gv(('环绕圈数K', 1)) - DEF['环绕圈数']) < 1e-6)
chk('还原：高度条纹', abs(gv(('高度条纹N', 1)) - DEF['高度条纹']) < 1e-6)
chk('还原：条纹宽度', abs(gv(('条纹', None, 1)) - (1.0 - DEF['条纹宽度'])) < 1e-6)
chk('还原：发光强度', abs(bsdf_strength() - DEF['发光强度']) < 1e-4)
chk('还原：上升速度', abs(gv(('上升偏移', 1)) - (-f0 * DEF['上升速度'])) < 1e-4)
chk('还原：帧号', sc.frame_current == f0, '%d' % sc.frame_current)

print()
print('=' * 74)
print('通过 %d 项 / 失败 %d 项' % (len(ok), len(bad)))
if bad:
    print('失败清单:')
    for b in bad:
        print('  -', b)
print('VERIFY ' + json.dumps({'pass': len(ok), 'fail': len(bad), 'failed': bad}, ensure_ascii=False))
