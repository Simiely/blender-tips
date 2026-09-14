# build_noise_scroll.py — 为 水晶走廊_竖向灯.001 建「程序化噪波滚动发光」材质
#
# 标准写法（对齐仓库 docs/渐变发光滚动材质.md 的滚筒方案 + docs/材质与驱动规范.md 的条纹方案）:
#
#   纹理坐标(Object→控制空物体) → 滚动映射(Mapping) → 噪波纹理(Noise 4D)
#        → 对比度(ColorRamp) → 反色(MapRange) → 发光强度(Math 乘)
#        → 原理化BSDF.Emission Strength
#
#   滚动   = Mapping 的 Location（与滚筒材质同源，不是手搓 Separate/Combine XYZ）
#   对比度 = ColorRamp 两个色标的位置（Blender 里做噪波对比度的标准做法：
#            "interrupt a Noise Texture signal chain with a Colour Ramp"）
#   反色   = MapRange 的 To Min / To Max 对调（0→1 / 1→0）⇒ 黑白互换
#
# v4（本次）新增「亮区阈值」控件 + 提高密度/对比度上限：
#   * ColorRamp 窗口从「绕 0.5 对称」改为「绕 T 对称」：
#       色标 = [T - 0.5/c , T + 0.5/c]（T=亮区阈值, c=对比度）
#     T=0.5 时与 v3 公式完全等价（向后兼容，默认值不变）
#     T 调高 ⇒ 窗口搬到噪波分布顶部 ⇒ 黑底零星白点（probe_63 实测：
#     T≈0.67/c=10 → 白占 10.3%；T≈0.70 → 3.5%；T≈0.72 → 0.9%；T≈0.75 → 0.2%）
#   * 噪波密度上限 20→100、噪波对比度上限 20→100（c=100 时窗口 ±0.005 ≈ 硬开关）
#
# v2 重写要点：
#   * 旧版用 MapRange「窗口拉伸」+ Separate/Combine XYZ 手搓滚动 → 全部删除
#   * 噪波 Fac 实测只聚在 0.24~0.74；直通映射 => 全片发亮、没有不发光暗区
#     现在由 ColorRamp 把关：低端压到 0 → 真正的不发光黑区
#
# v2.1 修复要点：
#   * 6 条驱动全改 SINGLE_PROP 变量（原来是命名空间函数直调 ⇒ 依赖图没有边 ⇒ 控件全哑）
#   * 面板加【看门狗定时器】刷新（原来只靠 Panel.draw() tag ⇒ 从自定义属性列表改数字不生效）
#
# v3（本次）新增「反色」控件：
#   * 插一个 MapRange 节点（命名 反色）夹在 对比度 与 发光强度 之间
#     From Min/Max 固定 0/1；To Min 驱动 = iv（0/1），To Max 驱动 = 1 - iv
#       iv=0 ⇒ To 0→1 = 恒等映射（原行为不变）
#       iv=1 ⇒ To 1→0 = 黑白互换（原亮区变暗区、原暗区变亮区）
#   * ⚠️ 这个 MapRange 只做「反色」，**不是** v1 那种拿 MapRange 当对比度窗口的错误用法；
#     对比度仍然只由 ColorRamp 色标位置决定。
#   * RESET_PROPS 改成 False：映射已定，重跑不再抹掉用户调好的值（新键照默认补上）
import bpy, json

# ============================ 配置区 ============================
TARGET_OBJ = "水晶走廊_竖向灯.001"
OLD_MAT    = "灯光光.004"                 # 原材质：保留为未使用材质（设 fake_user 防丢）
NEW_MAT    = "竖向灯001_噪波滚动发光"
CTRL_NAME  = "竖向灯001_噪波控制"
PANEL_TEXT = "噪波滚动控制.py"

SEED_SPAN = 10.0                          # 种子每 +1 在噪波空间里跳 10 个单位 → 保证"换一张图"

