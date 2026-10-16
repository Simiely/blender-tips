# -*- coding: utf-8 -*-
# 渐变扫过材质 · UV 方向角 —— 幂等构建脚本(经 9877 桥执行)
# ===========================================================================
# 建成什么:
#   「平面」上一个黑白 ColorRamp 横扫材质;扫过方向 = 0-360° 的 UV 平面角度;
#   5 个旋钮全挂在空对象「渐变控制」上(材质可整体搬到别的网格体);
#   另一层静态水平渐变与它相乘合成(水平层全白 = 中性,等于没接);
#   两个 ColorRamp 上不挂任何驱动 —— 颜色留给用户手调。
#
# 主链: 坐标_纹理.<COORD_SOURCE> → 分离XY            (默认 UV)
#         t = (u·cosθ + v·sinθ) / (|cosθ| + |sinθ|)      ★ θ=0° ⇒ t ≡ u(与原版逐点相同)
#         t ×条数 → −相位 → FLOORED_MODULO 1 → ColorRamp_扫过 ─┐
#       分离XY.Y ×水平条数 → FLOORED_MODULO 1 → ColorRamp_水平 ─┤
#                            混合(RGBA, MULTIPLY, Factor=1.0) ─┴→ Principled(Base + Emission)
#
# 生成节点 21 / 连线 23 / 驱动 6。
#
# ⚠️ 本脚本【会清空并重建整棵节点树】—— 色标是你的手调成果,会被抹掉。
#    所以进门前先比对色标指纹,不是出厂的"3 档黑/白/黑"就拒绝执行。
#    确认要重建,把下面 FORCE_REBUILD 改成 True。
#    只想"修驱动器/旋钮"不想动结构,去跑 maintain_ctrl.py。
# ⚠️ 已存在且结构完全正确的材质会【跳过重建】,只对齐旋钮与驱动器(幂等)。
#    ★ 闸的门槛是"本次是否真的会重建":结构已正确 ⇒ 不重建 ⇒ 色标原样保留,不拦。
# ===========================================================================
import bpy

# ═══ 配置(换工程改这里) ═══
PLANE = "平面"                                  # 目标网格体
MAT_NAME = "渐变扫过材质"
CTRL_NAME = "渐变控制"
FORCE_REBUILD = False                           # True = 明知会抹掉手调色标也要重建
COORD_SOURCE = "UV"                             # ★ 坐标源:"UV"(默认) 或 "Generated"
#   "UV"        = 跟着网格体自己的「渲染活动 UV 层」走 ⇒ 材质换到别的网格体上,
#                 图案跟着那个网格的 UV 走(不要求包围盒一致)。**要求目标网格体有 UV 层**。
#   "Generated" = 按物体包围盒归一化的局部坐标,不看 UV。适合"不想让用户先展 UV"的场合。
#   ⚠ 对一块平整、UV 恰好是 0~1 正投影的网格体,这两者**渲染结果逐像素相同**
#     (实测最大差 = 1/255 的量化步,只有 1~3 个分量)。所以"换没换"**光看画面分不出来**,
#     要证它必须扰动 UV(见 verify_uv_source.py:临时互换 u/v,k=看朝向翻不翻)。
# ═════════════════════════

C, D, sc = bpy.context, bpy.data, bpy.context.scene
FPS = float(sc.render.fps)

BLACK = (0.0, 0.0, 0.0, 1.0)
WHITE = (1.0, 1.0, 1.0, 1.0)

# 度数→弧度用的分母常数(只在驱动表达式里拼字面量,避免依赖 math 命名空间)
_K = "(abs(cos(radians(ang))) + abs(sin(radians(ang))))"

