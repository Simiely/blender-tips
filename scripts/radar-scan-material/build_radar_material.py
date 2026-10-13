# 平面「雷达扫描」空间材质（Y 轴投射 · 极坐标角度扫掠 + 拖尾）
# 参考:
#   docs/材质与驱动规范.md            （atan2 投影 / FLOORED_MODULO / Object 坐标不跟随旋转）
#   docs/材质参数统一控制器与实时面板.md（控制空物体 = 圆心 + 参数载体）
#   skills/blender-cylinder-spiral-material（Math 域波形，别让 ColorRamp 兼职）
# 用法: python send.py build_radar_material.py   （桥脚本见 scripts/blender-remote-control/）
#
# 空间材质（非 UV）: 纹理坐标(Object) → 锚点空物体 = 世界坐标相对该空物体
# Y 轴投射: 只读 X / Z 两个分量，Y 分量被丢弃 ⇒ 图案沿世界 Y 轴无变化（= 沿 Y 投射）
import bpy
import math
from mathutils import Vector

PLANE = "平面"              # 目标网格体名
MAT = "平面_雷达扫描"        # 材质名
CTRL = "雷达控制"            # 控制空物体（坐标系原点 + 参数载体）
COLL = "材质调整"            # 控制空物体所在集合（不存在则放场景根）

TAU = 2.0 * math.pi


# ---------- 0. 只读侦察目标平面 ----------
ob = bpy.data.objects.get(PLANE)
assert ob is not None and ob.type == 'MESH', "找不到网格体 " + PLANE

mw = ob.matrix_world
pts = [mw @ v.co for v in ob.data.vertices]
cx, cy, cz = (sum(p[i] for p in pts) / len(pts) for i in range(3))
half_x = (max(p.x for p in pts) - min(p.x for p in pts)) / 2
half_z = (max(p.z for p in pts) - min(p.z for p in pts)) / 2
half = min(half_x, half_z)
print("[侦察] %s 世界中心=(%.4f,%.4f,%.4f) 面内半宽 X=%.4f Z=%.4f → 用 %.4f" %
      (PLANE, cx, cy, cz, half_x, half_z, half))

# ---------- 1. 控制空物体（坐标系原点 + 参数载体） ----------
ctl = bpy.data.objects.get(CTRL)
if ctl is None:
    ctl = bpy.data.objects.new(CTRL, None)
    coll = bpy.data.collections.get(COLL) or bpy.context.scene.collection
    coll.objects.link(ctl)
ctl.parent = None
ctl.location = (cx, cy, cz)
ctl.rotation_euler = (0.0, 0.0, 0.0)
ctl.scale = (1.0, 1.0, 1.0)

# (默认值, 下限, 上限, 说明)。键名即 UI 显示名（中文键 = 中文滑块）
DEFAULTS = {
    "扫描速度": (110.0, 0.0, 720.0, "扫描头角速度（度/秒）"),
    "扫描条数": (5.0, 1.0, 24.0, "同时存在的扫描条数"),
    "拖尾长度": (129.0, 0.0, 360.0, "每条的拖尾角度（度）"),
    "扫描方向": (1.0, -1.0, 1.0, "1=逆时针(屏幕)  -1=顺时针"),
    "亮面半径": (round(0.84 * half, 4), 0.0, 10000.0, "亮面裁切半径（米），圆外纯黑"),
    "淡出宽度": (round(0.03 * half, 4), 0.0, 10000.0, "亮面外缘淡出宽度（米）"),
    "中心点半径": (round(0.03 * half, 4), 0.0, 10000.0, "中心亮点半径（米）"),
    "头部线宽": (0.004, 0.0, 0.2, "扫描头亮线的角宽（圈；0.004≈1.4°）"),
    "拖尾曲率": (1.8, 0.2, 8.0, "拖尾衰减指数（越大尾部越暗越快）"),
    "环数": (4.0, 0.0, 32.0, "网格同心圆环数"),
    "网格亮度": (0.12, 0.0, 1.0, "同心圆网格亮度"),
    "发光强度": (8.0, 0.0, 100.0, "自发光强度倍数"),
}
for k, (v, lo, hi, desc) in DEFAULTS.items():
    if k not in ctl:
        ctl[k] = v
    try:
        ctl.id_properties_ui(k).update(min=lo, soft_min=lo, soft_max=hi, max=hi, description=desc)
    except Exception as e:
        print("  (UI 元数据跳过)", k, e)