# (键, 中文名, 默认, 最小, 最大, 软最小, 软最大, 步进, 精度, 说明)
# ⚠️ 键就用中文：物体属性 > 自定义属性 列表里显示的字面量就是这个键名，
#    用英文键会在那里露出英文 UI（用户 2026-09-13 反馈）。
PROPS = [
    ("噪波密度",   "噪波密度",   2.0,   0.05, 100.0, 0.2,  20.0, 1, 2,
     "噪波频率(世界单位)。越大斑点越密越小；走廊 26m / 灯带高 3.09m"),
    ("噪波种子",   "噪波种子",   0.0,   0.0,  1000.0, 0.0, 100.0, 1, 0,
     "每 +1 = 换一整张噪波图案（整数跳变，快速切换不同效果）"),
    ("Z向速度",    "Z向速度",    0.02, -2.0,  2.0, -0.1, 0.1, 1, 4,
     "噪波沿世界 Z 的位移速度(米/帧)。可为负=反向；打关键帧可变/减速/停顿"),
    ("噪波对比度", "噪波对比度", 5.0,   1.0,  100.0, 2.0, 20.0, 1, 2,
     "ColorRamp 色标窗口宽度(实测定标)：1=窗口半宽0.5(全范围拉伸)；"
     "越大窗口越窄；5=黑白分明；50 以上≈硬开关"),
    ("亮区阈值",   "亮区阈值",   0.5,   0.3,  0.95, 0.5,  0.8, 1, 2,
     "窗口中心：0.5=常规(默认，跟 v3 完全一样)；调高→白点变稀疏(黑底零星白点，"
     "0.70 左右配高对比度)；调低→白多黑少"),
    ("发光强度",   "发光强度",   5.0,   0.0,  200.0, 0.0, 30.0, 1, 2,
     "亮区峰值亮度(暗区恒为0，不随它变亮)"),
    ("反色",       "反色",       0.0,   0.0,  1.0, 0.0, 1.0, 1, 0,
     "黑白反色开关：0=正常(噪波亮处发光) / 1=反色(噪波亮处变暗、暗处发光)；"
     "中间值=部分反色"),
]

# 重跑时是否把控件恢复默认。
# ⚠️ v3 起改为 False：材质映射已定型，重跑只应【补上新键】，不该抹掉用户调好的值。
#    （v2 时期设 True 是为了清掉旧映射下试出的过曝值，如 强度100 → 整片纯白；现在没这个需要了。）
RESET_PROPS = False
RESET_KEYS = ("噪波密度", "噪波种子", "Z向速度", "噪波对比度", "亮区阈值", "发光强度", "反色")

# 迁移表：老版本用过英文键 → 重跑时删掉，别在自定义属性列表里留英文残留；
# 同时作为读取兜底（万一旧键还在也能读到值）。
LEGACY_MAP = {
    "噪波密度": "noise_density",
    "噪波种子": "noise_seed",
    "Z向速度": "z_speed",
    "噪波对比度": "noise_contrast",
    "发光强度": "glow_strength",
    "反色": "invert",
}
# ===============================================================

rep = {"step": "build_noise_scroll_material", "version": 4,
       "chain": "Mapping+ColorRamp(T阈值)+MapRange(反色)"}
log = []


def _prop_fn(key, default):
    c = bpy.data.objects.get(CTRL_NAME)
    if c is None:
        return float(default)
    v = c.get(key, None)
    if v is None:                                  # 兜底读老英文键
        leg = LEGACY_MAP.get(key)
        v = c.get(leg, None) if leg else None
    try:
        return float(default if v is None else v)
    except Exception:
        return float(default)


def nz_density():  return _prop_fn("噪波密度", 2.0)
def nz_seed():     return _prop_fn("噪波种子", 0.0)
def nz_z_speed():  return _prop_fn("Z向速度", 0.02)
def nz_contrast(): return _prop_fn("噪波对比度", 5.0)
def nz_threshold(): return _prop_fn("亮区阈值", 0.5)
def nz_strength(): return _prop_fn("发光强度", 5.0)
def nz_invert():   return _prop_fn("反色", 0.0)


# ---- 对比度 ⇒ ColorRamp 两个色标的「窗口」 ----
#   窗口 = [0.5 - 0.5/c, 0.5 + 0.5/c]  （以噪波分布中心 0.5 为轴拉伸）
#   c=1  → 0.00 / 1.00  直通；噪波实测只有 0.24~0.74 ⇒ 全片皆亮、无暗区
#   c=5  → 0.40 / 0.60  黑白分明，约 6% 像素完全不发光
#   c=10 → 0.45 / 0.55  约 20% 像素完全不发光
def nz_c_lo():
    c = max(1.0, nz_contrast())
    t = nz_threshold()
    return max(0.0, min(1.0, t - 0.5 / c))


def nz_c_hi():
    c = max(1.0, nz_contrast())
    t = nz_threshold()
    return max(0.0, min(1.0, t + 0.5 / c))


NS_FUNCS = {"nz_density": nz_density, "nz_seed": nz_seed, "nz_z_speed": nz_z_speed,
            "nz_contrast": nz_contrast, "nz_threshold": nz_threshold,
            "nz_strength": nz_strength, "nz_invert": nz_invert,
            "nz_c_lo": nz_c_lo, "nz_c_hi": nz_c_hi}

