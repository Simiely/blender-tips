# retarget_material.py —— 材质被贴到别的文件/对象后「不动」时，把断掉的引用重新接上
#
# 原理：这个材质有【两个外部依赖】，跨文件复制时会断：
#   ① 纹理坐标.Object → 空物体「竖条旋转控制」（柱面坐标的基准）
#   ② 7 条驱动 → 变量指向「该空物体的自定义属性」+「某个场景的 frame_current」
# 断了之后的症状：条纹形状还对（坐标退回世界坐标仍能看出斜纹），但**完全不动**（驱动 is_valid=False）
#
# 用法：在【目标文件】里跑本脚本（send.py 或 Scripting 区 Run Script）。
#      它会：找/建锚点空物体 → 指回 tex.object → 重建 7 条驱动变量（指向本文件的锚点与当前场景）
import bpy
import math

MAT_KEY = '滚筒斜纹'
CTRL_NAME = '竖条旋转控制'
CAP_NAME = '滚动效果网格体_端盖黑'   # ⚠️ 必须与建脚本一致，否则会出现两个端盖材质
AXIS_X, AXIS_Y = 30.9216, 2.8832     # ⚠️ 换工程要改成目标柱的轴心
Z_BOTTOM = -1.1444
HEIGHT = 13.6764
CYL_RADIUS = 3.7789
H_OVER_P = HEIGHT / (2.0 * math.pi * CYL_RADIUS)
DEFAULTS = {'条纹数量': 3.0, '高度条纹数': 2.0, '前缘宽度': 0.12, '拖尾起点': 0.22,
            '上升速度': 0.01, '旋转速度': 0.0, '发光强度': 5.0}
# 节点名 → (驱动变量, 表达式)
DRIVES = [
    ('旋转相位',   'sp',  '-fr * sp'),
    ('上升偏移',   'us',  'fr * us'),
    ('条纹数量K',  'kn',  'floor(kn + 0.5)'),
    ('高度条纹N',  'hn',  'floor(hn + 0.5)'),
]
RAMP_DRIVES = [('前缘上升', 2, 'fe', 'fe'), ('拖尾衰减', 1, 'ts', 'ts')]

# 场景/对象变量统一在这里取
scene = bpy.context.scene


def ensure_ctrl():
    c = bpy.data.objects.get(CTRL_NAME)
    if c is None:
        c = bpy.data.objects.new(CTRL_NAME, None)
        scene.collection.objects.link(c)
        print('   新建锚点空物体:', CTRL_NAME)
    c.parent = None
    c.location = (AXIS_X, AXIS_Y, Z_BOTTOM)
    c.rotation_euler = (0, 0, 0)
    c.scale = (1, 1, 1)
    for k, v in DEFAULTS.items():
        if k not in c:
            c[k] = v
    return c


def bind(fc, expr, varmap):
    d = fc.driver
    d.type = 'SCRIPTED'
    for vn, (idtype, target, path) in varmap.items():
        v = d.variables.new()
        v.name = vn
        v.type = 'SINGLE_PROP'
        t = v.targets[0]
        t.id_type = idtype
        t.id = target
        t.data_path = path
    d.expression = expr
    fc.update()
    return fc


REQUIRED_NODES = ('旋转相位', '上升偏移', '条纹数量K', '高度条纹N',
                  '前缘上升', '拖尾衰减', '纹理坐标')


