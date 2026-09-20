# s71_helix_check.py —— v3 滚筒斜纹：斜向 + 运动方向验证
#   渲染 f = 365 / 400 / 435 三帧，看条纹是不是【/ 形】且往【左上】流动。
#   上升偏移 = -frame×0.01，两帧间 Δoffset = 0.35；高度条纹 N=2 ⇒ 相位走 0.7 个周期。
#   隔离场景渲染时节点树驱动不会被求值（本机实测），故每帧渲染前都改一次 ctrl 值触发。
import bpy
import os
import time
import numpy as np
from mathutils import Vector

TARGET = '滚动效果网格体'
CTRL = '竖条旋转控制'
OUTDIR = r'D:\workbuddy\2026-09-20-09-39-42\_liantiao\preview'
FRAMES = [365, 400, 435]
RES = (420, 900)
ORTHO = 15.5
CENTER = Vector((30.9216, 2.8832, 5.6938))
RUN = str(int(time.time()))[-6:]

main = bpy.context.scene
ob = bpy.data.objects[TARGET]
ctrl = bpy.data.objects[CTRL]
KEYS = ('条纹数量', '高度条纹数', '前缘宽度', '拖尾起点', '上升速度', '旋转速度', '发光强度')
base = {k: ctrl.get(k) for k in KEYS}
base_counts = (len(bpy.data.objects), len(bpy.data.scenes), len(bpy.data.worlds))

sc = bpy.data.scenes.new('__HX_PV__')
sc.collection.objects.link(ob)
sc.collection.objects.link(ctrl)
w = bpy.data.worlds.new('__HX_PV_W__')
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
bg.inputs[1].default_value = 0.0
sc.world = w
cd = bpy.data.cameras.new('__HX_PV_CAM__')
cd.type = 'ORTHO'
cd.ortho_scale = ORTHO
cam = bpy.data.objects.new('__HX_PV_CAM__', cd)
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
    for k in KEYS:                       # 抖动触发驱动重算（见坑 7）
        v = ctrl.get(k)
        ctrl[k] = float(v) * 1.0001 + 1e-7
        ctrl[k] = float(v)
    ctrl.update_tag()
    m = bpy.data.materials['滚动效果网格体_竖条旋转']
    m.update_tag()
    m.node_tree.update_tag()
    bpy.context.view_layer.update()


def shot(f):
    sc.render.filepath = os.path.join(OUTDIR, 'hx_f%03d_%s.png' % (f, RUN))
    main.frame_set(f)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True, scene=sc.name)
    p = sc.render.filepath
    assert os.path.exists(p), p
    shots.append(p)
    print('  f=%d  %s B' % (f, os.path.getsize(p)))


print('--- 设定：K=3 N=2（斜角 41°）、纯上升、速度 0.01 ---')
set_props(条纹数量=3, 高度条纹数=2, 前缘宽度=0.12, 拖尾起点=0.22,
          上升速度=0.01, 旋转速度=0.0, 发光强度=5.0)
print('--- 渲染 ---')
for f in FRAMES:
    shot(f)

# 斜向判定：读第一帧，在每个高度上找最亮列，看"高度升高时亮列往哪边移"
im = bpy.data.images.load(shots[0]); im.reload()
wpx, hpx = im.size
arr = np.array(im.pixels[:], dtype=np.float32).reshape(hpx, wpx, 4)
lum = arr[:, :, :3].mean(axis=2)
lum = lum[::-1]                                   # 翻成"行 0 = 顶部"
rows = [int(hpx * p) for p in (0.20, 0.35, 0.50, 0.65, 0.80)]
print()
print('--- 斜向判定（每个高度上最亮带的水平位置，0=左 1=右）---')
xs = []
for r in rows:
    col = lum[r, :]
    x = int(np.argmax(col))
    xs.append(x / float(wpx))
    print('   高度 %.2f  →  最亮列 %5.1f%%' % (1 - r / float(hpx), x / float(wpx) * 100))
dx = xs[0] - xs[-1]
print('   顶部 − 底部 = %+.1f%%' % (dx * 100))
print('   判定: %s' % ('顶部偏右 ⇒ 条纹为 / 形（左下→右上）✔ 与 v3 设计一致'
                     if dx > 0.01 else
                     ('顶部偏左 ⇒ 条纹为 \\ 形' if dx < -0.01 else '接近竖直，斜角太小')))
bpy.data.images.remove(im)

for k, v in base.items():
    ctrl[k] = v
for k in KEYS:
    v = ctrl.get(k)
    ctrl[k] = float(v) * 1.0001 + 1e-7
    ctrl[k] = float(v)
ctrl.update_tag()
bpy.context.view_layer.update()
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
sheet(shots, os.path.join(OUTDIR, 'O_v3_滚筒斜纹_三帧运动.png'))

print()
print('--- 清理 ---')
bpy.context.window.scene = main
bpy.data.scenes.remove(sc)
bpy.data.objects.remove(cam, do_unlink=True)
bpy.data.worlds.remove(w)
print('  leftover:', [o.name for o in bpy.data.objects if o.name.startswith('__HX_PV')],
      [s.name for s in bpy.data.scenes if s.name.startswith('__HX_PV')],
      [x.name for x in bpy.data.worlds if x.name.startswith('__HX_PV')])
print('  对象 %d->%d | 场景 %d->%d | 世界 %d->%d'
      % (base_counts[0], len(bpy.data.objects), base_counts[1], len(bpy.data.scenes),
         base_counts[2], len(bpy.data.worlds)))
print()
print('HELIX_OK')