# ---------------- 记录改动前状态 ----------------
obj = bpy.data.objects.get(TARGET_OBJ)
if obj is None:
    raise RuntimeError("找不到对象 " + TARGET_OBJ)
old = bpy.data.materials.get(OLD_MAT)
rep["before"] = {
    "object": obj.name,
    "slot0_material": obj.material_slots[0].material.name if obj.material_slots and obj.material_slots[0].material else None,
    "slot_link": obj.material_slots[0].link if obj.material_slots else None,
    "old_mat_exists": old is not None,
    "old_mat_users": old.users if old else None,
    "old_mat_nodes": [n.name for n in old.node_tree.nodes] if old and old.use_nodes else None,
    "mat_count": len(bpy.data.materials),
    "object_count": len(bpy.data.objects),
    "texts": [t.name for t in bpy.data.texts],
    "mesh_polys": len(obj.data.polygons),
}

# ---------------- 1) 控制空物体（世界原点 / 无旋转 / scale=1）----------------
ctrl = bpy.data.objects.get(CTRL_NAME)
created_ctrl = False
if ctrl is None:
    ctrl = bpy.data.objects.new(CTRL_NAME, None)
    tgt_col = obj.users_collection[0] if obj.users_collection else bpy.context.scene.collection
    tgt_col.objects.link(ctrl)
    created_ctrl = True
ctrl.location = (0.0, 0.0, 0.0)
ctrl.rotation_euler = (0.0, 0.0, 0.0)
ctrl.rotation_mode = 'XYZ'
ctrl.scale = (1.0, 1.0, 1.0)
ctrl.empty_display_type = 'PLAIN_AXES'
ctrl.empty_display_size = 1.0
props_before = {k: ctrl.get(k) for k in RESET_KEYS}
for key, label, dflt, mn, mx, smn, smx, step, prec, desc in PROPS:
    if RESET_PROPS:
        ctrl[key] = float(dflt)                    # 回到已知良好的默认基线
    elif key not in ctrl.keys():
        ctrl[key] = float(dflt)
    else:
        ctrl[key] = float(ctrl[key])
    try:
        ui = ctrl.id_properties_ui(key)
        ui.update(description="%s　| 默认 %.4g" % (desc, dflt),
                  min=float(mn), max=float(mx), soft_min=float(smn), soft_max=float(smx),
                  step=step, precision=prec)
    except Exception as e:
        log.append("UI_WARN %s %r" % (key, e))

# 删掉老的英文键：一律不留在「物体属性 > 自定义属性」列表里
legacy_removed = []
for _zh, _en in LEGACY_MAP.items():
    if _en in ctrl.keys():
        try:
            del ctrl[_en]
            legacy_removed.append(_en)
        except Exception as e:
            log.append("LEGACY_DEL_WARN %s %r" % (_en, e))

rep["ctrl"] = {"name": ctrl.name, "created": created_ctrl,
               "location": list(ctrl.location), "rotation_euler": list(ctrl.rotation_euler),
               "scale": list(ctrl.scale),
               "legacy_removed": legacy_removed,
               "reset_props": bool(RESET_PROPS),
               "props_before": props_before,
               "keys": [k for k in ctrl.keys() if not k.startswith("_")],
               "props": {k: ctrl.get(k) for k, *_ in PROPS}}

# 注册命名空间函数（本会话立即可用；持久化由下面的 Register 文本块负责）
for k, f in NS_FUNCS.items():
    bpy.app.driver_namespace[k] = f

# ---------------- 2) 新材质 + 节点树（标准链） ----------------
src = bpy.data.materials.get(NEW_MAT)
if src is None:
    src = bpy.data.materials.new(NEW_MAT)
src.name = NEW_MAT
src.use_nodes = True
src.use_fake_user = False
nt = src.node_tree
for n in list(nt.nodes):
    if n.type != 'OUTPUT_MATERIAL':
        nt.nodes.remove(n)
out_node = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
if out_node is None:
    out_node = nt.nodes.new('ShaderNodeOutputMaterial')
out_node.name = out_node.label = "材质输出"


def new_node(kind, name, loc):
    n = nt.nodes.new(kind)
    n.name = n.label = name
    n.location = loc
    return n


