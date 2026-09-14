# fb_build_cycle.py — 重建 FB_Firework_View 为「循环脉冲」版
#
# 用户要的时间轴（原始描述）：
#   开始是纯黑 → 一段帧数后开始扩散 → 填满 → 停留一段帧数
#   → 从中心（黑腔）扩散、吃到全黑 → 再停留一段帧数 → 循环
#
# 时间轴（v1.5：四段 = 一个完整循环，全部由 FB_ctrl 空物体属性驱动）：
#   [0]  变亮前等待   纯黑          ← 用户：「开始变亮之前的时间」
#   [1]  变亮时长     小圆 -> 满圆   ← 用户：「从开始变亮到完整变亮的时间」
#   [2]  全亮维持     满圆保持       ← 用户：「完整变亮维持的时间」
#   [3]  变黑时长     中心黑洞扩大 -> 全黑 -> 回到 [0]
#                                    ← 用户：「变亮之后多少时间又变全黑」
#   周期 = 四段之和（自动）
#
# ── 时间链（全部是 Math 节点）─────────────────────────────────
#   TVAL    原始帧号 f（关键帧 1->1, 250->250, LINEAR + 外推 LINEAR）
#   M_MOD   u = f floored_mod 周期      -> u ∈ [0, 周期)
#   M_SUB   v = u - 变亮前等待           -> 黑场期为负
#   M_PRG   prog = clamp(v / 活动帧数)   -> 黑场期 0，变黑结束为 1
#            活动帧数 = 变亮时长 + 全亮维持 + 变黑时长
#   A_SPL   split_in  = (变亮 + 全亮维持) / 活动帧数
#   A_SPLO  split_out = 变亮 / 活动帧数
#
# ★★ 四个时长参数【全部进相位】，所以每一个都在首周期内当场可见。
#   反面教训（旧版真 bug）：只要把某个时长【只】写进周期、不写进 `u - 参数`，
#   则任何 f < 周期 的帧上 u ≡ f，改它画面逐像素不变（实测 diff=0.0/255）。
#   旧版「全黑停留帧数」就是这么废掉的，用户帧范围 1–250 内拖它整段无反应。
#
# ★★ 控制面 = 空物体 FB_ctrl 的自定义属性，由【驱动器】打进节点插槽。
#   实测（Blender 5.2，见 y_drv*.py）：节点插槽驱动完全可用 ——
#   expression='frame' ★、纯常量 ★、SINGLE_PROP 取属性 ★（原生通道与自定义属性都行）。
#   两个必须知道的坑：
#     1) driver_add() 会把表达式自动填成当时的数值（看到 expr='20.0' 别慌，覆盖它）
#     2) 变量 data_path 必须写双引号 '["名字"]'；写单引号会静默解析失败返回 0
#     3) Python 里 ctrl['x']=v 走 IDProperty 底层接口、【不打更新标记】，
#        所以脚本改完要补 ctrl.update_tag()；UI 里拖属性走 RNA，Blender 自己会打标记
#
# ── 边界（与上一版一致）──────────────────────────────────────
#   R_out = MapRange(prog, [0, split] -> [0, 满圆半径])
#   R_in  = MapRange(prog, [split, 1] -> [0, 黑洞终半径])
#   f_out = clamp((R_out - r)/soft)     软边在内侧
#   f_in  = clamp((r - R_in + soft)/soft) 软边在内侧（R_in=0 时中心恒亮）
#   ring  = f_out * f_in                -> 仅 r ∈ [R_in, R_out] 为 1
#
# ★ 外观上的等价性：等待期 prog=0 -> R_out=0 -> ring≡0 -> 全黑（纯黑不透明）
#   全黑停留期 prog=1 -> R_in=1.30 > 角点半径 √2 -> ring≡0 -> 全黑
#
# 保留的实测踩坑（见 blender-remote-control / blender-spherical-radial-texture）：
#   1) Math 节点三个入口全叫 "Value"，取插件必须用索引
#   2) 材质槽必须 clear 再 append
#   3) 5.2 无 FRAME 驱动变量 —— 用 TVAL 关键帧 + LINEAR 外推代替（任意帧 raw == frame）。
#      注：节点插槽驱动【是能用的】（y_drv*.py 实测），上一版"驱动不生效"是误判：
#      driver_add() 自动把表达式填成了常量数值，等于没驱动。
#   4) Base Color 要乘亮度掩码
#   5) Map Range 有同名不同类型插槽，必须按 (name,type) 取
#   6) float32 精度 -> 校验必须用容差
#   7) 关键帧 LINEAR + fc.extrapolation='LINEAR' => 任意帧外推仍线性（raw = frame）
import bpy

