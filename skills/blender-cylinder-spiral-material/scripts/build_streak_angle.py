# build_streak_angle.py —— 「滚筒斜纹 · 按角度」（方案 B）
#
# 与「按条数」（方案 A）是【并列的两个独立方案】，各自一份材质 + 一个槽位，复用时选一个跑即可。
#   · B（本脚本）槽 3：「条纹数量 K」+「斜角」，高度周期数 N 由斜角经节点链反算
#   · A（build_streak_count.py）槽 1：直接给 K 与 N 两个整数控件
#
# 波形走 Math 域（MapRange(SMOOTHSTEP)×2 + MINIMUM），ColorRamp 只管颜色且零驱动。
# 端盖按法线分到独立纯黑槽。幂等：可反复重跑，已存在的控件值不被覆盖。
#
# ── 相对 v2（纯竖条旋转）的唯一结构改动：给相位加高度项 ─────────────────
#   v2:  p = FLOORED_MODULO((u + spin) × K, 1)
#   v3:  p = FLOORED_MODULO(u×K − v×N + up, 1)      ← 多了 v×N 与上升偏移
#
# ── 方向：靠【实测】定的，不是靠纸面推导（纸面推过一次，推反了）─────────────
#   结构：f = u×K − v'×N，其中 v' = v + up，up 为上升偏移。
#
#   实测（s72_shift.py，取固定高度一行的暗带中心，比两帧位置）：
#     up = −frame×us  ⇒ 暗带【右移】(+0.29 / +0.32)   ✗ 不是想要的方向
#     up = +frame×us  ⇒ 暗带【左移】                   ✔ 即「右下→左上」
#
#   手算复核（K=3 / N=2 / v=0.5）：
#     f = 3u − 2(0.5+up)。up = +t·us 时，t 从 365→400，常数 c = −2up 的小数部分
#     从 −0.30 变到 0.00；亮带条件 (3u+c) ∈ [0.12,0.22] ⇒ u 从 0.14~0.17 移到 0.04~0.07
#     ⇒ u 减小 = 左移 ✔
#
#   ★ 结论：SUBTRACT（uK − vN）配【正号】偏移 = 条纹左移 = 右下→左上。
#     想让条纹往右上走，把「上升速度」取负即可。
#
# ── 波形仍走 v2 的 Math 域方案（不动）──────────────────────────────────
#   前缘 = MapRange(SMOOTHSTEP, 0..A → 0..1)
#   拖尾 = MapRange(SMOOTHSTEP, B..1 → 1..0)
#   mask = MINIMUM(前缘, 拖尾)   ⇒ 快升/平台/慢降，色标不再被驱动锁死
#   ColorRamp（发光配色）零驱动 ⇒ 用户可自由加色标
#
# 斜角由 K/N 比值决定：`角度 = atan((K/N) × 柱高 / 周长)`。
#   本柱：周长 23.74、高 13.68 ⇒ 系数 0.576。K:N = 3:2 ⇒ 41°。
#
# 幂等：可反复重跑；已存在的控件值不被覆盖；废弃控件自动清理。
# 桥接 exec 时 __name__ 为 builtins，不用 __main__ 守卫。
import bpy
import io
import math

# ============================== 配置区 ==============================
TARGET_OBJ = '滚动效果网格体'
MAT_NAME = '滚动效果网格体_滚筒斜纹_按角度'
CTRL_NAME = '竖条旋转控制'
SLOT_INDEX = 0          # 条纹材质（唯一：跑哪个方案就装哪个）
CAP_MAT = '滚动效果网格体_端盖黑'          # 端盖专用（端盖上 atan2 是极角 ⇒ 条纹会摊成扇形）
CAP_SLOT = 1            # 端盖专用（纯黑）

# ⚠️ 以下圆柱几何是【本工程实测值】。换工程必须重新只读侦察后改写。
AXIS_X, AXIS_Y = 30.9216, 2.8832
Z_BOTTOM = -1.1444
HEIGHT = 13.6764                          # 锚点在底面 ⇒ Object 坐标 z ∈ [0, HEIGHT]
CYL_RADIUS = 3.7789                       # 柱半径（用于把「斜角」反算成高度周期数）

# ★ 斜角 → 高度周期数：θ = atan((K/N) × H/P)  ⇒  N = K × (H/P) / tan(θ)
H_OVER_P = HEIGHT / (2.0 * math.pi * CYL_RADIUS)

COLOR_DARK = (0.0, 0.0, 0.0, 1.0)         # 不发光部分的颜色（默认纯黑）
COLOR_BRIGHT = (1.0, 1.0, 1.0, 1.0)       # 发光部分的颜色（默认纯白）