# 节点规格: (类名, 名字, 位置)
NODE_SPEC = [
    ("ShaderNodeTexCoord",        "坐标_纹理",      (-2160,   40)),
    ("ShaderNodeSeparateXYZ",     "分离_XY",        (-1960,   40)),
    ("ShaderNodeValue",           "角度_余弦",      (-2160,  340)),
    ("ShaderNodeValue",           "角度_正弦",      (-2160,  160)),
    ("ShaderNodeMath",            "数学_方向X",     (-1760,  340)),
    ("ShaderNodeMath",            "数学_方向Y",     (-1760,  160)),
    ("ShaderNodeMath",            "数学_投影",      (-1560,  250)),
    ("ShaderNodeValue",           "条数",           (-1560, -120)),
    ("ShaderNodeValue",           "相位",           (-1560, -260)),
    ("ShaderNodeMath",            "数学_倍频",      (-1360,   40)),
    ("ShaderNodeMath",            "数学_相移",      (-1160,   40)),
    ("ShaderNodeMath",            "数学_循环",      ( -960,   40)),
    ("ShaderNodeValToRGB",        "颜色渐变_扫过",   ( -760,   40)),
    ("ShaderNodeValue",           "发光强度",        ( -960, -260)),
    ("ShaderNodeValue",           "水平条数",        (-1560, -430)),
    ("ShaderNodeMath",            "数学_倍频Y",     (-1360, -430)),
    ("ShaderNodeMath",            "数学_循环Y",     (-1160, -430)),
    ("ShaderNodeValToRGB",        "颜色渐变_水平",   ( -760, -430)),
    ("ShaderNodeMix",             "混合_水平x扫过",  ( -500,   40)),
    ("ShaderNodeBsdfPrincipled",  "原理化BSDF",     ( -220,   40)),
    ("ShaderNodeOutputMaterial",  "材质输出",       (   80,   40)),
]

# 连线规格(逐条核验用): (源节点, 源插座, 目标节点, 目标插座)
EXPECT_PAIRS = [
    ("坐标_纹理", COORD_SOURCE, "分离_XY", "Vector"),
    ("分离_XY", "X", "数学_方向X", "Value"),
    ("角度_余弦", "Value", "数学_方向X", "Value"),
    ("分离_XY", "Y", "数学_方向Y", "Value"),
    ("角度_正弦", "Value", "数学_方向Y", "Value"),
    ("数学_方向X", "Value", "数学_投影", "Value"),
    ("数学_方向Y", "Value", "数学_投影", "Value"),
    ("数学_投影", "Value", "数学_倍频", "Value"),
    ("条数", "Value", "数学_倍频", "Value"),
    ("数学_倍频", "Value", "数学_相移", "Value"),
    ("相位", "Value", "数学_相移", "Value"),
    ("数学_相移", "Value", "数学_循环", "Value"),
    ("数学_循环", "Value", "颜色渐变_扫过", "Factor"),
    ("分离_XY", "Y", "数学_倍频Y", "Value"),
    ("水平条数", "Value", "数学_倍频Y", "Value"),
    ("数学_倍频Y", "Value", "数学_循环Y", "Value"),
    ("数学_循环Y", "Value", "颜色渐变_水平", "Factor"),
    ("颜色渐变_扫过", "Color", "混合_水平x扫过", "A"),
    ("颜色渐变_水平", "Color", "混合_水平x扫过", "B"),
    ("混合_水平x扫过", "Result", "原理化BSDF", "Base Color"),
    ("混合_水平x扫过", "Result", "原理化BSDF", "Emission Color"),
    ("发光强度", "Value", "原理化BSDF", "Emission Strength"),
    ("原理化BSDF", "BSDF", "材质输出", "Surface"),
]

# 旋钮: (键名, 默认值, 类型, UI 元数据)
KNOBS = [
    ("扫过速度", 0.2, float, dict(min=0.0, soft_max=5.0,
        description="扫过速度(周期/秒)。0 = 静止;负值 = 反向")),
    ("扫过角度", 0.0, float, dict(min=0.0, soft_min=0.0, soft_max=360.0,
        description="扫过方向(UV 平面角度,单位度)。0° = 沿 +U(即原来的 1);"
                    "90° = 沿 +V;180° = 反向;任意中间角 = 斜扫")),
    ("扫过条数", 1.0, float, dict(min=1.0, soft_max=20.0,
        description="扫过方向上同时存在的渐变条数")),
    ("水平条数", 1.0, float, dict(min=1.0, soft_max=20.0,
        description="静态水平渐变(沿 V)的条数;水平层全白时无影响")),
    ("发光强度", 2.0, float, dict(min=0.0, soft_max=20.0,
        description="合成后的整体发光强度")),
]

# 驱动器: (节点名, 类型, [(属性键, 变量名)], 表达式)
DRIVER_SPEC = [
    ("相位", "SCRIPTED", [("扫过速度", "spd")], "spd * (frame - 1) / %f" % FPS),
    ("角度_余弦", "SCRIPTED", [("扫过角度", "ang")], "cos(radians(ang)) / %s" % _K),
    ("角度_正弦", "SCRIPTED", [("扫过角度", "ang")], "sin(radians(ang)) / %s" % _K),
    ("条数", "AVERAGE", [("扫过条数", "v")], None),
    ("水平条数", "AVERAGE", [("水平条数", "v")], None),
    ("发光强度", "AVERAGE", [("发光强度", "v")], None),
]