# NOTE: 下面 4 个名字是模板占位 —— 换成你工程里实际的对象/材质名再跑。
#       本脚本会把所有名为「平面*」的 mesh 的槽 0 指到 MAT（槽 1 保留 SRC）。
CTRL = "FB_ctrl"            # 控制空物体：既是纹理坐标的 Object 源，也是唯一控制面
MAT = "FB_Firework_View"    # 要重建的成品材质（循环脉冲版）
SRC = "FB_Firework"         # 备用原版材质：只读，绝不动它
PLANES = [ob.name for ob in bpy.data.objects
          if ob.type == 'MESH' and ob.name.startswith("平面")]

# ---------------- 参数（= FB_ctrl 空物体上的自定义属性，唯一控制面）----------
P = {
    # 时间轴（帧）：四段 = 一个完整循环
    "变亮前等待":   20.0,   # 开始变亮之前的纯黑帧数
    "变亮时长":     60.0,   # 从开始变亮到完全变亮
    "全亮维持":     24.0,   # 完全变亮之后保持
    "变黑时长":     70.0,   # 全亮之后到全部变黑
    # 形状
    "满圆半径":     1.05,   # 1.0 = 内切于 2x2 平面；>1.414 会铺满四角
    "黑洞终半径":   1.30,   # >= 满圆半径 + soft 时即全黑
    "边缘柔和":     0.09,
    # 外观
    "底色亮度":     1.00,
    "自发光强度":   1.20,
    # 派生：不是输入，而是【自动驱动】出来的只读读数（见 §3.5 末尾）
    "周期帧数":     174.0,
}
# 周期 = 四段之和（自动）。四段【全部】进相位，所以每个都当场可见。
P["周期帧数"] = (P["变亮前等待"] + P["变亮时长"] + P["全亮维持"]
                + P["变黑时长"])

# 空物体属性名 -> 材质节点 name（驱动器从这个键取值）
NODE_OF = {
    "变亮前等待": "T_BLACK",
    "变亮时长":   "T_GROW",
    "全亮维持":   "T_HOLD",
    "变黑时长":   "T_EAT",
    "满圆半径":   "V_ROUT",
    "黑洞终半径": "V_RIN",
    "边缘柔和":   "V_SOFT",
    "底色亮度":   "BASE_MULT",
    "自发光强度": "EMIT_MULT",
}
# 空物体属性的 UI 范围/描述（min/max 是硬钳位，所以时长下限给 1 防除零）
UI_RANGE = {
    "变亮前等待": (0.0, 2000.0, 0.0, 600.0,
                   "开始变亮之前的纯黑帧数（循环里每一圈都会先黑这么久）"),
    "变亮时长":   (1.0, 2000.0, 1.0, 300.0, "从开始变亮到完全变亮所需的帧数"),
    "全亮维持":   (0.0, 2000.0, 0.0, 300.0, "完全变亮之后保持不动的帧数"),
    "变黑时长":   (1.0, 2000.0, 1.0, 300.0, "全亮之后到全部变黑所需的帧数"),
    "满圆半径":   (0.0, 2.0, 0.2, 1.4,
                   "满圆半径；1.0 = 内切于 2x2 平面，超过 1.414 会铺满四角"),
    "黑洞终半径": (0.0, 3.0, 0.5, 2.0, "黑洞最终半径；>= 满圆半径 + 边缘柔和 时全黑"),
    "边缘柔和":   (0.001, 0.5, 0.01, 0.3, "边缘软边宽度（世界单位，平面半宽=1）"),
    "底色亮度":   (0.0, 5.0, 0.0, 3.0,
                   "Base Color 亮度倍率。⚠ 只在有环境光/视口材质预览下可见"),
    "自发光强度": (0.0, 20.0, 0.0, 8.0, "Emission 强度倍率"),
    "周期帧数":   (0.0, 10000.0, 0.0, 1000.0,
                   "自动计算（只读）= 变亮前等待 + 变亮时长 + 全亮维持 + 变黑时长"),
}
READONLY = ("周期帧数",)

# 时间轴四段（决定周期，也是「周期帧数」那条自动驱动的取数来源）
_TIME_KEYS = ("变亮前等待", "变亮时长", "全亮维持", "变黑时长")

log = []
I = lambda n, i: n.inputs[i]

def seti(n, i, v):
    n.inputs[i].default_value = v
    return n

def ramp(n, stops, interp='EASE'):
    el = n.color_ramp.elements
    while len(el) > 1:
        el.remove(el[-1])
    el[0].position, el[0].color = stops[0]
    for pos, col in stops[1:]:
        e = el.new(pos); e.color = col
    n.color_ramp.interpolation = interp
    return n

def sock(node, name, typ):
    got = [s for s in node.inputs if s.name == name and s.type == typ]
    assert got, "no socket %s/%s in %s (have %s)" % (
        name, typ, node.label or node.name,
        [(s.name, s.type) for s in node.inputs])
    return got[0]

