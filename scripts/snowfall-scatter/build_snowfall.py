# -*- coding: utf-8 -*-
# 下雪系统 · 完全重写
# 逻辑：在 平面.005 的 XY 覆盖区内, 生成 N_X×N_Y 个随机落点;
#       每片雪花从「天空」匀速下落到「地面(-1.3m)」, 触地即循环回天空,
#       顶部有 0→scale 的入场缩放. 全程实例化低模雪花, 源对象隐藏不渲染.
import bpy
import mathutils
import math

# ===== 参数(改这里即可) =====
SNOW_NAME   = '花瓣雪花_低模'    # 雪花源网格(26 顶点低模雪花, 浅蓝材质)
PLANE       = '平面.005'        # 地面参考(其 XY 足迹 = 落雪范围, 高度 = 地面)
HOST        = '下雪_宿主'
GROUP       = '下雪_GN'
COLL        = '下雪_效果'
N_X, N_Y    = 250, 200          # 生成点(250*200 = 50,000)
FALL_SPAN   = 30.0              # 下落高度跨度(天空 = 地面 + 30m, 加高落雪区)
CYCLE       = 60.0              # 一次完整下落的秒数(30m/60s ≈ 0.50m/s, 保持真实雪速)
FADE_FRAC   = 0.02              # 顶部入场缩放窗口(prog 0~2% 内 scale 0->满)
FLAKE_SCALE = 0.6                # 实例缩放: 低模源外径0.16 × 0.6 = 半径≈0.096m(最早效果)
VERT_TILT   = 90.0              # 朝向往Z轴改为垂直(度): 让平视也看得到雪花平面
TILT_JITTER = 15.0              # 倾角随机抖动(±度)
FACE_SPIN   = 360.0             # 绕Z随机朝向(度)
FLARE_R     = 0.32              # 薄片雪花外接直径(m)
FLARE_R_IN  = 0.13              # 薄片雪花凹陷半径(m)


def ensure_flat_flake(name):
    """建 12 顶点平面 6 角星薄片雪花(已存在则直接返回, 不重建)。"""
    ob = bpy.data.objects.get(name)
    if ob is not None:
        return ob
    verts = []
    for i in range(12):
        a = i * (math.pi / 6.0)
        rad = FLARE_R if i % 2 == 0 else FLARE_R_IN
        verts.append((rad * math.cos(a), rad * math.sin(a), 0.0))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], [list(range(12))])
    me.update()
    ob = bpy.data.objects.new(name, me)
    (bpy.data.collections.get(COLL) or bpy.context.scene.collection).objects.link(ob)
    old = bpy.data.objects.get('花瓣雪花_低模') or bpy.data.objects.get('花瓣雪花')
    if old is not None and old.data and old.data.materials:
        ob.data.materials.append(old.data.materials[0])
    return ob


# ===== 收集依赖对象 =====
snow = ensure_flat_flake(SNOW_NAME)
if snow is None:
    raise SystemExit('缺雪花源对象')
snow.hide_render = True
snow.hide_viewport = True
snow.visible_camera = False

# ===== 读取地面参考 平面.005 的世界包围盒 =====
try:
    p = bpy.data.objects.get(PLANE)
    if p is None:
        raise ValueError('no plane')
    mat = p.matrix_world
    wc = [mat @ mathutils.Vector(c) for c in p.bound_box]
    xs = [c[0] for c in wc]; ys = [c[1] for c in wc]; zs = [c[2] for c in wc]
    CX  = (max(xs) + min(xs)) / 2.0
    CY  = (max(ys) + min(ys)) / 2.0
    HX  = (max(xs) - min(xs)) / 2.0
    HY  = (max(ys) - min(ys)) / 2.0
    GROUND = (max(zs) + min(zs)) / 2.0
except Exception as e:
    CX, CY, HX, HY, GROUND = 0.0, 0.0, 8.0, 8.0, -1.3
    print('[snow] 读取 %s 失败(%s), 用默认' % (PLANE, e))
SKY = GROUND + FALL_SPAN

# ===== 集合与宿主 =====
coll = bpy.data.collections.get(COLL)
if coll is None:
    coll = bpy.data.collections.new(COLL)
    if COLL not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