EXPECT_SIG = [(0.0, (0.0, 0.0, 0.0)), (0.5, (1.0, 1.0, 1.0)), (1.0, (0.0, 0.0, 0.0))]
RAMP_NODES = ("颜色渐变_扫过", "颜色渐变_水平")


# ---------------------------------------------------------------- 小工具
def sock(node, *names):
    for nm in names:
        s = node.inputs.get(nm)
        if s is not None:
            return s
    raise KeyError("%s 里找不到插座 %r" % (node.name, names))


def find_sock(sockets, name, stype):
    for s in sockets:
        if s.name == name and s.type == stype:
            return s
    return None


def ramp_sig(node):
    return [(round(e.position, 3), tuple(round(c, 3) for c in e.color[:3]))
            for e in node.color_ramp.elements]


def has_link(nt, a, sa, b, sb):
    for l in nt.links:
        if (l.from_node.name == a and l.from_socket.name == sa
                and l.to_node.name == b and l.to_socket.name == sb):
            return True
    return False


def force_refresh(objs=()):
    """★ 改完自定义属性必须这样标脏,否则节点树上的驱动器不重算,
       读到的 is_valid 与插座值全是陈旧值(只 view_layer.update() 不够)。"""
    for o in objs:
        o.update_tag()
    C.evaluated_depsgraph_get().update()


# ---------------------------------------------------------------- 0. 基线
ob = D.objects.get(PLANE)
assert ob is not None and ob.type == 'MESH', "找不到网格体 %r" % PLANE
assert COORD_SOURCE in ("UV", "Generated"), "COORD_SOURCE 只能是 'UV' / 'Generated'"
_uvl = [l.name for l in ob.data.uv_layers]
print("BASELINE 目标=%r 现有材质槽=%d  空对象已存在=%s  坐标源=%s  UV 层=%r"
      % (ob.name, len(ob.material_slots), CTRL_NAME in D.objects, COORD_SOURCE, _uvl))
if COORD_SOURCE == "UV":
    # ★ 没有 UV 层时 坐标_纹理.UV 会给出全 0 ⇒ 图案整个塌成一种颜色(不是报错,是静默坏掉)
    assert len(_uvl) > 0, (
        "%r 没有 UV 层,而 COORD_SOURCE='UV' ⇒ 接 UV 会得到全 0、图案会坏。\n"
        "  先给网格体展 UV;或把 COORD_SOURCE 改成 'Generated'(按包围盒归一化,不看 UV)。" % PLANE)
    print("        活动 UV 层 = %r" % ob.data.uv_layers.active.name)

# ---------------------------------------------------------------- 1. 安全闸 + 幂等判定
# ★ 必须在任何破坏性操作之前 —— 而且这一节只【读】不写
mat = D.materials.get(MAT_NAME)
nt = mat.node_tree if (mat is not None and mat.use_nodes) else None
edited = {}
already_ok = False
if nt is not None:
    for nm in RAMP_NODES:
        n = nt.nodes.get(nm)
        if n is not None and ramp_sig(n) != EXPECT_SIG:
            edited[nm] = ramp_sig(n)
    already_ok = (len(nt.nodes) == len(NODE_SPEC) and len(nt.links) == len(EXPECT_PAIRS)
                  and all(has_link(nt, a, sa, b, sb) for a, sa, b, sb in EXPECT_PAIRS))

# ★ 闸的门槛是「本次是否真的会重建」,不是「色标是否被改过」。
#   结构已经正确 ⇒ 走跳过分支 ⇒ 根本没有重建 ⇒ 也就没有理由拦(否则幂等复跑会被误伤)。
will_rebuild = FORCE_REBUILD or not already_ok
if edited and will_rebuild and not FORCE_REBUILD:
    raise RuntimeError(
        "安全闸中止,未修改任何数据。以下色标已被手工改过,重建会抹掉它们: %r。\n"
        "  只想修驱动器/旋钮 ⇒ 跑 maintain_ctrl.py(它不碰色标)\n"
        "  确实要重建     ⇒ 把 build_sweep_angle.py 顶部的 FORCE_REBUILD 改成 True"
        % (edited,))
