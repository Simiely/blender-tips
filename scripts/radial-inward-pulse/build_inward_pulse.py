# -*- coding: utf-8 -*-
"""
新建：径向「内收多脉冲」材质（旧材质 立体灯光_径向脉冲 完全不动）
=================================================================
需求：多个脉冲**从外往里收**、循环；脉冲之间有一小段黑色间隔；
      "脉冲最多的时候有 3 个"，黑间隔填充到网格体上。

做法：把径向图案写成一个【周期为 脉冲间距 的方波-梯形带】，沿 r 反向平移即"内收"。
      t = FRACT( r/间距 + 相位 ),  相位 = 帧号 ÷ 循环周期 (+相位偏移)
      ★ 用【循环周期(帧)】而不是【速度(周期/帧)】：一个完整循环 = 图案整体移动一个间距
      → 相位增大 ⇒ 带的位置 r = 间距×(k − 相位) 减小 ⇒ 往中心收。
      FRACT 天然环绕 ⇒ 无缝循环。

★ 间距是按**实测网格**算出来的：
      角点半径 R_max / 期望周期数 = 间距
      期望周期数取 2.8 ⇒ 任意相位下可见脉冲 ≤ 3 个（取 3.0 时首尾可能各露一条，会变 4）。
      黑间隔 = 间距 − 脉冲宽度。

★ 不动的东西：材质 立体灯光_径向脉冲 / 空物体 立体灯光_脉冲控制（只读旧材质的自发光颜色用来"类似"）。
★ 三个平面的槽：槽0 = 新材质，槽1 = 旧材质（备份，想切回去改面的 material_index 即可）。

幂等；桥 exec 环境没有 __file__，一切路径用常量。
"""
import bpy
from mathutils import Vector
import math
import collections

# ============================ 配置区 ============================
COL_NAME  = "立体灯光材质"
PLANES    = ["平面.001", "平面.002", "平面.003"]
MAT_OLD   = "立体灯光_径向脉冲"          # ★ 只读：取它的自发光颜色，别的一概不动
CTRL_OLD  = "立体灯光_脉冲控制"          # ★ 只读：只用来取圆心坐标

MAT_NEW   = "立体灯光_径向内收脉冲"      # 新建材质
CTRL_NEW  = "立体灯光_内收控制"          # 新建控制器（与旧的各自独立，位置相同）
PREFIX    = "内收"

MAX_BANDS_DEF = 3        # 期望「任意相位下可见脉冲」的上限（用于算间距，见下方计算段）

PROPS = [
    ("脉冲间距",   1.370),   # 会自动按实测 R_max 重算
    ("脉冲宽度",   0.960),   # 黑间隔 = 间距 − 宽度
    ("边缘柔和",   0.160),
    ("循环周期",   50.0),    # ★ 走完一个完整循环（黑→亮→黑）的帧数 = 1/每帧推进的周期数；负值=向外扩
    ("相位偏移",   0.000),
    ("发光强度",   1.500),   # 会按旧材质的「自发光强度」自动对齐
    ("底色亮度",   0.000),
    ("色相半径",   1.000),   # 会按实测网格半宽重算；色相色标铺满这个半径
    ("亮面半径",   1.000),   # 会按实测网格半宽重算；超出它渐隐到全黑
    ("淡出宽度",   0.200),   # 会按间距重算；亮面半径之外的过渡带宽度
]
# ★ 色相/外缘两条 ColorRamp 的色标【从旧材质实时读取】，见下方 grab_ramp()
SRC_MAT_FOR_COLOR = MAT_OLD          # 颜色来源材质
SRC_COL_NAMES = ("COL",)             # 旧材质里色相节点的名字候选
SRC_COL_LABEL = "色相"
SRC_RIM_NAMES = ("RIM",)
SRC_RIM_LABEL = "外缘"

READONLY = "可见脉冲数"
UI_RANGE = {
    "脉冲间距": (0.10, 8.00, 0.30, 4.00, "相邻脉冲中心的距离（世界单位）。黑间隔 = 间距 − 脉冲宽度"),
    "脉冲宽度": (0.02, 8.00, 0.10, 4.00, "亮带宽度（世界单位）。≥ 间距时就没有黑间隔了"),
    "边缘柔和": (0.005, 1.00, 0.02, 0.50, "亮带两侧的软边宽度（世界单位）"),
    "循环周期": (-2000.0, 2000.0, 6.0, 400.0,
                 "★ 黑→亮→黑 走完一个完整循环所需的帧数。默认 50（= 旧的 每帧0.02）；负值 = 向外扩"),
    "相位偏移": (0.000, 1.000, 0.000, 1.000, "整体相位，用来调脉冲起始落点"),
    "发光强度": (0.00, 200.00, 0.00, 60.00, "Emission 强度倍率（默认与旧材质一致 = 20）"),
    "底色亮度": (0.00, 5.00, 0.00, 3.00, "Base Color 亮度倍率（默认 0 = 只有自发光）"),
    "色相半径": (0.05, 20.00, 0.20, 8.00,
                 "色相色标铺满的半径。默认 = 网格半宽；调大 = 颜色变化更慢更靠外"),
    "亮面半径": (0.00, 20.00, 0.20, 8.00,
                 "★ 发光只在这个半径内；超出后经「淡出宽度」渐隐到全黑。默认 = 网格半宽（限制在圆内）"),
    "淡出宽度": (0.001, 5.00, 0.01, 1.00, "亮面半径之外的过渡带宽度（世界单位）"),
}
NODE_OF = {
    "脉冲间距": PREFIX + "_间距", "脉冲宽度": PREFIX + "_宽度", "边缘柔和": PREFIX + "_边缘",
    "循环周期": PREFIX + "_循环周期", "相位偏移": PREFIX + "_相位偏移",
    "发光强度": PREFIX + "_发光强度", "底色亮度": PREFIX + "_底色",
    "色相半径": PREFIX + "_色相半径",
    "亮面半径": PREFIX + "_亮面半径", "淡出宽度": PREFIX + "_淡出宽度",
}
# ==============================================================

