# s35_paramsweep.py — 参数扫描：一次渲 4 组配置拼图，用于定默认值
import bpy, os, json
import numpy as np
from mathutils import Vector

TARGET = '滚动效果网格体'
CTRL = '螺旋上升控制'
MAT = '滚动效果网格体_螺旋上升'
OUTDIR = r'D:\workbuddy\2026-09-20-09-39-42\_liantiao\preview'
FRAME = 365
RES = (400, 640)
ORTHO = 15.0
CENTER = Vector((30.9216, 2.8832, 5.6938))

# (标签, K, N, 宽度)
CONFIGS = [
    ('K2 N1 w0.50', 2.0, 1.0, 0.50),
    ('K2 N1 w0.30', 2.0, 1.0, 0.30),
    ('K3 N2 w0.35', 3.0, 2.0, 0.35),
    ('K4 N2 w0.25', 4.0, 2.0, 0.25),
]

os.makedirs(OUTDIR, exist_ok=True)
main = bpy.context.scene
ob = bpy.data.objects[TARGET]
ctrl = bpy.data.objects[CTRL]
mat = bpy.data.materials[MAT]
saved = {k: ctrl.get(k) for k in ('环绕圈数', '高度条纹', '条纹宽度', '上升速度', '发光强度')}
base_objects, base_scenes, base_worlds, base_mats = (len(bpy.data.objects), len(bpy.data.scenes),
                                                     len(bpy.data.worlds), len(bpy.data.materials))

sc = bpy.data.scenes.new('__SPIRAL_SW__')
sc.collection.objects.link(ob)
w = bpy.data.worlds.new('__SPIRAL_SW_W__')
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0, 0, 0, 1)
bg.inputs[1].default_value = 0.0
sc.world = w
cd = bpy.data.cameras.new('__SPIRAL_SW_CAM__')
cd.type = 'ORTHO'
cd.ortho_scale = ORTHO
cam = bpy.data.objects.new('__SPIRAL_SW_CAM__', cd)
sc.collection.objects.link(cam)
cam.location = CENTER + Vector((60, 0, 0))
cam.rotation_euler = (CENTER - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam
sc.render.engine = 'CYCLES'
sc.cycles.samples = 16
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'
sc.render.dither_intensity = 0.0
sc.view_settings.view_transform = 'AgX'
sc.render.use_stamp = True
for f in ('use_stamp_date', 'use_stamp_time', 'use_stamp_camera', 'use_stamp_scene',
          'use_stamp_filename', 'use_stamp_render_time', 'use_stamp_lens',
          'use_stamp_memory', 'use_stamp_hostname', 'use_stamp_marker'):
    if hasattr(sc.render, f):
        setattr(sc.render, f, False)
sc.render.use_stamp_note = True
sc.render.stamp_font_size = 20

paths = []
for label, K, N, W in CONFIGS:
    ctrl['环绕圈数'], ctrl['高度条纹'], ctrl['条纹宽度'] = K, N, W
    ctrl.update_tag(); mat.update_tag(); mat.node_tree.update_tag()
    bpy.context.view_layer.update()
    sc.render.stamp_note_text = label
    p = os.path.join(OUTDIR, 'sw_%s.png' % label.replace(' ', '').replace('.', ''))
    sc.render.filepath = p
    main.frame_set(FRAME)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True, scene=sc.name)
    assert os.path.exists(p)
    paths.append((label, p))
    print('  rendered', os.path.basename(p))

# 还原用户参数
for k, v in saved.items():
    ctrl[k] = v
ctrl.update_tag(); mat.update_tag(); mat.node_tree.update_tag()
bpy.context.view_layer.update()

# ---- 拼 1x4 ----
tiles = [bpy.data.images.load(p) for _, p in paths]
Wt = sum(t.size[0] for t in tiles); Ht = max(t.size[1] for t in tiles)
buf = np.zeros((Ht, Wt, 4), dtype=np.float32); buf[:, :, 3] = 1.0
x = 0
for t in tiles:
    tw, th = t.size
    buf[:th, x:x + tw] = np.array(t.pixels[:], dtype=np.float32).reshape(th, tw, 4)
    x += tw
    bpy.data.images.remove(t)
out = bpy.data.images.new('swsheet', Wt, Ht)
out.pixels = buf.ravel()
out.filepath_raw = os.path.join(OUTDIR, 'C_参数对比_K_N_宽度.png')
out.file_format = 'PNG'
out.save()
print('  sheet ->', out.filepath_raw, os.path.getsize(out.filepath_raw), 'B')
bpy.data.images.remove(out)

# ---- 清理 ----
bpy.context.window.scene = main
bpy.data.scenes.remove(sc)
bpy.data.objects.remove(cam, do_unlink=True)
bpy.data.worlds.remove(w)
print('leftover:',
      [o.name for o in bpy.data.objects if o.name.startswith('__SPIRAL')],
      [s.name for s in bpy.data.scenes if s.name.startswith('__SPIRAL')],
      [x.name for x in bpy.data.worlds if x.name.startswith('__SPIRAL')])
print('计数 对象 %d->%d 场景 %d->%d 世界 %d->%d 材质 %d->%d'
      % (base_objects, len(bpy.data.objects), base_scenes, len(bpy.data.scenes),
         base_worlds, len(bpy.data.worlds), base_mats, len(bpy.data.materials)))
print('参数已还原:', {k: ctrl.get(k) for k in saved})