if edited and will_rebuild:
    print("  ⚠ FORCE_REBUILD=True:将抹掉被改过的色标 %r" % list(edited))
if edited and not will_rebuild:
    print("  色标已被手工改过(节点 %r)—— 但结构已正确、本次不重建,色标原样保留" % list(edited))

# ---------------------------------------------------------------- 2. 锚点空对象
ctrl = D.objects.get(CTRL_NAME)
if ctrl is None:
    ctrl = D.objects.new(CTRL_NAME, None)          # None ⇒ EMPTY,不动用 operator
    sc.collection.objects.link(ctrl)
    ctrl.empty_display_type = 'CUBE'
    ctrl.empty_display_size = 1.6
    ctrl.location = (0.0, 0.0, 2.6)
    ctrl.hide_render = True
    print("  新建控制器空对象 %r" % CTRL_NAME)
else:
    print("  复用已有控制器空对象 %r" % CTRL_NAME)
assert ctrl.type == 'EMPTY', "%r 不是空对象" % CTRL_NAME

FIXED = {"扫过速度": 0.2, "扫过角度": 0.0, "扫过条数": 1.0,
         "水平条数": 1.0, "发光强度": 2.0}
migrated = []
for name, val, typ, meta in KNOBS:
    if name not in ctrl:
        # 允许先把值写在目标对象上,再迁移过来(保住用户已经调过的值)
        ctrl[name] = typ(ob[name]) if name in ob else typ(val)
        if name in ob:
            migrated.append(name)
    try:
        ctrl.id_properties_ui(name).update(**meta)
    except Exception as e:
        print("  (UI 元数据设置失败 %s: %r)" % (name, e))
for name in migrated:
    del ob[name]
print("  旋钮=%r  已从目标对象迁入=%r" % ({k: ctrl[k] for k, _, _, _ in KNOBS}, migrated))

# ---------------------------------------------------------------- 3. 材质与节点
if mat is None:
    mat = D.materials.new(MAT_NAME)
mat.use_fake_user = True
mat.use_nodes = True
mat.diffuse_color = WHITE
nt = mat.node_tree

# already_ok 已在第 1 节算好(那一节只读不写,所以安全闸和跳过分支持同一个判定)

if already_ok and not FORCE_REBUILD:
    print("  结构已是目标状态(节点 %d / 连线 %d),跳过重建" % (len(nt.nodes), len(nt.links)))
