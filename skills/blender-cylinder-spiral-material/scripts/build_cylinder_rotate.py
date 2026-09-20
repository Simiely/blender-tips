# build_cylinder_rotate.py —— 给「滚动效果网格体」建「竖条旋转」发光材质
#
# 圆柱面【竖直】条纹，条纹绕 Z 轴旋转（纹理相位绕轴转，不是螺旋）：
#   f = (u + spin) × K   →  FLOORED_MODULO 1  →  ColorRamp 条纹  →  Emission
#   u    = (atan2(y, x) + π) / 2π     绕柱角度归一化 0~1（u 增大 = 俯视逆时针）
#   spin = -frame × 旋转速度          每帧转多少圈；正速度 = u 增大 = 俯视逆时针
#   无高度项 v ⇒ 条纹是竖直母线，不倾斜
#
# 与「螺旋上升」的关系：同一套柱面坐标，那份多了 v×N 项（斜条纹）+ 上升偏移；
#   这份去掉高度项、把相位换成 spin。两份材质各自占一个槽，可随时切换。
#
# 依据：仓库 docs/材质与驱动规范.md（圆柱投影 / FLOORED_MODULO / 三大坑）
#      + skills/blender-procedural-emission-material（SINGLE_PROP 依赖边 + 看门狗）
#
# 幂等：可反复重跑。已存在的控件值不被覆盖（只补缺失的）。
# 桥接 exec 时 __name__ 为 builtins，不用 __main__ 守卫。
import bpy
import io
import math

# ============================== 配置区 ==============================
TARGET_OBJ = '滚动效果网格体'
MAT_NAME = '滚动效果网格体_竖条旋转'
CTRL_NAME = '竖条旋转控制'
SLOT_INDEX = 1            # ★ 新增到槽 1；槽 0 保留「螺旋上升」材质不动（可随时切回）
# ★ 端盖专用槽：端盖上 atan2(y,x) 是【极角】⇒ 竖条纹会摊成 K 个扇形（实测俯视图像风车）。
#   灯柱端盖通常看不见，给纯黑不发光最干净。想让端盖也亮，改 CAP_MAT 的颜色即可。
CAP_MAT = '滚动效果网格体_端盖黑'
CAP_SLOT = 2

# 圆柱实测几何 —— ⚠️ 下面这几个数是【本工程实测值】。
#    换工程必须重新只读侦察（逐顶点世界坐标求包围盒 ⇒ 半径是否恒定 / 轴向 / zmin / zmax）后再改，
#    否则 u（绕柱角度）的基准就是错的。（本份不用 v，但 ANCHOR 位置仍须是柱轴心）
# 锚点空物体放柱【底面中心】，rotation 0 / scale 1 ⇒ Object 坐标 = 柱面坐标
AXIS_X, AXIS_Y = 30.9216, 2.8832      # 柱轴心（世界 XY）
Z_BOTTOM = -1.1444                    # 柱底面世界 Z
HEIGHT = 13.6764                      # 柱高（本份仅用于文档/校验，不进节点）

# 条纹配色（想换颜色改这两行）
COLOR_DARK = (0.0, 0.0, 0.0, 1.0)
COLOR_BRIGHT = (1.0, 1.0, 1.0, 1.0)

# 面板源码（写进 Register 文本块；文本块必须自包含，故从文件读入）
PANEL_SRC = r'D:\workbuddy\2026-09-20-09-39-42\_liantiao\vertical_stripes_panel.py'
PANEL_TEXT = 'vertical_stripes_panel.py'

# 控件：(键名, 默认, min, max, soft_min, soft_max, step, precision, 说明)
# 默认值由参数扫描定（见 preview/D_竖条参数对比.png）
PROPS = [
    ('条纹数量', 4.0, 1.0, 24.0, 1.0, 12.0, 1, 0,
     '竖条绕柱一周的条数 —— 必须整数，否则 u=0/2π 接缝处会错位'),
    ('条纹宽度', 0.4, 0.05, 1.0, 0.1, 0.9, 1, 2,
     '亮条占一个周期的比例（1.0 = 全亮无暗区）'),
    ('渐变柔化', 0.6, 0.0, 1.0, 0.0, 1.0, 1, 2,
     '亮暗之间的过渡带宽度：0 = 硬边直角，1 = 过渡带与亮条等宽（最柔）'),
    ('流星拖尾', 0.8, 0.0, 1.0, 0.0, 1.0, 1, 2,
     '渐变的【不对称度】：0 = 前后对称（普通条纹）；1 = 前缘极陡 + 后缘长拖尾（流星）'),
    ('旋转速度', 0.01, -0.2, 0.2, 0.0, 0.04, 1, 4,
     '每帧条纹绕 Z 轴转过的圈数（0.01 = 100 帧一圈）；正值 = 俯视逆时针、正视图上条纹向右'),
    ('发光强度', 5.0, 0.0, 100.0, 1.0, 30.0, 1, 1,
     '发光强度倍数（AgX 会压暗发光，看不清就往大调）'),
]

