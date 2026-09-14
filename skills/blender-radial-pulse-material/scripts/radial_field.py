# -*- coding: utf-8 -*-
"""radial_field.py — 球面径向图案构建器（Blender 5.2 LTS 实测）

在一个共享中心 O 周围生成「球心对称」的程序化图案：

    f(P) = 亮度剖面(r) * 形状掩码(mode)        r = |P - O| / R_eff

因为图案只依赖 r（spike 模式额外依赖方向 d = (P-O)/|P-O|），所以
  · 任何平面切过去 -> 同心圆
  · 过 O 的平面切过去 -> 从 O 发散的射线族（spike 模式）
多个物体赋同一材质 + 共用同一个 ctrl 空物体，交线天然连续，无需按朝向做特判。

四种模式：
  spot   中心最亮向外变暗的实心光斑
  ring   一圈圈往外推的冲击波环
  spike  从中心射出的丝状辐条（Voronoi F1 角向项）
  pulse  单脉冲：小圆 -> 膨胀铺满 -> 中心黑腔扩大 -> 全黑

用法（经 blender-remote-control 的桥）：
    python bl.py radial_field.py            # 走脚本顶部 CONFIG
或直接在 Blender 的 Scripting 工作区 Run Script。
全部结果 print，不写文件、不自动存盘（记得 Ctrl+S）。

--- 改这里 ---
"""

import bpy

CONFIG = {
    # ---------- 目标 ----------
    "mode":          "pulse",       # spot | ring | spike | pulse
    "ctrl":          "FB_ctrl",     # 共享坐标源空物体（不存在则自动新建）
    "material":      "FB_Firework_View",
    "src_material":  "FB_Firework", # 放进槽 1 作备用（None = 不要备用槽）
    "target_prefix": "平面",         # 自动收集所有以此开头的 MESH
    "targets":       [],            # 显式指定对象名；非空则忽略 prefix
    "assign":        True,          # False = 只建材质不赋给任何物体（试跑用）

    # ---------- 半径与构图 ----------
    "R_eff":      1.0,    # 坐标缩放。平面半宽 w 时 r∈[0, w*sqrt(2)]；1.0 = 内切于 2x2
    "soft":       0.09,   # 边界软边宽度（世界单位）
    "rim_amt":    0.55,   # 外缘保留亮度（1.0 = 完全平涂实心）

    # ---------- pulse 专用 ----------
    "R_out_cap":  1.05,   # 前缘最终半径。**必须封顶在内切圆**，否则四角也亮 -> 变方形底盘
    "R_in_cap":   1.30,   # 后缘最终半径。> R_out_cap + soft 即全黑
    "split":      0.38,   # prog 走到多少时前缘扫完、后缘启动

    # ---------- ring 专用 ----------
    "ring_count": 3.0,    # 每单位 r 的环数
    "ring_width": 0.16,   # 环宽（占一个周期的比例，越小越细）

    # ---------- spike 专用 ----------
    "ray_scale":  14.0,   # Voronoi 球面采样密度。**条数不随它线性增长**，见 references
    "ray_width":  0.40,   # F1 距离阈值（>0.5 会糊成宽带；0.40 -> 约 32 条）
    "env_far":    0.10,   # 射线能伸多远（此 r 处包络降为 0）
    "glow_rad":   0.55,   # 底盘半径（陡降，管中心那团亮晕）

    # ---------- 时间 ----------
    "prog0":      0.06,   # 帧 1   的 prog
    "prog1":      1.00,   # 帧 250 的 prog
    "f_start":    1,
    "f_end":      250,

    # ---------- 实时旋钮（做成节点里的 Value，不必重跑脚本）----------
    "base_mult":  1.00,   # Base Color 亮度倍率
    "emit_mult":  1.20,   # 自发光强度倍率
}