D = bpy.data
C = bpy.context
scn = C.scene
log = []
fails = []


def chk(cond, msg):
    (log if cond else fails).append(("  ok " if cond else "  xx ") + msg)


# ---------------------------------------------------- 0. 前置：旧系统只读校核
old = D.materials.get(MAT_OLD)
if old is None:
    raise RuntimeError("旧材质 %s 不存在" % MAT_OLD)
old_users_before = old.users
old_nt_nodes = len(old.node_tree.nodes) if old.node_tree else 0
old_ctrl = D.objects.get(CTRL_OLD)
CTR = Vector(old_ctrl.location) if old_ctrl else None
log.append("旧材质 %s：users=%d 节点=%d（只读）" % (MAT_OLD, old_users_before, old_nt_nodes))
log.append("旧控制器 %s：loc=%s"
           % (CTRL_OLD, tuple(round(x, 4) for x in CTR) if CTR else "缺失"))

# ★ 配色链：从旧材质【实时读取】两条 ColorRamp 的色标 + 自发光强度（真·同一个颜色效果）
def grab_ramp(src, names, label_kw):
    if src is None or not src.use_nodes or src.node_tree is None:
        return None
    for nm in names:
        n = src.node_tree.nodes.get(nm)
        if n is not None and n.type == 'VALTORGB':
            return n
    for n in src.node_tree.nodes:
        if n.type == 'VALTORGB' and label_kw and label_kw in (n.label or ""):
            return n
    return None


_src = D.materials.get(SRC_MAT_FOR_COLOR)
_col_n = grab_ramp(_src, SRC_COL_NAMES, SRC_COL_LABEL)
_rim_n = grab_ramp(_src, SRC_RIM_NAMES, SRC_RIM_LABEL)
if _col_n is None:
    raise RuntimeError("在 %s 里找不到色相 ColorRamp（名字候选 %s / label 含 %r）"
                       % (SRC_MAT_FOR_COLOR, SRC_COL_NAMES, SRC_COL_LABEL))
COL_STOPS = [(e.position, tuple(e.color)) for e in _col_n.color_ramp.elements]
COL_INTERP = _col_n.color_ramp.interpolation
RIM_STOPS = ([(e.position, tuple(e.color)) for e in _rim_n.color_ramp.elements]
             if _rim_n is not None else [])
RIM_INTERP = _rim_n.color_ramp.interpolation if _rim_n is not None else 'EASE'
EMIT_COLOR = COL_STOPS[0][1]          # 只用于 mat.diffuse_color（视口纯色模式）
log.append("★ 从旧材质 %s 复制色相链：" % SRC_MAT_FOR_COLOR)
log.append("    色相「%s」%d 色标 %s = %s"
           % (_col_n.label or _col_n.name, len(COL_STOPS), COL_INTERP,
              [(round(p, 3), tuple(round(c, 3) for c in col[:3])) for p, col in COL_STOPS]))
if RIM_STOPS:
    log.append("    外缘「%s」%d 色标 %s = %s"
               % (_rim_n.label or _rim_n.name, len(RIM_STOPS), RIM_INTERP,
                  [(round(p, 3), tuple(round(c, 3) for c in col[:3])) for p, col in RIM_STOPS]))
else:
    log.append("    !! 旧材质里找不到外缘 ColorRamp ⇒ 不启用「外缘轻收」")

# 自发光强度：与旧材质对齐
SRC_EMIT = 20.0
if old_ctrl is not None and "自发光强度" in old_ctrl.keys():
    SRC_EMIT = float(old_ctrl["自发光强度"])
log.append("对齐旧材质「自发光强度」= %.2f" % SRC_EMIT)

# ---------------------------------------------------- 1. 实测网格 → 算圆心与 R_max
col = D.collections.get(COL_NAME)
if col is None:
    raise RuntimeError("找不到集合 %s" % COL_NAME)

pts = []
for pn in PLANES:
    ob = D.objects.get(pn)
    if ob is None:
        raise RuntimeError("网格 %s 不存在" % pn)
    mw = ob.matrix_world
    pts += [mw @ v.co for v in ob.data.vertices]
xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
center_calc = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
if CTR is None:
    CTR = center_calc
log.append("网格实测中心 = (%.4f, %.4f, %.4f) | 与旧圆心偏差 = %.4f"
           % (center_calc.x, center_calc.y, center_calc.z, (center_calc - CTR).length))
log.append("网格并集 span = (%.4f, %.4f, %.4f)"
           % (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))

R_max = max((p - CTR).length for p in pts)          # 角点半径
R_min = min((p - CTR).length for p in pts)
log.append("到圆心的半径：最小 = %.4f | 最大 R_max = %.4f" % (R_min, R_max))

