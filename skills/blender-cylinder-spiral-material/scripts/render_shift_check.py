# s31_render_preview.py — 隔离临时场景渲染验收：螺旋 + 上升方向（像素级判据）
# 规则：临时场景只【额外 link】目标对象，不 unlink 主场景（否则材质不参与求值）；
#       换帧调主场景；关 dither；用完清理并自证无残留。
import bpy
import json
import os
import numpy as np
from mathutils import Vector

TARGET = '滚动效果网格体'
OUTDIR = r'D:\workbuddy\2026-09-20-09-39-42\_liantiao\preview'
FRAMES = [365, 375, 385]
RES = (640, 1024)
ORTHO = 15.0
CENTER = Vector((30.9216, 2.8832, 5.6938))
VIEWS = [('AgX', 'AgX'), ('STD', 'Standard')]

os.makedirs(OUTDIR, exist_ok=True)
main = bpy.context.scene
ob = bpy.data.objects[TARGET]
base_objects = len(bpy.data.objects)
base_scenes = len(bpy.data.scenes)
base_worlds = len(bpy.data.worlds)

# ---------- 建临时场景 ----------
sc = bpy.data.scenes.new('__SPIRAL_PV__')
sc.collection.objects.link(ob)                      # 额外 link，主场景不动

w = bpy.data.worlds.new('__SPIRAL_PV_W__')
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
bg.inputs[1].default_value = 0.0
sc.world = w

cam_data = bpy.data.cameras.new('__SPIRAL_PV_CAM__')
cam_data.type = 'ORTHO'
cam_data.ortho_scale = ORTHO
cam = bpy.data.objects.new('__SPIRAL_PV_CAM__', cam_data)
sc.collection.objects.link(cam)
cam.location = CENTER + Vector((60.0, 0.0, 0.0))     # 从 +X 正对柱面
cam.rotation_euler = (CENTER - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam

sc.render.engine = 'CYCLES'
sc.cycles.samples = 16
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'
sc.render.dither_intensity = 0.0                     # ★ 位移估计的前提
sc.render.film_transparent = False
# 自带标签（ASCII，默认字体无中文）
sc.render.use_stamp = True
for f in ('use_stamp_date', 'use_stamp_time', 'use_stamp_camera', 'use_stamp_scene',
          'use_stamp_filename', 'use_stamp_render_time', 'use_stamp_lens',
          'use_stamp_marker', 'use_stamp_memory', 'use_stamp_hostname'):
    if hasattr(sc.render, f):
        setattr(sc.render, f, False)
sc.render.use_stamp_note = True
sc.render.stamp_font_size = 26

shots = []
def render(tag, frame, vt):
    sc.view_settings.view_transform = vt
    sc.render.stamp_note_text = '%s f%d %s' % (tag, frame, vt)
    p = os.path.join(OUTDIR, '%s_f%03d_%s.png' % (tag, frame, vt))
    sc.render.filepath = p                              # ★ 必须先设，否则静默不写盘
    main.frame_set(frame)                               # ★ 帧驱动指向主场景
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True, scene=sc.name)
    assert os.path.exists(p), '渲染未落盘: ' + p
    shots.append((tag, frame, vt, p))
    print('  rendered', os.path.basename(p), os.path.getsize(p), 'B')


print('--- 渲染 ---')
for f in FRAMES:
    render('rise', f, 'AgX')
render('vt', FRAMES[0], 'Standard')

# ---------- 读图 + 垂直位移估计 ----------
def lum_profile(path):
    im = bpy.data.images.load(path)
    wpx, hpx = im.size
    arr = np.array(im.pixels[:], dtype=np.float32).reshape(hpx, wpx, 4)
    lum = arr[:, :, :3].mean(axis=2)
    prof = lum.mean(axis=1)          # 行 0 = 图像最底行
    bpy.data.images.remove(im)
    return prof, (wpx, hpx)