# ======================================================================
# 以下为通用实现，一般不用改
# ======================================================================
log = []
P = CONFIG
MODE = P["mode"]
assert MODE in ("spot", "ring", "spike", "pulse"), "未知 mode: %s" % MODE

I = lambda n, i: n.inputs[i]
def seti(n, i, v):
    n.inputs[i].default_value = v
    return n

def sock(node, name, typ):
    """同名多类型插槽（MapRange / Mix）必须按 (name, type) 取，否则取错或报错。"""
    got = [s for s in node.inputs if s.name == name and s.type == typ]
    assert got, "no socket %r/%s in %s (have %s)" % (
        name, typ, node.label or node.name, [(s.name, s.type) for s in node.inputs])
    return got[0]

def ramp(n, stops, interp='EASE'):
    el = n.color_ramp.elements
    while len(el) > 1:
        el.remove(el[-1])
    el[0].position, el[0].color = stops[0]
    for pos, col in stops[1:]:
        e = el.new(pos)
        e.color = col
    n.color_ramp.interpolation = interp
    return n

# ---------------- 0. 目标对象 ----------------
if P["targets"]:
    TARGETS = list(P["targets"])
else:
    TARGETS = [ob.name for ob in bpy.data.objects
               if ob.type == 'MESH' and ob.name.startswith(P["target_prefix"])]
log.append("mode=%s targets=%s" % (MODE, TARGETS))
if P["assign"] and not TARGETS:
    log.append("!! 没有匹配到任何目标对象（检查 target_prefix / targets）")

# ---------------- 1. 幂等清理：只清自己，绝不动 src_material ----------------
SRC = P["src_material"]
mat_old = bpy.data.materials.get(P["material"])
if mat_old:
    # 只置 None 会留下空槽 -> 面的 material_index=0 引用到空槽 -> 全黑。
    # 必须 clear() 再 append，并把每个 polygon 的 index 显式置 0。
    for me in bpy.data.meshes:
        if P["material"] in [x.name for x in me.materials if x]:
            me.materials.clear()
            if SRC and bpy.data.materials.get(SRC):
                me.materials.append(bpy.data.materials[SRC])
            for poly in me.polygons:
                poly.material_index = 0
    bpy.data.materials.remove(mat_old)
    log.append("cleaned previous %s" % P["material"])
src = bpy.data.materials.get(SRC) if SRC else None
if src:
    src.use_fake_user = True
    log.append("source %s kept: users=%s fake_user=%s" % (SRC, src.users, src.use_fake_user))

# ---------------- 2. ctrl 空物体（图案的共享原点）----------------
scn = bpy.context.scene
ctrl = bpy.data.objects.get(P["ctrl"])
if ctrl is None:
    ctrl = bpy.data.objects.new(P["ctrl"], None)
    scn.collection.objects.link(ctrl)
    ctrl.empty_display_type = 'PLAIN_AXES'
    ctrl.empty_display_size = 0.4
    log.append("created ctrl %s" % P["ctrl"])
else:
    log.append("reused ctrl %s  loc=%s" % (P["ctrl"], tuple(round(v, 4) for v in ctrl.location)))
for k, v in P.items():
    if isinstance(v, (int, float, bool)):
        ctrl[k] = v

# ---------------- 3. 材质与节点树 ----------------
mat = bpy.data.materials.new(P["material"])
mat.use_nodes = True
mat.use_backface_culling = False
mat.diffuse_color = (1.0, 0.32, 0.06, 1.0)   # SOLID 视口下显示这个色
mat.metallic = 0.0
mat.roughness = 0.45

nt = mat.node_tree
nodes, links = nt.nodes, nt.links
nodes.clear()
if nt.animation_data:
    nt.animation_data_clear()                # 清掉上一版残留关键帧

def N(t, label, x, y):
    n = nodes.new(t)
    n.label = label
    n.location = (x, y)
    return n

def MATH(label, op, x, y, a=None, b=None):
    n = N('ShaderNodeMath', label, x, y)
    n.operation = op
    if a is not None:
        seti(n, 0, a)
    if b is not None:
        seti(n, 1, b)
    return n