PANEL_SRC = r'D:/workbuddy/2026-09-20-09-39-42/_liantiao\streak_angle_panel.py' 
PANEL_TEXT = 'streak_angle_panel.py'

# 控件：(键名, 默认, min, max, soft_min, soft_max, step, precision, 说明)
PROPS = [
    ('条纹数量', 3.0, 1.0, 24.0, 1.0, 12.0, 1, 0,
     '绕柱一周的条纹条数 —— 必须整数，否则接缝处错位'),
    ('斜角', 41.0, 5.0, 85.0, 10.0, 70.0, 1, 1,
     '条纹倾斜角度（度）。高度周期数由「条纹数量」与它反算 ⇒ 不用改条数就能调斜度'),
    ('前缘宽度', 0.12, 0.005, 1.0, 0.02, 0.5, 1, 3,
     '一个周期里升到最亮所占的比例（0.12 = 快到 12% 处就满亮）。越小头越尖'),
    ('拖尾起点', 0.22, 0.005, 1.0, 0.05, 0.9, 1, 3,
     '从周期哪个位置开始衰减 —— 拖尾长度 = 1 − 此值。0.22 ⇒ 拖尾占 78%'),
    ('上升速度', 0.01, -0.2, 0.2, 0.0, 0.04, 1, 4,
     '每帧沿柱高流动多少（正 = 条纹【右下→左上】；负 = 左上→右下）'),
    ('旋转速度', 0.0, -0.2, 0.2, 0.0, 0.04, 1, 4,
     '每帧额外绕 Z 轴转多少圈（默认 0；正值 = 俯视逆时针）'),
    ('发光强度', 5.0, 0.0, 100.0, 1.0, 30.0, 1, 1,
     '发光强度倍数（AgX 会压暗发光，看不清就往大调）'),
]
# 历史版本遗留、现已废弃的控件 —— 重跑时清掉，避免面板/文档出现幽灵参数
DEPRECATED = ('条纹宽度', '渐变柔化', '流星拖尾')   # ⚠️ 不含「斜角」/「高度条纹数」—— 那两个是 A/B 各自在用的键

# 节点名（中文；驱动 data_path 与面板都引用它们）
N_TEX, N_SEP = '纹理坐标', '分离XYZ'
N_ATAN, N_PI, N_U = '柱面_相位角', '柱面_角度偏置', '柱面_角度U'
N_SPIN, N_K = '旋转相位', '条纹数量K'
N_HV, N_UP, N_HN, N_COMB = '柱面_高度V', '上升偏移', '高度条纹N', '螺旋合成'
N_ANG_RAD, N_ANG_TAN, N_NUM, N_NCALC = '斜角_弧度', '斜角_正切', 'N_分子', 'N_计算'
N_MOD = '相位取模'
N_RISE, N_FALL, N_MASK = '前缘上升', '拖尾衰减', '波形合成'
N_RAMP = '发光配色'
# ====================================================================


def cleanup_old_ui():
    """清掉上一版留下的面板类 / 文本块 / 看门狗（本版类名与定时器键都换了）。"""
    for key, cls, txt in (('_streak_angle_watch', 'VIEW3D_PT_streak_angle', 'streak_angle_panel.py'),
                          ('_streak_watch', 'VIEW3D_PT_streak', 'streak_panel.py'),
                          ('_vertical_stripes_watch', 'VIEW3D_PT_vertical_stripes',
                           'vertical_stripes_panel.py')):
        old = bpy.app.driver_namespace.get(key)
        if old is not None:
            try:
                bpy.app.timers.unregister(old)
            except Exception:
                pass
            bpy.app.driver_namespace.pop(key, None)
            print('  摘除旧看门狗', key)
        c = getattr(bpy.types, cls, None)
        if c is not None:
            try:
                bpy.utils.unregister_class(c)
                print('  注销旧面板类', cls)
            except Exception as e:
                print('  旧面板类注销失败', cls, repr(e))
        t = bpy.data.texts.get(txt)
        if t is not None:
            bpy.data.texts.remove(t)
            print('  删除旧文本块', txt)


def ensure_ctrl():
    ob = bpy.data.objects.get(TARGET_OBJ)
    col = ob.users_collection[0] if (ob and ob.users_collection) else None
    c = bpy.data.objects.get(CTRL_NAME)
    if c is None:
        c = bpy.data.objects.new(CTRL_NAME, None)
        (col or bpy.context.scene.collection).objects.link(c)
        print('新建控制空物体:', CTRL_NAME)
    c.parent = None
    c.location = (AXIS_X, AXIS_Y, Z_BOTTOM)
    c.rotation_euler = (0.0, 0.0, 0.0)
    c.scale = (1.0, 1.0, 1.0)
    for key in DEPRECATED:
        if key in c:
            del c[key]
            print('  清理废弃控件:', key)
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