# ---------- 2. 材质与空节点树 ----------
mat = bpy.data.materials.get(MAT)
if mat is None:
    mat = bpy.data.materials.new(MAT)
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)


def node(t, name):
    n = nt.nodes.new(t)
    n.name = name
    n.label = name
    return n


def mathop(name, op, a=None, b=None, c=None):
    n = node('ShaderNodeMath', name)
    n.operation = op
    if a is not None:
        n.inputs[0].default_value = a
    if b is not None:
        n.inputs[1].default_value = b
    if c is not None:
        n.inputs[2].default_value = c
    return n


def maprange(name, fmin, fmax, tmin, tmax):
    n = node('ShaderNodeMapRange', name)
    n.interpolation_type = 'LINEAR'
    n.clamp = True
    n.inputs[1].default_value = fmin   # From Min (VALUE)
    n.inputs[2].default_value = fmax   # From Max (VALUE)
    n.inputs[3].default_value = tmin   # To Min
    n.inputs[4].default_value = tmax   # To Max
    return n


def L(a, b):
    nt.links.new(a, b)


# ---- 坐标（空间材质 · Y 投射） ----
n_tex = node('ShaderNodeTexCoord', '雷达_纹理坐标')
n_tex.object = ctl                                   # ★ Object 坐标的相对原点 = 控制空物体
n_sep = node('ShaderNodeSeparateXYZ', '雷达_分离XYZ')

# ---- 角度 u = (atan2(Z, X) + π) / 2π  （只吃 X/Z ⇒ 沿 Y 投射） ----
n_ang = mathop('雷达_相位角', 'ARCTAN2', b=None)      # in0=Z(y) in1=X(x)
n_plus = mathop('雷达_角度偏置', 'ADD', b=math.pi)
n_u = mathop('雷达_角度U', 'MULTIPLY', b=1.0 / TAU)

# ---- 时间与相位 ----
n_time = node('ShaderNodeValue', '雷达_时刻')          # 被驱动 = frame/fps * 速度/360（圈）
n_cnt = mathop('雷达_有向条数', 'MULTIPLY')            # 条数 × 方向（两个输入都驱动）
n_t = mathop('雷达_时间项', 'MULTIPLY')
n_a = mathop('雷达_角项', 'MULTIPLY')
n_diff = mathop('雷达_相位差', 'SUBTRACT')
n_D = mathop('雷达_相位D', 'FLOORED_MODULO', b=1.0)   # ★ 必须 FLOORED_MODULO

# ---- 拖尾包络（Math 域波形，ColorRamp 不兼职） ----
n_trail = maprange('雷达_拖尾包络', 0.0, 5.0 * 129.0 / 360.0, 1.0, 0.0)
n_pow = mathop('雷达_拖尾曲率', 'POWER', b=1.8)

# ---- 头部亮线：min(D, 1-D) < 线宽 ----
n_1mD = mathop('雷达_线_1减D', 'SUBTRACT', a=1.0)
n_minD = mathop('雷达_线_对称距', 'MINIMUM')
n_line = maprange('雷达_头部线', 0.0, 0.004, 1.0, 0.0)

# ---- 半径：面内 (X, 0, Z) → 长度 ----
n_comb = node('ShaderNodeCombineXYZ', '雷达_面内坐标')
n_r = node('ShaderNodeVectorMath', '雷达_半径')
n_r.operation = 'LENGTH'
n_dot = maprange('雷达_中心点', 0.0, round(0.03 * half, 4), 1.0, 0.0)