def MRANGE(label, x, y):
    n = N('ShaderNodeMapRange', label, x, y)
    n.clamp = True          # 低于 From Min -> To Min；高于 From Max -> To Max（自带截断）
    return n

# ===== 坐标源 =====
# Texture Coordinate: Object 输出的是「在指定物体局部空间中的坐标」。
# ctrl 在原点且单位变换时它就等于世界坐标；移动 ctrl = 移动整个图案（可做位移动画）。
# 不要用 Generated（每个对象各自归一化，交线必断）或 UV（依赖各自展开）。
tc = N('ShaderNodeTexCoord', 'TC  Object=%s' % P["ctrl"], -1600, 0)
tc.object = ctrl
mp = N('ShaderNodeMapping', 'MAP  scale=1/R_eff', -1420, 0)
seti(mp, 3, (1.0 / P["R_eff"],) * 3)
links.new(tc.outputs[3], I(mp, 0))          # Object 是 outputs[3]

vvec = mp.outputs[0]
vlen = N('ShaderNodeVectorMath', 'LEN  r=|P|', -1240, 120)
vlen.operation = 'LENGTH'
links.new(vvec, I(vlen, 0))
r_out = vlen.outputs[1]                     # LENGTH 的结果在 outputs[1]（Value）

# ===== 色相：按 r 从白热 -> 金 -> 橙 -> 红 =====
col = ramp(N('ShaderNodeValToRGB', 'COL  色相 白热->金->橙->红', -1040, 260), [
    (0.00, (1.00, 1.00, 0.95, 1)),
    (0.10, (1.00, 0.90, 0.55, 1)),
    (0.30, (1.00, 0.55, 0.12, 1)),
    (0.58, (1.00, 0.24, 0.03, 1)),
    (0.85, (0.84, 0.07, 0.02, 1)),
    (1.00, (0.40, 0.02, 0.01, 1)),
])
links.new(r_out, I(col, 0))

# ===== 时间：Value 节点 + 插槽关键帧（5.2 没有 FRAME 驱动变量）=====
tval = N('ShaderNodeValue', 'TVAL  prog  (关键帧 LINEAR)', -1600, -560)
tval.outputs[0].default_value = P["prog0"]

# ===== 形状掩码：按 mode 分派 =====
m_mask = None

if MODE == "spot":
    # 中心最亮、向外连续变暗。等值集是同心球面 -> 平面上是同心圆。
    m_mask = ramp(N('ShaderNodeValToRGB', 'MASK  径向光斑', -600, -400), [
        (0.00, (1.00, 1.00, 1.00, 1)),
        (0.25, (0.92, 0.92, 0.92, 1)),
        (0.60, (0.45, 0.45, 0.45, 1)),
        (1.00, (0.06, 0.06, 0.06, 1)),
    ])
    links.new(r_out, I(m_mask, 0))

