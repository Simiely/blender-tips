"""
构建 同心圆扩展灯材质 + 统一控制器 + 实时面板 (可复用)
=====================================================
用法:
    python send.py build_ring_controls.py       # 经 socket 桥远程执行
    # 或 在 Blender Scripting 工作区 Run Script

它做三件事(均可通过顶部常量配置):
1. 确保控制空物体 {CTRL_NAME} 存在并带有 5 个自定义属性
   (speed/density/gain/solid/gradient_on,已有值保留);
2. 把目标材质 {MAT_NAME} 重建为「XZ 径向同心圆渐变」自发光管线,
   全部参数由控制空物体以 SCRIPTED 驱动统一接管(共用同一圆心);
3. 把 ring_control_panel.py 注入 .blend 文本块并勾选 Register,
   使重启打开文件后面板自动注册(Auto Run Python Scripts 需开启)。

本脚本按仓库规范不写 __main__ 守卫(桥 exec 时 __name__ 是 builtins)。
"""
import bpy

# ===== 可复用配置 =====
CTRL_NAME   = "主装置_圆环控制"          # 统一控制器(也是共用圆心参照)
MAT_NAME    = "主装置_发光材质_需要做圆形扩展灯效果"   # 要重建的目标材质
PREFIX      = "主装置"                  # 节点名前缀(避免冲突)
PANEL_FILE  = "ring_control_panel.py"   # 仓库内随附面板脚本文件名
PANEL_TITLE = "材质参数实时控制器"

PROPS = {   # 键 → 默认值(已有值保留)
    "speed":       0.01,
    "gradient_on": 1.0,
    "density":     1.0,
    "gain":        25.0,
    "solid":       20.0,
}