# ★ 可见脉冲数的真正约束（不是简单的 R_max/d ≤ 3）：
#   亮带窗口宽 wu = w/d、彼此间隔 1；查询区间长 L = R_max/d。
#   落进区间的窗口数 ≤ L + wu  ⇒ 要 ≤ 3 条就必须 **L + wu ≤ 3**。
#   （第一版只取了 L = 2.8，扫描实测最大 4 条 —— 因为在宽占空比下首尾各能多露一条。）
# ★ 要「恒为 3 条亮环」，有效窗口要一路扣干净，公式是：
#     可见带区间 = L + 占空比 − 软边占比 − 2×最小可见宽度
#     （阈值 0.5 下亮带实际宽度 = 占空比 − 软边；两端各要留 ≥1% 周期才算"看得见"）
#   ⇒ 令它 = 3 ⇒ L = 3 + 2×最小可见宽度 − 占空比 + 软边占比
#   S_eff < 3 → 相位里会有 2 条的窗口（上一版就是这个毛病，用户看到有时只有 2 条）
#   S_eff > 3 → 会多出第 4 条
MAX_BANDS = 3
REF_FOR_COUNT = 'CIRCLE' # ★ 计数基准：'CIRCLE' = 内切圆（网格半宽）| 'CORNER' = 对角线角点
# ★ 暗区【感知】占比 = 纯黑 (1−占空比) + 两侧软边 2×软边占比
#   本版目标 10%：占空比 0.94 ⇒ 纯黑 6%，软边 0.02 ⇒ 两侧 4%，合计 10%
DUTY      = 0.94
EDGE_FRAC = 0.02
FILTER_FRAC = 0.01       # 「看得见」的最小宽度（占周期）——扫描判据，也是视觉判据
MARGIN    = 0.003        # 极小余量，防浮点把窗口顶过 N 而多出一条
# 可见带窗口 = L + 占空比 − 软边占比 − 2×最小可见宽度，要它 ≈ N
#   ⇒ L = N − 余量 − 占空比 + 软边占比 + 2×最小可见宽度
PERIODS_ACROSS = (MAX_BANDS - MARGIN - DUTY + EDGE_FRAC
                  + 2 * FILTER_FRAC)               # ≈ 2.097

# ★ 亮面裁切：把发光限制在一个圆内（超出「亮面半径」渐隐到全黑）
#   —— 这就是「亮面的面积缩小」，同时让四角不再多出 4~5 条环
GLOW_FADE_FRAC = 0.25    # 淡出宽度 = 间距 × 这个比例

# 暗区【感知】占比 = 纯黑间隔 + 两侧软边 = (1 − 占空比) + 2 × 软边占比

half_w = (max(xs) - min(xs)) / 2.0                 # 正方形半宽 = 内切圆半径
R_REF = half_w if REF_FOR_COUNT == 'CIRCLE' else R_max
log.append("★ 计数基准 = %s：R_ref = %.4f（内切圆 %.4f / 角点 %.4f）"
           % ('内切圆（看圆）' if REF_FOR_COUNT == 'CIRCLE' else '角点（看对角线）',
              R_REF, half_w, R_max))

D_SPACING = round(R_REF / PERIODS_ACROSS, 4)      # ★ 算出来的间距
W_DEFAULT = round(D_SPACING * DUTY, 4)            # 亮带；黑间隔 = 间距 − 宽度
E_DEFAULT = round(D_SPACING * EDGE_FRAC, 4)       # 单侧软边宽度
HUE_DEFAULT = round(half_w, 4)                    # ★ 色相铺满网格半宽（与旧材质同比例）
GLOW_DEFAULT = round(R_REF, 4)                    # ★ 亮面半径 = 内切圆（发光限制在圆内）
FADE_DEFAULT = round(D_SPACING * GLOW_FADE_FRAC, 4)

# 按实测值重建默认表（位置索引太脆，改成显式构造）
_DEF = {"脉冲间距": D_SPACING, "脉冲宽度": W_DEFAULT, "边缘柔和": E_DEFAULT,
        "循环周期": 50.0, "相位偏移": 0.000,
        "发光强度": SRC_EMIT, "底色亮度": 0.000, "色相半径": HUE_DEFAULT,
        "亮面半径": GLOW_DEFAULT, "淡出宽度": FADE_DEFAULT}
PROPS = [(k, _DEF[k]) for k in ("脉冲间距", "脉冲宽度", "边缘柔和", "循环周期",
                                "相位偏移", "发光强度", "底色亮度", "色相半径",
                                "亮面半径", "淡出宽度")]

log.append("★ 计算：要「恒为 %d 条」需【可见带窗口】"
           "= L + 占空比 − 软边 − 2×最小可见宽 ≈ %d" % (MAX_BANDS, MAX_BANDS))
log.append("    占空比 %.2f、软边 %.2f、最小可见宽 %.2f、余量 %.4f ⇒ L = %.4f"
           % (DUTY, EDGE_FRAC, FILTER_FRAC, MARGIN, PERIODS_ACROSS))
log.append("    间距 = %s / %.4f = %.4f"
           % ('%.4f' % R_REF, PERIODS_ACROSS, D_SPACING))
_lv = R_REF / D_SPACING
_wu = W_DEFAULT / D_SPACING
_eu = E_DEFAULT / D_SPACING
log.append("    实际 L(ref) = %.5f、占空比 = %.5f、软边 = %.5f" % (_lv, _wu, _eu))
log.append("    可见带窗口 = %.5f − 2×%.2f = %.5f（目标 %d）"
           % (_lv + _wu - _eu, FILTER_FRAC, _lv + _wu - _eu - 2 * FILTER_FRAC, MAX_BANDS))
log.append("    阈值 0.5 下亮带可见宽度 = 占空比 − 软边 = %.5f" % (_wu - _eu))
log.append("★ 黑间隔 = 间距 %.4f − 宽度 %.4f = %.4f（纯黑占周期 %.1f%%）"
           % (D_SPACING, W_DEFAULT, D_SPACING - W_DEFAULT, 100.0 * (1 - _wu)))