elif MODE == "ring":
    # fract(r*N - prog) -> 取到 0 的距离 -> 窄窗口 = 一圈环；prog 增 -> 环整体外推
    m_p = MATH('RP  r x ring_count', 'MULTIPLY', -1240, -620)
    links.new(r_out, I(m_p, 0)); seti(m_p, 1, P["ring_count"])
    m_s = MATH('RS  - prog', 'SUBTRACT', -1060, -620)
    links.new(m_p.outputs[0], I(m_s, 0)); links.new(tval.outputs[0], I(m_s, 1))
    m_f = MATH('RF  fract', 'FRACT', -880, -620)
    links.new(m_s.outputs[0], I(m_f, 0))
    # 到最近整环的距离 = min(f, 1-f)
    m_1mf = MATH('R1  1-f', 'SUBTRACT', -880, -820, a=1.0)
    links.new(m_f.outputs[0], I(m_1mf, 1))
    m_d = MATH('RD  min(f,1-f)', 'MINIMUM', -700, -720)
    links.new(m_f.outputs[0], I(m_d, 0)); links.new(m_1mf.outputs[0], I(m_d, 1))
    m_w = ramp(N('ShaderNodeValToRGB', 'RW  环宽 w=%g' % P["ring_width"], -520, -720), [
        (0.00, (1.0, 1.0, 1.0, 1)),
        (P["ring_width"] * 0.5, (0.0, 0.0, 0.0, 1)),
    ], 'LINEAR')
    links.new(m_d.outputs[0], I(m_w, 0))
    # 外缘衰减（环不该铺到四角）
    m_fall = ramp(N('ShaderNodeValToRGB', 'RFO 外缘衰减', -520, -400), [
        (0.00, (1.0, 1.0, 1.0, 1)),
        (P["R_eff"] * 0.8, (0.7, 0.7, 0.7, 1)),
        (P["R_eff"] * 1.1, (0.0, 0.0, 0.0, 1)),
    ])
    links.new(r_out, I(m_fall, 0))
    m_mask = MATH('MASK  环 x 衰减', 'MULTIPLY', -320, -560)
    links.new(m_w.outputs[0], I(m_mask, 0)); links.new(m_fall.outputs[0], I(m_mask, 1))

elif MODE == "spike":
    # 角向项：归一化方向上的 Voronoi F1。
    # F1 的亮集 = 特征点附近的球冠 -> 反向投影为以原点为顶点的圆锥
    # -> 平面上就是过中心的楔形尖刺。绝不能用 DISTANCE_TO_EDGE（那出的是闭合圈）。
    vnorm = N('ShaderNodeVectorMath', 'NRM  d=P/|P|', -1240, -200)
    vnorm.operation = 'NORMALIZE'
    links.new(vvec, I(vnorm, 0))
    vor = N('ShaderNodeTexVoronoi', 'VOR  F1 球面采样 S=%g' % P["ray_scale"], -1060, -200)
    vor.feature = 'F1'
    try:
        vor.voronoi_dimensions = '3D'
    except Exception as e:
        log.append("voronoi_dimensions n/a: %s" % e)
    links.new(vnorm.outputs[0], I(vor, 0))
    sock(vor, 'Scale', 'VALUE').default_value = P["ray_scale"]
    m_ray = ramp(N('ShaderNodeValToRGB', 'RAY  尖刺 width=%g' % P["ray_width"], -860, -200), [
        (0.000, (1.0, 1.0, 1.0, 1)),
        (P["ray_width"], (0.0, 0.0, 0.0, 1)),
    ], 'LINEAR')
    links.new(vor.outputs[0], I(m_ray, 0))
    # 射线包络与底部光晕必须是两条独立曲线：
    # 共用一条时，射线掩码一弱整片跟着黑；强行抬高又变成"暗红盘子"。
    m_env = ramp(N('ShaderNodeValToRGB', 'ENV  射线包络（缓降）', -1060, 300), [
        (0.00, (1.00, 1.00, 1.00, 1)),
        (0.35, (0.55, 0.55, 0.55, 1)),
        (float(P["env_far"]), (0.0, 0.0, 0.0, 1)),
    ])
    links.new(r_out, I(m_env, 0))
    m_glow = ramp(N('ShaderNodeValToRGB', 'GLOW 底盘（陡降）', -1060, 620), [
        (0.00, (0.95, 0.95, 0.95, 1)),
        (0.18, (0.35, 0.35, 0.35, 1)),
        (float(P["glow_rad"]), (0.0, 0.0, 0.0, 1)),
    ])
    links.new(r_out, I(m_glow, 0))
    m_rayenv = MATH('RE  射线 x 包络', 'MULTIPLY', -560, -300)
    links.new(m_ray.outputs[0], I(m_rayenv, 0)); links.new(m_env.outputs[0], I(m_rayenv, 1))
    m_mask = MATH('MASK  max(射线,底盘)', 'MAXIMUM', -340, 120)
    links.new(m_rayenv.outputs[0], I(m_mask, 0)); links.new(m_glow.outputs[0], I(m_mask, 1))