else:
    if nt.animation_data:
        nt.animation_data_clear()          # ★ 清掉残留旧驱动,避免节点名复用后错绑
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    assert len(nt.nodes) == 0, "节点未清干净: %d" % len(nt.nodes)

    for cls, name, loc in NODE_SPEC:
        n = nt.nodes.new(cls)
        n.name = name
        n.label = name
        n.location = loc

    def N(name):
        return nt.nodes[name]

    # 运算类型
    N("数学_方向X").operation = 'MULTIPLY'
    N("数学_方向Y").operation = 'MULTIPLY'
    N("数学_投影").operation = 'ADD'
    N("数学_倍频").operation = 'MULTIPLY'
    N("数学_相移").operation = 'SUBTRACT'
    N("数学_循环").operation = 'FLOORED_MODULO'      # ★ 不能用 MODULO(负值会被裁剪)
    N("数学_倍频Y").operation = 'MULTIPLY'
    N("数学_循环Y").operation = 'FLOORED_MODULO'
    for nm in ("数学_方向X", "数学_方向Y", "数学_投影", "数学_倍频", "数学_相移",
               "数学_循环", "数学_倍频Y", "数学_循环Y"):
        N(nm).use_clamp = False

    # 混合节点(优先 ShaderNodeMix(RGBA);万一不可用退回老的 MixRGB)
    n_mix = N("混合_水平x扫过")
    try:
        n_mix.data_type = 'RGBA'
        n_mix.blend_type = 'MULTIPLY'
        mx_fac = find_sock(n_mix.inputs, "Factor", "VALUE")
        mx_a = find_sock(n_mix.inputs, "A", "RGBA")
        mx_b = find_sock(n_mix.inputs, "B", "RGBA")
        mx_out = find_sock(n_mix.outputs, "Result", "RGBA")
        if None in (mx_fac, mx_a, mx_b, mx_out):
            raise RuntimeError("ShaderNodeMix 的 RGBA 插座没找齐")
    except Exception as e:
        print("  (ShaderNodeMix 不可用: %r —— 退回 ShaderNodeMixRGB)" % e)
        nt.nodes.remove(n_mix)
        n_mix = nt.nodes.new("ShaderNodeMixRGB")
        n_mix.name = n_mix.label = "混合_水平x扫过"
        n_mix.location = (-500, 40)
        n_mix.blend_type = 'MULTIPLY'
        mx_fac = n_mix.inputs["Fac"]
        mx_a, mx_b = n_mix.inputs["Color1"], n_mix.inputs["Color2"]
        mx_out = n_mix.outputs["Color"]
    print("  MIX_NODE=%s" % n_mix.bl_idname)
    mx_fac.default_value = 1.0      # ★ 1.0 = 纯相乘;Fac=0 会退化成"只取 A"

    # 色标:出厂 3 档黑/白/黑,EASE 插值
    for nm in RAMP_NODES:
        cr = N(nm).color_ramp
        cr.interpolation = 'EASE'
        while len(cr.elements) < 2:
            cr.elements.new(1.0)                 # ColorRamp 元素数下限是 2
        if len(cr.elements) < 3:
            cr.elements.new(0.5)
        for e, (pos, col) in zip(cr.elements, ((0.0, BLACK), (0.5, WHITE), (1.0, BLACK))):
            e.position, e.color = pos, col
        assert ramp_sig(N(nm)) == EXPECT_SIG, "%s 色标写入不符" % nm

    # 接线
    L = nt.links.new
    L(N("坐标_纹理").outputs[COORD_SOURCE], N("分离_XY").inputs[0])
    L(N("分离_XY").outputs["X"], N("数学_方向X").inputs[0])
    L(N("角度_余弦").outputs[0], N("数学_方向X").inputs[1])
    L(N("分离_XY").outputs["Y"], N("数学_方向Y").inputs[0])
    L(N("角度_正弦").outputs[0], N("数学_方向Y").inputs[1])
    L(N("数学_方向X").outputs[0], N("数学_投影").inputs[0])
    L(N("数学_方向Y").outputs[0], N("数学_投影").inputs[1])
    L(N("数学_投影").outputs[0], N("数学_倍频").inputs[0])
    L(N("条数").outputs[0], N("数学_倍频").inputs[1])
    L(N("数学_倍频").outputs[0], N("数学_相移").inputs[0])
    L(N("相位").outputs[0], N("数学_相移").inputs[1])
    L(N("数学_相移").outputs[0], N("数学_循环").inputs[0])
    N("数学_循环").inputs[1].default_value = 1.0
    L(N("数学_循环").outputs[0], N("颜色渐变_扫过").inputs[0])
    L(N("分离_XY").outputs["Y"], N("数学_倍频Y").inputs[0])
    L(N("水平条数").outputs[0], N("数学_倍频Y").inputs[1])
    L(N("数学_倍频Y").outputs[0], N("数学_循环Y").inputs[0])
    N("数学_循环Y").inputs[1].default_value = 1.0
    L(N("数学_循环Y").outputs[0], N("颜色渐变_水平").inputs[0])
    L(N("颜色渐变_扫过").outputs["Color"], mx_a)
    L(N("颜色渐变_水平").outputs["Color"], mx_b)
    L(mx_out, sock(N("原理化BSDF"), "Base Color"))
    L(mx_out, sock(N("原理化BSDF"), "Emission Color", "Emission"))
    L(N("发光强度").outputs[0], sock(N("原理化BSDF"), "Emission Strength"))
    L(N("原理化BSDF").outputs[0], N("材质输出").inputs["Surface"])

# ---------------------------------------------------------------- 4. 驱动器
for node_name, dtype, vars_, expr in DRIVER_SPEC:
    n = nt.nodes.get(node_name)
    if n is None or not len(n.outputs):
        print("  ⚠ 找不到节点 %r,驱动器跳过" % node_name)
        continue
    ad = nt.animation_data
    path = 'nodes["%s"].outputs[0].default_value' % node_name
    old = ad.drivers.find(path) if ad else None
    if old is not None:
        ad.drivers.remove(old)                 # ★ 原子重建:整条删掉再加
    drv = n.outputs[0].driver_add("default_value").driver
    drv.type = dtype
    for v in list(drv.variables):
        drv.variables.remove(v)
    for prop, var_name in vars_:               # ★ 顺序: (属性键, 变量名),反了会造悬空变量
        var = drv.variables.new()
        var.name = var_name
        var.type = 'SINGLE_PROP'
        t = var.targets[0]
        t.id_type = 'OBJECT'                   # ★ 必须先 id_type 再 id
        t.id = ctrl                             # ★ 驱动源 = 空对象
        t.data_path = '["%s"]' % prop
    if dtype == 'SCRIPTED':
        drv.expression = expr

