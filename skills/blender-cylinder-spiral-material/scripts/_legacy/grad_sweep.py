# s47_grad_sweep.py — 双渐变节点改造的视觉验收
#   A) 渐变柔化扫描：0 / 0.3 / 0.6 / 1.0  → 看硬边 → 柔边的过渡
#   B) 发光配色演示：改「发光配色」两端色标   → 证明这个节点真的可调任意颜色
# 规则同 s41：临时场景只【额外 link】目标对象；用完清理并自证无残留。
import bpy
import json
import os
import numpy as np
from mathutils import Vector

TARGET = '滚动效果网格体'
MAT = '滚动效果网格体_竖条旋转'
CTRL = '竖条旋转控制'
OUTDIR = r'D:\workbuddy\2026-09-20-09-39-42\_liantiao\preview'
FRAME = 365
RES = (420, 900)
ORTHO = 15.0
CENTER = Vector((30.9216, 2.8832, 5.6938))

os.makedirs(OUTDIR, exist_ok=True)
main = bpy.context.scene
ob = bpy.data.objects[TARGET]
ctrl = bpy.data.objects[CTRL]
nt = bpy.data.materials[MAT].node_tree
ramp2 = nt.nodes['发光配色']
ramp1 = nt.nodes['条纹遮罩']

base_objects = len(bpy.data.objects)
base_scenes = len(bpy.data.scenes)
base_worlds = len(bpy.data.worlds)
base_soft = ctrl.get('渐变柔化')
base_cols = [tuple(e.color) for e in ramp2.color_ramp.elements]

# ---------- 临时场景 ----------
sc = bpy.data.scenes.new('__GS_PV__')
sc.collection.objects.link(ob)
w = bpy.data.worlds.new('__GS_PV_W__')
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
bg.inputs[1].default_value = 0.0
sc.world = w
cd = bpy.data.cameras.new('__GS_PV_CAM__')
cd.type = 'ORTHO'
cd.ortho_scale = ORTHO
cam = bpy.data.objects.new('__GS_PV_CAM__', cd)
sc.collection.objects.link(cam)
cam.location = CENTER + Vector((60.0, 0.0, 0.0))
cam.rotation_euler = (CENTER - cam.location).to_track_quat('-Z', 'Y').to_euler()
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

shots = []


def touch():
    """IDProperty 改动后必须打 tag，否则依赖图不重算（实测踩过）。"""
    ctrl.update_tag()
    nt.update_tag()
    bpy.context.view_layer.update()


def render(tag):
    sc.view_settings.view_transform = 'AgX'
    sc.render.stamp_note_text = tag
    p = os.path.join(OUTDIR, 'gs_%s.png' % tag)
    sc.render.filepath = p
    main.frame_set(FRAME)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True, scene=sc.name)
    assert os.path.exists(p), '渲染未落盘: ' + p
    shots.append((tag, p))
    print('  rendered', os.path.basename(p), os.path.getsize(p), 'B')


def positions():
    return [round(e.position, 4) for e in ramp1.color_ramp.elements]


print('--- A) 渐变柔化扫描（条纹宽度 0.4 / K=4）---')
soft_rows = []
for sv in (0.0, 0.3, 0.6, 1.0):
    ctrl['渐变柔化'] = sv
    touch()
    print('   柔化=%.2f → 色标位置 %s' % (sv, positions()))
    render('soft%02d' % int(round(sv * 100)))
    soft_rows.append('gs_soft%02d' % int(round(sv * 100)))

print()
print('--- B) 发光配色演示（改「发光配色」两端色标）---')
tint_rows = []
ctrl['渐变柔化'] = base_soft
touch()

# 默认：不发光 = 黑，发光 = 白
render('tint_A_default')
tint_rows.append('gs_tint_A_default')

