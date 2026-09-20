# build_spiral_rise.py —— 给「滚动效果网格体」建「螺旋上升」发光材质
#
# 圆柱面螺旋条纹（理发店滚筒）：
#   f = u×K + v×N   →  FLOORED_MODULO 1  →  ColorRamp 条纹  →  Emission
#   u = (atan2(y, x) + π) / 2π        绕柱角度归一化 0~1
#   v = z / 柱高                       高度归一化 0~1（锚点在柱底面）
#   条纹随时间上升：v 上加偏移 = frame × 上升速度（正值 = 向上）
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
MAT_NAME = '滚动效果网格体_螺旋上升'
CTRL_NAME = '螺旋上升控制'

# 圆柱实测几何 —— ⚠️ 下面这几个数是【本工程实测值】。
#    换工程必须重新只读侦察（逐顶点世界坐标求包围盒 ⇒ 半径是否恒定 / 轴向 / zmin / zmax）后再改，
#    否则 u（绕柱角度）与 v（高度归一化）的基准就是错的。
# 锚点空物体放柱【底面中心】，于是 Object 坐标 z 天然落在 [0, HEIGHT]（v 少一次减法）
AXIS_X, AXIS_Y = 30.9216, 2.8832      # 柱轴心（世界 XY）
Z_BOTTOM = -1.1444                    # 柱底面世界 Z
HEIGHT = 13.6764                      # 柱高

# 条纹配色（想换颜色改这两行）
COLOR_DARK = (0.0, 0.0, 0.0, 1.0)
COLOR_BRIGHT = (1.0, 1.0, 1.0, 1.0)

# 面板源码（写进 Register 文本块；文本块必须自包含，故从文件读入）
PANEL_SRC = r'D:\workbuddy\2026-09-20-09-39-42\_liantiao\spiral_rise_panel.py'
PANEL_TEXT = 'spiral_rise_panel.py'

# 控件：(键名, 默认, min, max, soft_min, soft_max, step, precision, 说明)
# 默认值由参数扫描定：K3/N2/w0.35 是「几道螺旋光带绕柱」的灯柱感（见 preview/C_参数对比）
PROPS = [
    ('环绕圈数', 3.0, 1.0, 12.0, 1.0, 6.0, 1, 0,
     '条纹绕柱的条数 —— 必须整数，否则 u=0/2π 接缝处会错位'),
    ('高度条纹', 2.0, 1.0, 12.0, 1.0, 6.0, 1, 0,
     '高度方向的条纹周期数 —— 与环绕圈数的比值决定螺旋角'),
    ('条纹宽度', 0.35, 0.05, 1.0, 0.1, 0.9, 1, 2,
     '亮条占一个周期的比例（1.0 = 全亮无暗区）'),
    ('上升速度', 0.02, -0.2, 0.2, 0.0, 0.06, 1, 3,
     '每帧上升多少倍柱高；正值 = 向上流动，负值 = 向下'),
    ('发光强度', 5.0, 0.0, 100.0, 1.0, 30.0, 1, 1,
     '发光强度倍数（AgX 会压暗发光，看不清就往大调）'),
]

# 节点名（中文，驱动 data_path 与面板都引用它们）
N_TEX, N_SEP = '纹理坐标', '分离XYZ'
N_ATAN, N_PI, N_U = '柱面_相位角', '柱面_角度偏置', '柱面_角度U'
N_V, N_RISE = '柱面_高度V', '上升偏移'
N_K, N_NN, N_SUM, N_MODEC = '环绕圈数K', '高度条纹N', '螺旋合成', '螺旋取模'
N_RAMP = '条纹'
# ====================================================================


def ensure_ctrl():
    ob = bpy.data.objects.get(TARGET_OBJ)
    col = ob.users_collection[0] if (ob and ob.users_collection) else None
    c = bpy.data.objects.get(CTRL_NAME)
    if c is None:
        c = bpy.data.objects.new(CTRL_NAME, None)
        (col or bpy.context.scene.collection).objects.link(c)
        print('新建控制空物体:', CTRL_NAME)
    # 锚点必须是「柱底面中心 + rotation 0 + scale 1」，Object 坐标才等于柱面坐标
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


