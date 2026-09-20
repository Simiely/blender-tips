# s48_orbit.py — 环绕多视角渲染：看「竖条绕 Z 轴」的真实三维形态
#   4 个侧面角度（0/90/180/270）+ 俯视端盖 + 斜视 3/4
#   目的：判断「对称」是柱面投影的正常表现，还是端盖/材质出了问题。
import bpy
import json
import os
import numpy as np
from mathutils import Vector

TARGET = '滚动效果网格体'
OUTDIR = r'D:\workbuddy\2026-09-20-09-39-42\_liantiao\preview'
FRAME = 365
RES = (420, 900)
ORTHO = 15.5
CENTER = Vector((30.9216, 2.8832, 5.6938))

os.makedirs(OUTDIR, exist_ok=True)
main = bpy.context.scene
ob = bpy.data.objects[TARGET]
base_objects = len(bpy.data.objects)
base_scenes = len(bpy.data.scenes)
base_worlds = len(bpy.data.worlds)

sc = bpy.data.scenes.new('__ORB_PV__')
sc.collection.objects.link(ob)
w = bpy.data.worlds.new('__ORB_PV_W__')
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
bg.inputs[1].default_value = 0.0
sc.world = w
cd = bpy.data.cameras.new('__ORB_PV_CAM__')
cd.type = 'ORTHO'
cam = bpy.data.objects.new('__ORB_PV_CAM__', cd)
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
sc.render.stamp_font_size = 22

VIEWS = [
    ('a000', Vector((60.0, 0.0, 0.0))),
    ('b090', Vector((0.0, 60.0, 0.0))),
    ('c180', Vector((-60.0, 0.0, 0.0))),
    ('d270', Vector((0.0, -60.0, 0.0))),
    ('e_top', Vector((0.0, 0.0, 60.0))),
    ('f_iso', Vector((42.0, -42.0, 26.0))),
]
shots = []
for tag, off in VIEWS:
    cd.ortho_scale = ORTHO
    cam.location = CENTER + off
    cam.rotation_euler = (CENTER - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.view_settings.view_transform = 'AgX'
    sc.render.stamp_note_text = tag
    p = os.path.join(OUTDIR, 'orb_%s.png' % tag)
    sc.render.filepath = p
    main.frame_set(FRAME)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True, scene=sc.name)
    assert os.path.exists(p)
    shots.append((tag, p))
    print('  rendered', tag, os.path.getsize(p), 'B')


def sheet(tags, outp):
    paths = [p for t, p in shots if t in tags]
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
sheet(['a000', 'b090', 'c180', 'd270'], os.path.join(OUTDIR, 'I_环绕360_四视角.png'))
sheet(['e_top', 'f_iso'], os.path.join(OUTDIR, 'J_俯视端盖_与_斜视.png'))

print()
print('--- 清理 ---')
bpy.context.window.scene = main
bpy.data.scenes.remove(sc)
bpy.data.objects.remove(cam, do_unlink=True)
bpy.data.worlds.remove(w)
for im in list(bpy.data.images):
    if 'PNG' in im.name or '.png' in im.name:
        bpy.data.images.remove(im)
print('  leftover:', [o.name for o in bpy.data.objects if o.name.startswith('__ORB_PV')],
      [s.name for s in bpy.data.scenes if s.name.startswith('__ORB_PV')],
      [x.name for x in bpy.data.worlds if x.name.startswith('__ORB_PV')])
print('  对象 %d->%d | 场景 %d->%d | 世界 %d->%d'
      % (base_objects, len(bpy.data.objects), base_scenes, len(bpy.data.scenes),
         base_worlds, len(bpy.data.worlds)))
print()
print('ORBIT_OK')