def new_maprange(nt, loc, name, fmin, fmax, tmin, tmax):
    """v2 的核心构建块：Smooth Step 映射。
    inputs 实测顺序 = [0]Value [1]From Min [2]From Max [3]To Min [4]To Max [5]Steps"""
    n = nt.nodes.new('ShaderNodeMapRange')
    n.name = n.label = name
    n.location = loc
    n.interpolation_type = 'SMOOTHSTEP'
    n.clamp = True
    n.inputs[0].default_value = 0.0
    n.inputs[1].default_value = fmin
    n.inputs[2].default_value = fmax
    n.inputs[3].default_value = tmin
    n.inputs[4].default_value = tmax
    return n


def rebuild(mat, ctrl):
    nt = mat.node_tree
    nt.animation_data_clear()                       # 幂等：先清旧驱动
    # ★ 快照用户手调的配色，重建后原样还原（结构性端点钉死在 0/1）
    snap = None
    old = nt.nodes.get(N_RAMP)
    if old is not None and old.type == 'VALTORGB':
        snap = [(e.position, tuple(e.color)) for e in old.color_ramp.elements]
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if out is None:
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        out.location = (1400, 0)

    # ── ① 柱面坐标：Object 输出指向锚点空物体 ⇒ 坐标 = 柱面坐标 ──
    tex = nt.nodes.new('ShaderNodeTexCoord'); tex.name = tex.label = N_TEX
    tex.location = (-1900, 0)
    tex.object = ctrl
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.name = sep.label = N_SEP
    sep.location = (-1720, 0)
    nt.links.new(tex.outputs['Object'], sep.inputs['Vector'])

    # ── ② u = (atan2(y, x) + π) / 2π —— 绕柱角度归一化（y 分子 / x 分母）──
    atan = new_math(nt, 'ARCTAN2', (-1540, 300), N_ATAN)
    nt.links.new(sep.outputs['Y'], atan.inputs[0])
    nt.links.new(sep.outputs['X'], atan.inputs[1])
    n_pi = new_math(nt, 'ADD', (-1390, 300), N_PI, math.pi)
    nt.links.new(atan.outputs[0], n_pi.inputs[0])
    n_u = new_math(nt, 'MULTIPLY', (-1240, 300), N_U, 1.0 / (2.0 * math.pi))
    nt.links.new(n_pi.outputs[0], n_u.inputs[0])

    # ── ③ v = z / 柱高（锚点在底面 ⇒ z 天然 ∈ [0, 柱高]，少一个减法节点）──
    n_hv = new_math(nt, 'MULTIPLY', (-1540, -260), N_HV, 1.0 / HEIGHT)
    nt.links.new(sep.outputs['Z'], n_hv.inputs[0])
    # 上升偏移（被驱动为 −frame×上升速度 ⇒ 正速度 = 条纹往左上走）
    n_up = new_math(nt, 'ADD', (-1380, -260), N_UP, 0.0)
    nt.links.new(n_hv.outputs[0], n_up.inputs[0])
    # 高度条纹 N：乘数由【斜角】反算，不再单独占一个控件
    #   N = K × (柱高/周长) ÷ tan(radians(斜角))     ← 节点里实时算，天然跟随 K 变化
    n_hn = new_math(nt, 'MULTIPLY', (-1220, -260), N_HN, 1.0)
    nt.links.new(n_up.outputs[0], n_hn.inputs[0])

    # ── ③b 斜角 → N 的反算链：RADIANS → TANGENT；K×(H/P) ÷ tan ──
    n_rad = new_math(nt, 'RADIANS', (-1400, -560), N_ANG_RAD)      # 输入 = 度数
    n_tan = new_math(nt, 'TANGENT', (-1240, -560), N_ANG_TAN)      # tan(θ)
    nt.links.new(n_rad.outputs[0], n_tan.inputs[0])
    n_num = new_math(nt, 'MULTIPLY', (-1400, -720), N_NUM, H_OVER_P)   # K × (H/P)
    n_ncalc = new_math(nt, 'DIVIDE', (-1080, -640), N_NCALC)
    nt.links.new(n_num.outputs[0], n_ncalc.inputs[0])
    nt.links.new(n_tan.outputs[0], n_ncalc.inputs[1])
    nt.links.new(n_ncalc.outputs[0], n_hn.inputs[1])               # N 接到高度条纹N

    # ── ④ 水平相位（旋转）与竖向相位（上升）──
    # spin 加在【乘 K 之前】⇒ 旋                       转速度与条纹条数解耦
    n_spin = new_math(nt, 'ADD', (-1080, 300), N_SPIN, 0.0)
    nt.links.new(n_u.outputs[0], n_spin.inputs[0])
    n_k = new_math(nt, 'MULTIPLY', (-920, 300), N_K, 1.0)
    nt.links.new(n_spin.outputs[0], n_k.inputs[0])
    nt.links.new(n_k.outputs[0], n_num.inputs[0])                  # K 同时喂给 N 反算

    # ── ⑤ ★ 螺旋合成 = u×K − v×N  ⇒ 条纹是 `/` 形（左下→右上）──
    #    SUBTRACT 的 inputs[0] = 水平相位（K 侧）、inputs[1] = 竖向相位（N 侧）
    #    取减号是为了让「上升偏移取负」时条纹往【左上】移动（见文件头方向表）
    n_comb = new_math(nt, 'SUBTRACT', (-760, 40), N_COMB)
    nt.links.new(n_k.outputs[0], n_comb.inputs[0])
    nt.links.new(n_hn.outputs[0], n_comb.inputs[1])

    # ── ⑥ 取模（必须 FLOORED_MODULO：偏移为负时 f 取负，普通 MODULO 会裁掉条纹底部）──
    n_mod = new_math(nt, 'FLOORED_MODULO', (-600, 40), N_MOD, 1.0)
    nt.links.new(n_comb.outputs[0], n_mod.inputs[0])

    # ── ⑦ 波形：前缘上升 ∩ 拖尾衰减（v2 的 Math 域方案，与斜纹无关）──
    rise = new_maprange(nt, (-380, 320), N_RISE, 0.0, 0.12, 0.0, 1.0)
    nt.links.new(n_mod.outputs[0], rise.inputs[0])
    fall = new_maprange(nt, (-380, 60), N_FALL, 0.22, 1.0, 1.0, 0.0)
    nt.links.new(n_mod.outputs[0], fall.inputs[0])
    mask = new_math(nt, 'MINIMUM', (-160, 190), N_MASK)
    nt.links.new(rise.outputs['Result'], mask.inputs[0])
    nt.links.new(fall.outputs['Result'], mask.inputs[1])

    # ── ⑧ 颜色：★ 这个 ColorRamp 一个驱动都不挂，完全交给用户 ──
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.name = ramp.label = N_RAMP
    ramp.location = (80, 190)
    ramp.color_ramp.interpolation = 'LINEAR'
    els = ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = COLOR_DARK
    els[1].position = 1.0
    els[1].color = COLOR_BRIGHT
    if snap:
        while len(els) > 2 and len(els) > len(snap):
            els.remove(els[-1])
        while len(els) < len(snap):
            els.new(0.5)
        for e, (pos, col) in zip(els, snap):
            e.position = pos
            e.color = col
        els[0].position = 0.0        # ★ 结构性端点钉死（曾因删错元素导致曲线提前饱和）
        els[-1].position = 1.0
    nt.links.new(mask.outputs[0], ramp.inputs[0])

    # ── ⑨ 发光：Base Color 纯黑（不反光），Emission Color = 配色，Strength 单挂驱动 ──
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (360, 190)
    bsdf.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs['Roughness'].default_value = 1.0
    bsdf.inputs['Metallic'].default_value = 0.0
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Emission Color'])
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
        'us': ('OBJECT', ctrl, '["上升速度"]'),
        'kn': ('OBJECT', ctrl, '["条纹数量"]'),
        'ang': ('OBJECT', ctrl, '["斜角"]'),
        'fe': ('OBJECT', ctrl, '["前缘宽度"]'),
        'ts': ('OBJECT', ctrl, '["拖尾起点"]'),
        'st': ('OBJECT', ctrl, '["发光强度"]'),
    }
    made = []
    # ① 旋转相位 = −frame × 旋转速度（正速度 = u 增大 = 俯视逆时针）
    p = 'nodes["%s"].inputs[1].default_value' % N_SPIN
    bind_drive(nt.driver_add(p, -1), '-fr * sp', {'fr': V['fr'], 'sp': V['sp']})
    made.append(p)
    # ② ★ 上升偏移 = +frame × 上升速度（正号 ⇒ 正速度 = 条纹往【左上】流动；实测定标）
    #    ⚠️ 纸面推导会得出相反结论，务必以 s72_shift.py 的实测为准（见文件头）
    p = 'nodes["%s"].inputs[1].default_value' % N_UP
    bind_drive(nt.driver_add(p, -1), 'fr * us', {'fr': V['fr'], 'us': V['us']})
    made.append(p)
    # ③ 条纹数量 K
    p = 'nodes["%s"].inputs[1].default_value' % N_K
    bind_drive(nt.driver_add(p, -1), 'floor(kn + 0.5)', {'kn': V['kn']})   # ★ 取整：K 必须整数，否则绕柱接缝处会错位半格
    made.append(p)
    # ④ 斜角（度）→ 斜角_弧度 的输入（N 随后由节点链反算，这样调斜度不必改条数）
    p = 'nodes["%s"].inputs[0].default_value' % N_ANG_RAD
    bind_drive(nt.driver_add(p, -1), 'ang', {'ang': V['ang']})
    made.append(p)
    # ⑤ 前缘宽度 → 前缘 MapRange 的 From Max（inputs[2]）
    p = 'nodes["%s"].inputs[2].default_value' % N_RISE
    bind_drive(nt.driver_add(p, -1), 'fe', {'fe': V['fe']})
    made.append(p)
    # ⑥ 拖尾起点 → 拖尾 MapRange 的 From Min（inputs[1]）
    p = 'nodes["%s"].inputs[1].default_value' % N_FALL
    bind_drive(nt.driver_add(p, -1), 'ts', {'ts': V['ts']})
    made.append(p)
    # ⑦ 发光强度（socket 直接挂，不连线 ⇒ 核验时能读到真值）
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
    t.use_module = True
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
        out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (300, 0)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled'); b.location = (0, 0)
    b.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    b.inputs['Roughness'].default_value = 1.0
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Emission Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    b.inputs['Emission Strength'].default_value = 0.0
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    return m