# ---------------- 0. 幂等清理（只清自己，绝不动 FB_Firework）----------------
m = bpy.data.materials.get(MAT)
if m:
    for me in bpy.data.meshes:
        if MAT in [x.name for x in me.materials if x]:
            me.materials.clear()
            me.materials.append(bpy.data.materials[SRC])
            for p in me.polygons:
                p.material_index = 0
    bpy.data.materials.remove(m)
    log.append("cleaned previous %s" % MAT)

src = bpy.data.materials.get(SRC)
if src is None:
    raise RuntimeError("源材质 %s 不存在" % SRC)
src.use_fake_user = True

# ---------------- 1. FB_ctrl 空物体 = 唯一控制面 ----------------
scn = bpy.context.scene
ctrl = bpy.data.objects.get(CTRL)
if ctrl is None:
    ctrl = bpy.data.objects.new(CTRL, None)
    scn.collection.objects.link(ctrl)
    ctrl.empty_display_type = 'PLAIN_AXES'
    ctrl.empty_display_size = 0.4
    log.append("created %s" % CTRL)
else:
    log.append("reused %s" % CTRL)

# ★ 它同时是纹理坐标的 Object 源，必须保持原点 + 单位变换，否则整个径向场会偏心
ctrl.location = (0.0, 0.0, 0.0)
ctrl.rotation_euler = (0.0, 0.0, 0.0)
ctrl.scale = (1.0, 1.0, 1.0)

# ★★ 参数写进空物体的自定义属性，并由【驱动器】真正打进节点插槽（见 §3.5）。
#    上一版把这些属性只当「快照镜像」，没有任何东西读它 —— 是个能拖但无效的假控件；
#    这一版每个属性都有一条驱动器连到材质节点，在「物体属性 > 自定义属性」里拖当场生效。
# ★ 重建前先清掉 ctrl 自己的旧驱动：「周期帧数」自 v1.6 起带一条自动驱动，
#   不清就会指向马上要被删掉的属性（下次求值时报错 / 读到旧值）。
if ctrl.animation_data:
    ctrl.animation_data_clear()
    log.append("ctrl: 清掉旧驱动")
for k in [k for k in ctrl.keys() if k != "_RNA_UI"]:
    del ctrl[k]
for k, v in P.items():
    ctrl[k] = v
    mn, mx, smn, smx, desc = UI_RANGE.get(
        k, (0.0, 10000.0, 0.0, 1000.0, "只读：四段之和，自动计算"))
    ctrl.id_properties_ui(k).update(min=mn, max=mx, soft_min=smn,
                                    soft_max=smx, description=desc)
ctrl.update_tag()
log.append("ctrl: 写入 %d 个属性（带 min/max/soft/描述）" % len(P))
log.append("ctrl: %s" % list(P))

# ---------------- 2. 材质与节点树 ----------------
mat = bpy.data.materials.new(MAT)
mat.use_nodes = True
mat.use_backface_culling = False
mat.diffuse_color = (1.0, 0.32, 0.06, 1.0)
mat.metallic = 0.0
mat.roughness = 0.45

nt = mat.node_tree
nodes, links = nt.nodes, nt.links
nodes.clear()
if nt.animation_data:
    nt.animation_data_clear()

def N(t, name, label, x, y):
    n = nodes.new(t); n.name = name; n.label = label; n.location = (x, y); return n

def V(name, label, val, x, y):
    n = N('ShaderNodeValue', name, label, x, y)
    n.outputs[0].default_value = val
    return n

def MATH(name, label, op, x, y, a=None, b=None, c=None):
    """★ 两个 Math 陷阱（都实测踩过）：
    1) 节点有 3 个 Value 输入，【未链接的输入会用 default_value 参与运算】，新建默认 0.5。
       -> 这里把所有输入显式归零，否则 ADD 会偷偷多加上 0.5。
    2) 第三个输入【只有 MULTIPLY_ADD 会用】，ADD/SUBTRACT/MULTIPLY 都只读前两个。
       -> 三个数相加必须串两个 ADD，不能指望一个 ADD 吃掉三路。"""
    n = N('ShaderNodeMath', name, label, x, y); n.operation = op
    for i, v in enumerate((0.0 if a is None else a,
                           0.0 if b is None else b,
                           0.0 if c is None else c)):
        seti(n, i, v)
    return n

def MRANGE(name, label, x, y):
    n = N('ShaderNodeMapRange', name, label, x, y); n.clamp = True
    return n

# ===== 坐标源 =====
tc = N('ShaderNodeTexCoord', 'TC', '坐标源 Object=FB_ctrl', -1600, 0); tc.object = ctrl
mp = N('ShaderNodeMapping', 'MAP', '缩放（保持 1）', -1420, 0)
seti(mp, 3, (1.0, 1.0, 1.0))
links.new(tc.outputs[3], I(mp, 0))