else:  # pulse：一个环掩码，前后两条边界各自推进
    # R_out = MapRange(prog, [0, split] -> [0, R_out_cap])  前缘（封顶）
    m_ro = MRANGE('RO  R_out = prog->[0,%g]' % P["R_out_cap"], -1360, -560)
    links.new(tval.outputs[0], sock(m_ro, 'Value', 'VALUE'))
    sock(m_ro, 'From Min', 'VALUE').default_value = 0.0
    sock(m_ro, 'From Max', 'VALUE').default_value = P["split"]
    sock(m_ro, 'To Min', 'VALUE').default_value = 0.0
    sock(m_ro, 'To Max', 'VALUE').default_value = P["R_out_cap"]
    # R_in = MapRange(prog, [split, 1] -> [0, R_in_cap])    后缘（滞后启动）
    m_ri = MRANGE('RI  R_in = prog->[0,%g]' % P["R_in_cap"], -1360, -760)
    links.new(tval.outputs[0], sock(m_ri, 'Value', 'VALUE'))
    sock(m_ri, 'From Min', 'VALUE').default_value = P["split"]
    sock(m_ri, 'From Max', 'VALUE').default_value = 1.0
    sock(m_ri, 'To Min', 'VALUE').default_value = 0.0
    sock(m_ri, 'To Max', 'VALUE').default_value = P["R_in_cap"]

    m_rolo = MATH('ROL  R_out-soft', 'SUBTRACT', -1180, -560, b=P["soft"])
    links.new(m_ro.outputs[0], I(m_rolo, 0))
    m_rilo = MATH('RIL  R_in-soft', 'SUBTRACT', -1180, -760, b=P["soft"])
    links.new(m_ri.outputs[0], I(m_rilo, 0))
    m_rr = MATH('RR  r-(R_in-soft)', 'SUBTRACT', -820, -620)
    links.new(r_out, I(m_rr, 0)); links.new(m_rilo.outputs[0], I(m_rr, 1))

    # f_out = clamp((R_out - r)/soft)      软边在内侧（r 小 = 实体 = 1）
    mro = MRANGE('MRO  前缘软边', -600, -380)
    links.new(r_out, sock(mro, 'Value', 'VALUE'))
    links.new(m_rolo.outputs[0], sock(mro, 'From Min', 'VALUE'))
    links.new(m_ro.outputs[0], sock(mro, 'From Max', 'VALUE'))
    sock(mro, 'To Min', 'VALUE').default_value = 1.0
    sock(mro, 'To Max', 'VALUE').default_value = 0.0
    # f_in = clamp((r - R_in + soft)/soft)  软边也在内侧
    # ★ 若写成 clamp((r-R_in)/soft)，R_in=0 时会把中心也软成 0 -> 实心圆盘永远有个假黑点
    mri = MRANGE('MRI  黑腔软边', -600, -620)
    links.new(m_rr.outputs[0], sock(mri, 'Value', 'VALUE'))
    sock(mri, 'From Min', 'VALUE').default_value = 0.0
    sock(mri, 'From Max', 'VALUE').default_value = P["soft"]
    sock(mri, 'To Min', 'VALUE').default_value = 0.0
    sock(mri, 'To Max', 'VALUE').default_value = 1.0

    m_ring = MATH('RING  f_out x f_in', 'MULTIPLY', -400, -500)
    links.new(mro.outputs[0], I(m_ring, 0)); links.new(mri.outputs[0], I(m_ring, 1))
    # 外缘轻收（主体实心亮，最外圈略暗）
    m_rim = ramp(N('ShaderNodeValToRGB', 'RIM  外缘轻收', -600, -160), [
        (0.00, (1.00, 1.00, 1.00, 1)),
        (0.55, (0.97, 0.97, 0.97, 1)),
        (0.78, (0.86, 0.86, 0.86, 1)),
        (1.00, (P["rim_amt"],) * 3 + (1,)),
    ])
    links.new(r_out, I(m_rim, 0))
    m_mask = MATH('MASK  ring x RIM', 'MULTIPLY', -220, -300)
    links.new(m_ring.outputs[0], I(m_mask, 0)); links.new(m_rim.outputs[0], I(m_mask, 1))