def assign_slot(ob, mat, idx):
    """侧面 → 槽 idx；端盖 → 槽 CAP_SLOT（纯黑）。
    ⚠️ 端盖按【法线平行 Z 轴】判定，不写死面索引。返回 (原槽位, 改动面数, 端盖面数)。"""
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
    cleanup_old_ui()
    bsdf = rebuild(mat, ctrl)
    drives, fc_st = add_drives(mat, ctrl, bsdf)
    before, changed, cap_n = assign_slot(ob, mat, SLOT_INDEX)

    txt = write_panel_text()
    try:
        txt.as_module().register()
        _wf = bpy.app.driver_namespace.get('_streak_angle_watch')
        panel_ok = bool(_wf and bpy.app.timers.is_registered(_wf))
    except Exception as e:
        panel_ok = False
        print('PANEL_REGISTER_WARN', repr(e))

    nt = mat.node_tree
    k = ctrl.get('条纹数量') or 1.0
    ang = ctrl.get('斜角') or 0.0
    n_calc = k * H_OVER_P / math.tan(math.radians(ang)) if ang else 0.0
    print('=== BUILD_OK (方案B · 按角度) ===')
    print('斜角      : %.1f° ⇒ 高度周期数 N = %.4f（由 K=%.0f 与斜角反算）'
          % (ang, n_calc, k))
    print('对象      :', TARGET_OBJ, '| 槽位 =',
          [(i, s.material.name if s.material else None) for i, s in enumerate(ob.material_slots)])
    print('面索引    : 改动 %d 个面 | 侧面 → 槽 %d | 端盖 %d 个 → 槽 %d'
          % (changed, SLOT_INDEX, cap_n, CAP_SLOT))
    print('控制空物体:', CTRL_NAME, '| loc =', tuple(round(v, 4) for v in ctrl.location),
          '| keys =', [k2 for k2 in ctrl.keys() if not k2.startswith('_')])
    print('节点数    :', len(nt.nodes), '| 连线数:', len(nt.links))
    print('螺旋合成  : SUBTRACT | 条纹 %s×K − %s×N ⇒ / 形'
          % (nt.nodes[N_K].operation, nt.nodes[N_HN].operation))
    print('上升方向  : 驱动 +fr * us ⇒ 正速度 = 右下→左上（s72 实测定标）')
    print('驱动数    :', len(nt.animation_data.drivers), '| 明细:')
    for d in nt.animation_data.drivers:
        print('   ', d.data_path, '|', d.driver.expression, '| valid =', d.driver.is_valid)
    print('配色色标  :', len(nt.nodes[N_RAMP].color_ramp.elements), '个（无驱动，用户可自由加）')
    print('文本块    :', txt.name, '| use_module =', txt.use_module, '| 面板+看门狗在线 =', panel_ok)
    print('控件值    :', {k2: ctrl.get(k2) for k2, *_ in PROPS})


main()
