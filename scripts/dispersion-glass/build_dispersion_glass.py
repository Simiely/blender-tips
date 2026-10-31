# 水晶色散材质 · 构建脚本
# 桥安全：无 __main__ 守卫、无文件级 operator、纯内存操作
# 用法（二选一）：
#   1) 桥：python send.py build_dispersion_glass.py
#   2) Scripting 工作区：文本编辑器打开本文件 → Run Script
#
# 前置：先选中目标网格对象（脚本只改选中对象的材质槽）

import bpy

MAT_NAME = "dispersion glass"

# ---- 参数（按需改这几个即可）----
IOR_R = 1.450
IOR_G = 1.500
IOR_B = 1.550
IOR_W = 1.500
NOISE_SCALE = 15.0
NOISE_DETAIL = 15.0
NOISE_ROUGH = 1.0
RAMP_BLACK_EDGE = 0.459      # ★ 第二段黑标位置：写成两段（不要这个黑标）会变磨砂白

old = bpy.data.materials.get(MAT_NAME)
if old:
    bpy.data.materials.remove(old)
mat = bpy.data.materials.new(MAT_NAME)
mat.use_nodes = True
nt = mat.node_tree
for nd in list(nt.nodes):
    nt.nodes.remove(nd)


def N(t, **kw):
    n = nt.nodes.new(t)
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def L(a, sa, b, sb):
    nt.links.new(a.outputs[sa], b.inputs[sb])


# ---- 噪波 → 三段色带 ----
tc = N("ShaderNodeTexCoord")
mp = N("ShaderNodeMapping")
mp.vector_type = 'POINT'
mp.inputs["Scale"].default_value = (1.0, 1.0, 1.0)          # 恒等，缩放靠噪波自身 Scale
L(tc, "Object", mp, "Vector")

nz = N("ShaderNodeTexNoise")
nz.noise_dimensions = '3D'
nz.inputs["Scale"].default_value = NOISE_SCALE
nz.inputs["Detail"].default_value = NOISE_DETAIL
nz.inputs["Roughness"].default_value = NOISE_ROUGH
nz.inputs["Lacunarity"].default_value = 2.0
nz.inputs["Distortion"].default_value = 0.0
L(mp, 0, nz, "Vector")

ramp = N("ShaderNodeValToRGB")
ramp.color_ramp.interpolation = 'LINEAR'
ramp.color_ramp.color_mode = 'RGB'
els = ramp.color_ramp.elements
els[0].position = 0.0
els[0].color = (0, 0, 0, 1)
els[1].position = 1.0
els[1].color = (1, 1, 1, 1)
mid = els.new(RAMP_BLACK_EDGE)                              # ★ 关键：三段
mid.color = (0, 0, 0, 1)
L(nz, "Fac", ramp, 0)


def glass(col, ior, rough):
    g = N("ShaderNodeBsdfGlass")
    g.inputs["Color"].default_value = (col[0], col[1], col[2], 1.0)
    g.inputs["IOR"].default_value = ior
    g.inputs["Roughness"].default_value = 0.0
    if rough:
        L(ramp, "Color", g, "Roughness")
    return g


g1 = glass((1, 0, 0), IOR_R, True)
g2 = glass((0, 1, 0), IOR_G, True)
g3 = glass((0, 0, 1), IOR_B, True)
g4 = glass((1, 1, 1), IOR_W, False)                         # 白色那片不接色带

a1 = N("ShaderNodeAddShader")
L(g2, 0, a1, 0)
L(g3, 0, a1, 1)
a2 = N("ShaderNodeAddShader")
L(a1, 0, a2, 0)
L(g1, 0, a2, 1)

lp = N("ShaderNodeLightPath")
mx = N("ShaderNodeMixShader")
L(lp, "Transmission Depth", mx, 0)                          # ★ 必须进 Fac
L(a2, 0, mx, 1)
L(g4, 0, mx, 2)

out = N("ShaderNodeOutputMaterial")
L(mx, 0, out, 0)

# ---- 套到选中对象 ----
targets = [o for o in bpy.context.selected_objects if o.type == 'MESH']
if not targets:
    targets = [o for o in bpy.data.objects if o.type == 'MESH']
for o in targets:
    if not o.material_slots:
        o.data.materials.append(mat)
    else:
        o.material_slots[0].material = mat
    print("assigned ->", o.name)

print("nodes=%d links=%d" % (len(nt.nodes), len(nt.links)))
print("ramp stops=", [(round(e.position, 3), tuple(round(c, 2) for c in e.color[:3]))
                      for e in ramp.color_ramp.elements])
print("BUILD OK")
