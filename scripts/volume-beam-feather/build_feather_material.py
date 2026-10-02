"""建 / 重建「羽化体积光锥」材质(含参数滑块与驱动器)

核心链(缺一不可):
    u      = MapRange(z → 0..1)
    轴向项  = MapRange(u, 0 … 尾部羽化 → 0..1, SMOOTHSTEP)   ★ 端点必须精确到 0
    径向项  = 1 − ρ^p

    fall = 轴向项 × 径向项

    Density           ← fall × 浓度
    Emission Strength ← fall × 亮度      ★ 少了这条羽化完全不生效

为什么轴向要用 "MapRange + SMOOTHSTEP" 而不是 ColorRamp:
    需求是「羽化距离可调」= 渐变终点可调。
    ColorRamp 的色标位置没有输入插槽,连不上 Value 节点;MapRange 的 From Max 是 socket。

几何常量 R / L 会被**烘焙**进材质,所以:
    **只有几何完全一致的锥体才能共用这一份材质**(不一致就换 MAT_NAME 再跑一次)

用法:
    python build_feather_material.py
    python bl.py build_feather_material.py <port>
"""
import bpy
import math
import traceback

# ============================ CONFIG ============================
SAMPLE_CONE = "射灯_光.001_光锥"      # 样板锥:用它实测 L / R
MAT_NAME = "光锥_羽化材质"

LEN_MIN_UNUSED = None                 # (旧参数,已废弃:线性衰减底值不是 0 会让远端变成平切硬边)
ANISOTROPY = 0.40                     # 轻微前向散射
EMISSION_COLOR = (1.0, 0.88, 0.68)    # 暖白
WITH_DRIVERS = True                   # 是否把四个参数挂成场景属性滑块

#           Value节点名   场景属性键    默认值  描述                                          min   max   soft_min soft_max
PARAMS = [
    ("羽化指数", "光锥羽化",     1.00, "径向羽化:越小越柔(0.1 极柔 / 4.0 亮芯集中)", 0.10, 8.0, 0.50, 4.0),
    ("尾部羽化", "光锥尾部羽化", 1.00, "轴向收尾渐变长度:越大→渐变越长、远端越柔(1.0 最柔)", 0.15, 1.0, 0.50, 1.0),
    ("浓度",     "光锥浓度",     0.80, "体积浓度(只影响吸收/散射,不影响自发光亮度)", 0.00, 3.0, 0.20, 1.5),
    ("亮度",     "光锥亮度",     2.50, "自发光亮度(主要亮度旋钮)",                 0.00, 20.0, 0.50, 8.0),
]
# ================================================================


def make_fresh_tree(mat):
    """清空材质节点树,只留输出节点。

    ★ 5.2 坑:对 nt.nodes 做 remove() 之后,之前持有的节点 Python 引用会失效
      (表现为 out.name 读出乱码 → UnicodeDecodeError,或 out.inputs["Volume"] 抛 KeyError,
       更阴的是链接静默丢失)。所以删完必须**重新遍历**取输出节点。
    """
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = None
    for n in nt.nodes:                      # ← 重新遍历,不用旧引用
        if n.type == 'OUTPUT_MATERIAL':
            out = n
            break
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")
    return nt, out