vlen = N('ShaderNodeVectorMath', 'LEN', '半径 r = |P|', -1240, 120)
vlen.operation = 'LENGTH'
links.new(mp.outputs[0], I(vlen, 0))

# ===== 亮度剖面 =====
rim = ramp(N('ShaderNodeValToRGB', 'RIM', '外缘轻收', -600, -160), [
    (0.00, (1.00, 1.00, 1.00, 1)),
    (0.55, (0.97, 0.97, 0.97, 1)),
    (0.78, (0.86, 0.86, 0.86, 1)),
    (1.00, (0.55, 0.55, 0.55, 1)),
])
links.new(vlen.outputs[1], I(rim, 0))

# ===== 色相 =====
col = ramp(N('ShaderNodeValToRGB', 'COL', '色相 白热→金→橙→红', -1040, 260), [
    (0.00, (1.00, 1.00, 0.95, 1)),
    (0.10, (1.00, 0.90, 0.55, 1)),
    (0.30, (1.00, 0.55, 0.12, 1)),
    (0.58, (1.00, 0.24, 0.03, 1)),
    (0.85, (0.84, 0.07, 0.02, 1)),
    (1.00, (0.40, 0.02, 0.01, 1)),
])
links.new(vlen.outputs[1], I(col, 0))

# ===== 参数节点（label 中文；name 是给驱动器定位用的键）=====
v_black = V('T_BLACK', '变亮前等待', P["变亮前等待"], -2050, -520)
v_grow  = V('T_GROW',  '变亮时长',   P["变亮时长"],   -2050, -640)
v_hold  = V('T_HOLD',  '全亮维持',   P["全亮维持"],   -2050, -760)
v_eat   = V('T_EAT',   '变黑时长',   P["变黑时长"],   -2050, -880)
v_rout  = V('V_ROUT',  '满圆半径',   P["满圆半径"],   -2050, -1120)
v_rin   = V('V_RIN',   '黑洞终半径', P["黑洞终半径"], -2050, -1240)
v_soft  = V('V_SOFT',  '边缘柔和',   P["边缘柔和"],   -2050, -1360)

# ---- 帧数合成 ----
a_s1  = MATH('A_S1',  '变亮+全亮维持', 'ADD', -1860, -640)
links.new(v_grow.outputs[0], I(a_s1, 0)); links.new(v_hold.outputs[0], I(a_s1, 1))

a_act = MATH('A_ACT', '活动帧数 = S1+变黑', 'ADD', -1700, -700)
links.new(a_s1.outputs[0], I(a_act, 0)); links.new(v_eat.outputs[0], I(a_act, 1))

# ★ 周期 = 活动帧数 + 变亮前等待。四段【全部】进相位，
#   所以「变亮前等待」不是开场一次性延迟，而是循环里每圈的纯黑段，改它当场可见。
a_per = MATH('A_PER', '周期 = 活动 + 变亮前等待', 'ADD', -1540, -800)
links.new(a_act.outputs[0], I(a_per, 0))
links.new(v_black.outputs[0], I(a_per, 1))

a_spl = MATH('A_SPL', 'split_in = S1/活动', 'DIVIDE', -1860, -760)
links.new(a_s1.outputs[0], I(a_spl, 0)); links.new(a_act.outputs[0], I(a_spl, 1))

# ★ 前缘与后缘的归一化位置【不同】：
#   R_out 在「变亮时长」内从 0 涨到满圆   -> 前缘比例 = 变亮/活动
#   R_in  在「变亮+全亮维持」之后才启动   -> 后缘比例 = (变亮+全亮维持)/活动
# 用同一个比例会把扩散段拉长「全亮维持」那么多帧（实测踩过）。
a_splo = MATH('A_SPLO', 'split_out = 变亮/活动', 'DIVIDE', -1860, -880)
links.new(v_grow.outputs[0], I(a_splo, 0)); links.new(a_act.outputs[0], I(a_splo, 1))

# ---- 时间链 ----
tval = V('TVAL', '原始帧号 f', 1.0, -2050, -400)

m_mod = MATH('M_MOD', 'u = f mod 周期', 'FLOORED_MODULO', -1860, -400)
links.new(tval.outputs[0], I(m_mod, 0))
links.new(a_per.outputs[0], I(m_mod, 1))

# ★ 减的是「变亮前等待」：黑场在循环开头，所以这个参数进了相位，拖它当场就能看见。
m_sub = MATH('M_SUB', 'v = u - 变亮前等待', 'SUBTRACT', -1700, -400)
links.new(m_mod.outputs[0], I(m_sub, 0))
links.new(v_black.outputs[0], I(m_sub, 1))

m_prg = MRANGE('M_PRG', 'prog 0..1（等待期=0）', -1540, -400)
links.new(m_sub.outputs[0], sock(m_prg, 'Value', 'VALUE'))
sock(m_prg, 'From Min', 'VALUE').default_value = 0.0
links.new(a_act.outputs[0], sock(m_prg, 'From Max', 'VALUE'))
sock(m_prg, 'To Min', 'VALUE').default_value = 0.0
sock(m_prg, 'To Max', 'VALUE').default_value = 1.0