# ---- 网格同心圆 ----
n_rgap = mathop('雷达_环带周期', 'DIVIDE')             # r ÷ 环间距
n_rfrac = mathop('雷达_环带分带', 'FRACT')
n_rring = maprange('雷达_环带', 0.0, 0.05, 1.0, 0.0)
n_rgain = mathop('雷达_网格亮度', 'MULTIPLY', b=0.12)

# ---- 合成 + 裁切 + 强度 ----
n_sumA = mathop('雷达_合成A', 'ADD')
n_sumB = mathop('雷达_合成B', 'ADD')
n_sumC = mathop('雷达_合成C', 'ADD')
n_lim = mathop('雷达_合成限幅', 'MINIMUM', b=1.0)
n_clip = maprange('雷达_亮面裁切', round(0.84 * half, 4), round(0.87 * half, 4), 1.0, 0.0)
n_mask = mathop('雷达_总掩码', 'MULTIPLY')
n_gain = mathop('雷达_发光强度', 'MULTIPLY', b=8.0)

n_col = node('ShaderNodeRGB', '雷达_颜色')
n_col.outputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
n_bsdf = node('ShaderNodeBsdfPrincipled', '雷达_BSDF')
n_bsdf.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
n_bsdf.inputs['Roughness'].default_value = 1.0
n_bsdf.inputs['Metallic'].default_value = 0.0
n_out = node('ShaderNodeOutputMaterial', '雷达_输出')

# ---------- 3. 连线 ----------
L(n_tex.outputs['Object'], n_sep.inputs[0])
L(n_sep.outputs['Z'], n_ang.inputs[0])               # atan2(y=Z, x=X)
L(n_sep.outputs['X'], n_ang.inputs[1])
L(n_ang.outputs[0], n_plus.inputs[0])
L(n_plus.outputs[0], n_u.inputs[0])
# 时间项 = 时刻 × 条数（不含方向）；角项 = u × (方向×条数)
#   D = frac(条数×时刻 − 方向×条数×u)  ⇒ 头位置 u = 方向×时刻（方向=±1 真正反向）
L(n_time.outputs[0], n_t.inputs[0])
L(n_u.outputs[0], n_a.inputs[0])
L(n_cnt.outputs[0], n_a.inputs[1])
L(n_t.outputs[0], n_diff.inputs[0])
L(n_a.outputs[0], n_diff.inputs[1])
L(n_diff.outputs[0], n_D.inputs[0])
L(n_D.outputs[0], n_trail.inputs[0])
L(n_trail.outputs['Result'], n_pow.inputs[0])
L(n_D.outputs[0], n_1mD.inputs[1])
L(n_1mD.outputs[0], n_minD.inputs[0])
L(n_D.outputs[0], n_minD.inputs[1])
L(n_minD.outputs[0], n_line.inputs[0])
L(n_sep.outputs['X'], n_comb.inputs['X'])
L(n_sep.outputs['Z'], n_comb.inputs['Z'])
L(n_comb.outputs[0], n_r.inputs[0])
L(n_r.outputs[1], n_dot.inputs[0])
L(n_r.outputs[1], n_clip.inputs[0])
L(n_r.outputs[1], n_rgap.inputs[0])
L(n_rgap.outputs[0], n_rfrac.inputs[0])
L(n_rfrac.outputs[0], n_rring.inputs[0])
L(n_rring.outputs['Result'], n_rgain.inputs[0])
L(n_pow.outputs[0], n_sumA.inputs[0])
L(n_line.outputs['Result'], n_sumA.inputs[1])
L(n_sumA.outputs[0], n_sumB.inputs[0])
L(n_dot.outputs['Result'], n_sumB.inputs[1])
L(n_sumB.outputs[0], n_sumC.inputs[0])
L(n_rgain.outputs[0], n_sumC.inputs[1])
L(n_sumC.outputs[0], n_lim.inputs[0])
L(n_lim.outputs[0], n_mask.inputs[0])
L(n_clip.outputs['Result'], n_mask.inputs[1])
L(n_mask.outputs[0], n_gain.inputs[0])
L(n_gain.outputs[0], n_bsdf.inputs['Emission Strength'])
L(n_col.outputs['Color'], n_bsdf.inputs['Emission Color'])
L(n_bsdf.outputs['BSDF'], n_out.inputs['Surface'])