# 节点名（中文，驱动 data_path 与面板都引用它们）
N_TEX, N_SEP = '纹理坐标', '分离XYZ'
N_ATAN, N_PI, N_U = '柱面_相位角', '柱面_角度偏置', '柱面_角度U'
N_SPIN, N_K, N_MODEC = '旋转相位', '条纹数量K', '竖条取模'
N_RAMP, N_RAMP2 = '条纹遮罩', '发光配色'
# ====================================================================


def ensure_ctrl():
    ob = bpy.data.objects.get(TARGET_OBJ)
    col = ob.users_collection[0] if (ob and ob.users_collection) else None
    c = bpy.data.objects.get(CTRL_NAME)
    if c is None:
        c = bpy.data.objects.new(CTRL_NAME, None)
        (col or bpy.context.scene.collection).objects.link(c)
        print('新建控制空物体:', CTRL_NAME)
    # 锚点必须是「柱轴心 + rotation 0 + scale 1」，Object 坐标才等于柱面坐标
    c.parent = None
    c.location = (AXIS_X, AXIS_Y, Z_BOTTOM)
    c.rotation_euler = (0.0, 0.0, 0.0)
    c.scale = (1.0, 1.0, 1.0)
    for key, dv, mn, mx, smn, smx, step, prec, desc in PROPS:
        if key not in c:                 # 只在缺失时写默认 ⇒ 重跑不覆盖用户调过的值
            c[key] = dv
        try:
            c.id_properties_ui(key).update(description=desc, min=mn, max=mx,
                                           soft_min=smn, soft_max=smx,
                                           step=step, precision=prec)
        except Exception as e:
            print('UI_WARN', key, repr(e))
    return c


def new_math(nt, op, loc, name, v1=None):
    n = nt.nodes.new('ShaderNodeMath')
    n.operation = op
    n.name = n.label = name
    n.location = loc
    if v1 is not None:
        n.inputs[1].default_value = v1
    return n


def apply_ramp_snapshot(ramp, snap):
    """把用户上次手工调好的色标（数量/位置/颜色）还原回去 —— 重跑建脚本不冲掉调色。

    ⚠️ 首尾两个色标位置【强制归位】到 0 / 1 —— 它们是结构性的（映射区间的两端），
       一旦偏移，整条曲线会「提前饱和」。实测踩过：演示脚本做多段渐变后还原时
       删错了元素（删了位置最大的那个），末端停在 0.45，渲出来是「提前变白 + 宽色块」，
       当场被误判成材质坏了。教训：还原不能只靠 diff 快照，结构性端点必须钉死。
    """
    els = ramp.color_ramp.elements
    while len(els) > 2 and len(els) > len(snap):
        els.remove(els[-1])
    while len(els) < len(snap):
        els.new(0.5)
    for e, (pos, col) in zip(els, snap):
        e.position = pos
        e.color = col
    els[0].position = 0.0
    els[-1].position = 1.0