log.append("★ 暗区【感知】占比 = 纯黑 %.1f%% + 两侧软边 %.1f%% = %.1f%%"
           % (100.0 * (1 - _wu), 100.0 * 2 * _eu, 100.0 * ((1 - _wu) + 2 * _eu)))
log.append("★ 各处可见环数（同一公式 L+R−软边−2×最小可见宽）：")
for _lbl, _rr in (("内切圆 %.4f（看圆）" % half_w, half_w),
                  ("角点   %.4f（看对角）" % R_max, R_max)):
    _L_ = _rr / D_SPACING
    log.append("    %s ⇒ L=%.3f ⇒ 可见环数 ≈ %.2f"
               % (_lbl, _L_, _L_ + _wu - _eu - 2 * FILTER_FRAC))
_CYC = float(_DEF["循环周期"])          # 此刻控制器还没建，用默认表里的值
log.append("★ 循环周期 = %.1f 帧/圈 ⇒ 每帧推进 %.5f 个周期；场景帧 %d–%d 共约 %.2f 圈"
           % (_CYC, 1.0 / _CYC, scn.frame_start, scn.frame_end,
              (scn.frame_end - scn.frame_start) / _CYC))
log.append("★ 亮面裁切：半径 ≤ %.4f 全亮，到 %.4f 渐隐为全黑（四角落在裁切外 ⇒ 不再多出环）"
           % (GLOW_DEFAULT, GLOW_DEFAULT + FADE_DEFAULT))
log.append("★ 色相半径 = 网格半宽 %.4f（色标铺满它，与旧材质同比例）" % HUE_DEFAULT)

# ---------------------------------------------------- 2. 控制器
ctl = D.objects.get(CTRL_NEW)
if ctl is None:
    ctl = D.objects.new(CTRL_NEW, None)
    col.objects.link(ctl)
    log.append("新建控制器 %s" % CTRL_NEW)
else:
    log.append("复用控制器 %s" % CTRL_NEW)
if ctl.name not in [o.name for o in col.objects]:
    try:
        col.objects.link(ctl)
    except Exception:
        pass
ctl.location = CTR                             # ★ 同一个圆心
ctl.rotation_euler = (0.0, 0.0, 0.0)
ctl.scale = (1.0, 1.0, 1.0)
ctl.empty_display_type = 'CIRCLE'
ctl.empty_display_size = max(0.2, R_max * 0.2)

if ctl.animation_data:
    ctl.animation_data_clear()
for k in [k for k in ctl.keys() if k != "_RNA_UI"]:
    del ctl[k]
for k, v in PROPS:
    ctl[k] = v
    mn, mx, smn, smx, desc = UI_RANGE[k]
    ctl.id_properties_ui(k).update(min=mn, max=mx, soft_min=smn, soft_max=smx,
                                   description=desc)
# 只读派生：可见脉冲数 = R_max / 脉冲间距
ctl[READONLY] = round(R_max / D_SPACING, 3)
ctl.id_properties_ui(READONLY).update(
    min=0.0, max=100.0, soft_min=0.0, soft_max=10.0,
    description="自动计算（只读）= 角点半径 %.4f ÷ 脉冲间距" % R_max)
ctl.update_tag()
log.append("控制器属性 = %s" % {k: round(float(ctl[k]), 4) for k, _ in PROPS})

# ---------------------------------------------------- 3. 材质与节点
mat = D.materials.get(MAT_NEW)
if mat is None:
    mat = D.materials.new(MAT_NEW)
    log.append("新建材质 %s" % MAT_NEW)
else:
    log.append("复用材质 %s（重建节点树）" % MAT_NEW)
mat.use_nodes = True
mat.use_backface_culling = False
mat.diffuse_color = EMIT_COLOR
nt = mat.node_tree
nt.nodes.clear()
if nt.animation_data:
    nt.animation_data_clear()

P = PREFIX


def N(t, nm, x, y):
    n = nt.nodes.new(t)
    n.name = n.label = nm
    n.location = (x, y)
    return n


def V(nm, val, x, y):
    n = N('ShaderNodeValue', nm, x, y)
    n.outputs[0].default_value = val
    return n


def MATH(nm, op, x, y, a=None, b=None, c=None):
    n = N('ShaderNodeMath', nm, x, y)
    n.operation = op
    for i, v in ((0, a), (1, b), (2, c)):
        if v is not None:
            n.inputs[i].default_value = v
    return n


def mrsock(n, name):
    """MapRange 有两套同名不同类型的插槽（VALUE / VECTOR）⇒ 必须按 (name,type) 取。"""
    for i, sk in enumerate(n.inputs):
        if sk.name == name and sk.type == 'VALUE':
            return i
    raise RuntimeError("MapRange %s 找不到插槽 %s/VALUE" % (n.name, name))


def MR(nm, x, y, fmin=0.0, fmax=1.0, tmin=0.0, tmax=1.0):
    n = N('ShaderNodeMapRange', nm, x, y)
    n.inputs[mrsock(n, 'From Min')].default_value = fmin
    n.inputs[mrsock(n, 'From Max')].default_value = fmax
    n.inputs[mrsock(n, 'To Min')].default_value = tmin
    n.inputs[mrsock(n, 'To Max')].default_value = tmax
    n.clamp = True
    return n


def I(n, i):
    return n.inputs[i]


def L(a, b):
    nt.links.new(a, b)


# ---- 径向骨架 ----
tex = N('ShaderNodeTexCoord', P + '_纹理坐标', -1600, 200)
tex.object = ctl
mp = N('ShaderNodeMapping', P + '_映射', -1400, 200)
rlen = N('ShaderNodeVectorMath', P + '_半径r', -1200, 200)
rlen.operation = 'LENGTH'
L(tex.outputs['Object'], I(mp, 0))
L(mp.outputs[0], I(rlen, 0))