def fix(mat, ctrl):
    nt = mat.node_tree
    # ★★ 先做完整性检查，再动破坏性操作（否则中途抛异常会留下「驱动被清空」的残缺材质）
    missing = [n for n in REQUIRED_NODES if n not in nt.nodes]
    if missing:
        print('   ✗ 缺节点 %s —— 节点链不完整，请改用建脚本重建' % missing)
        return False
    if not any(n.type == 'BSDF_PRINCIPLED' for n in nt.nodes):
        print('   ✗ 缺原理化 BSDF —— 请改用建脚本重建')
        return False
    nt.animation_data_clear()                     # 幂等：先清掉（可能失效的）旧驱动
    # ① 锚点
    t = nt.nodes['纹理坐标']
    t.object = ctrl
    print('   ✔ tex.object →', ctrl.name)
    # ② 驱动
    nt.animation_data_create()
    # ★ 驱动变量名 → ctrl 上的中文属性键
    VAR2KEY = {'sp': '旋转速度', 'us': '上升速度', 'kn': '条纹数量',
               'hn': '高度条纹数', 'fe': '前缘宽度', 'ts': '拖尾起点',
               'st': '发光强度'}
    V = {v: ('OBJECT', ctrl, '["%s"]' % k) for v, k in VAR2KEY.items()}
    V['fr'] = ('SCENE', scene, 'frame_current')
    made = 0
    for node, var, expr in DRIVES:
        if node not in nt.nodes:
            print('   ! 缺节点', node); continue
        p = 'nodes["%s"].inputs[1].default_value' % node
        need = {'fr': V['fr'], var: V[var]}
        bind(nt.driver_add(p, -1), expr, need); made += 1
    for node, idx, var, expr in RAMP_DRIVES:
        if node not in nt.nodes:
            continue
        p = 'nodes["%s"].inputs[%d].default_value' % (node, idx)
        bind(nt.driver_add(p, -1), expr, {var: V[var]}); made += 1
    b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is not None:
        bind(b.inputs['Emission Strength'].driver_add('default_value'),
             'st', {'st': V['st']}); made += 1
    print('   ✔ 重建驱动 %d 条' % made)
    bad = [d.data_path for d in nt.animation_data.drivers if not d.driver.is_valid]
    print('   %s 全部有效' % ('✔' if not bad else '✗ 仍无效: %s' % bad))
    return not bad


def main():
    mats = [m for m in bpy.data.materials if MAT_KEY in m.name and m.use_nodes]
    print('=== 重建脚本（场景: %s）===' % scene.name)
    if not mats:
        print('   没找到材质（%r）—— 先把材质贴过来再跑' % MAT_KEY); return
    ctrl = ensure_ctrl()
    for m in mats:
        print('--- %s' % m.name)
        fix(m, ctrl)
    # 顺带：端盖材质 + 面索引
    ob_names = {s.material.name for m in mats for s in []}  # 占位
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or not hasattr(ob, 'material_slots'):
            continue
        names = [s.material.name for s in ob.material_slots if s.material]
        if not any(MAT_KEY in n for n in names):
            continue
        me = ob.data
        si = next(i for i, n in enumerate(names) if MAT_KEY in n)
        cap = bpy.data.materials.get(CAP_NAME)
        if cap is None:
            cap = bpy.data.materials.new(CAP_NAME)
            cap.use_nodes = True
            nt2 = cap.node_tree
            for n in list(nt2.nodes):
                if n.type != 'OUTPUT_MATERIAL':
                    nt2.nodes.remove(n)
            out = next((n for n in nt2.nodes if n.type == 'OUTPUT_MATERIAL'), None) \
                or nt2.nodes.new('ShaderNodeOutputMaterial')
            bb = nt2.nodes.new('ShaderNodeBsdfPrincipled')
            bb.inputs['Base Color'].default_value = (0, 0, 0, 1)
            bb.inputs['Roughness'].default_value = 1.0
            bb.inputs['Emission Strength'].default_value = 0.0
            nt2.links.new(bb.outputs['BSDF'], out.inputs['Surface'])
            print('   新建端盖材质:', CAP_NAME)
        while len(me.materials) <= max(si, 1):
            me.materials.append(None)
        ci = 1 if si != 1 else len(me.materials) - 1
        me.materials[ci] = cap
        n = 0
        for p in me.polygons:
            tgt = ci if abs(abs(p.normal.z) - 1.0) < 1e-3 else si
            if p.material_index != tgt:
                p.material_index = tgt; n += 1
        print('   对象 %s：槽 条纹=%d 端盖=%d，改 %d 个面' % (ob.name, si, ci, n))
    print()
    print('完成。若仍有 ✗，请改用建脚本 build_streak_count.py 整体重建。')
    print('RETARGET_OK')


main()
