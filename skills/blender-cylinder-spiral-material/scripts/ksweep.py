# s53_ksweep.py — 条纹数量对比（定「像不像绕柱的条纹」）
#   正面：K=4（当前默认）/ 6 / 8  +  一张 3/4 斜视（K=6，看端盖已干净）
# 规则同前：临时场景只额外 link；用完清理并自证；最后还原 K。
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
DIRS = {
    'face': Vector((60.0, 0.0, 0.0)),
    'iso': Vector((42.0, -42.0, 26.0)),
}

main = bpy.context.scene
ob = bpy.data.objects[TARGET]
ctrl = bpy.data.objects[CTRL]
base_K = ctrl.get('条纹数量')
base = (len(bpy.data.objects), len(bpy.data.scenes), len(bpy.data.worlds))

sc = bpy.data.scenes.new('__KS_PV__')
sc.collection.objects.link(ob)
w = bpy.data.worlds.new('__KS_PV_W__')
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
bg.inputs[1].default_value = 0.0
sc.world = w
cd = bpy.data.cameras.new('__KS_PV_CAM__')
cd.type = 'ORTHO'
cd.ortho_scale = ORTHO
cam = bpy.data.objects.new('__KS_PV_CAM__', cd)
sc.collection.objects.link(cam)
sc.camera = cam
sc.render.engine = 'CYCLES'
sc.cycles.samples = 24
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'
sc.render.dither_intensity = 0.0
sc.render.film_transparent = False
sc.render.use_stamp = True
for f in ('use_stamp_date', 'use_stamp_time', 'use_stamp_camera', 'use_stamp_scene',
          'use_stamp_filename', 'use_stamp_render_time', 'use_stamp_lens',
          'use_stamp_marker', 'use_stamp_memory', 'use_stamp_hostname'):
    if hasattr(sc.render, f):
        setattr(sc.render, f, False)
sc.render.use_stamp_note = True
sc.render.stamp_font_size = 24

shots = []


def touch():
    ctrl.update_tag()
    for m in bpy.data.materials:
        if m.name.startswith('滚动效果网格体'):
            m.update_tag()
            if m.use_nodes and m.node_tree:
                m.node_tree.update_tag()
    bpy.context.view_layer.update()


def shot(tag, dirkey):
    off = DIRS[dirkey]
    cam.location = CENTER + off
    cam.rotation_euler = (CENTER - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.view_settings.view_transform = 'AgX'
    sc.render.stamp_note_text = tag
    p = os.path.join(OUTDIR, 'ks_%s.png' % tag.replace(' ', '_').replace('=', ''))
    sc.render.filepath = p
    main.frame_set(FRAME)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True, scene=sc.name)
    assert os.path.exists(p)
    shots.append(p)
    print('  ', tag, os.path.getsize(p), 'B')


print('--- K 扫描 ---')
for k in (4, 6, 8):
    ctrl['条纹数量'] = float(k)
    touch()
    shot('K%d' % k, 'face')
ctrl['条纹数量'] = 6.0
touch()
shot('K6-iso', 'iso')

ctrl['条纹数量'] = base_K
touch()
print('  已还原 K =', ctrl.get('条纹数量'))


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
print('--- 拼图 ---')
sheet(shots, os.path.join(OUTDIR, 'K_条纹数量_K4_K6_K8_加斜视.png'))

print()
print('--- 清理 ---')
bpy.context.window.scene = main
bpy.data.scenes.remove(sc)
bpy.data.objects.remove(cam, do_unlink=True)
bpy.data.worlds.remove(w)
for im in list(bpy.data.images):
    if 'png' in im.name:
        bpy.data.images.remove(im)
print('  leftover:', [o.name for o in bpy.data.objects if o.name.startswith('__KS_PV')],
      [s.name for s in bpy.data.scenes if s.name.startswith('__KS_PV')],
      [x.name for x in bpy.data.worlds if x.name.startswith('__KS_PV')])
print('  对象 %d->%d | 场景 %d->%d | 世界 %d->%d'
      % (base[0], len(bpy.data.objects), base[1], len(bpy.data.scenes),
         base[2], len(bpy.data.worlds)))
print()
print('KSWEEP_OK')