def vin(node, name):
    """按名字取【标量(VALUE)】输入插槽。
    ⚠️ MapRange 里 From Min/From Max/To Min/To Max 各有两个同名插槽
       （FLOAT 版 + VECTOR 版）⇒ 必须按 type=='VALUE' 挑，否则可能拿到向量版。"""
    for s in node.inputs:
        if s.name == name and s.type == 'VALUE':
            return s
    raise KeyError("%s 里找不到标量插槽 %s" % (node.name, name))


# ① 纹理坐标：Object 源 = 控制空物体（位于世界原点、无旋转、scale=1 ⇒ Object 坐标 == 世界坐标）
tc = new_node('ShaderNodeTexCoord', "纹理坐标", (-1060, 0))
tc.object = ctrl

# ② 滚动映射：Location.Z 由驱动写入 ⇒ 噪波沿世界 Z 滚动（与滚筒材质同源）
mp = new_node('ShaderNodeMapping', "滚动映射", (-840, 0))
mp.vector_type = 'POINT'
mp.inputs['Location'].default_value = (0.0, 0.0, 0.0)
mp.inputs['Scale'].default_value = (1.0, 1.0, 1.0)

# ③ 噪波纹理：4D（W = 种子通道），Fac 输出
noise = new_node('ShaderNodeTexNoise', "噪波纹理", (-620, 0))
noise.noise_dimensions = '4D'
noise.inputs['Detail'].default_value = 3.0
noise.inputs['Roughness'].default_value = 0.5
noise.inputs['Lacunarity'].default_value = 2.0
noise.inputs['Distortion'].default_value = 0.0

# ④ 对比度：ColorRamp 两个色标的位置 = 对比度窗口
#    ⚠️ 默认色标就在 0 / 1（= 直通）⇒ 必须显式挪，否则等于没做对比度
ramp = new_node('ShaderNodeValToRGB', "对比度", (-400, 0))
ramp.color_ramp.interpolation = 'LINEAR'
ramp.color_ramp.elements[0].position = nz_c_lo()
ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)     # 黑 = 不发光
ramp.color_ramp.elements[1].position = nz_c_hi()
ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)     # 白 = 满亮

# ⑤ 反色：MapRange 把 [0,1] 映到 [To Min, To Max]
#    To Min / To Max 由「反色」驱动写入 ⇒ iv=0 时 To 0/1（恒等），iv=1 时 To 1/0（黑白互换）
#    From Min/Max 固定 0/1（ColorRamp 的输出本来就是 0~1 灰度）
inv = new_node('ShaderNodeMapRange', "反色", (-290, 0))
inv.data_type = 'FLOAT'
inv.interpolation_type = 'LINEAR'
inv.clamp = True
vin(inv, 'From Min').default_value = 0.0
vin(inv, 'From Max').default_value = 1.0
vin(inv, 'To Min').default_value = nz_invert()            # 0 = 不反色
vin(inv, 'To Max').default_value = 1.0 - nz_invert()      # 1 = 反色

# ⑥ 发光强度：亮区峰值倍率（暗区 0 × 任何值 = 0，不会被拉亮）
mul = new_node('ShaderNodeMath', "发光强度", (-180, 0))
mul.operation = 'MULTIPLY'
mul.inputs[1].default_value = nz_strength()

# ⑦ 原理化 BSDF：自发光
bsdf = new_node('ShaderNodeBsdfPrincipled', "原理化 BSDF", (60, 0))
bsdf.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
bsdf.inputs['Emission Color'].default_value = (1.0, 1.0, 1.0, 1.0)

L = nt.links
L.new(tc.outputs['Object'], mp.inputs['Vector'])
L.new(mp.outputs['Vector'], noise.inputs['Vector'])
L.new(noise.outputs['Fac'], ramp.inputs['Fac'])
L.new(ramp.outputs['Color'], vin(inv, 'Value'))
L.new(inv.outputs['Result'], mul.inputs[0])
L.new(mul.outputs['Value'], bsdf.inputs['Emission Strength'])
L.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

rep["material"] = {"name": src.name, "nodes": [n.name for n in nt.nodes],
                   "links": ["%s.%s -> %s.%s" % (l.from_node.name, l.from_socket.name,
                                                 l.to_node.name, l.to_socket.name) for l in nt.links]}

# ---------------- 3) 挂驱动 ----------------
if nt.animation_data is None:
    nt.animation_data_create()
else:
    nt.animation_data_clear()          # 幂等：重跑时先清掉旧驱动，避免重复叠加
    nt.animation_data_create()

SCENE = bpy.context.scene