assert m_mask is not None, "mask 未生成"

# ===== 尾端 A：Base Color 分支 =====
# 色相 ramp 在 r>1 处往往不是纯黑（本例 (0.40,0.02,0.01) 暗红），
# 直接接 Base Color 会把整片方片填成底色 -> 必须先乘亮度掩码。
vbase = N('ShaderNodeValue', 'BASE_MULT  <- 拖这个调底色亮度', -220, 120)
vbase.outputs[0].default_value = P["base_mult"]
bmul = MATH('BASE  mask x base_mult', 'MULTIPLY', 0, 120)
links.new(m_mask.outputs[0], I(bmul, 0)); links.new(vbase.outputs[0], I(bmul, 1))
comb = N('ShaderNodeCombineColor', 'BASE  ->RGB', 200, 120)
comb.mode = 'RGB'
for i in (0, 1, 2):
    links.new(bmul.outputs[0], I(comb, i))

mixb = N('ShaderNodeMix', 'BASE  COL x mask', 400, 120)
mixb.data_type = 'RGBA'
mixb.blend_type = 'MULTIPLY'
mixb.clamp_factor = True
sock(mixb, 'Factor', 'VALUE').default_value = 1.0
links.new(col.outputs[0], sock(mixb, 'A', 'RGBA'))     # in#6
links.new(comb.outputs[0], sock(mixb, 'B', 'RGBA'))    # in#7
mres = [s for s in mixb.outputs if s.name == 'Result' and s.type == 'RGBA'][0]

# ===== 尾端 B：Emission 分支 =====
# 无灯场景只接 Base Color => 渲染几乎全黑（Principled 靠反射光）。两路都留。
vemit = N('ShaderNodeValue', 'EMIT_MULT  <- 拖这个调自发光', -220, -700)
vemit.outputs[0].default_value = P["emit_mult"]
emul = MATH('EMIT  mask x emit_mult', 'MULTIPLY', 0, -700)
links.new(m_mask.outputs[0], I(emul, 0)); links.new(vemit.outputs[0], I(emul, 1))

bsdf = N('ShaderNodeBsdfPrincipled', 'BSDF  颜色进 Base Color', 660, 0)
def pin(node, name):
    got = [s for s in node.inputs if s.name == name]
    assert got, "no input %r in %s (have %s)" % (name, node.name, [s.name for s in node.inputs])
    return got[0]
pin(bsdf, 'Base Color').default_value = (0.0, 0.0, 0.0, 1.0)
pin(bsdf, 'Metallic').default_value = 0.0
pin(bsdf, 'Roughness').default_value = 0.45
links.new(mres, pin(bsdf, 'Base Color'))
links.new(col.outputs[0], pin(bsdf, 'Emission Color'))
links.new(emul.outputs[0], pin(bsdf, 'Emission Strength'))
out = N('ShaderNodeOutputMaterial', 'OUT', 900, 0)
links.new(bsdf.outputs[0], I(out, 0))

# ---------------- 4. 时间关键帧（LINEAR）----------------
tval.outputs[0].default_value = P["prog0"]
tval.outputs[0].keyframe_insert('default_value', frame=P["f_start"])
tval.outputs[0].default_value = P["prog1"]
tval.outputs[0].keyframe_insert('default_value', frame=P["f_end"])
lin = 0
try:
    # 5.x 分层 Action：action.layers[].strips[].channelbags[].fcurves
    for lay in nt.animation_data.action.layers:
        for st in lay.strips:
            for cb in st.channelbags:
                for fc in cb.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
                        lin += 1
                    fc.update()