def rebuild(mat, ctrl):
    nt = mat.node_tree
    nt.animation_data_clear()                       # 幂等：先清旧驱动
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

    # --- v：z / 柱高（锚点在底面 ⇒ 无需减 zmin） ---
    n_v = new_math(nt, 'MULTIPLY', (-1000, -100), N_V, 1.0 / HEIGHT)
    nt.links.new(sep.outputs['Z'], n_v.inputs[0])

    # --- 上升偏移：v + (-frame × 速度) ⇒ 正速度 = 条纹向上 ---
    n_rise = new_math(nt, 'ADD', (-850, -100), N_RISE, 0.0)
    nt.links.new(n_v.outputs[0], n_rise.inputs[0])

    # --- f = u×K + v×N ---
    n_k = new_math(nt, 'MULTIPLY', (-520, 200), N_K, 2.0)
    nt.links.new(n_u.outputs[0], n_k.inputs[0])
    n_n = new_math(nt, 'MULTIPLY', (-520, -100), N_NN, 1.0)
    nt.links.new(n_rise.outputs[0], n_n.inputs[0])
    n_sum = new_math(nt, 'ADD', (-350, 60), N_SUM)
    nt.links.new(n_k.outputs[0], n_sum.inputs[0])
    nt.links.new(n_n.outputs[0], n_sum.inputs[1])

    # --- 取模：必须 FLOORED_MODULO（普通 MODULO 负值被钳 ⇒ 条纹底部被裁） ---
    n_mod = new_math(nt, 'FLOORED_MODULO', (-180, 60), N_MODEC, 1.0)
    nt.links.new(n_sum.outputs[0], n_mod.inputs[0])

    # --- 条纹：★ 暗底 + 亮条 ---
    # 3 色标 + CONSTANT 插值 ⇒ [0, 1-w) 恒暗，[1-w, 1] 恒亮（硬边，占空比 = 条纹宽度）
    # ⚠️ 反例（v1 实测踩过）：若 e0 用 LINEAR，[0,1-w] 会整段渐变到白 ⇒ 渲染出来是
    #    「宽白底 + 一条细黑缝」，完全不像灯带。暗底必须靠 CONSTANT 才能成立。
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.name = ramp.label = N_RAMP
    ramp.location = (0, 60)
    # ⚠️ Blender 5.2 的 ColorRampElement 【没有】interpolation 属性 ——
    #    插值方式是整个 ColorRamp 的属性，即 ramp.color_ramp.interpolation。
    ramp.color_ramp.interpolation = 'CONSTANT'
    el = ramp.color_ramp.elements
    el[0].position = 0.0
    el[0].color = COLOR_DARK
    el[1].position = 0.5                    # 由「条纹宽度」驱动 = 1 - w
    el[1].color = COLOR_BRIGHT
    e2 = el.new(1.0)
    e2.color = COLOR_BRIGHT
    nt.links.new(n_mod.outputs[0], ramp.inputs['Fac'])

    # --- 发光：Base Color 纯黑（不反光），Emission Color = 条纹色，Strength 单挂驱动 ---
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (300, 60)
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
        'us': ('OBJECT', ctrl, '["上升速度"]'),
        'kn': ('OBJECT', ctrl, '["环绕圈数"]'),
        'hn': ('OBJECT', ctrl, '["高度条纹"]'),
        'wd': ('OBJECT', ctrl, '["条纹宽度"]'),
        'st': ('OBJECT', ctrl, '["发光强度"]'),
    }
    made = []
    # ① 上升偏移 = -frame × 上升速度（负号 ⇒ 正速度 = 向上流动）
    p = 'nodes["%s"].inputs[1].default_value' % N_RISE
    bind_drive(nt.driver_add(p, -1), '-fr * us', {'fr': V['fr'], 'us': V['us']})
    made.append(p)
    # ② 环绕圈数 K
    p = 'nodes["%s"].inputs[1].default_value' % N_K
    bind_drive(nt.driver_add(p, -1), 'kn', {'kn': V['kn']})
    made.append(p)
    # ③ 高度条纹 N
    p = 'nodes["%s"].inputs[1].default_value' % N_NN
    bind_drive(nt.driver_add(p, -1), 'hn', {'hn': V['hn']})
    made.append(p)
    # ④ 条纹宽度 → ColorRamp 色标（不是 socket，只能走 nt.driver_add）
    p = 'nodes["%s"].color_ramp.elements[1].position' % N_RAMP
    bind_drive(nt.driver_add(p, -1), '1.0 - wd', {'wd': V['wd']})
    made.append(p)
    # ⑤ 发光强度（socket 直接挂，不连线 ⇒ 核验时能读到真值）
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

    # 指派到槽 0（对象原本无材质）
    if not ob.material_slots:
        ob.data.materials.append(mat)
    else:
        ob.material_slots[0].material = mat

    txt = write_panel_text()
    # ⚠️ use_module 只在【下次加载文件】时自动执行 —— 当次会话必须手动跑一次，
    #    否则面板和看门狗要等重开文件才出现。
    try:
        txt.as_module().register()
        _wf = bpy.app.driver_namespace.get('_spiral_rise_watch')
        panel_ok = bool(_wf and bpy.app.timers.is_registered(_wf))
    except Exception as e:
        panel_ok = False
        print('PANEL_REGISTER_WARN', repr(e))

    nt = mat.node_tree
    print('=== BUILD_OK ===')
    print('对象      :', TARGET_OBJ, '| 槽0 =', ob.material_slots[0].material.name)
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