# ---- 两条边界 ----
m_ro = MRANGE('RO', 'R_out', -1360, -560)
links.new(m_prg.outputs[0], sock(m_ro, 'Value', 'VALUE'))
sock(m_ro, 'From Min', 'VALUE').default_value = 0.0
links.new(a_splo.outputs[0], sock(m_ro, 'From Max', 'VALUE'))
sock(m_ro, 'To Min', 'VALUE').default_value = 0.0
links.new(v_rout.outputs[0], sock(m_ro, 'To Max', 'VALUE'))

m_ri = MRANGE('RI', 'R_in', -1360, -760)
links.new(m_prg.outputs[0], sock(m_ri, 'Value', 'VALUE'))
links.new(a_spl.outputs[0], sock(m_ri, 'From Min', 'VALUE'))
sock(m_ri, 'From Max', 'VALUE').default_value = 1.0
sock(m_ri, 'To Min', 'VALUE').default_value = 0.0
links.new(v_rin.outputs[0], sock(m_ri, 'To Max', 'VALUE'))

m_rolo = MATH('ROL', 'R_out - soft', 'SUBTRACT', -1180, -560)
links.new(m_ro.outputs[0], I(m_rolo, 0)); links.new(v_soft.outputs[0], I(m_rolo, 1))

m_rilo = MATH('RIL', 'R_in - soft', 'SUBTRACT', -1180, -760)
links.new(m_ri.outputs[0], I(m_rilo, 0)); links.new(v_soft.outputs[0], I(m_rilo, 1))

m_rr = MATH('RR', 'r - (R_in - soft)', 'SUBTRACT', -820, -620)
links.new(vlen.outputs[1], I(m_rr, 0)); links.new(m_rilo.outputs[0], I(m_rr, 1))

mro = MRANGE('MRO', '前缘软边', -600, -380)
links.new(vlen.outputs[1], sock(mro, 'Value', 'VALUE'))
links.new(m_rolo.outputs[0], sock(mro, 'From Min', 'VALUE'))
links.new(m_ro.outputs[0], sock(mro, 'From Max', 'VALUE'))
sock(mro, 'To Min', 'VALUE').default_value = 1.0
sock(mro, 'To Max', 'VALUE').default_value = 0.0

mri = MRANGE('MRI', '黑腔软边', -600, -620)
links.new(m_rr.outputs[0], sock(mri, 'Value', 'VALUE'))
sock(mri, 'From Min', 'VALUE').default_value = 0.0
links.new(v_soft.outputs[0], sock(mri, 'From Max', 'VALUE'))
sock(mri, 'To Min', 'VALUE').default_value = 0.0
sock(mri, 'To Max', 'VALUE').default_value = 1.0

m_ring = MATH('RING', 'ring = f_out × f_in', 'MULTIPLY', -400, -500)
links.new(mro.outputs[0], I(m_ring, 0)); links.new(mri.outputs[0], I(m_ring, 1))

m_mask = MATH('MASK', 'mask = ring × RIM', 'MULTIPLY', -220, -300)
links.new(m_ring.outputs[0], I(m_mask, 0)); links.new(rim.outputs[0], I(m_mask, 1))

# ===== 尾端 A：Base Color =====
vbase = V('BASE_MULT', '底色亮度', P["底色亮度"], -220, 120)

bmul = MATH('BASE', 'mask × 底色亮度', 'MULTIPLY', 0, 120)
links.new(m_mask.outputs[0], I(bmul, 0)); links.new(vbase.outputs[0], I(bmul, 1))

comb = N('ShaderNodeCombineColor', 'BASE_RGB', '→RGB', 200, 120)
comb.mode = 'RGB'
for i in (0, 1, 2):
    links.new(bmul.outputs[0], I(comb, i))

def mix_rgba(node, want_name, want_type):
    got = [s for s in node.inputs if s.name == want_name and s.type == want_type]
    assert got, "no socket %s/%s" % (want_name, want_type)
    return got[0]

mixb = N('ShaderNodeMix', 'BASE_MIX', 'COL × mask', 400, 120)
mixb.data_type = 'RGBA'
mixb.blend_type = 'MULTIPLY'
mixb.clamp_factor = True
mix_rgba(mixb, 'Factor', 'VALUE').default_value = 1.0
links.new(col.outputs[0], mix_rgba(mixb, 'A', 'RGBA'))
links.new(comb.outputs[0], mix_rgba(mixb, 'B', 'RGBA'))
mres = [s for s in mixb.outputs if s.name == 'Result' and s.type == 'RGBA'][0]