# 不发光部分 = 深蓝底，发光部分 = 暖白（模拟"暗处有冷调底光"）
e = ramp2.color_ramp.elements
e[0].color = (0.02, 0.06, 0.30, 1.0)
e[1].color = (1.0, 0.88, 0.62, 1.0)
nt.update_tag()
bpy.context.view_layer.update()
render('tint_B_coolwarm')
tint_rows.append('gs_tint_B_coolwarm')

# 三段渐变：暗蓝 → 品红 → 暖白（证明中间可加色标）
mid = e.new(0.45)
mid.color = (0.85, 0.10, 0.45, 1.0)
nt.update_tag()
bpy.context.view_layer.update()
render('tint_C_tristop')
tint_rows.append('gs_tint_C_tristop')

# ---------- 还原用户数据 ----------
# ★ 结构性端点必须【钉死】，不能只靠索引/快照 diff —— 实测踩过：删错元素
#   （remove(e[-1]) 删的是位置最大的那个）导致末端停在 0.45，曲线提前饱和，
#   视觉上变成另一个效果，而且是【静默】的。见 skill 坑 6。
while len(e) > 2:
    e.remove(e[-1])
e[0].position, e[0].color = 0.0, base_cols[0]
e[1].position, e[1].color = 1.0, base_cols[1]
ctrl['渐变柔化'] = base_soft
touch()

# ★ 还原后必须断言，否则错误会留在用户工程里（这是本次事故的直接教训）
_els = ramp2.color_ramp.elements
assert len(_els) == 2, '还原失败: 色标数 %d' % len(_els)
assert abs(_els[0].position) < 1e-6 and abs(_els[1].position - 1.0) < 1e-6, \
    '还原失败: 首尾位置 %s' % [round(x.position, 4) for x in _els]
assert tuple(_els[0].color)[:3] == tuple(base_cols[0])[:3], '还原失败: 左端颜色'
assert tuple(_els[1].color)[:3] == tuple(base_cols[1])[:3], '还原失败: 右端颜色'
assert abs(ctrl.get('渐变柔化') - base_soft) < 1e-9, '还原失败: 渐变柔化'
print()
print('  已还原【并断言通过】: 渐变柔化 =', ctrl.get('渐变柔化'), '| 配色色标 =',
      [(round(x.position, 3), tuple(round(c, 3) for c in x.color)) for x in _els])


# ---------- 拼图 ----------
def sheet(names, outp):
    imgs = [bpy.data.images.load(os.path.join(OUTDIR, n + '.png')) for n in names]
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
sheet(soft_rows, os.path.join(OUTDIR, 'G_渐变柔化_0_030_060_100.png'))
sheet(tint_rows, os.path.join(OUTDIR, 'H_发光配色_默认_冷暖_三段.png'))

# ---------- 清理 ----------
print()
print('--- 清理 ---')
bpy.context.window.scene = main
bpy.data.scenes.remove(sc)
bpy.data.objects.remove(cam, do_unlink=True)
bpy.data.worlds.remove(w)
for im in list(bpy.data.images):
    if im.name.startswith('gs_') or '.png' in im.name:
        bpy.data.images.remove(im)
print('  leftover_objects :', [o.name for o in bpy.data.objects if o.name.startswith('__GS_PV')])
print('  leftover_scenes  :', [s.name for s in bpy.data.scenes if s.name.startswith('__GS_PV')])
print('  leftover_worlds  :', [x.name for x in bpy.data.worlds if x.name.startswith('__GS_PV')])
print('  leftover_cams    :', [o.name for o in bpy.data.objects if o.type == 'CAMERA' and o.name.startswith('__')])
print('  对象数 %d -> %d (基线 %d)' % (base_objects, len(bpy.data.objects), base_objects))
print('  场景数 %d -> %d | 世界数 %d -> %d' % (base_scenes, len(bpy.data.scenes),
                                              base_worlds, len(bpy.data.worlds)))
print()
print('SWEEP_OK ' + json.dumps({'soft': soft_rows, 'tint': tint_rows}, ensure_ascii=False))