def main():
    cone = bpy.data.objects.get(SAMPLE_CONE)
    if cone is None:
        raise RuntimeError("样板锥 %s 不存在,先跑 add_cones_all_lights.py" % SAMPLE_CONE)

    vs = list(cone.data.vertices)
    zmax = max(v.co.z for v in vs)
    zmin = min(v.co.z for v in vs)
    L = zmax - zmin
    R = max(math.hypot(v.co.x, v.co.y) for v in vs)
    print("GEOM  L=%.4f  R=%.4f  z=[%.4f, %.4f]  verts=%d" % (L, R, zmin, zmax, len(vs)))

    # ---------- 场景属性(带 min/max 才会变滑块) ----------
    sc = bpy.context.scene
    if WITH_DRIVERS:
        for node_name, key, dv, desc, mn, mx, smn, smx in PARAMS:
            if key not in sc:
                sc[key] = dv
            try:
                sc.id_properties_ui(key).update(
                    description=desc, min=mn, max=mx, soft_min=smn, soft_max=smx)
            except Exception as e:
                print("   属性 UI 设置失败(不影响功能): %s" % e)
            print("PROP  %-12s = %-8s 范围[%s, %s] 软[%s, %s]" % (
                key, round(sc[key], 3), mn, mx, smn, smx))

    # ---------- 材质 ----------
    mat = bpy.data.materials.get(MAT_NAME) or bpy.data.materials.new(MAT_NAME)
    nt, out = make_fresh_tree(mat)

    def MN(op, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        if b is not None:
            n.inputs[1].default_value = b
        return n

    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.label = "体积"
    pv.inputs["Color"].default_value = EMISSION_COLOR + (1.0,)
    pv.inputs["Emission Color"].default_value = EMISSION_COLOR + (1.0,)
    try:
        pv.inputs["Anisotropy"].default_value = ANISOTROPY
    except Exception:
        pass

    vals = {}
    for node_name, key, dv, desc, mn, mx, smn, smx in PARAMS:
        vn = nt.nodes.new("ShaderNodeValue")
        vn.name = node_name
        vn.label = node_name
        vn.outputs[0].default_value = sc[key] if (WITH_DRIVERS and key in sc) else dv
        vals[node_name] = vn

    # ---------- 坐标 ----------
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])

    # ---------- 轴向(长度)衰减:归一化 + 平滑黑白渐变,端点精确到 0 ----------
    # ★ 不要用线性 MapRange 直接映到 0.05..1.0:底值不是 0 ⇒ 端面圆盘带残余亮度被几何硬切
    # ★ 不要用 ColorRamp 做"终点可调":色标 position 没有插槽,连不上 Value 节点;
    #   MapRange 的 From Max 是 socket,可以直接接滑块
    mru = nt.nodes.new("ShaderNodeMapRange")
    mru.inputs["From Min"].default_value = zmin
    mru.inputs["From Max"].default_value = zmax
    mru.inputs["To Min"].default_value = 0.0
    mru.inputs["To Max"].default_value = 1.0
    mru.clamp = True
    nt.links.new(sep.outputs["Z"], mru.inputs["Value"])

    mrl = nt.nodes.new("ShaderNodeMapRange")      # ← 黑白渐变本体
    mrl.label = "轴向收尾渐变(黑→白)"
    mrl.interpolation_type = 'SMOOTHSTEP'
    mrl.inputs["From Min"].default_value = 0.0
    mrl.inputs["To Min"].default_value = 0.0
    mrl.inputs["To Max"].default_value = 1.0
    mrl.clamp = True
    nt.links.new(mru.outputs["Result"], mrl.inputs["Value"])
    if WITH_DRIVERS:
        nt.links.new(vals["尾部羽化"].outputs[0], mrl.inputs["From Max"])   # ← 滑块进来
    else:
        mrl.inputs["From Max"].default_value = 1.0

    # ---------- 径向衰减 1 − ρ^p ----------
    # ρ = √(x²+y²) / radius(z),  radius(z) = R/2 − R·z/L
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], comb.inputs["X"])
    nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
    vl = nt.nodes.new("ShaderNodeVectorMath")
    vl.operation = 'LENGTH'
    nt.links.new(comb.outputs["Vector"], vl.inputs[0])

    mz = MN('MULTIPLY', -R / L)
    nt.links.new(sep.outputs["Z"], mz.inputs[0])
    ad = MN('ADD', R / 2.0)
    nt.links.new(mz.outputs[0], ad.inputs[0])
    den = MN('MAXIMUM', 0.0001)             # 防锥尖 0/0 出 NaN
    nt.links.new(ad.outputs[0], den.inputs[0])

    rho = MN('DIVIDE')
    nt.links.new(vl.outputs["Value"], rho.inputs[0])
    nt.links.new(den.outputs[0], rho.inputs[1])

    pw = MN('POWER')
    pw.use_clamp = True
    nt.links.new(rho.outputs[0], pw.inputs[0])
    nt.links.new(vals["羽化指数"].outputs[0], pw.inputs[1])      # 指数来自 Value 节点

    inv = MN('SUBTRACT')
    inv.inputs[0].default_value = 1.0
    inv.use_clamp = True
    nt.links.new(pw.outputs[0], inv.inputs[1])

    fall = MN('MULTIPLY')
    nt.links.new(mrl.outputs["Result"], fall.inputs[0])
    nt.links.new(inv.outputs[0], fall.inputs[1])

    # ---------- Density ← fall × 浓度 ----------
    dm = MN('MULTIPLY')
    nt.links.new(fall.outputs[0], dm.inputs[0])
    nt.links.new(vals["浓度"].outputs[0], dm.inputs[1])
    nt.links.new(dm.outputs[0], pv.inputs["Density"])

    # ---------- ★ Emission Strength ← fall × 亮度(羽化的关键) ----------
    em = MN('MULTIPLY')
    nt.links.new(fall.outputs[0], em.inputs[0])
    nt.links.new(vals["亮度"].outputs[0], em.inputs[1])
    nt.links.new(em.outputs[0], pv.inputs["Emission Strength"])

    nt.links.new(pv.outputs[0], out.inputs["Volume"])

    # ---------- 驱动器 ----------
    if WITH_DRIVERS:
        for node_name, key, dv, desc, mn, mx, smn, smx in PARAMS:
            sock = vals[node_name].outputs[0]
            try:
                sock.driver_remove("default_value")
            except Exception:
                pass
            fc = sock.driver_add("default_value")
            d = fc.driver
            # ★ AVERAGE = 单变量、无表达式 ⇒ 不需要"脚本自动执行"权限
            #   (SCRIPTED 型在非受信任打开的 .blend 里会静默不求值)
            d.type = 'AVERAGE'
            var = d.variables.new()
            var.name = "v"
            var.type = 'SINGLE_PROP'
            tgt = var.targets[0]
            tgt.id_type = 'SCENE'            # ★ 必须先设 id_type 再赋 id
            tgt.id = sc
            tgt.data_path = '["%s"]' % key
            print("DRIVER  %-8s → SCENE[\"%s\"]  valid=%s" % (node_name, key, d.is_valid))

    # ---------- 回读核验 ----------
    print("-" * 72)
    print("MAT   %s  nodes=%d links=%d" % (mat.name, len(nt.nodes), len(nt.links)))
    n_d = len([lk for lk in nt.links if lk.to_socket == pv.inputs["Density"]])
    n_e = len([lk for lk in nt.links if lk.to_socket == pv.inputs["Emission Strength"]])
    n_v = len([lk for lk in nt.links if lk.to_socket == out.inputs["Volume"]])
    n_f = len([lk for lk in nt.links if lk.to_socket == mrl.inputs["From Max"]]) \
        if WITH_DRIVERS else -1
    print("LINK  Density=%d  EmissionStrength=%d  Volume=%d  尾部羽化→FromMax=%d   (都要 = 1)" % (
        n_d, n_e, n_v, n_f))
    if n_e != 1:
        print("⚠️ Emission Strength 没接上 —— 羽化不会生效!检查 out 引用是否失效")
    print("轴向渐变 interpolation=%s  (必须是 SMOOTHSTEP)" % mrl.interpolation_type)

    sc.update_tag()
    for node_name in vals:
        print("SOCKET  %-8s = %.4f" % (node_name, vals[node_name].outputs[0].default_value))

    print("BUILD_FEATHER_MATERIAL_DONE")


try:
    main()
except Exception:
    print("EXCEPTION")
    print(traceback.format_exc())