# ===== 尾端 B：Emission =====
vemit = V('EMIT_MULT', '自发光强度', P["自发光强度"], -220, -700)

emul = MATH('EMIT', 'mask × 自发光强度', 'MULTIPLY', 0, -700)
links.new(m_mask.outputs[0], I(emul, 0)); links.new(vemit.outputs[0], I(emul, 1))

# ===== Principled BSDF =====
bsdf = N('ShaderNodeBsdfPrincipled', 'BSDF', '颜色 → Base Color', 660, 0)
def pin(node, name):
    got = [s for s in node.inputs if s.name == name]
    assert got, "no input %r (have %s)" % (name, [s.name for s in node.inputs])
    return got[0]

pin(bsdf, 'Base Color').default_value = (0.0, 0.0, 0.0, 1.0)
pin(bsdf, 'Metallic').default_value = 0.0
pin(bsdf, 'Roughness').default_value = 0.45
# ★ 镜面反射必须归零：mask=0 处的 Base Color 是纯黑，但 Principled 仍会镜面反射世界光，
#   在「等待期 / 全黑期」留下约 0.025 的底噪（实测）。发光材质不需要镜面 —— 归零后才是真·纯黑。
_spec_names = [s.name for s in bsdf.inputs]
for _sp in ('Specular IOR Level', 'Specular'):
    if _sp in _spec_names:
        pin(bsdf, _sp).default_value = 0.0
        log.append("BSDF.%s = 0（消除镜面底噪）" % _sp)
        break
links.new(mres, pin(bsdf, 'Base Color'))
links.new(col.outputs[0], pin(bsdf, 'Emission Color'))
links.new(emul.outputs[0], pin(bsdf, 'Emission Strength'))

out = N('ShaderNodeOutputMaterial', 'OUT', '输出', 900, 0)
links.new(bsdf.outputs[0], I(out, 0))

# ---------------- 3. TVAL 关键帧：raw = frame，线性 + 线性外推 ----------------
tval.outputs[0].default_value = 1.0
tval.outputs[0].keyframe_insert('default_value', frame=1)
tval.outputs[0].default_value = 250.0
tval.outputs[0].keyframe_insert('default_value', frame=250)

lin = 0
extrap = 0
for lay in nt.animation_data.action.layers:
    for st in lay.strips:
        for cb in st.channelbags:
            for fc in cb.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
                    lin += 1
                fc.extrapolation = 'LINEAR'     # ★ 关键：外推也线性 => 任意帧 raw == frame
                fc.update()
                extrap += 1
log.append("TVAL keyframes=2 linearized=%d extrapolation=LINEAR on %d fcurve(s)" % (lin, extrap))

# ---------------- 3.5 驱动器：FB_ctrl 属性 -> 节点插槽（数据驱动）------------
# 实测（Blender 5.2，脚本 y_drv.py / y_drv2/3/4.py）：
#   · 节点插槽驱动【完全可用】：expression='frame' ★、纯常量 ★、SINGLE_PROP 取属性 ★
#     （原生通道 location/scale 与自定义属性都行，中文属性名也行）
#   · ★ driver_add() 会把表达式【自动填成当时的数值】（expr='20.0'）—— 这正是上一版
#     误判「节点驱动不生效」的根源：等于装了个常量驱动，渲染当然不变。
#   · ★ 变量 data_path 必须写双引号 '["名字"]'；写单引号会静默解析失败并返回 0。
#   · ★ Python 里 ctrl['x']=v 走 IDProperty 底层接口、【不给物体打更新标记】，
#     所以脚本改完要补 ctrl.update_tag()；UI 里拖属性走 RNA，Blender 自己会打标记。
nt.animation_data_create()
n_drv = 0
for _k, _node in NODE_OF.items():
    _nd = nodes.get(_node)
    if _nd is None:
        log.append("!! 驱动器失败：材质里没有节点 %s" % _node)
        continue
    _fc = nt.driver_add('nodes["%s"].outputs[0].default_value' % _node)
    _d = _fc.driver
    _d.type = 'SCRIPTED'
    _var = _d.variables.new()
    _var.name = 'v'
    _var.type = 'SINGLE_PROP'
    _tg = _var.targets[0]
    _tg.id_type = 'OBJECT'
    _tg.id = ctrl
    _tg.data_path = '["%s"]' % _k
    _d.expression = 'v'
    n_drv += 1
log.append("drivers: %d 个  FB_ctrl 属性 -> 节点插槽" % n_drv)