# ---- 归一化 + 相位 ----
v_d = V(P + '_间距', D_SPACING, -1200, 460)
q = MATH(P + '_归一化r', 'DIVIDE', -1000, 200)          # q = r / 间距
L(rlen.outputs['Value'], I(q, 0))
L(v_d.outputs[0], I(q, 1))

v_spd = V(P + '_循环周期', 50.0, -1400, 640)
# ★★ 帧号 × 速度：两个因子各自落在【Value 节点】上，再让 Math 相乘。
#    ⚠️ 千万别把驱动直接写在 Math 节点的【输出】插槽上 —— 输出由节点运算决定，
#    驱动会被覆盖成无效 ⇒ 该项恒 0 ⇒ 相位不变 ⇒ 画面静止（本机踩过，用户报"拖进度条没动态"）。
v_fr = V(P + '_帧号', 0.0, -1400, 780)
mul_spd = MATH(P + '_相位推进', 'DIVIDE', -1000, 700)   # 帧号 ÷ 循环周期
L(v_fr.outputs[0], I(mul_spd, 0))
L(v_spd.outputs[0], I(mul_spd, 1))
v_ph0 = V(P + '_相位偏移', 0.0, -1200, 940)
add_ph = MATH(P + '_相位', 'ADD', -820, 700)             # 帧号×速度 + 相位偏移
L(mul_spd.outputs[0], I(add_ph, 0))
L(v_ph0.outputs[0], I(add_ph, 1))
t0 = MATH(P + '_相位叠加', 'ADD', -640, 300)             # q + 相位
L(q.outputs[0], I(t0, 0))
L(add_ph.outputs[0], I(t0, 1))
tfr = MATH(P + '_周期取模', 'FRACT', -460, 300)
L(t0.outputs[0], I(tfr, 0))

# ---- 梯形脉冲剖面 ----
v_w = V(P + '_宽度', W_DEFAULT, -1200, 940)
v_e = V(P + '_边缘', E_DEFAULT, -1200, 1100)
wu = MATH(P + '_宽度归一', 'DIVIDE', -1000, 940)         # w / d
L(v_w.outputs[0], I(wu, 0))
L(v_d.outputs[0], I(wu, 1))
wu_c = MATH(P + '_宽度夹取', 'MINIMUM', -820, 940)       # min(wu, 1) ⇒ 黑间隔不为负
I(wu_c, 1).default_value = 1.0
L(wu.outputs[0], I(wu_c, 0))
eu = MATH(P + '_边缘归一', 'DIVIDE', -1000, 1100)        # e / d
L(v_e.outputs[0], I(eu, 0))
L(v_d.outputs[0], I(eu, 1))
wu_minus_eu = MATH(P + '_降沿起点', 'SUBTRACT', -640, 1100)
L(wu_c.outputs[0], I(wu_minus_eu, 0))
L(eu.outputs[0], I(wu_minus_eu, 1))

mr_up = MR(P + '_上升沿', -280, 420, 0.0, 1.0, 0.0, 1.0)   # FromMax 走连线
L(tfr.outputs[0], mr_up.inputs[mrsock(mr_up, 'Value')])
L(eu.outputs[0],  mr_up.inputs[mrsock(mr_up, 'From Max')])        # FromMax = e/d
mr_dn = MR(P + '_下降沿', -280, 200, 0.0, 1.0, 1.0, 0.0)   # From* 走连线
L(tfr.outputs[0], mr_dn.inputs[mrsock(mr_dn, 'Value')])
L(wu_minus_eu.outputs[0], mr_dn.inputs[mrsock(mr_dn, 'From Min')])  # FromMin = wu − eu
L(wu_c.outputs[0],        mr_dn.inputs[mrsock(mr_dn, 'From Max')])  # FromMax = wu
band = MATH(P + '_脉冲', 'MULTIPLY', -80, 300)
L(mr_up.outputs[0], I(band, 0))
L(mr_dn.outputs[0], I(band, 1))

# ---- 配色链（★ 色标从旧材质实时复制；色调 = rn 的函数）----
def RAMP(nm, x, y, stops, interp):
    n = N('ShaderNodeValToRGB', nm, x, y)
    cr = n.color_ramp
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position = stops[0][0]
    cr.elements[0].color = stops[0][1]
    for st in stops[1:]:
        e = cr.elements.new(st[0])
        e.color = st[1]
    cr.interpolation = interp
    return n


def msock(n, name, typ, out=False):
    coll = n.outputs if out else n.inputs
    for i, s in enumerate(coll):
        if s.name == name and s.type == typ:
            return i
    raise RuntimeError("节点 %s 找不到 %s/%s" % (n.name, name, typ))


# rn = r / 色相半径 —— 旧材质的色标是在 r∈[0,1] 上铺的（那时网格半宽正好 1.0），
# 现在网格半宽 2.0146，不归一化的话超过 1 的部分全被钳到最后一个色标（暗红）。
v_hue = V(P + '_色相半径', HUE_DEFAULT, -1400, 1180)
rn = MATH(P + '_色相归一', 'DIVIDE', -1000, 1180)
L(rlen.outputs['Value'], I(rn, 0))
L(v_hue.outputs[0], I(rn, 1))

colr = RAMP(P + '_色相', -820, 1180, COL_STOPS, COL_INTERP)
L(rn.outputs[0], colr.inputs[0])          # ⚠ ColorRamp 的输入 socket name='Factor'（identifier='Fac'）⇒ 用索引