def rebuild(mat, ctrl):
    nt = mat.node_tree
    nt.animation_data_clear()                       # 幂等：先清旧驱动
    # ★ 重建前先快照「发光配色」的手工调色，重建后原样还原
    snap2 = None
    _old2 = nt.nodes.get(N_RAMP2)
    if _old2 is not None and _old2.type == 'VALTORGB':
        snap2 = [(e.position, tuple(e.color)) for e in _old2.color_ramp.elements]
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if out is None:
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        out.location = (1000, 0)

    # --- 坐标源：Object 输出指向锚点空物体 ---
    tex = nt.nodes.new('ShaderNodeTexCoord'); tex.name = tex.label = N_TEX
    tex.location = (-1400, 0)
    tex.object = ctrl
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.name = sep.label = N_SEP
    sep.location = (-1200, 0)
    nt.links.new(tex.outputs['Object'], sep.inputs['Vector'])

    # --- u：atan2(y, x) → +π → ÷2π ---
    atan = new_math(nt, 'ARCTAN2', (-1000, 200), N_ATAN)
    nt.links.new(sep.outputs['Y'], atan.inputs[0])   # 分子 = y
    nt.links.new(sep.outputs['X'], atan.inputs[1])   # 分母 = x
    n_pi = new_math(nt, 'ADD', (-850, 200), N_PI, math.pi)
    nt.links.new(atan.outputs[0], n_pi.inputs[0])
    n_u = new_math(nt, 'MULTIPLY', (-700, 200), N_U, 1.0 / (2.0 * math.pi))
    nt.links.new(n_pi.outputs[0], n_u.inputs[0])

    # --- 旋转相位：u + spin（input[1] 被驱动）---
    # ★ spin 加在【乘 K 之前】⇒ 转速与条纹数量无关（改条数不会改转速）
    n_spin = new_math(nt, 'ADD', (-520, 200), N_SPIN, 0.0)
    nt.links.new(n_u.outputs[0], n_spin.inputs[0])

    # --- f = (u + spin) × K —— 只依赖 u ⇒ 条纹是竖直母线 ---
    n_k = new_math(nt, 'MULTIPLY', (-350, 200), N_K, 1.0)
    nt.links.new(n_spin.outputs[0], n_k.inputs[0])

    # --- 取模：必须 FLOORED_MODULO（普通 MODULO 负值被钳 ⇒ spin 为负时条纹断裂）---
    n_mod = new_math(nt, 'FLOORED_MODULO', (-180, 200), N_MODEC, 1.0)
    nt.links.new(n_k.outputs[0], n_mod.inputs[0])

    # --- ① 条纹遮罩：6 色标 + EASE ⇒ 暗 →（渐亮）→ 亮平台 →（渐暗）→ 暗 ---
    #     周期首尾同色 ⇒ 无缝；亮带居中 c=0.5，半宽 hw=w/2，过渡带 t=柔化×hw。
    #     4 个色标位置由「条纹宽度」「渐变柔化」驱动（见 add_drives）：
    #       [1]=max(0, c-hw-t)   [2]=c-hw   [3]=c+hw   [4]=min(1, c+hw+t)
    #     本节点只输出【灰度遮罩】（黑→白→黑），不管颜色 ⇒ 颜色交给下一个节点。
    #     ⚠️ 插值是整个 ColorRamp 的属性（color_ramp.interpolation）；
    #        Blender 5.2 的 ColorRampElement 【没有】interpolation 属性。
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.name = ramp.label = N_RAMP
    ramp.location = (-20, 200)
    ramp.color_ramp.interpolation = 'EASE'
    el = ramp.color_ramp.elements
    el[0].position = 0.0
    el[0].color = (0.0, 0.0, 0.0, 1.0)
    el[1].position = 0.4                    # ← 驱动
    el[1].color = (0.0, 0.0, 0.0, 1.0)
    for pos, col in ((0.5, (1.0, 1.0, 1.0, 1.0)),   # ← 驱动
                     (0.6, (1.0, 1.0, 1.0, 1.0)),   # ← 驱动
                     (0.8, (0.0, 0.0, 0.0, 1.0)),   # ← 驱动
                     (1.0, (0.0, 0.0, 0.0, 1.0))):
        e = el.new(pos)
        e.color = col

    # --- ② 发光配色：遮罩 → 颜色。★ 这个节点是【给你手动调的】---
    #     左色标 = 不发光的部分，右色标 = 发光的部分；
    #     双击节点可在中间加色标做多段渐变（例如「暗蓝 → 青 → 白」）。
    #     默认 黑→白；你改过的色标会被快照保留，重跑建脚本不冲掉。
    ramp2 = nt.nodes.new('ShaderNodeValToRGB'); ramp2.name = ramp2.label = N_RAMP2
    ramp2.location = (160, 200)
    ramp2.color_ramp.interpolation = 'LINEAR'
    e2s = ramp2.color_ramp.elements
    e2s[0].position = 0.0
    e2s[0].color = COLOR_DARK
    e2s[1].position = 1.0
    e2s[1].color = COLOR_BRIGHT
    if snap2:
        apply_ramp_snapshot(ramp2, snap2)
    nt.links.new(n_mod.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs['Color'], ramp2.inputs[0])

    # --- 发光：Base Color 纯黑（不反光），Emission Color = 条纹色，Strength 单挂驱动 ---
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (300, 200)
    bsdf.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs['Roughness'].default_value = 1.0
    bsdf.inputs['Metallic'].default_value = 0.0
    nt.links.new(ramp2.outputs['Color'], bsdf.inputs['Emission Color'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return bsdf


def bind_drive(fc, expr, varmap):
    """变量先绑好，再写 expression（顺序反了会静默取默认值）。"""
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


def add_drives(mat, ctrl, bsdf):
    """全部用 SINGLE_PROP 变量指向 ctrl 的 ID 属性 —— 这才有真「依赖边」。"""
    nt = mat.node_tree
    nt.animation_data_create()
    scene = bpy.context.scene
    V = {
        'fr': ('SCENE', scene, 'frame_current'),
        'sp': ('OBJECT', ctrl, '["旋转速度"]'),
        'kn': ('OBJECT', ctrl, '["条纹数量"]'),
        'wd': ('OBJECT', ctrl, '["条纹宽度"]'),
        'sf': ('OBJECT', ctrl, '["渐变柔化"]'),
        'tl': ('OBJECT', ctrl, '["流星拖尾"]'),
        'st': ('OBJECT', ctrl, '["发光强度"]'),
    }
    made = []
    # ① 旋转相位 = -frame × 旋转速度（负号 ⇒ 正速度 = u 增大 = 俯视逆时针）
    p = 'nodes["%s"].inputs[1].default_value' % N_SPIN
    bind_drive(nt.driver_add(p, -1), '-fr * sp', {'fr': V['fr'], 'sp': V['sp']})
    made.append(p)
    # ② 条纹数量 K
    p = 'nodes["%s"].inputs[1].default_value' % N_K
    bind_drive(nt.driver_add(p, -1), 'kn', {'kn': V['kn']})
    made.append(p)
    # ③ 条纹宽度 + 渐变柔化 + 流星拖尾 → 条纹遮罩 4 个色标位置
    #    （色标位置不是 socket，只能走 nt.driver_add）
    #    符号：hw = w/2（亮带半宽）  tr = 柔化×hw（基础过渡带）  tl = 流星拖尾
    #    亮峰中心 c = 0.5 − tl×(0.5 − hw − 0.02)
    #        ⇒ tl=0：居中（前后对称）；tl=1：贴到周期开头（前面几乎没空间）
    #    前缘 rise = tr×(1−tl)          ⇒ tl=1 时 = 0（垂直上升）
    #    后缘 fall = tr + (avail − tr)×tl，avail = 1 − (c + hw)
    #        ⇒ tl=0 时 = tr（对称）；tl=1 时 = avail（拖尾铺满剩余周期）
    C = '0.5 - tl * (0.5 - 0.5 * wd - 0.02)'
    HW = '0.5 * wd'
    TR = 'sf * 0.5 * wd'
    RISE = 'sf * 0.5 * wd * (1.0 - tl)'
    AVAIL = '1.0 - ((%s) + 0.5 * wd)' % C
    FALL = '(%s) + ((%s) - (%s)) * tl' % (TR, AVAIL, TR)
    VARS = {'wd': V['wd'], 'sf': V['sf'], 'tl': V['tl']}
    RAMP_POS = {
        1: 'max(0.0, (%s) - 0.5 * wd - (%s))' % (C, RISE),    # 前缘起点（暗）
        2: '(%s) - 0.5 * wd' % C,                              # 亮带前沿
        3: '(%s) + 0.5 * wd' % C,                              # 亮带后沿
        4: 'min(1.0, (%s) + 0.5 * wd + (%s))' % (C, FALL),     # 拖尾终点（暗）
    }
    for idx, expr in RAMP_POS.items():
        p = 'nodes["%s"].color_ramp.elements[%d].position' % (N_RAMP, idx)
        bind_drive(nt.driver_add(p, -1), expr, VARS)
        made.append(p)
    # ④ 发光强度（socket 直接挂，不连线 ⇒ 核验时能读到真值）
    fc_st = bind_drive(bsdf.inputs['Emission Strength'].driver_add('default_value'),
                       'st', {'st': V['st']})
    made.append('BSDF.Emission Strength')
    return made, fc_st


def write_panel_text():
    src = io.open(PANEL_SRC, encoding='utf-8').read()
    t = bpy.data.texts.get(PANEL_TEXT)
    if t is None:
        t = bpy.data.texts.new(PANEL_TEXT)
    t.clear()
    t.write(src)
    t.use_module = True                  # = UI 上的 Register 勾
    return t


def ensure_cap_mat():
    """端盖材质：纯黑、不发光、不反光。幂等重建。"""
    m = bpy.data.materials.get(CAP_MAT)
    if m is None:
        m = bpy.data.materials.new(CAP_MAT)
        print('新建端盖材质:', CAP_MAT)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if out is None:
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        out.location = (300, 0)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.location = (0, 0)
    b.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    b.inputs['Roughness'].default_value = 1.0
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Emission Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    b.inputs['Emission Strength'].default_value = 0.0
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    return m


def assign_slot(ob, mat, idx):
    """侧面 → 槽 idx（条纹材质）；端盖 → 槽 CAP_SLOT（纯黑）。
    ⚠️ 端盖判定按【法线平行于 Z 轴】，不是按面索引 —— 换模型索引会变。
    返回 (原槽位快照, 被改动的面数, 端盖面数)。不 clear ⇒ 不破坏其他槽。"""
    me = ob.data
    before = [(i, s.name if s else None) for i, s in enumerate(me.materials)]
    while len(me.materials) <= max(idx, CAP_SLOT):
        me.materials.append(None)
    me.materials[idx] = mat
    me.materials[CAP_SLOT] = ensure_cap_mat()
    changed, caps = 0, 0
    for p in me.polygons:
        tgt = CAP_SLOT if abs(abs(p.normal.z) - 1.0) < 1e-3 else idx
        if tgt == CAP_SLOT:
            caps += 1
        if p.material_index != tgt:
            p.material_index = tgt
            changed += 1
    ob.active_material_index = idx
    return before, changed, caps


def main():
    ob = bpy.data.objects.get(TARGET_OBJ)
    if ob is None:
        print('ERR 目标对象不存在:', TARGET_OBJ)
        return
    mat = bpy.data.materials.get(MAT_NAME)
    if mat is None:
        mat = bpy.data.materials.new(MAT_NAME)
        print('新建材质:', MAT_NAME)
    mat.use_nodes = True

    ctrl = ensure_ctrl()
    bsdf = rebuild(mat, ctrl)
    drives, fc_st = add_drives(mat, ctrl, bsdf)
    before, changed, cap_n = assign_slot(ob, mat, SLOT_INDEX)

    txt = write_panel_text()
    # ⚠️ use_module 只在【下次加载文件】时自动执行 —— 当次会话必须手动跑一次，
    #    否则面板和看门狗要等重开文件才出现。
    try:
        txt.as_module().register()
        _wf = bpy.app.driver_namespace.get('_vertical_stripes_watch')
        panel_ok = bool(_wf and bpy.app.timers.is_registered(_wf))
    except Exception as e:
        panel_ok = False
        print('PANEL_REGISTER_WARN', repr(e))

    nt = mat.node_tree
    print('=== BUILD_OK ===')
    print('对象      :', TARGET_OBJ, '| 槽位 =',
          [(i, s.material.name if s.material else None) for i, s in enumerate(ob.material_slots)])
    print('面索引    : 本次改动 %d 个面 | 侧面 %d → 槽 %d | 端盖 %d → 槽 %d'
          % (changed, len(ob.data.polygons) - cap_n, SLOT_INDEX, cap_n, CAP_SLOT))
    print('           改动前槽位快照:', before)
    print('控制空物体:', CTRL_NAME, '| loc =', tuple(round(v, 4) for v in ctrl.location))
    print('锚点校验  : tex.object =', (lambda a: a.object.name if (a and a.object) else '（缺失！）')(
        next((n for n in nt.nodes if n.type == 'TEX_COORD'), None)))
    print('节点数    :', len(nt.nodes), '| 连线数:', len(nt.links))
    print('驱动数    :', len(nt.animation_data.drivers), '| 明细:')
    for d in nt.animation_data.drivers:
        print('   ', d.data_path, '|', d.driver.expression,
              '| valid =', d.driver.is_valid)
    print('BSDF 驱动 :', fc_st.data_path, '|', fc_st.driver.expression,
          '| valid =', fc_st.driver.is_valid)
    print('文本块    :', txt.name, '| use_module =', txt.use_module,
          '| 面板+看门狗在线 =', panel_ok)
    print('控件值    :', {k: ctrl.get(k) for k, *_ in PROPS})


main()