# ★★ 第 10 条：「周期帧数」自己也要自动 = 四段之和。
#    这条不是给材质用的（材质里 A_PER 早已自动求和），而是给【用户看的】。
#    实测教训：用户拖「全亮维持」到 80，材质那边周期已经变成 230，但这个属性的
#    数字还停在 174 —— 用户看到它不动，直接判定"代码逻辑没理顺 / 改了没效果"。
#    所以这个读数必须自己会跳。
#    坑同上：driver_add 会把表达式自动填成当时的数值（看到 expr='174.0' 要覆盖掉）。
ctrl.animation_data_create()
_fc = ctrl.driver_add('["%s"]' % READONLY[0])
_d = _fc.driver
_d.type = 'SCRIPTED'
for _i, _k in enumerate(_TIME_KEYS):
    _v = _d.variables.new()
    _v.name = 'p%d' % _i
    _v.type = 'SINGLE_PROP'
    _t = _v.targets[0]
    _t.id_type = 'OBJECT'
    _t.id = ctrl
    _t.data_path = '["%s"]' % _k
_d.expression = '+'.join('p%d' % _i for _i in range(len(_TIME_KEYS)))
ctrl.update_tag()
bpy.context.view_layer.update()
log.append("driver: 周期帧数 <- %s  当前 = %s（期望 %.0f）" % (
    _d.expression, ctrl[READONLY[0]], sum(P[k] for k in _TIME_KEYS)))

# ---------------- 4. 赋给平面 ----------------
for name in PLANES:
    ob = bpy.data.objects.get(name)
    if not ob:
        log.append("!! MISSING %s" % name); continue
    me = ob.data
    me.materials.clear()
    me.materials.append(mat)
    me.materials.append(src)
    for p in me.polygons:
        p.material_index = 0
    log.append("assign %-10s slots=%s faces->%s" % (
        name, [x.name if x else None for x in me.materials],
        sorted({p.material_index for p in me.polygons})))

# ---------------- 5. 回读校验 ----------------
log.append("nodes=%d links=%d users=%s" % (len(nodes), len(links), mat.users))

def feed(n, i):
    s = n.inputs[i]
    got = [l.from_node.name for l in links if l.to_socket == s]
    return got[0] if got else "=<%.4g>" % s.default_value

checks = [
    ("M_PRG.Value      <-", feed(m_prg, [i for i, s in enumerate(m_prg.inputs)
                                         if s.name == 'Value' and s.type == 'VALUE'][0]), "M_SUB"),
    ("M_PRG.FromMax    <-", feed(m_prg, [i for i, s in enumerate(m_prg.inputs)
                                         if s.name == 'From Max' and s.type == 'VALUE'][0]), "A_ACT"),
    ("M_MOD.a          <-", feed(m_mod, 0), "TVAL"),
    ("M_MOD.b          <-", feed(m_mod, 1), "A_PER"),
    ("M_SUB.a          <-", feed(m_sub, 0), "M_MOD"),
    ("M_SUB.b          <-", feed(m_sub, 1), "T_BLACK"),
    ("RO.Value         <-", feed(m_ro, [i for i, s in enumerate(m_ro.inputs)
                                        if s.name == 'Value' and s.type == 'VALUE'][0]), "M_PRG"),
    ("RO.FromMax       <-", feed(m_ro, [i for i, s in enumerate(m_ro.inputs)
                                        if s.name == 'From Max' and s.type == 'VALUE'][0]), "A_SPLO"),
    ("RO.ToMax         <-", feed(m_ro, [i for i, s in enumerate(m_ro.inputs)
                                        if s.name == 'To Max' and s.type == 'VALUE'][0]), "V_ROUT"),
    ("RI.FromMin       <-", feed(m_ri, [i for i, s in enumerate(m_ri.inputs)
                                        if s.name == 'From Min' and s.type == 'VALUE'][0]), "A_SPL"),
    ("RI.ToMax         <-", feed(m_ri, [i for i, s in enumerate(m_ri.inputs)
                                        if s.name == 'To Max' and s.type == 'VALUE'][0]), "V_RIN"),
    ("ROL.b            <-", feed(m_rolo, 1), "V_SOFT"),
    ("RIL.b            <-", feed(m_rilo, 1), "V_SOFT"),
    ("MRI.FromMax      <-", feed(mri, [i for i, s in enumerate(mri.inputs)
                                       if s.name == 'From Max' and s.type == 'VALUE'][0]), "V_SOFT"),
    ("A_PER.a          <-", feed(a_per, 0), "A_ACT"),
    ("A_PER.b          <-", feed(a_per, 1), "T_BLACK"),
]
log.append("--- CHECKS ---")

def close(got, want):
    try:
        return abs(float(got) - float(want)) <= max(1e-5, abs(float(want)) * 1e-4)
    except (TypeError, ValueError):
        return str(got) == str(want)

fails = 0
for k, got, want in checks:
    ok = close(got, want) or str(want) in str(got)
    if not ok:
        fails += 1
    log.append("  %-20s got=%-10s want=%-10s %s" % (k, got, want, "OK " if ok else "**FAIL**"))

# ---------------- 6. 解析表：每帧处在哪一段 ----------------
def clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