# mask = band × RIM（外缘轻收；旧材质没有 RIM 就跳过）
mask = MATH(P + '_掩码', 'MULTIPLY', 60, 460)
L(band.outputs[0], I(mask, 0))
if RIM_STOPS:
    rimn = RAMP(P + '_外缘', -820, 1420, RIM_STOPS, RIM_INTERP)
    L(rn.outputs[0], rimn.inputs[0])
    L(rimn.outputs['Color'], I(mask, 1))   # 颜色→float 走 Blender 隐式转换（取亮度）
else:
    rimn = None
    I(mask, 1).default_value = 1.0

# ★ 亮面裁切：发光限制在「亮面半径」内，超出后经「淡出宽度」渐隐到全黑
v_glow = V(P + '_亮面半径', GLOW_DEFAULT, -1400, 1540)
v_fade = V(P + '_淡出宽度', FADE_DEFAULT, -1400, 1680)
sub_rg = MATH(P + '_裁切距离', 'SUBTRACT', -1000, 1540)   # r − 亮面半径
L(rlen.outputs['Value'], I(sub_rg, 0))
L(v_glow.outputs[0], I(sub_rg, 1))
div_cut = MATH(P + '_裁切归一', 'DIVIDE', -820, 1540)     # ÷ 淡出宽度 ⇒ 0..1
L(sub_rg.outputs[0], I(div_cut, 0))
L(v_fade.outputs[0], I(div_cut, 1))
mr_cut = MR(P + '_裁切', -640, 1540, 0.0, 1.0, 1.0, 0.0)  # 0→1 落到 1→0（clamp）
L(div_cut.outputs[0], mr_cut.inputs[mrsock(mr_cut, 'Value')])
mask_c = MATH(P + '_掩码裁切', 'MULTIPLY', 120, 620)
L(mask.outputs[0], I(mask_c, 0))
L(mr_cut.outputs[0], I(mask_c, 1))

# ---- 输出 ----
v_emit = V(P + '_发光强度', SRC_EMIT, -1400, 1260)
mul_emit = MATH(P + '_自发光', 'MULTIPLY', 300, 620)
L(mask_c.outputs[0], I(mul_emit, 0))
L(v_emit.outputs[0], I(mul_emit, 1))
v_base = V(P + '_底色', 0.0, -1400, 1420)
mul_base = MATH(P + '_底色亮度', 'MULTIPLY', 300, 400)
L(mask_c.outputs[0], I(mul_base, 0))
L(v_base.outputs[0], I(mul_base, 1))

bsdf = N('ShaderNodeBsdfPrincipled', P + '_发光主体', 760, 460)
outn = N('ShaderNodeOutputMaterial', '材质输出', 1000, 460)
if 'Specular IOR Level' in bsdf.inputs:
    bsdf.inputs['Specular IOR Level'].default_value = 0.0
bsdf.inputs['Emission Color'].default_value = EMIT_COLOR     # 会被下面连线覆盖，仅作兜底
bsdf.inputs['Roughness'].default_value = 0.45

# Base Color = 色相 × (掩码 × 底色亮度) —— 与旧材质的 BASE_MIX 同构
bmix = N('ShaderNodeMix', P + '_底色混合', 540, 220)
bmix.data_type = 'RGBA'
bmix.blend_type = 'MULTIPLY'
bmix.inputs[msock(bmix, 'Factor', 'VALUE')].default_value = 1.0
L(colr.outputs['Color'], bmix.inputs[msock(bmix, 'A', 'RGBA')])
L(mul_base.outputs[0], bmix.inputs[msock(bmix, 'B', 'RGBA')])

L(colr.outputs['Color'], bsdf.inputs['Emission Color'])      # ★ 颜色 = 色相色带
L(bmix.outputs[msock(bmix, 'Result', 'RGBA', out=True)], bsdf.inputs['Base Color'])
L(mul_emit.outputs[0], bsdf.inputs['Emission Strength'])
L(bsdf.outputs['BSDF'], outn.inputs['Surface'])

