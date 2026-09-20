# s54_tailsweep.py — 流星拖尾参数对比
#   A) 流星拖尾 0 / 0.4 / 0.8 / 1.0（其余默认）
#   B) 最像 SVG 的配置：细亮带 + 满拖尾 + 少条纹（w 0.15 / tl 1.0 / K 2）
# 用完还原所有控件值；临时场景自清。
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

main = bpy.context.scene
ob = bpy.data.objects[TARGET]
ctrl = bpy.data.objects[CTRL]
KEYS = ('条纹数量', '条纹宽度', '渐变柔化', '流星拖尾')
base = {k: ctrl.get(k) for k in KEYS}
base_counts = (len(bpy.data.objects), len(bpy.data.scenes), len(bpy.data.worlds))

sc = bpy.data.scenes.new('__TS_PV__')
sc.collection.objects.link(ob)
w = bpy.data.worlds.new('__TS_PV_W__')
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
bg.inputs[1].default_value = 0.0
sc.world = w
cd = bpy.data.cameras.new('__TS_PV_CAM__')
cd.type = 'ORTHO'
cd.ortho_scale = ORTHO
cam = bpy.data.objects.new('__TS_PV_CAM__', cd)
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


def ramp_pos():
    return [round(e.position, 4) for e in
            bpy.data.materials['滚动效果网格体_竖条旋转'].node_tree.nodes['条纹遮罩'].color_ramp.elements]


def shot(tag):
    sc.view_settings.view_transform = 'AgX'
    sc.render.stamp_note_text = tag
    p = os.path.join(OUTDIR, 'ts_%s.png' % tag.replace(' ', '_').replace('/', '-'))
    sc.render.filepath = p
    main.frame_set(FRAME)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True, scene=sc.name)
    assert os.path.exists(p)
    shots.append(p)
    print('  ', tag, '| 色标', ramp_pos(), '|', os.path.getsize(p), 'B')


print('--- A) 流星拖尾扫描（w=0.4 / 柔化0.6 / K=4）---')
for tl in (0.0, 0.4, 0.8, 1.0):
    ctrl['流星拖尾'] = tl
    touch()
    shot('tl%02d' % int(round(tl * 100)))

print()
print('--- B) 最像 SVG 的配置（细亮带 + 满拖尾 + 少条纹）---')
ctrl['流星拖尾'] = 1.0
ctrl['条纹宽度'] = 0.15
ctrl['条纹数量'] = 2.0
touch()
shot('SVGlike_w015_tl100_K2')

for k, v in base.items():
    ctrl[k] = v
touch()
print()
print('  已还原:', {k: ctrl.get(k) for k in KEYS}, '| 色标', ramp_pos())
assert abs(ctrl.get('流星拖尾') - base['流星拖尾']) < 1e-9
assert abs(ctrl.get('条纹宽度') - base['条纹宽度']) < 1e-9
assert abs(ctrl.get('条纹数量') - base['条纹数量']) < 1e-9
assert len(bpy.data.materials['滚动效果网格体_竖条旋转'].node_tree.nodes['发光配色'].color_ramp.elements) == 2


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
sheet(shots, os.path.join(OUTDIR, 'L_流星拖尾_0_04_08_10_加SVG式.png'))

print()
print('--- 清理 ---')
bpy.context.window.scene = main
bpy.data.scenes.remove(sc)
bpy.data.objects.remove(cam, do_unlink=True)
bpy.data.worlds.remove(w)
for im in list(bpy.data.images):
    if 'png' in im.name:
        bpy.data.images.remove(im)
print('  leftover:', [o.name for o in bpy.data.objects if o.name.startswith('__TS_PV')],
      [s.name for s in bpy.data.scenes if s.name.startswith('__TS_PV')],
      [x.name for x in bpy.data.worlds if x.name.startswith('__TS_PV')])
print('  对象 %d->%d | 场景 %d->%d | 世界 %d->%d'
      % (base_counts[0], len(bpy.data.objects), base_counts[1], len(bpy.data.scenes),
         base_counts[2], len(bpy.data.worlds)))
print()
print('TSWEEP_OK')