def ring_at(r, r_out, r_in, soft):
    return clamp01((r_out - r) / soft) * clamp01((r - r_in + soft) / soft)

def predict(f):
    period = P["周期帧数"]
    blk = P["变亮前等待"]
    active = P["变亮时长"] + P["全亮维持"] + P["变黑时长"]
    split_out = P["变亮时长"] / active
    split_in = (P["变亮时长"] + P["全亮维持"]) / active
    u = f % period
    v = u - blk
    prog = clamp01(v / active)
    k_out = clamp01(prog / split_out) if split_out > 0 else 1.0
    k_in = clamp01((prog - split_in) / (1.0 - split_in)) if split_in < 1 else 0.0
    r_out = k_out * P["满圆半径"]
    r_in = k_in * P["黑洞终半径"]
    if prog <= 0.0:
        stage = "变亮前等待(纯黑)"
    elif r_in + P["边缘柔和"] >= P["满圆半径"]:
        stage = "全黑(变黑完成)"
    elif k_out >= 1.0 and k_in <= 0.0:
        stage = "全亮维持"
    elif k_in <= 0.0:
        stage = "变亮中(半径%.2f)" % r_out
    else:
        stage = "变黑中"
    return u, prog, r_out, r_in, stage, ring_at(0.0, r_out, r_in, P["边缘柔和"])

B, G, H, E = (P["变亮前等待"], P["变亮时长"], P["全亮维持"], P["变黑时长"])
log.append("--- 周期 = %.0f 帧（四段之和，全部由 FB_ctrl 属性驱动）---" % P["周期帧数"])
log.append("    变亮前等待 0-%.0f | 变亮 %.0f-%.0f | 全亮维持 %.0f-%.0f | 变黑 %.0f-%.0f" % (
    B, B, B + G, B + G, B + G + H, B + G + H, B + G + H + E))
log.append("    （第 2 个循环起于绝对帧 %d）" % (int(P["周期帧数"]) + 1))
log.append("--- 抽样帧的解析值（覆盖各段边界）---")
for f in (1, 19, 20, 21, 45, 79, 80, 81, 103, 104, 105, 139, 173, 174,
          175, 200, 348, 349):
    u, prog, ro, ri, stage, r0 = predict(f)
    log.append("  f%3d u=%6.1f prog=%.3f R_out=%.3f R_in=%.3f ring@r=0=%.2f  %s" % (
        f, u, prog, ro, ri, r0, stage))

# --- 验证 TVAL 的线性外推：任意帧 raw 应等于帧号 ---
log.append("--- TVAL 实测（关键帧 LINEAR + extrapolation LINEAR）---")
bad = 0
for f in (1, 100, 250, 300, 500, 1000):
    scn.frame_set(f)
    e = nt.evaluated_get(bpy.context.evaluated_depsgraph_get())
    got = e.nodes["TVAL"].outputs[0].default_value
    ok = abs(got - f) < 1e-3
    bad += 0 if ok else 1
    log.append("  f%4d TVAL=%.3f  期望 %d  %s" % (f, got, f, "OK" if ok else "**FAIL**"))
log.append("  外推失败帧数=%d" % bad)

# --- 驱动器自检：写 FB_ctrl 属性 -> 读材质节点插槽 ---
# ★ 脚本侧改自定义属性必须补 ctrl.update_tag()，否则依赖图不会重算、读回旧值。
log.append("--- 驱动器自检：FB_ctrl 属性 -> 节点插槽 ---")
drv_bad = 0
for _k, _node in NODE_OF.items():
    mn, mx, _smn, _smx, _desc = UI_RANGE[_k]
    probe = mn + (mx - mn) * 0.37
    _orig = ctrl[_k]
    ctrl[_k] = probe
    ctrl.update_tag()
    bpy.context.view_layer.update()
    got = nodes[_node].outputs[0].default_value
    ok = abs(got - probe) <= max(1e-4, abs(probe) * 1e-4)
    drv_bad += 0 if ok else 1
    log.append("  ctrl['%s']=%9.4f -> %s.outputs[0]=%9.4f  %s" % (
        _k, probe, _node, got, "OK" if ok else "**FAIL**"))
    ctrl[_k] = _orig
    ctrl.update_tag()
bpy.context.view_layer.update()
log.append("  驱动器失败数=%d" % drv_bad)
fails += drv_bad
log.append("--- FB_ctrl 上的属性（这就是控制面）---")
for _k in P:
    log.append("  %-12s = %-10s  %s" % (
        _k, round(float(ctrl[_k]), 4),
        UI_RANGE.get(_k, (0, 0, 0, 0, "只读：四段之和，自动计算"))[4]))

scn.frame_set(1)
log.append("materials=%s  objects=%s" % (
    sorted(x.name for x in bpy.data.materials), sorted(o.name for o in bpy.data.objects)))
log.append("FAILS=%d" % fails)
print("\n".join(log))