# ---------------------------------------------------------------- 5. 挂到目标网格体
if ob.material_slots:
    keep = ob.material_slots[0].material
    ob.material_slots[0].material = mat
    if keep is not None and keep is not mat:
        keep.use_fake_user = True              # 旧材质留着,便于回退
        print("  原 0 号槽材质 %r 保留(use_fake_user=True)" % keep.name)
else:
    ob.data.materials.append(mat)
assert ob.material_slots and ob.material_slots[0].material is mat

# ---------------------------------------------------------------- 6. 交付姿态
# ★ 物体属性面板只显示【活动对象】—— 参数挂在这个空对象上,就必须把它设成活动对象
for o in C.view_layer.objects:
    o.select_set(False)
ctrl.select_set(True)
C.view_layer.objects.active = ctrl
force_refresh((ctrl,))

# ---------------------------------------------------------------- 7. 自检
print("MAT=%r  NODES=%d (期望 %d)  LINKS=%d (期望 %d)"
      % (mat.name, len(nt.nodes), len(NODE_SPEC), len(nt.links), len(EXPECT_PAIRS)))
missing = [t for t in EXPECT_PAIRS if not has_link(nt, *t)]
print("缺线=%r" % missing)
assert not missing, "有连线没建上"

# ★ 坐标源:只能有一路在连(否则"另一路"还会偷偷参与,而且看不出是哪一路在起作用)
_other = "Generated" if COORD_SOURCE == "UV" else "UV"
assert not has_link(nt, "坐标_纹理", _other, "分离_XY", "Vector"), \
    "坐标_纹理.%s 还连着 分离_XY.Vector —— 只允许一路" % _other
print("坐标源 = 坐标_纹理.%s(另一路 %s 未连)" % (COORD_SOURCE, _other))

for nm in ("数学_循环", "数学_循环Y"):
    assert nt.nodes[nm].operation == 'FLOORED_MODULO', "%s 不是 FLOORED_MODULO" % nm
    assert abs(nt.nodes[nm].inputs[1].default_value - 1.0) < 1e-6, "%s 取模基准不是 1.0" % nm

drs = list(nt.animation_data.drivers) if nt.animation_data else []
targets = sorted({(t.id.name if t.id else None) for d in drs
                  for v in d.driver.variables for t in v.targets})
print("DRIVERS=%d (期望 %d)  INVALID=%d  TARGETS=%r"
      % (len(drs), len(DRIVER_SPEC), sum(1 for d in drs if not d.driver.is_valid), targets))
assert len(drs) == len(DRIVER_SPEC), "驱动器数不对"
assert targets == [CTRL_NAME], "驱动器源不是唯一地指向 %r: %r" % (CTRL_NAME, targets)
print("REFERENCES_PLANE=%s (必须 False)" % (PLANE in targets))

# 数值核对:改一个旋钮看跟不跟(行为法,不看 is_valid)
_f0 = sc.frame_current
ctrl["扫过角度"] = 45.0
force_refresh((ctrl,))
ev = D.materials[mat.name].evaluated_get(C.evaluated_depsgraph_get()).node_tree
c45 = ev.nodes["角度_余弦"].outputs[0].default_value
s45 = ev.nodes["角度_正弦"].outputs[0].default_value
ctrl["扫过角度"] = 0.0
force_refresh((ctrl,))
ev = D.materials[mat.name].evaluated_get(C.evaluated_depsgraph_get()).node_tree
c0 = ev.nodes["角度_余弦"].outputs[0].default_value
print("角度 45° -> 余弦=%.5f 正弦=%.5f (期望 0.5 / 0.5)" % (c45, s45))
print("角度  0° -> 余弦=%.5f (期望 1.0)" % c0)
assert abs(c45 - 0.5) < 1e-4 and abs(s45 - 0.5) < 1e-4 and abs(c0 - 1.0) < 1e-4, "角度驱动没跟随"
sc.frame_set(_f0)
print("ACTIVE=%r" % (C.view_layer.objects.active.name if C.view_layer.objects.active else None))
print("旋钮 keys=%r" % list(ctrl.keys()))
print("BUILD_OK")