# ★★ 为什么必须用 SINGLE_PROP 变量，而不是「表达式直接调命名空间函数」：
#   依赖图只认【已声明的依赖边】。表达式直接调 nz_xxx() ⇒ 没有任何边指向控制空物体 ⇒
#   改属性后驱动不会自己重算，只能靠 UI 侧手动 tag。而「靠 UI tag」这条路很脆：
#   实测用户在「物体属性 → 自定义属性」里改数字时，我的 N 面板并没有重绘
#   ⇒ 不会 tag ⇒ **5 个控件全部失效**（用户实际报的现象）。
#   改用 SINGLE_PROP 变量指向 ctrl 的中文 ID 属性 ⇒ 边真实存在 ⇒ 改属性即自动重算。
#   驱动表达式里 max() / min() / abs() 均可用（probe_driver_autotrigger.py / probe_driver_tag_matrix.py 实测）。
VAR_OF = {"噪波密度": "dn", "噪波种子": "sd", "Z向速度": "sp", "噪波对比度": "ct",
          "亮区阈值": "tt", "发光强度": "st", "反色": "iv"}


def _bind_var(d, name, id_type, id_obj, data_path):
    v = d.variables.new()
    v.name = name
    v.type = 'SINGLE_PROP'
    t = v.targets[0]
    t.id_type = id_type
    t.id = id_obj
    t.data_path = data_path
    return v


def _bind_frame_var(d):
    """fr = scene.frame_current
    用 SINGLE_PROP 是为了**显式声明依赖边**，不是因为内置 frame 不可用 ——
    【勘误 2026-09-14】内建 frame 在 5.2 实测**可用**（probe_51 当年报"取值恒停在默认 0"，
    真凶是表达式里引用的 nz_z_speed 没注册进命名空间 ⇒ 整条驱动 is_valid=False 取默认值 0，
    frame 是被连累的）。滚筒方案用的也是 SINGLE_PROP。详见本 skill §3 勘误与 AGENTS.md。"""
    return _bind_var(d, 'fr', 'SCENE', SCENE, 'frame_current')


def _bind_props(d, props):
    """把 ctrl 上的中文 ID 属性绑成变量（变量名见 VAR_OF）"""
    out = {}
    for k in props:
        _bind_var(d, VAR_OF[k], 'OBJECT', ctrl, '["%s"]' % k)
        out[VAR_OF[k]] = k
    return out


def add_drv(sock, expr, arr=-1, props=(), frame_var=False):
    """给节点插槽挂驱动。arr=-1 → 标量；0/1/2 → 向量分量。"""
    fc = sock.driver_add('default_value', arr) if arr >= 0 else sock.driver_add('default_value')
    d = fc.driver
    d.type = 'SCRIPTED'
    vmap = _bind_props(d, props)
    if frame_var:
        _bind_frame_var(d)
        vmap['fr'] = 'scene.frame_current'
    d.expression = expr                      # 变量绑好再写表达式
    fc.update()
    return {"path": fc.data_path, "array_index": fc.array_index, "expr": expr, "vars": vmap}


def add_ramp_drv(el, expr, props=()):
    """ColorRamp 色标位置不是插槽，只能按节点树路径挂驱动。
    实测路径可用：nodes["对比度"].color_ramp.elements[N].position（probe_50/52）"""
    fc = nt.driver_add('nodes["%s"].color_ramp.elements[%d].position' % (ramp.name, el), -1)
    d = fc.driver
    d.type = 'SCRIPTED'
    vmap = _bind_props(d, props)
    d.expression = expr
    fc.update()
    return {"path": fc.data_path, "array_index": fc.array_index, "expr": expr, "vars": vmap}


drivers = {}
drivers['滚动映射.Location.Z'] = add_drv(mp.inputs['Location'], 'fr * sp', arr=2,
                                        props=("Z向速度",), frame_var=True)
drivers['噪波纹理.Scale'] = add_drv(noise.inputs['Scale'], 'dn', props=("噪波密度",))
drivers['噪波纹理.W'] = add_drv(noise.inputs['W'], 'sd * %s' % SEED_SPAN, props=("噪波种子",))
drivers['对比度.elements[0].position'] = add_ramp_drv(0, 'max(0.0, tt - 0.5 / ct)',
                                                     props=("噪波对比度", "亮区阈值"))
drivers['对比度.elements[1].position'] = add_ramp_drv(1, 'min(1.0, tt + 0.5 / ct)',
                                                     props=("噪波对比度", "亮区阈值"))
