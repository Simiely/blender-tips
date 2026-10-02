# -*- coding: utf-8 -*-
"""
分体翻页牌 —— 几何节点版翻页（不烘焙、可复制、免信任、参数仍可调）

为什么要用 GN 替代「驱动 / frame_change 处理器 / 烘焙」:
  GN 修改器是**纯数据** ⇒ 复制、存盘、重开、File > Append 全部跟着走,
  且**不需要 Python 执行权限**(不像驱动会被信任机制静默屏蔽,也不像处理器只活在内存里),
  参数还留在修改器面板里,随时可调。

节点逻辑:
  中心 = 边界框中心(卡片轴心在角上,必须自己算)
  t = (SceneTime.Frame - 延迟) FLOORED_MODULO 周期
  u = min(t / 时长, 1)
  s = u²(3 - 2u)                      # smoothstep: 慢起 → 加速 → 减速停住
  角度 = s × 圈数 × 2π                 # 弧度!整圈(360×N)才落回初始朝向
  几何: 平移(-中心) → 绕本地 X 旋转 → 平移(+中心)   # 本地 X = 沿牌宽 = 世界 Y

★ 5.2 两个必须知道的 API 事实:
  1. 修改器输入在 `mod.properties.inputs[identifier]`,且是 **Group IDProperty**,
     值要写进 `['value']`:`ins['Socket_2']['value'] = 4.0`(直接 `ins[id] = 4.0` 会 TypeError)
  2. **改完输入必须 `obj.update_tag()` + `view_layer.update()`**,否则读到的还是缓存网格,
     表现为"改了没反应 / 所有卡片同步"(实测踩过)
"""
import bpy
import math
from mathutils import Vector

scene = bpy.context.scene
NG_NAME = "翻页旋转_GN"
MOD_NAME = "翻页旋转"

# ---------------- 可调默认（写在组接口上，改一处全场生效）----------------
DEF = {"周期": 60.0, "时长": 16.0, "圈数": 3.0}
# ------------------------------------------------------------------------

# ---- 1. 建节点组 ----
ng = bpy.data.node_groups.get(NG_NAME)
if ng:
    bpy.data.node_groups.remove(ng)
ng = bpy.data.node_groups.new(NG_NAME, 'GeometryNodeTree')

g_in = ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
g_out = ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
socks = {}
for nm in ("延迟", "周期", "时长", "圈数"):
    s = ng.interface.new_socket(nm, in_out='INPUT', socket_type='NodeSocketFloat')
    s.default_value = DEF.get(nm, 0.0)
    socks[nm] = s

N = ng.nodes
n_in, n_out = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
bb, st = N.new('GeometryNodeBoundBox'), N.new('GeometryNodeInputSceneTime')

def mnode(op, a=None, b=None):
    n = N.new('ShaderNodeMath'); n.operation = op
    if a is not None: n.inputs[0].default_value = a
    if b is not None: n.inputs[1].default_value = b
    return n

def vnode(op, scale=None):
    n = N.new('ShaderNodeVectorMath'); n.operation = op
    if scale is not None: n.inputs[3].default_value = scale
    return n

vm_add, vm_half, vm_neg = vnode('ADD'), vnode('SCALE', 0.5), vnode('SCALE', -1.0)
m_sub, m_mod, m_div = mnode('SUBTRACT'), mnode('FLOORED_MODULO'), mnode('DIVIDE')
m_min = mnode('MINIMUM', b=1.0)
m_u2, m_2u = mnode('MULTIPLY'), mnode('MULTIPLY', b=2.0)
m_term = mnode('SUBTRACT', a=3.0)
m_s, m_total, m_angle = mnode('MULTIPLY'), mnode('MULTIPLY', b=2.0*math.pi), mnode('MULTIPLY')
comb = N.new('ShaderNodeCombineXYZ')
t1, t2 = N.new('GeometryNodeTransform'), N.new('GeometryNodeTransform')
for t in (t1, t2):
    if 'mode' in t.bl_rna.properties and 'COMPONENT' in t.bl_rna.properties['mode'].enum_items:
        t.mode = 'COMPONENT'