def best_shift(a, b):
    """找 d 使 roll(b, d) ≈ a。d>0 ⇒ b 的内容出现在更大的行号 ⇒ 内容【上移】。"""
    h = len(a)
    lo, hi = int(h * 0.25), int(h * 0.75)
    best_d, best_c = None, -2.0
    for d in range(-400, 401):
        bb = np.roll(b, d)
        c = float(np.corrcoef(a[lo:hi], bb[lo:hi])[0, 1])
        if c > best_c:
            best_c, best_d = c, d
    return best_d, best_c


print()
print('--- 位移估计 ---')
profs = {}
for tag, f, vt, p in shots:
    if vt == 'AgX':
        profs[f] = lum_profile(p)[0]
res = {}
for f1, f2 in zip(FRAMES, FRAMES[1:]):
    d, c = best_shift(profs[f1], profs[f2])
    res['f%d->f%d' % (f1, f2)] = {'shift_px': d, 'corr': round(c, 4)}
    print('  f%d -> f%d : 位移 %+d px (相关 %.4f)' % (f1, f2, d, c))

# 几何预期：速度 0.02 归一化柱高/帧；N=1 ⇒ 竖直 1 个条纹周期 = 整根柱高
hpx = RES[1]
col_px = 13.6764 / ORTHO * hpx
exp = 10 * 0.02 * col_px
print('  几何预期: 每 10 帧位移 %.0f px（柱高 %.0f px）' % (exp, col_px))

# ---------- 拼对照图 ----------
def sheet(paths, outp):
    tiles = [bpy.data.images.load(p) for p in paths]
    W = sum(t.size[0] for t in tiles)
    H = max(t.size[1] for t in tiles)
    buf = np.zeros((H, W, 4), dtype=np.float32)
    buf[:, :, 3] = 1.0
    x = 0
    for t in tiles:
        tw, th = t.size
        arr = np.array(t.pixels[:], dtype=np.float32).reshape(th, tw, 4)
        buf[:th, x:x + tw] = arr
        x += tw
        bpy.data.images.remove(t)
    out = bpy.data.images.new(os.path.basename(outp), W, H)
    out.pixels = buf.ravel()
    out.filepath_raw = outp
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(out)
    print('  sheet ->', outp, os.path.getsize(outp), 'B')


print()
print('--- 拼图 ---')
rise_paths = [p for tag, f, vt, p in shots if vt == 'AgX']
sheet(rise_paths, os.path.join(OUTDIR, 'A_上升序列_f365_375_385.png'))
vt_paths = [p for tag, f, vt, p in shots if f == FRAMES[0]]
sheet(vt_paths, os.path.join(OUTDIR, 'B_视图变换对照_AgX_vs_Standard.png'))

# ---------- 清理 ----------
print()
print('--- 清理 ---')
bpy.context.window.scene = main
bpy.data.scenes.remove(sc)
for ob_ in [cam]:
    bpy.data.objects.remove(ob_, do_unlink=True)
bpy.data.worlds.remove(w)
for im in list(bpy.data.images):
    if im.name.startswith('preview') or im.name in ('A_上升序列_f365_375_385.png',
                                                    'B_视图变换对照_AgX_vs_Standard.png'):
        bpy.data.images.remove(im)
leftover = [o.name for o in bpy.data.objects if o.name.startswith('__SPIRAL_PV')]
print('  leftover_objects :', leftover)
print('  leftover_scenes  :', [s.name for s in bpy.data.scenes if s.name.startswith('__SPIRAL_PV')])
print('  leftover_worlds  :', [x.name for x in bpy.data.worlds if x.name.startswith('__SPIRAL_PV')])
print('  对象数 %d -> %d (基线 %d)' % (base_objects, len(bpy.data.objects), base_objects))
print('  场景数 %d -> %d | 世界数 %d -> %d' % (base_scenes, len(bpy.data.scenes),
                                              base_worlds, len(bpy.data.worlds)))
print()
print('PREVIEW ' + json.dumps(res, ensure_ascii=False))