host = bpy.data.objects.get(HOST)
if host is None:
    host = bpy.data.objects.new(HOST, None)
    coll.objects.link(host)
# 宿主变换清零, 雪区才能精确锚定到参考平面(地面=-1.3), 否则会整体偏移
host.location = (0.0, 0.0, 0.0)
host.rotation_euler = (0.0, 0.0, 0.0)
host.scale = (1.0, 1.0, 1.0)

# ===== 重建节点组(彻底删除旧的) =====
old_grp = bpy.data.node_groups.get(GROUP)
if old_grp:
    for m in list(host.modifiers):
        if m.type == 'NODES' and m.node_group is old_grp:
            host.modifiers.remove(m)
    bpy.data.node_groups.remove(old_grp)
ng = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')


def N(*tys):
    for t in tys:
        try:
            return ng.nodes.new(t)
        except RuntimeError as e:
            if '尚未定义' not in str(e):
                raise
    raise RuntimeError('no node: %s' % (tys,))


def set_rv(node, lo, hi):
    for sock in ('Min', 'Max'):
        if sock in node.inputs:
            node.inputs[sock].default_value = lo if sock == 'Min' else hi


def set_seed(node, val):
    if 'Seed' in node.inputs:
        node.inputs['Seed'].default_value = val
    elif 'ID' in node.inputs:
        node.inputs['ID'].default_value = val


# ---- 建节点 ----
grid  = N('GeometryNodeMeshGrid')
m2p   = N('GeometryNodeMeshToPoints')
idx   = N('GeometryNodeInputIndex')                 # 每点唯一编号 -> 驱动随机 ID(防"同随机值冻结/堆顶")
scene = N('GeometryNodeInputSceneTime')
phRv  = N('FunctionNodeRandomValue', 'ShaderNodeRandomValue')   # 相位(沿下落列分布)
xrv   = N('FunctionNodeRandomValue', 'ShaderNodeRandomValue')   # X 随机
yrv   = N('FunctionNodeRandomValue', 'ShaderNodeRandomValue')   # Y 随机
invC  = N('FunctionNodeMath', 'ShaderNodeMath')                 # t / CYCLE
addP  = N('FunctionNodeMath', 'ShaderNodeMath')                 # + 相位
mod   = N('FunctionNodeMath', 'ShaderNodeMath')                 # fmod -> prog
zsub  = N('FunctionNodeMath', 'ShaderNodeMath')                 # 1 - prog
zsk   = N('FunctionNodeMath', 'ShaderNodeMath')                 # * FALL_SPAN
zadd  = N('FunctionNodeMath', 'ShaderNodeMath')                 # + GROUND
cxz   = N('FunctionNodeCombineXYZ', 'ShaderNodeCombineXYZ')
setp  = N('GeometryNodeSetPosition')
objI  = N('GeometryNodeObjectInfo')
iop   = N('GeometryNodeInstanceOnPoints')
mapr  = N('FunctionNodeMapRange', 'ShaderNodeMapRange', 'GeometryNodeMapRange')  # 顶部入场缩放(0->满, 触地时已为满尺寸)
cxs   = N('FunctionNodeCombineXYZ', 'ShaderNodeCombineXYZ')
rvT   = N('FunctionNodeRandomValue', 'ShaderNodeRandomValue')   # 倾角(近垂直)
rvF   = N('FunctionNodeRandomValue', 'ShaderNodeRandomValue')   # 绕Z朝向
crot  = N('FunctionNodeCombineXYZ', 'ShaderNodeCombineXYZ')
out   = ng.nodes.new('NodeGroupOutput')