# ---------- 4. 驱动（控制空物体 → 节点插槽；变量绑好后再写表达式） ----------
scene = bpy.context.scene
PR = lambda k: '["' + k + '"]'


def bind(path, expr, specs):
    d = nt.driver_add(path)   # 标量属性不能传 index（传 0 会报 not an array）
    for v in list(d.driver.variables):
        d.driver.variables.remove(v)
    for nm, id_type, id_ref, dp in specs:
        v = d.driver.variables.new()
        v.name = nm
        v.type = 'SINGLE_PROP'
        t = v.targets[0]
        t.id_type = id_type
        t.id = id_ref
        t.data_path = dp
    d.driver.expression = expr
    return d


def P(k):
    return ('OBJECT', ctl, PR(k))


S_FR = ('SCENE', scene, 'frame_current')
S_FPS = ('SCENE', scene, 'render.fps')

bind('nodes["雷达_时刻"].outputs[0].default_value',
     'fr / fps * sp / 360.0', [('fr', *S_FR), ('fps', *S_FPS), ('sp', *P("扫描速度"))])
bind('nodes["雷达_有向条数"].inputs[0].default_value', 'cn', [('cn', *P("扫描条数"))])
bind('nodes["雷达_有向条数"].inputs[1].default_value', 'dr', [('dr', *P("扫描方向"))])
bind('nodes["雷达_时间项"].inputs[1].default_value', 'cn', [('cn', *P("扫描条数"))])
bind('nodes["雷达_拖尾包络"].inputs[2].default_value', 'cn * tl / 360.0',
     [('cn', *P("扫描条数")), ('tl', *P("拖尾长度"))])
bind('nodes["雷达_拖尾曲率"].inputs[1].default_value', 'pw', [('pw', *P("拖尾曲率"))])
bind('nodes["雷达_亮面裁切"].inputs[1].default_value', 'rc', [('rc', *P("亮面半径"))])
bind('nodes["雷达_亮面裁切"].inputs[2].default_value', 'rc + fw',
     [('rc', *P("亮面半径")), ('fw', *P("淡出宽度"))])
bind('nodes["雷达_中心点"].inputs[2].default_value', 'drm', [('drm', *P("中心点半径"))])
bind('nodes["雷达_头部线"].inputs[2].default_value', 'lw', [('lw', *P("头部线宽"))])
bind('nodes["雷达_环带周期"].inputs[1].default_value', 'rc / rn',
     [('rc', *P("亮面半径")), ('rn', *P("环数"))])
bind('nodes["雷达_网格亮度"].inputs[1].default_value', 'gg', [('gg', *P("网格亮度"))])
bind('nodes["雷达_发光强度"].inputs[1].default_value', 'gn', [('gn', *P("发光强度"))])

# ---------- 5. 挂到平面（保留旧材质块，便于回退） ----------
if len(ob.material_slots) == 0:
    ob.data.materials.append(mat)
else:
    ob.material_slots[0].link = 'DATA'
    ob.material_slots[0].material = mat

drivers = len(nt.animation_data.drivers) if nt.animation_data else 0
print("[结果] 材质=%s 节点=%d 连线=%d 驱动=%d 槽0=%s" %
      (mat.name, len(nt.nodes), len(nt.links), drivers, ob.material_slots[0].material.name))
print("[控制] %s 自定义属性: %s" % (CTRL, sorted(k for k in ctl.keys() if not k.startswith('_'))))
print("[空间] 坐标源=Object(%s) 只读 X/Z，丢弃 Y ⇒ 沿世界 Y 轴投射" % CTRL)