drivers['发光强度.inputs[1]'] = add_drv(mul.inputs[1], 'st', props=("发光强度",))
# 反色：把 [0,1] 映射到 [iv, 1-iv] ⇒ iv=0 恒等、iv=1 完全互换（标准做法）
drivers['反色.To Min'] = add_drv(vin(inv, 'To Min'), 'iv', props=("反色",))
drivers['反色.To Max'] = add_drv(vin(inv, 'To Max'), '1.0 - iv', props=("反色",))
rep["drivers"] = drivers
rep["driver_count"] = len(nt.animation_data.drivers)

# ---------------- 4) 指派材质 + 保住原材质 ----------------
if obj.material_slots:
    obj.material_slots[0].material = src
else:
    obj.data.materials.append(src)
if old is not None and old.name != src.name:
    old.use_fake_user = True
rep["assign"] = {"slot0_material": obj.material_slots[0].material.name,
                 "old_mat_users": old.users if old else None,
                 "old_mat_fake_user": bool(old.use_fake_user) if old else None}

# ---------------- 5) Register 面板文本块 ----------------
PANEL_TEMPLATE = '''# -*- coding: utf-8 -*-
# 噪波滚动发光 · 参数实时面板（Register 文本块，随 .blend 保存）
# 自动注册：偏好设置 -> Save & Load -> Auto Run Python Scripts 已开启
#
# 材质链（标准写法）:
#   纹理坐标(Object) -> 滚动映射(Mapping) -> 噪波纹理(4D)
#       -> 对比度(ColorRamp) -> 反色(MapRange) -> 发光强度(乘)
#       -> 原理化BSDF.Emission Strength
import bpy

CTRL_NAME = "@@CTRL@@"
MAT_NAMES = @@MATS@@
PROPS = @@PROPS@@
LEGACY_MAP = @@LEGACY@@
PANEL_LABEL = "@@LABEL@@"
PANEL_CATEGORY = "@@CATEGORY@@"


def _prop_fn(key, default):
    c = bpy.data.objects.get(CTRL_NAME)
    if c is None:
        return float(default)
    v = c.get(key, None)
    if v is None:                                  # 兜底读老英文键
        leg = LEGACY_MAP.get(key)
        v = c.get(leg, None) if leg else None
    try:
        return float(default if v is None else v)
    except Exception:
        return float(default)


def nz_density():  return _prop_fn("噪波密度", @@D_DENSITY@@)
def nz_seed():     return _prop_fn("噪波种子", @@D_SEED@@)
def nz_z_speed():  return _prop_fn("Z向速度", @@D_ZSPEED@@)
def nz_contrast(): return _prop_fn("噪波对比度", @@D_CONTRAST@@)
def nz_threshold(): return _prop_fn("亮区阈值", @@D_THRESHOLD@@)
def nz_strength(): return _prop_fn("发光强度", @@D_STRENGTH@@)
def nz_invert():   return _prop_fn("反色", @@D_INVERT@@)


def nz_c_lo():
    c = max(1.0, nz_contrast())
    t = nz_threshold()
    return max(0.0, min(1.0, t - 0.5 / c))


def nz_c_hi():
    c = max(1.0, nz_contrast())
    t = nz_threshold()
    return max(0.0, min(1.0, t + 0.5 / c))


def _register_ns():
    ns = {"nz_density": nz_density, "nz_seed": nz_seed, "nz_z_speed": nz_z_speed,
          "nz_contrast": nz_contrast, "nz_threshold": nz_threshold,
          "nz_strength": nz_strength, "nz_invert": nz_invert,
          "nz_c_lo": nz_c_lo, "nz_c_hi": nz_c_hi}
    # 旧名别名：万一残留驱动还指向旧函数名，不至于报红
    ns["nz_win_lo"] = nz_c_lo
    ns["nz_win_hi"] = nz_c_hi
    ns["nz_contrast_lo"] = nz_c_lo
    ns["nz_contrast_hi"] = nz_c_hi
    bpy.app.driver_namespace.update(ns)


class NOISE_SCROLL_PT_controls(bpy.types.Panel):
    bl_label = PANEL_LABEL
    bl_idname = "NOISE_SCROLL_PT_controls"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = PANEL_CATEGORY

    def draw(self, context):
        lay = self.layout
        ctl = bpy.data.objects.get(CTRL_NAME)
        if ctl is None:
            lay.label(text="未找到控制器 " + CTRL_NAME, icon='ERROR')
            return
        box = lay.box()
        box.label(text=CTRL_NAME, icon='SHADING_RENDERED')
        for key, label in PROPS:
            box.prop(ctl, '["%s"]' % key, text=label)
        box.separator()
        box.label(text="对比度=窗口宽度(50+≈硬开关) · 5=黑白分明", icon='COLOR')
        box.label(text="亮区阈值=窗口中心：0.5常规 · 调高=黑底零星白点", icon='COLOR')
        box.label(text="发光强度是亮区峰值，暗区恒为0不会被拉亮", icon='LIGHT')
        box.label(text="反色 0=正常 / 1=黑白互换；Z向速度可为负(反向)", icon='ARROW_LEFTRIGHT')
        box.label(text="Z向速度打关键帧 = 变速 / 停顿", icon='INFO')
        lay.separator()
        lay.label(text="噪波写在世界 XZ 平面，沿世界 Z 滚动", icon='ORIENTATION_GLOBAL')
        lay.label(text="从任何地方改数字都会立刻生效（看门狗自动刷新）", icon='CHECKMARK')


# ---------------- 刷新机制 ----------------
# ★★ 为什么不能只在面板 draw() 里 tag（上一版的错误）：
#   面板 draw() 只在「N 面板显示本分类、且被重绘」时才执行。用户在
#   「物体属性 → 自定义属性」列表里改数字时它根本不执行 ⇒ 不会 tag
#   ⇒ 驱动停在旧值 ⇒ **5 个控件全部失效**（用户实际遇到的现象）。
#   所以改为【独立定时看门狗】：每 0.25 s 比对属性值，变了就 tag 重算。
#   它不依赖任何 UI 路径，从哪改都生效。
_TICK = 0.25
_WATCH_LAST = {}


def _touch():
    """强制重算挂在材质节点树上的驱动。
    ⚠️ 只有 ctl.update_tag() 是【不够】的：驱动拥有者是材质/节点树（probe_36/37 实测）。"""
    c = bpy.data.objects.get(CTRL_NAME)
    if c is not None:
        c.update_tag()
    for mn in MAT_NAMES:
        m = bpy.data.materials.get(mn)
        if m is None:
            continue
        m.update_tag()
        if m.use_nodes and m.node_tree:
            m.node_tree.update_tag()
    bpy.context.view_layer.update()


def _watch():
    try:
        c = bpy.data.objects.get(CTRL_NAME)
        if c is not None:
            dirty = False
            for k, _lbl in PROPS:
                v = c.get(k)
                if _WATCH_LAST.get(k) != v:
                    _WATCH_LAST[k] = v
                    dirty = True
            if dirty:
                _touch()
    except Exception:
        pass
    return _TICK


def register():
    _register_ns()
    if hasattr(bpy.types, 'NOISE_SCROLL_PT_controls'):
        try:
            bpy.utils.unregister_class(NOISE_SCROLL_PT_controls)
        except Exception:
            pass
    bpy.utils.register_class(NOISE_SCROLL_PT_controls)
    try:
        bpy.app.timers.unregister(_watch)
    except Exception:
        pass
    bpy.app.timers.register(_watch, first_interval=0.5, persistent=True)


def unregister():
    try:
        bpy.app.timers.unregister(_watch)
    except Exception:
        pass
    if hasattr(bpy.types, 'NOISE_SCROLL_PT_controls'):
        try:
            bpy.utils.unregister_class(NOISE_SCROLL_PT_controls)
        except Exception:
            pass


register()
'''

