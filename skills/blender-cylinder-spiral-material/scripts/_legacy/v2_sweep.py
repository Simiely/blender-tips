# s70_v2_sweep.py — v2 参数对比渲染
#   A) 形状：对称条纹 / 流星（默认）/ 细长流星
#   B) 条纹数量：K = 2 / 4 / 8
# 说明：隔离临时场景里节点树驱动不会被渲染求值（本机实测），
#       所以每张图渲染前都【改一次 ctrl 值】触发更新（s64 已验证可行）。
import bpy
import os
import time
import numpy as np
from mathutils import Vector

TARGET = '滚动效果网格体'
CTRL = '竖条旋转控制'
OUTDIR = r'D:\workbuddy\2026-09-20-09-39-42\_liantiao\preview'
FRAME = 365
RES = (300, 650)
ORTHO = 15.5
CENTER = Vector((30.9216, 2.8832, 5.6938))
RUN = str(int(time.time()))[-6:]

main = bpy.context.scene
ob = bpy.data.objects[TARGET]
ctrl = bpy.data.objects[CTRL]
KEYS = ('条纹数量', '前缘宽度', '拖尾起点', '旋转速度', '发光强度')
base = {k: ctrl.get(k) for k in KEYS}
base_counts = (len(bpy.data.objects), len(bpy.data.scenes), len(bpy.data.worlds))

sc = bpy.data.scenes.new('__V2_PV__')
sc.collection.objects.link(ob)
sc.collection.objects.link(ctrl)
w = bpy.data.worlds.new('__V2_PV_W__')
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
bg.inputs[1].default_value = 0.0
sc.world = w
cd = bpy.data.cameras.new('__V2_PV_CAM__')
cd.type = 'ORTHO'
cd.ortho_scale = ORTHO
cam = bpy.data.objects.new('__V2_PV_CAM__', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = CENTER + Vector((60.0, 0.0, 0.0))
cam.rotation_euler = (CENTER - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.engine = 'CYCLES'
sc.cycles.samples = 24
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'
sc.render.dither_intensity = 0.0
sc.render.film_transparent = False
sc.render.use_stamp = False
sc.view_settings.view_transform = 'AgX'

shots = []


def set_props(**kw):
    for k, v in kw.items():
        ctrl[k] = float(v)
    # 抖一下确保所有驱动都被推给渲染 depsgraph
    for k in KEYS:
        v = ctrl.get(k)
        ctrl[k] = float(v) * 1.0001 + 1e-7
        ctrl[k] = float(v)
    ctrl.update_tag()
    m = bpy.data.materials['滚动效果网格体_竖条旋转']
    m.update_tag()
    m.node_tree.update_tag()
    bpy.context.view_layer.update()


def shot(tag):
    sc.render.filepath = os.path.join(OUTDIR, 'v2_%s_%s.png' % (tag, RUN))
    main.frame_set(FRAME)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True, scene=sc.name)
    p = sc.render.filepath
    assert os.path.exists(p), p
    shots.append(p)
    print('  %-16s %s B' % (tag, os.path.getsize(p)))


print('--- A) 形状对比（K=4）---')
for tag, a, b in (('A1_对称条纹', 0.35, 0.65), ('A2_流星', 0.12, 0.22), ('A3_细长流星', 0.04, 0.14)):
    set_props(条纹数量=4, 前缘宽度=a, 拖尾起点=b)
    shot(tag)

print()
print('--- B) 条纹数量对比（A=0.12 B=0.22）---')
for k in (2, 4, 8):
    set_props(条纹数量=k, 前缘宽度=0.12, 拖尾起点=0.22)
    shot('B%d_K%d' % (k, k))

set_props(**{k: base[k] for k in KEYS})
print()
print('  已还原:', {k: ctrl.get(k) for k in KEYS})


def sheet(paths, outp):
    imgs = [bpy.data.images.load(p) for p in paths]
    W = sum(i.size[0] for i in imgs)
    H = max(i.size[1] for i in imgs)
    buf = np.zeros((H, W, 4), dtype=np.float32)
    buf[:, :, 3] = 1.0
    x = 0
    for i in imgs:
        iw, ih = i.size
        buf[:ih, x:x + iw] = np.array(i.pixels[:], dtype=np.float32).reshape(ih, iw, 4)
        x += iw
        bpy.data.images.remove(i)
    out = bpy.data.images.new(os.path.basename(outp), W, H)
    out.pixels = buf.ravel()
    out.filepath_raw = outp
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(out)
    print('  sheet ->', os.path.basename(outp), os.path.getsize(outp), 'B')


print()
sheet(shots[:3], os.path.join(OUTDIR, 'M_v2_三种形状_对称_流星_细长.png'))
sheet(shots[3:], os.path.join(OUTDIR, 'N_v2_条纹数量_K2_K4_K8.png'))

print()
print('--- 清理 ---')
bpy.context.window.scene = main
bpy.data.scenes.remove(sc)
bpy.data.objects.remove(cam, do_unlink=True)
bpy.data.worlds.remove(w)
print('  leftover:', [o.name for o in bpy.data.objects if o.name.startswith('__V2_PV')],
      [s.name for s in bpy.data.scenes if s.name.startswith('__V2_PV')],
      [x.name for x in bpy.data.worlds if x.name.startswith('__V2_PV')])
print('  对象 %d->%d | 场景 %d->%d | 世界 %d->%d'
      % (base_counts[0], len(bpy.data.objects), base_counts[1], len(bpy.data.scenes),
         base_counts[2], len(bpy.data.worlds)))
print()
print('V2SWEEP_OK')