# ---- 常量 ----
grid.inputs['Size X'].default_value = 1.0
grid.inputs['Size Y'].default_value = 1.0
grid.inputs['Vertices X'].default_value = N_X
grid.inputs['Vertices Y'].default_value = N_Y
set_rv(phRv, 0.0, 1.0)
set_rv(xrv, CX - HX, CX + HX)
set_rv(yrv, CY - HY, CY + HY)
import math as _m
set_rv(rvT, _m.radians(VERT_TILT - TILT_JITTER), _m.radians(VERT_TILT + TILT_JITTER))
set_rv(rvF, 0.0, _m.radians(FACE_SPIN))
set_seed(phRv, 29)
set_seed(xrv, 7)
set_seed(yrv, 13)
set_seed(rvT, 401)
set_seed(rvF, 509)
invC.inputs[1].default_value = 1.0 / CYCLE
mod.inputs[1].default_value = 1.0
zsub.inputs[0].default_value = 1.0
zsk.inputs[0].default_value = FALL_SPAN
zadd.inputs[1].default_value = GROUND
mapr.inputs['From Min'].default_value = 0.0
mapr.inputs['From Max'].default_value = FADE_FRAC
mapr.inputs['To Min'].default_value = 0.0
mapr.inputs['To Max'].default_value = FLAKE_SCALE
mapr.clamp = True
objI.inputs['Object'].default_value = snow
objI.transform_space = 'RELATIVE'
for nd, op in ((invC, 'MULTIPLY'), (addP, 'ADD'), (mod, 'FLOORED_MODULO'),
               (zsub, 'SUBTRACT'), (zsk, 'MULTIPLY'), (zadd, 'ADD')):
    nd.operation = op

# ---- 接线: 每点显式 ID -> 随机值互不相同(防顶部堆积/冻结) ----
LN = ng.links.new
LN(idx.outputs['Index'], phRv.inputs['ID'])
LN(idx.outputs['Index'], xrv.inputs['ID'])
LN(idx.outputs['Index'], yrv.inputs['ID'])
LN(idx.outputs['Index'], rvT.inputs['ID'])
LN(idx.outputs['Index'], rvF.inputs['ID'])
# prog = fmod(seconds/CYCLE + phase, 1) 全体匀速
LN(scene.outputs['Seconds'], invC.inputs[0])
LN(invC.outputs[0], addP.inputs[0])
LN(phRv.outputs[0], addP.inputs[1])
LN(addP.outputs[0], mod.inputs[0])
# Z = GROUND + (1 - prog) * FALL_SPAN
LN(mod.outputs[0], zsub.inputs[1])
LN(zsub.outputs[0], zsk.inputs[1])
LN(zsk.outputs[0], zadd.inputs[0])
# 位置
LN(xrv.outputs[0], cxz.inputs['X'])
LN(yrv.outputs[0], cxz.inputs['Y'])
LN(zadd.outputs[0], cxz.inputs['Z'])
# 顶部入场缩放
LN(mod.outputs[0], mapr.inputs['Value'])
LN(mapr.outputs['Result'], cxs.inputs['X'])
LN(mapr.outputs['Result'], cxs.inputs['Y'])
LN(mapr.outputs['Result'], cxs.inputs['Z'])
# 随机朝向: 立起(近垂直/平行Z) + 绕Z随机转
LN(rvT.outputs[0], crot.inputs['X'])
LN(rvF.outputs[0], crot.inputs['Z'])
# 主链
LN(grid.outputs[0], m2p.inputs[0])
LN(m2p.outputs[0], setp.inputs['Geometry'])
LN(cxz.outputs[0], setp.inputs['Position'])
LN(setp.outputs['Geometry'], iop.inputs['Points'])
LN(objI.outputs['Geometry'], iop.inputs['Instance'])
LN(cxs.outputs[0], iop.inputs['Scale'])
LN(crot.outputs[0], iop.inputs['Rotation'])
LN(iop.outputs['Instances'], out.inputs['Geometry'])

# ---- 挂修改器 ----
mod = next((m for m in host.modifiers if m.type == 'NODES'), None)
if mod is None:
    mod = host.modifiers.new(GROUP, 'NODES')
mod.node_group = ng
mod.show_viewport = True

print('[snow] 重写完成: %s 实例=%d 源=%s 中心=(%.1f,%.1f) 半宽=(%.1f,%.1f) 地面=%.2f 天空=%.2f 缩放=%.2f'
      % (HOST, N_X * N_Y, snow.name, CX, CY, HX, HY, GROUND, SKY, FLAKE_SCALE))
bpy.context.evaluated_depsgraph_get().update()
print('[snow] 评估通过')