# ---------------------------------------------------- 4. 驱动
def drv(sock, expr, vars_):
    fc = sock.driver_add('default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    for v in list(d.variables):
        d.variables.remove(v)
    for vn, idt, idd, path in vars_:
        v = d.variables.new()
        v.name = vn
        v.type = 'SINGLE_PROP'
        t = v.targets[0]
        t.id_type = idt
        t.id = idd
        t.data_path = path
    d.expression = expr          # ★ driver_add 会把表达式填成当时数值，必须覆盖
    fc.update()
    return fc


drv(v_d.outputs[0],    'dd', [('dd', 'OBJECT', ctl, '["脉冲间距"]')])
drv(v_w.outputs[0],    'ww', [('ww', 'OBJECT', ctl, '["脉冲宽度"]')])
drv(v_e.outputs[0],    'ee', [('ee', 'OBJECT', ctl, '["边缘柔和"]')])
drv(v_hue.outputs[0],  'hh', [('hh', 'OBJECT', ctl, '["色相半径"]')])
drv(v_glow.outputs[0], 'gr', [('gr', 'OBJECT', ctl, '["亮面半径"]')])
drv(v_fade.outputs[0], 'gf', [('gf', 'OBJECT', ctl, '["淡出宽度"]')])
drv(v_spd.outputs[0],  'pd', [('pd', 'OBJECT', ctl, '["循环周期"]')])
drv(v_ph0.outputs[0],  'p0', [('p0', 'OBJECT', ctl, '["相位偏移"]')])
drv(v_emit.outputs[0], 'em', [('em', 'OBJECT', ctl, '["发光强度"]')])
drv(v_base.outputs[0], 'bs', [('bs', 'OBJECT', ctl, '["底色亮度"]')])
# ★ 帧号：单独一个 Value 节点承载，SINGLE_PROP 指 scene.frame_current
#   （不依赖 auto-execute；拖动时间轴时依赖图会重算它 → 相位推进 → 脉冲移动）
drv(v_fr.outputs[0], 'fr', [('fr', 'SCENE', scene, 'frame_current')])
# 只读派生：可见脉冲数 = R_max / 间距
cdrv = ctl.driver_add('["%s"]' % READONLY)
cdrv.driver.type = 'SCRIPTED'
for v in list(cdrv.driver.variables):
    cdrv.driver.variables.remove(v)
_v = cdrv.driver.variables.new(); _v.name = 'dd'; _v.type = 'SINGLE_PROP'
_t = _v.targets[0]; _t.id_type = 'OBJECT'; _t.id = ctl; _t.data_path = '["脉冲间距"]'
cdrv.driver.expression = '%.6f / dd' % R_max
log.append("驱动：材质 %d 条 + 控制器 1 条（可见脉冲数）"
           % len(nt.animation_data.drivers))
# ★★ 守卫：所有材质驱动必须挂在【Value 节点】的输出上。
#    挂在 Math / MapRange 等【计算节点】的输出上 = 被节点自身的运算覆盖 = 等于没写。
#    （本机就是这一条没守：相位推进那项恒 0，用户拖时间轴画面完全静止。）
_bad = []
for d in nt.animation_data.drivers:
    p = d.data_path
    nm = p.split('"')[1] if '"' in p else None
    _n = nt.nodes.get(nm) if nm else None
    if _n is None or _n.type != 'VALUE':
        _bad.append((p, _n.type if _n else None))
chk(not _bad, "★ 所有驱动都挂在 Value 节点输出上（实际挂错的：%s）" % _bad)

# ---------------------------------------------------- 5. 指派（新在槽0，旧在槽1）
for pn in PLANES:
    ob = D.objects.get(pn)
    me = ob.data
    if me.users > 1:
        ob.data = me = me.copy()
        log.append("  %s 网格数据被共享，已独立化" % pn)
    me.materials.clear()
    me.materials.append(mat)
    me.materials.append(old)          # ★ 旧材质放槽1当备份，材质本身不动
    for p in me.polygons:
        p.material_index = 0
    log.append("  %s → 槽 = %s | 面 index = %s"
               % (pn, [x.name if x else None for x in me.materials],
                  sorted({p.material_index for p in me.polygons})))

bpy.context.view_layer.update()
log.append("节点 %d / 连线 %d / users %d" % (len(nt.nodes), len(nt.links), mat.users))

# ---------------------------------------------------- 6. 自检
def feed(n, idx):
    s = n.inputs[idx]
    got = [l.from_node.name for l in nt.links if l.to_socket == s]
    return got[0] if got else "=<%.4g>" % s.default_value


log.append("--- 连线自检 ---")
for n, idx, want in [
    (q, 0, P + '_半径r'), (q, 1, P + '_间距'),
    (t0, 0, P + '_归一化r'), (t0, 1, P + '_相位'),
    (tfr, 0, P + '_相位叠加'),
    (mul_spd, 0, P + '_帧号'), (mul_spd, 1, P + '_循环周期'),
    (add_ph, 0, P + '_相位推进'), (add_ph, 1, P + '_相位偏移'),
    (mr_up, 0, P + '_周期取模'),
    (mr_dn, 0, P + '_周期取模'),
    (band, 0, P + '_上升沿'), (band, 1, P + '_下降沿'),
    (rn, 0, P + '_半径r'), (rn, 1, P + '_色相半径'),
    (colr, 0, P + '_色相归一'),
    (mask, 0, P + '_脉冲'), (mask, 1, P + '_外缘'),
    (sub_rg, 0, P + '_半径r'), (sub_rg, 1, P + '_亮面半径'),
    (div_cut, 0, P + '_裁切距离'), (div_cut, 1, P + '_淡出宽度'),
    (mr_cut, 0, P + '_裁切归一'),
    (mask_c, 0, P + '_掩码'), (mask_c, 1, P + '_裁切'),
    (mul_emit, 0, P + '_掩码裁切'), (mul_emit, 1, P + '_发光强度'),
    (mul_base, 0, P + '_掩码裁切'), (mul_base, 1, P + '_底色'),
]:
    got = feed(n, idx)
    chk(got == want, "%s.in[%d] <- %s（期望 %s）" % (n.name, idx, got, want))
chk(len(nt.nodes) == 39, "节点数 = 39（实际 %d）" % len(nt.nodes))
chk(len(nt.links) == 48, "连线数 = 48（实际 %d）" % len(nt.links))
# ★ 亮面裁切必须真的接进发光/底色链（否则四角仍会亮）
chk(feed(mul_emit, 0) == P + '_掩码裁切', "发光取自【裁切后】的掩码")
chk(feed(mul_base, 0) == P + '_掩码裁切', "底色取自【裁切后】的掩码")
# ★ 配色链断言：颜色必须来自色相色带，不是常量白
_ec = [l for l in nt.links if l.to_node == bsdf and l.to_socket.name == 'Emission Color']
chk(bool(_ec) and _ec[0].from_node == colr,
    "Emission Color 来自色相 ColorRamp（实际 %s）"
    % ([l.from_node.name for l in _ec] or "未连线"))
_nc = len(colr.color_ramp.elements)
chk(_nc == len(COL_STOPS), "新色相色标数 = %d（与旧材质一致）" % _nc)
chk([(round(e.position, 4), tuple(round(c, 4) for c in e.color))
     for e in colr.color_ramp.elements]
    == [(round(p, 4), tuple(round(c, 4) for c in col)) for p, col in COL_STOPS],
    "新色相色标与旧材质逐项一致")

log.append("--- 可见脉冲数扫描（解析式：任意相位下最多几条亮带）---")
d_ = D_SPACING
w_ = W_DEFAULT
e_ = E_DEFAULT
eu_n = e_ / d_
wu_n = min(w_ / d_, 1.0)


def band_of(t):
    """与节点链同式的梯形剖面：f_up × f_dn。"""
    up = min(1.0, max(0.0, t / eu_n)) if eu_n > 0 else 1.0
    dn = min(1.0, max(0.0, (wu_n - t) / eu_n)) if eu_n > 0 else 1.0
    return up * dn


def scan_counts(r_hi, n_ph=600, n_s=4000):
    """在半径 [0, r_hi] 上扫相位，返回 (最小环数, 最大环数, 恰为 MAX_BANDS 的相位占比)。
    只统计「看得见」的带：径向宽度 ≥ FILTER_FRAC 个周期（滤掉边界上刀尖似的碎屑）。"""
    step_ = r_hi / n_s
    worst_, least_, n_exact = 0, 99, 0
    for k in range(n_ph):
        ph = k / n_ph
        prev = False
        runs, cur = [], 0
        for i in range(n_s + 1):
            r = r_hi * i / n_s
            t = math.fmod(r / d_ + ph, 1.0)
            if t < 0:
                t += 1.0
            b = band_of(t) > 0.5
            if b:
                cur += 1
            elif prev:
                runs.append(cur)
                cur = 0
            prev = b
        if cur:
            runs.append(cur)
        cnt = len([w__ for w__ in runs if w__ * step_ >= FILTER_FRAC * d_])
        if cnt == MAX_BANDS:
            n_exact += 1
        worst_ = max(worst_, cnt)
        least_ = min(least_, cnt)
    return least_, worst_, n_exact / float(n_ph)


_c_l, _c_w, _c_f = scan_counts(R_REF)
_k_l, _k_w, _k_f = scan_counts(R_max)
chk(_c_w <= MAX_BANDS, "以内切圆计数：环数从不超过 %d（最大 %d）" % (MAX_BANDS, _c_w))
chk(_c_f >= 0.99, "★ 以内切圆计数：环数【恒为】%d ⇒ 占 %.2f%%（最小 %d）"
    % (MAX_BANDS, 100.0 * _c_f, _c_l))
log.append("    内切圆 r≤%.4f（看圆）：最小 %d / 最大 %d；恰 %d 条占 %.2f%%"
           % (R_REF, _c_l, _c_w, MAX_BANDS, 100.0 * _c_f))
log.append("    到角点 r≤%.4f（看对角）：最小 %d / 最大 %d；恰 %d 条占 %.2f%%"
           % (R_max, _k_l, _k_w, MAX_BANDS, 100.0 * _k_f))

log.append("--- 驱动/自检：改属性 → 节点读回 ---")
def ev(nm):
    dg = bpy.context.evaluated_depsgraph_get()
    return mat.evaluated_get(dg).node_tree.nodes[nm].outputs[0].default_value

ORIG = {k: ctl[k] for k, _ in PROPS} | {READONLY: ctl[READONLY]}
PROBE = {"脉冲间距": 1.111, "脉冲宽度": 0.777, "边缘柔和": 0.123,
         "循环周期": 37.0, "相位偏移": 0.456, "发光强度": 3.3,
         "底色亮度": 0.9, "色相半径": 1.7, "亮面半径": 1.4, "淡出宽度": 0.21}
for k, v in PROBE.items():
    ctl[k] = v
    ctl.update_tag()
    bpy.context.view_layer.update()
    got = float(ev(NODE_OF[k]))
    chk(abs(got - v) < 1e-4, "%s=%s → 节点 %s = %.4f" % (k, v, NODE_OF[k], got))
for k, v in ORIG.items():
    ctl[k] = v
ctl.update_tag()
bpy.context.view_layer.update()
chk(all(abs(float(ctl[k]) - float(v)) < 1e-9 for k, v in ORIG.items()), "属性已还原")
chk(abs(float(ctl[READONLY]) - R_max / float(ctl["脉冲间距"])) < 1e-6,
    "只读 可见脉冲数 = %.3f（= %.4f / %.4f）"
    % (float(ctl[READONLY]), R_max, float(ctl["脉冲间距"])))

# ★ 帧号响应自检 —— 拖时间轴有没有动态，全看这条链通不通
log.append("--- 帧号响应自检（拖时间轴）---")
_f0 = scn.frame_current
for f in (1, 60, 137, 300):
    scn.frame_set(f)
    bpy.context.view_layer.update()
    gv = float(ev(P + '_帧号'))
    chk(abs(gv - float(f)) < 1e-3, "帧 %d → 帧号节点 = %.3f" % (f, gv))
scn.frame_set(int(_f0))
bpy.context.view_layer.update()
chk(int(scn.frame_current) == int(_f0), "帧已还原为 %d" % int(_f0))

# 旧材质必须原封不动
chk(old.users == old_users_before, "旧材质 users 未变（%d）" % old.users)
chk(len(old.node_tree.nodes) == old_nt_nodes, "旧材质节点数未变（%d）" % len(old.node_tree.nodes))
cnt = collections.Counter(o.type for o in D.objects)
log.append("对象构成 = %s | 材质总数 = %d | 文本块 = %d"
           % (dict(cnt), len(D.materials), len(D.texts)))

print("\n".join(log))
print()
print("FAILS=%d" % len(fails))
for f in fails:
    print(f)