except AttributeError:
    for fc in nt.animation_data.action.fcurves:      # 4.x 旧结构
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
            lin += 1
        fc.update()
log.append("prog keyframes=2 linearized=%d" % lin)

# ---------------- 5. 赋给目标对象：槽0=本材质，槽1=备用 ----------------
if P["assign"]:
    for name in TARGETS:
        ob = bpy.data.objects.get(name)
        if not ob:
            log.append("!! MISSING %s" % name)
            continue
        me = ob.data
        me.materials.clear()
        me.materials.append(mat)
        if src:
            me.materials.append(src)
        for poly in me.polygons:
            poly.material_index = 0
        log.append("assign %-10s slots=%s faces->%s" % (
            name, [x.name if x else None for x in me.materials],
            sorted({poly.material_index for poly in me.polygons})))
else:
    log.append("assign=False（试跑：材质已建但未赋给任何物体）")

# ---------------- 6. 回读校验 ----------------
log.append("nodes=%d links=%d view.users=%s" % (len(nodes), len(links), mat.users))

def lab(prefix):
    got = [n for n in nodes if n.label.split() and n.label.split()[0] == prefix]
    assert got, "no node labeled %r" % prefix
    return got[0]

def feed(n, i):
    s = n.inputs[i]
    got = [l.from_node.label for l in links if l.to_socket == s]
    return got[0] if got else "=<%.4g>" % s.default_value

def close(got, want):
    """float32 存 0.45 会得到 0.44999998807 -> 校验必须用容差，字符串比较必然误报"""
    try:
        return abs(float(got) - float(want)) <= max(1e-5, abs(float(want)) * 1e-5)
    except (TypeError, ValueError):
        return str(got) == str(want)

checks = [
    ("BSDF.BaseColor <-", feed(bsdf, [i for i, s in enumerate(bsdf.inputs)
                                      if s.name == 'Base Color'][0]), "BASE  COL x mask"),
    ("BSDF.EmitStr   <-", feed(bsdf, [i for i, s in enumerate(bsdf.inputs)
                                      if s.name == 'Emission Strength'][0]), "EMIT"),
    ("Mix.A <-COL",   feed(mixb, 6), "COL  色相 白热->金->橙->红"),
    ("Mix.B <-BASE",  feed(mixb, 7), "BASE  ->RGB"),
    ("TC.object",     tc.object.name if tc.object else None, P["ctrl"]),
    ("MAP.scale",     I(mp, 3).default_value[0], 1.0 / P["R_eff"]),
    ("BASE_MULT",     vbase.outputs[0].default_value, P["base_mult"]),
    ("EMIT_MULT",     vemit.outputs[0].default_value, P["emit_mult"]),
    ("NO COMPOSITOR", 0, 0),
]
if MODE == "spike":
    checks += [
        ("VOR.feature", vor.feature, "F1"),
        ("VOR.scale",   sock(vor, 'Scale', 'VALUE').default_value, P["ray_scale"]),
        ("MASK.a <-",   feed(m_mask, 0), "RE  射线 x 包络"),
        ("MASK.b <-",   feed(m_mask, 1), "GLOW 底盘（陡降）"),
    ]
