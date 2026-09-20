# s64_kdiag.py —— 黑盒诊断：'条纹数量' K 在【渲染】时到底有没有生效？
#   固定 旋转速度=0（spin=0 ⇒ f = u×K），渲染 K = 1 / 4 / 16
#   可见弧 u∈[0.301,0.699] ⇒ 预期周期数 = 0.398×K = 0.4 / 1.6 / 6.4
#   读剖面数「亮区段数」，与预期对比。
import bpy
import os
import numpy as np
from mathutils import Vector

TARGET = '滚动效果网格体'
CTRL = '竖条旋转控制'
OUTDIR = r'D:\workbuddy\2026-09-20-09-39-42\_liantiao\preview'
FRAME = 365
RES = (420, 900)
ORTHO = 15.5
CENTER = Vector((30.9216, 2.8832, 5.6938))
R_CYL = 3.7789
PHI_MAX = 1.25
NPHI = 601
STRENGTH = 0.6

main = bpy.context.scene
ob = bpy.data.objects[TARGET]
ctrl = bpy.data.objects[CTRL]
KEYS = ('条纹数量', '前缘宽度', '拖尾起点', '旋转速度', '发光强度')
base = {k: ctrl.get(k) for k in KEYS}

sc = bpy.data.scenes.new('__KD_PV__')
sc.collection.objects.link(ob)
w = bpy.data.worlds.new('__KD_PV_W__')
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
bg.inputs[1].default_value = 0.0
sc.world = w
cd = bpy.data.cameras.new('__KD_PV_CAM__')
cd.type = 'ORTHO'
cd.ortho_scale = ORTHO
cam = bpy.data.objects.new('__KD_PV_CAM__', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = CENTER + Vector((60.0, 0.0, 0.0))
cam.rotation_euler = (CENTER - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.engine = 'CYCLES'
sc.cycles.samples = 12
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'
sc.render.dither_intensity = 0.0
sc.render.film_transparent = False
sc.render.use_stamp = False
sc.view_settings.view_transform = 'Standard'


def touch():
    ctrl.update_tag()
    m = bpy.data.materials['滚动效果网格体_竖条旋转']
    m.update_tag()
    m.node_tree.update_tag()
    bpy.context.view_layer.update()


def srgb_to_linear(v):
    v = np.asarray(v, dtype=np.float64)
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def mask_profile(path, strength):
    """读 PNG（sRGB 编码）→ 反解线性 → 除强度 ⇒ mask"""
    im = bpy.data.images.load(path)
    wpx, hpx = im.size
    arr = np.array(im.pixels[:], dtype=np.float32).reshape(hpx, wpx, 4)
    lum = arr[:, :, :3].mean(axis=2)
    band = lum[int(hpx * 0.30):int(hpx * 0.70), :]
    col = band.mean(axis=0)
    bpy.data.images.remove(im)
    lin = srgb_to_linear(col) / strength
    pix_per_unit_x = RES[0] / ORTHO
    PHI = np.linspace(-PHI_MAX, PHI_MAX, NPHI)
    X = R_CYL * np.sin(PHI) * pix_per_unit_x + RES[0] / 2.0
    return np.clip(np.interp(X, np.arange(wpx), lin), 0, 2), PHI


def count_bright(m):
    """>50% 的连续段数"""
    b = m > 0.5
    n, i = 0, 0
    while i < len(b):
        if b[i]:
            n += 1
            while i < len(b) and b[i]:
                i += 1
        else:
            i += 1
    return n


print('--- 渲染 K 扫描（速度=0）---')
ctrl['旋转速度'] = 0.0
ctrl['发光强度'] = STRENGTH
ctrl['前缘宽度'] = 0.12
ctrl['拖尾起点'] = 0.22
touch()

for k in (1, 4, 16):
    ctrl['条纹数量'] = float(k)
    touch()
    p = os.path.join(OUTDIR, 'kdiag_K%02d.png' % k)
    sc.render.filepath = p
    main.frame_set(FRAME)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True, scene=sc.name)
    m, PHI = mask_profile(p, STRENGTH)
    exp_cycles = 0.398 * k
    print('  K=%-3d | mask min/mean/max = %.4f/%.4f/%.4f | >50%% 段数 = %d | 预期周期数 = %.2f'
          % (k, m.min(), m.mean(), m.max(), count_bright(m), exp_cycles))

print()
print('--- 驱动真值（渲染后从求值图读）---')
dg = bpy.context.evaluated_depsgraph_get()
ev = bpy.data.materials['滚动效果网格体_竖条旋转'].evaluated_get(dg).node_tree
print('  条纹数量K.inputs[1] =', ev.nodes['条纹数量K'].inputs[1].default_value)
print('  旋转相位.inputs[1]  =', ev.nodes['旋转相位'].inputs[1].default_value)
print('  ctrl["条纹数量"]     =', ctrl.get('条纹数量'))

for k, v in base.items():
    ctrl[k] = v
touch()
print()
print('  已还原:', {k: ctrl.get(k) for k in KEYS})

bpy.context.window.scene = main
bpy.data.scenes.remove(sc)
bpy.data.objects.remove(cam, do_unlink=True)
bpy.data.worlds.remove(w)
print('  leftover:', [o.name for o in bpy.data.objects if o.name.startswith('__KD_PV')],
      [s.name for s in bpy.data.scenes if s.name.startswith('__KD_PV')],
      [x.name for x in bpy.data.worlds if x.name.startswith('__KD_PV')])
print()
print('KDIAG_OK')