# ===== 驱动函数 =====
def drive_socket(sock, expr, var, path):
    fc = sock.driver_add('default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    d.expression = expr
    for v in list(d.variables):
        d.variables.remove(v)
    v = d.variables.new()
    v.name = var
    v.type = 'SINGLE_PROP'
    v.targets[0].id = ctl
    v.targets[0].data_path = path


def ramp_set(cr):
    """柔和环带: B-Spline 插值 + 最暗处 10% 白,避免生硬黑白跳变。"""
    cr.interpolation = 'B_SPLINE'
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    e0 = cr.elements[0]; e0.position = 0.08; e0.color = (0.10, 0.10, 0.10, 1.0)
    for pos, lum in [(0.30, 0.10), (0.40, 0.30), (0.50, 1.00),
                     (0.60, 0.30), (0.70, 0.10), (0.92, 0.10)]:
        e = cr.elements.new(pos); e.color = (lum, lum, lum, 1.0)


def build_controls():
    ctl = bpy.data.objects.get(CTRL_NAME)
    if ctl is None:
        ctl = bpy.data.objects.new(CTRL_NAME, None)
        bpy.context.collection.objects.link(ctl)
    for k, dflt in PROPS.items():
        ctl[k] = ctl.get(k, dflt)
    return ctl


def build_material(mname):
    mat = bpy.data.materials.new(mname) if mname not in bpy.data.materials else bpy.data.materials[mname]
    nt = mat.node_tree
    for n_ in list(nt.nodes):
        nt.nodes.remove(n_)
    def nn(t_): return nt.nodes.new(t_)
    def nval(name, v, x, y):
        n = nn('ShaderNodeValue'); n.name = n.label = name
        n.outputs[0].default_value = v; n.location = (x, y); return n
    P = PREFIX

    tex = nn('ShaderNodeTexCoord'); tex.name = tex.label = P + '_纹理坐标'
    tex.object = ctl; tex.location = (-1500, 0)          # 关键: 共用圆心 = 控制空物体
    sep = nn('ShaderNodeSeparateXYZ'); sep.name = sep.label = P + '_取XZ'; sep.location = (-1300, 0)
    comb = nn('ShaderNodeCombineXYZ'); comb.name = comb.label = P + '_径向2D'; comb.location = (-1100, 0)
    rlen = nn('ShaderNodeVectorMath'); rlen.name = rlen.label = P + '_半径'; rlen.operation = 'LENGTH'; rlen.location = (-900, 0)
    dens = nval(P + '_环数', 1.0, -900, 220)
    mul  = nn('ShaderNodeMath'); mul.name = mul.label = P + '_相位基准'; mul.operation = 'MULTIPLY'; mul.location = (-700, 0)
    exp  = nval(P + '_扩张', 0.0, -900, 380)
    sub  = nn('ShaderNodeMath'); sub.name = sub.label = P + '_相位'; sub.operation = 'SUBTRACT'; sub.location = (-500, 0)
    frac = nn('ShaderNodeMath'); frac.name = frac.label = P + '_分带'; frac.operation = 'FRACT'; frac.location = (-300, 0)
    ramp = nn('ShaderNodeValToRGB'); ramp.name = ramp.label = P + '_环渐变'; ramp.location = (-100, 0)
    ramp_set(ramp.color_ramp)
    gain = nval(P + '_强度', 25.0, -100, 220)
    strength = nn('ShaderNodeMath'); strength.name = strength.label = P + '_发光强度'; strength.operation = 'MULTIPLY'; strength.location = (100, 0)
    solid = nval(P + '_纯色强度', 20.0, -100, -100)
    sw = nval(P + '_渐变开关', 1.0, -100, 400)
    mixn = nn('ShaderNodeMix'); mixn.name = mixn.label = P + '_混合'
    mixn.data_type = 'FLOAT'; mixn.blend_type = 'MIX'
    mixn.inputs['Factor'].default_value = 1.0; mixn.location = (220, 0)
    bsdf = nn('ShaderNodeBsdfPrincipled'); bsdf.name = bsdf.label = P + '_发光主体'; bsdf.location = (320, 0)
    bsdf.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.35
    bsdf.inputs['Emission Color'].default_value = (0.35, 0.85, 1.0, 1.0)
    outm = nn('ShaderNodeOutputMaterial'); outm.name = outm.label = '材质输出'; outm.location = (520, 0)

    def L(a, b): nt.links.new(a, b)
    funct = {'density': dens.outputs[0], 'gain': gain.outputs[0],
             'solid': solid.outputs[0], 'gradient_on': sw.outputs[0]}
    L(tex.outputs['Object'], sep.inputs['Vector'])
    L(sep.outputs['X'], comb.inputs['X']); L(sep.outputs['Z'], comb.inputs['Y'])
    L(comb.outputs['Vector'], rlen.inputs['Vector'])
    L(rlen.outputs['Value'], mul.inputs[0]); L(dens.outputs[0], mul.inputs[1])
    L(mul.outputs[0], sub.inputs[0]); L(exp.outputs[0], sub.inputs[1])
    L(sub.outputs[0], frac.inputs[0]); L(frac.outputs[0], ramp.inputs['Fac'])
    L(ramp.outputs['Color'], strength.inputs[0]); L(gain.outputs[0], strength.inputs[1])
    L(mixn.outputs['Result'], bsdf.inputs['Emission Strength'])
    L(solid.outputs[0], mixn.inputs['A']); L(strength.outputs[0], mixn.inputs['B'])
    L(sw.outputs[0], mixn.inputs['Factor'])
    L(bsdf.outputs['BSDF'], outm.inputs['Surface'])

    # 5 个驱动全部指向控制空物体
    drive_socket(exp.outputs[0], '(frame - 1) * speed', 'speed', '["speed"]')
    drive_socket(dens.outputs[0], 'density', 'density', '["density"]')
    drive_socket(gain.outputs[0], 'gain', 'gain', '["gain"]')
    drive_socket(solid.outputs[0], 'solid', 'solid', '["solid"]')
    drive_socket(sw.outputs[0], 'on', 'on', '["gradient_on"]')
    return mat


def inject_panel():
    """把随附面板脚本作为 .blend 文本块并标记 Register(重启自动注册)。"""
    import os
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), PANEL_FILE)
    with open(src, encoding='utf-8') as f:
        content = f.read()
    if PANEL_FILE in bpy.data.texts:
        bpy.data.texts.remove(bpy.data.texts[PANEL_FILE])
    t = bpy.data.texts.new(PANEL_FILE)
    t.write(content)
    t.use_module = True
    exec(content, {'__name__': '__main__'})
    return t


def main():
    global ctl
    ctl = build_controls()
    mat = build_material(MAT_NAME)
    t = inject_panel()
    bpy.context.view_layer.update()
    print('控制器:', CTRL_NAME, '| 属性:', {k: round(float(ctl[k]), 3) for k in PROPS})
    print('材质:', MAT_NAME, '| 节点', len(mat.node_tree.nodes), '连线', len(mat.node_tree.links))
    print('面板文本块:', t.name, '| use_module =', t.use_module,
          '| Panel 已注册 =', hasattr(bpy.types, 'RING_CTRL_PT_controls'))


main()