props_src = "[\n" + "".join('    ("%s", "%s"),\n' % (k, lbl) for k, lbl, *_ in PROPS) + "]"
legacy_src = "{\n" + "".join('    "%s": "%s",\n' % (zh, en) for zh, en in LEGACY_MAP.items()) + "}"
panel_src = (PANEL_TEMPLATE
             .replace("@@CTRL@@", CTRL_NAME)
             .replace("@@MATS@@", '["%s"]' % NEW_MAT)
             .replace("@@PROPS@@", props_src)
             .replace("@@LEGACY@@", legacy_src)
             .replace("@@LABEL@@", "噪波滚动发光 · 参数控制")
             .replace("@@CATEGORY@@", "噪波控制")
             .replace("@@D_DENSITY@@", repr(PROPS[0][2]))
             .replace("@@D_SEED@@", repr(PROPS[1][2]))
             .replace("@@D_ZSPEED@@", repr(PROPS[2][2]))
             .replace("@@D_CONTRAST@@", repr(PROPS[3][2]))
             .replace("@@D_THRESHOLD@@", repr(PROPS[4][2]))
             .replace("@@D_STRENGTH@@", repr(PROPS[5][2]))
             .replace("@@D_INVERT@@", repr(PROPS[6][2])))

txt = bpy.data.texts.get(PANEL_TEXT)
if txt is None:
    txt = bpy.data.texts.new(PANEL_TEXT)