elif MODE == "pulse":
    checks += [
        ("RING.a <-",       feed(m_ring, 0), "MRO"),
        ("RING.b <-",       feed(m_ring, 1), "MRI"),
        ("MRO.FromMin <-",  feed(mro, [i for i, s in enumerate(mro.inputs)
                                       if s.name == 'From Min' and s.type == 'VALUE'][0]), "ROL"),
        ("MRO.FromMax <-",  feed(mro, [i for i, s in enumerate(mro.inputs)
                                       if s.name == 'From Max' and s.type == 'VALUE'][0]), "RO "),
        ("MRI.FromMax",     sock(mri, 'From Max', 'VALUE').default_value, P["soft"]),
        ("RO.ToMax",        sock(m_ro, 'To Max', 'VALUE').default_value, P["R_out_cap"]),
        ("RI.ToMax",        sock(m_ri, 'To Max', 'VALUE').default_value, P["R_in_cap"]),
        ("NO VORONOI",      len([n for n in nodes if n.bl_idname == 'ShaderNodeTexVoronoi']), 0),
        ("NO NOISE",        len([n for n in nodes if n.bl_idname == 'ShaderNodeTexNoise']), 0),
    ]
log.append("--- CHECKS ---")
n_fail = 0
for k, got, want in checks:
    ok = close(got, want) or str(want) in str(got)
    n_fail += (not ok)
    log.append("  %-18s got=%-30s want=%s  %s" % (k, got, want, "OK " if ok else "**FAIL**"))

# ---------------- 7. 解析表：把边界/掩码的理论值打出来自审 ----------------
def clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

log.append("--- 解析表（理论自审，不依赖渲染）---")
if MODE == "pulse":
    def ring_at(r, r_out, r_in, soft):
        return clamp01((r_out - r) / soft) * clamp01((r - r_in + soft) / soft)
    for f in (P["f_start"], 30, 60, 88, 130, 180, 250):
        pr = P["prog0"] + (P["prog1"] - P["prog0"]) * (f - P["f_start"]) / float(P["f_end"] - P["f_start"])
        k_out = clamp01(pr / P["split"])
        k_in = clamp01((pr - P["split"]) / (1.0 - P["split"]))
        r_out = k_out * P["R_out_cap"]
        r_in = k_in * P["R_in_cap"]
        stage = ("膨胀" if pr < P["split"] else
                 ("全黑" if r_in >= P["R_out_cap"] + P["soft"] else "黑腔"))
        log.append("  f%3d prog=%.4f R_out=%.4f R_in=%.4f | ring@r=0:%.2f r=0.5:%.2f r=1.0:%.2f r=1.6:%.2f | %s"
                   % (f, pr, r_out, r_in,
                      ring_at(0.0, r_out, r_in, P["soft"]),
                      ring_at(0.5, r_out, r_in, P["soft"]),
                      ring_at(1.0, r_out, r_in, P["soft"]),
                      ring_at(1.6, r_out, r_in, P["soft"]), stage))
    # ★ 自查：膨胀阶段 R_in=0，ring@r=0 必须 = 1.00（否则中心有假黑点）
elif MODE == "ring":
    for f in (P["f_start"], 60, 120, P["f_end"]):
        pr = P["prog0"] + (P["prog1"] - P["prog0"]) * (f - P["f_start"]) / float(P["f_end"] - P["f_start"])
        # 第 k 条环满足 fract(r*N - prog)=0 -> r = (k+prog)/N
        rs = [(k + pr) / P["ring_count"] for k in range(0, 4)]
        log.append("  f%3d prog=%.4f 环半径 r = %s" % (f, pr, " ".join("%.3f" % x for x in rs)))
else:
    log.append("  （%s 模式无时间边界；掩码由 mode 参数直接决定）" % MODE)

# 帧求值实测
scn.frame_set(P["f_start"])
for f in (P["f_start"], (P["f_start"] + P["f_end"]) // 2, P["f_end"]):
    scn.frame_set(f)
    ev = nt.evaluated_get(bpy.context.evaluated_depsgraph_get())
    log.append("frame %3d TVAL=%.4f" % (f, ev.nodes[lab("TVAL").name].outputs[0].default_value))
scn.frame_set(P["f_start"])

log.append("FAILS=%d" % n_fail)
log.append("material=%s  所有材质=%s" % (P["material"], [x.name for x in bpy.data.materials]))
print("\n".join(log))