L = ng.links
L.new(n_in.outputs[g_in.identifier], bb.inputs['Geometry'])
L.new(bb.outputs['Min'], vm_add.inputs[0]); L.new(bb.outputs['Max'], vm_add.inputs[1])
L.new(vm_add.outputs['Vector'], vm_half.inputs[0]); L.new(vm_half.outputs['Vector'], vm_neg.inputs[0])
L.new(st.outputs['Frame'], m_sub.inputs[0]); L.new(n_in.outputs[socks['延迟'].identifier], m_sub.inputs[1])
L.new(m_sub.outputs['Value'], m_mod.inputs[0]); L.new(n_in.outputs[socks['周期'].identifier], m_mod.inputs[1])
L.new(m_mod.outputs['Value'], m_div.inputs[0]); L.new(n_in.outputs[socks['时长'].identifier], m_div.inputs[1])
L.new(m_div.outputs['Value'], m_min.inputs[0])
L.new(m_min.outputs['Value'], m_u2.inputs[0]); L.new(m_min.outputs['Value'], m_u2.inputs[1])
L.new(m_min.outputs['Value'], m_2u.inputs[0]); L.new(m_2u.outputs['Value'], m_term.inputs[1])
L.new(m_u2.outputs['Value'], m_s.inputs[0]); L.new(m_term.outputs['Value'], m_s.inputs[1])
L.new(n_in.outputs[socks['圈数'].identifier], m_total.inputs[0])
L.new(m_s.outputs['Value'], m_angle.inputs[0]); L.new(m_total.outputs['Value'], m_angle.inputs[1])
L.new(m_angle.outputs['Value'], comb.inputs['X'])
L.new(n_in.outputs[g_in.identifier], t1.inputs['Geometry'])
L.new(vm_neg.outputs['Vector'], t1.inputs['Translation'])
L.new(t1.outputs['Geometry'], t2.inputs['Geometry'])
L.new(vm_half.outputs['Vector'], t2.inputs['Translation'])
L.new(comb.outputs['Vector'], t2.inputs['Rotation'])
L.new(t2.outputs['Geometry'], n_out.inputs[g_out.identifier])
print("节点组:", NG_NAME, "| 节点数:", len(ng.nodes))

# ---- 2. 挂到每张卡（相位取轴上的 flip_delay；没有轴就按列/行现算）----
pivots = sorted([o for o in bpy.data.objects if 'flip_delay' in o], key=lambda p: p.name)
targets = []
for p in pivots:
    c = bpy.data.objects.get(p.get("flip_card", "")) if "flip_card" in p else None
    if c:
        targets.append((c, int(p.get("flip_delay", 0)), p))
if not targets:
    cards = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("G-物体")]
    for i, c in enumerate(sorted(cards, key=lambda o: o.name)):
        targets.append((c, (i % 8) * 2, None))
print("目标卡片:", len(targets))

for c, delay, p in targets:
    for m in [m for m in c.modifiers if m.name == MOD_NAME]:
        c.modifiers.remove(m)
    mod = c.modifiers.new(MOD_NAME, 'NODES')
    mod.node_group = ng
    ins = mod.properties.inputs                       # ★ 5.2 新位置
    ins[socks['延迟'].identifier]['value'] = float(delay)          # ★ Group IDProperty
    ins[socks['周期'].identifier]['value'] = DEF['周期']
    ins[socks['时长'].identifier]['value'] = DEF['时长']
    ins[socks['圈数'].identifier]['value'] = DEF['圈数']

# ---- 3. 清掉轴上残留的烘焙关键帧（否则两套动画叠加）----
for p in pivots:
    if p.animation_data:
        p.animation_data_clear()
    p.rotation_euler = (0.0, 0.0, 0.0)

# ★ 改完输入/清完动画必须打标记，否则读到缓存网格
for c, _, _ in targets:
    c.update_tag()
bpy.context.view_layer.update()
print("已挂载并打更新标记")

# ---- 4. 验证 ----
def dims(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    pts = [ev.matrix_world @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return tuple(round(max(p[i] for p in pts) - min(p[i] for p in pts), 4) for i in range(3))

print("--- 推帧（绕Y轴转 ⇒ Y 跨度恒 0.08；不同相位应错开）---")
picks = sorted(targets, key=lambda t: t[1])[:3]
for f in (5, 9, 13, 17, 21):
    scene.frame_set(f)
    print("frame %3d | %s" % (f, "  ".join("延迟%d:%s" % (d, dims(c)) for c, d, _ in picks)))
scene.frame_set(40)
bad = [c.name for c, _, _ in targets if abs(dims(c)[0] - 0.01) > 0.004]
print("静止帧竖直核验:", "全部 OK (%d 张)" % len(targets) if not bad else "FAIL → %s" % bad[:5])
scene.frame_set(1)
print("[GN DONE] 现在可整体复制/存盘，动画随数据走，参数在修改器面板可调")