txt.clear()
txt.write(panel_src)
txt.use_module = True
try:
    txt.use_fake_user = True
except Exception:
    pass
rep["panel_text"] = {"name": txt.name, "use_module": txt.use_module, "chars": len(panel_src)}

# 执行一次 → 本会话立刻有面板 + 命名空间函数
try:
    exec(compile(panel_src, PANEL_TEXT, 'exec'), {"__name__": "builtins", "__builtins__": __builtins__})
    rep["panel_exec"] = "OK"
except Exception as e:
    rep["panel_exec"] = "ERR %r" % e

# ---------------- 6) 即时自检 ----------------
bpy.context.view_layer.update()
chk = {}
chk["mat_assigned"] = obj.material_slots[0].material.name == NEW_MAT
chk["texcoord_is_ctrl"] = (tc.object is not None and tc.object.name == CTRL_NAME)
chk["noise_is_4d"] = noise.noise_dimensions == '4D'
chk["has_color_ramp"] = (ramp.bl_idname == 'ShaderNodeValToRGB')
chk["ramp_stops"] = [round(ramp.color_ramp.elements[0].position, 4),
                     round(ramp.color_ramp.elements[1].position, 4)]
chk["ramp_lo_is_black"] = tuple(round(x, 3) for x in ramp.color_ramp.elements[0].color) == (0.0, 0.0, 0.0, 1.0)
chk["ramp_hi_is_white"] = tuple(round(x, 3) for x in ramp.color_ramp.elements[1].color) == (1.0, 1.0, 1.0, 1.0)
# ★ v3：MapRange 现在【只用来做反色】，不是 v1 那种拿它当对比度窗口的错误用法
_mrs = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeMapRange']
chk["maprange_count_is_1"] = (len(_mrs) == 1)
chk["maprange_named_invert"] = (_mrs[0].name == "反色") if _mrs else False
chk["maprange_is_float"] = (_mrs[0].data_type == 'FLOAT') if _mrs else False
chk["maprange_from_is_0_1"] = ([round(vin(_mrs[0], 'From Min').default_value, 6),
                               round(vin(_mrs[0], 'From Max').default_value, 6)] == [0.0, 1.0]) if _mrs else False
chk["maprange_between_ramp_and_mul"] = bool(_mrs) and any(
    l.from_node.name == "对比度" and l.to_node.name == "反色" for l in nt.links) and any(
    l.from_node.name == "反色" and l.to_node.name == "发光强度" for l in nt.links)
chk["no_separate_combine"] = not any(n.bl_idname in ('ShaderNodeSeparateXYZ', 'ShaderNodeCombineXYZ')
                                     for n in nt.nodes)
chk["link_count"] = len(nt.links)
chk["driver_data_paths"] = ["%s[%d]" % (d.data_path, d.array_index) for d in nt.animation_data.drivers]
chk["driver_count"] = len(nt.animation_data.drivers)
chk["invert_drivers_present"] = (
    sum(1 for d in nt.animation_data.drivers
        if d.data_path.startswith('nodes["反色"].inputs[')) == 2)
chk["drivers_have_frame_var"] = any(v.name == 'fr' for d in nt.animation_data.drivers
                                    for v in d.driver.variables)
chk["ns_registered"] = all(k in bpy.app.driver_namespace for k in NS_FUNCS)
chk["panel_class"] = hasattr(bpy.types, 'NOISE_SCROLL_PT_controls')
chk["mesh_polys_unchanged"] = len(obj.data.polygons) == rep["before"]["mesh_polys"]
chk["object_count"] = len(bpy.data.objects)
chk["ctrl_keys"] = [k for k in ctrl.keys() if not k.startswith("_")]
chk["no_legacy_english_keys"] = not any(en in ctrl.keys() for en in LEGACY_MAP.values())
chk["texts"] = [t.name for t in bpy.data.texts]
# 对比度窗口自检：窗口下界必须高于噪波实测最小值(0.24) ⇒ 才有真正不发光暗区
chk["contrast_window"] = [round(nz_c_lo(), 4), round(nz_c_hi(), 4)]
chk["window_gives_true_black"] = nz_c_lo() > 0.24
chk["contrast_default_ok"] = (nz_contrast() >= 3.0)
rep["selfcheck"] = chk
rep["log"] = log

import os as _os
p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "build_noise_scroll.json")
with open(p, "w", encoding="utf-8") as f:
    json.dump(rep, f, ensure_ascii=False, indent=1)
print("BUILD_NOISE_SCROLL_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("BUILD_NOISE_SCROLL_END")
