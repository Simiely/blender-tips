# s61_shape_check.py —— v2 端到端验证：渲染出来的波形 = 算出来的波形吗？
#
# 做法：
#   1. 隔离临时场景、正交相机正视柱面、Standard 视图变换（线性响应）、输出 EXR（线性浮点）
#   2. 把屏幕像素重采样到【柱面角度 φ 空间】（x = R·sinφ）—— 旋转在 φ 空间是纯平移
#   3. 用 Blender 的 MapRange/SMOOTHSTEP 定义【独立重算】理论 mask
#   4. 两者归一化后求相关系数（对单调变换稳健），再比亮区边界位置
#
# 这条链路证明的是：Math 域构造的波形确实按预期到达了像素，而不只是"节点连对了"。
import bpy
import io
import os
import time
import numpy as np
from mathutils import Vector

BUILD = r'D://workbuddy//2026-09-20-09-39-42//_liantiao//build_cylinder_streak.py'

# ★★ 每次运行用不同的输出文件名。
#    bpy 的 images 数据块按【文件路径】缓存：渲染覆盖同名文件后再 load，
#    拿回的是第一次的旧像素。实测踩过 —— 连续四次运行"结果完全相同、连字节数都一样"，
#    实际是后三次读的都是第一次的缓存图，白排查很久。
RUN = str(int(time.time()))[-6:]

TARGET = '滚动效果网格体'
CTRL = '竖条旋转控制'
OUTDIR = r'D:\workbuddy\2026-09-20-09-39-42\_liantiao\preview'
FRAME = 365
RES = (420, 900)
ORTHO = 15.5
CENTER = Vector((30.9216, 2.8832, 5.6938))
R_CYL = 3.7789
PHI_MAX = 1.25            # ±71.6°，避开 |φ|→90° 的采样退化
NPHI = 601
PROBE_STRENGTH = 0.6      # 探测时把发光强度调低，避免高光饱和削顶

main = bpy.context.scene
ob = bpy.data.objects[TARGET]
ctrl = bpy.data.objects[CTRL]
DEF = {'条纹数量': 4.0, '前缘宽度': 0.12, '拖尾起点': 0.22, '旋转速度': 0.01, '发光强度': 5.0}
base = {k: ctrl.get(k) for k in DEF}
base_counts = (len(bpy.data.objects), len(bpy.data.scenes), len(bpy.data.worlds))

sc = bpy.data.scenes.new('__SH_PV__')
sc.collection.objects.link(ob)
# ★★ 关键：驱动变量是 ('OBJECT', ctrl, '[...]')。若 ctrl 不在渲染场景里，
#    渲染 depsgraph 解析不到这个 ID ⇒ 表达式求值失败 ⇒ 节点用 default_value 渲染。
#    症状极具迷惑性：evaluated_get() 读到的全是正确值，但渲染出来是 default 的样子。
#    （实测：K 渲染成 1 条、spin 渲染成 0、强度渲染成 1.0）
sc.collection.objects.link(ctrl)
w = bpy.data.worlds.new('__SH_PV_W__')
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
bg.inputs[1].default_value = 0.0
sc.world = w
cd = bpy.data.cameras.new('__SH_PV_CAM__')
cd.type = 'ORTHO'
cd.ortho_scale = ORTHO
cam = bpy.data.objects.new('__SH_PV_CAM__', cd)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = CENTER + Vector((60.0, 0.0, 0.0))
cam.rotation_euler = (CENTER - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.engine = 'CYCLES'
sc.cycles.samples = 16
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
sc.render.image_settings.color_mode = 'RGB'
sc.render.dither_intensity = 0.0
sc.render.film_transparent = False
sc.render.use_stamp = False


def touch():
    ctrl.update_tag()
    m = bpy.data.materials['滚动效果网格体_竖条旋转']
    m.update_tag()
    m.node_tree.update_tag()
    bpy.context.view_layer.update()
    try:
        bpy.context.view_layer.depsgraph.update()
    except Exception as e:
        print('    depsgraph.update 失败:', repr(e))


def jiggle():
    """★ 实测坑：挂在【节点树】上的驱动（nt.driver_add）只有在 ctrl 属性被【写入】
    之后才会推给渲染用的 depsgraph；赋一个相同的值不算写入。
    症状：不改 K 直接渲染 ⇒ 渲染读到 K 的 default 1.0，条纹只有 1 条。
    修法：渲染前对所有相关属性做一次 epsilon 抖动（改走再改回），强制重算。"""
    for k in ('条纹数量', '前缘宽度', '拖尾起点', '旋转速度', '发光强度'):
        v = ctrl.get(k)
        if v is None:
            continue
        ctrl[k] = float(v) * 1.0001 + 1e-7
        ctrl[k] = float(v)
    touch()


def check_ev(label):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = bpy.data.materials['滚动效果网格体_竖条旋转'].evaluated_get(dg).node_tree
    b = next(n for n in ev.nodes if n.type == 'BSDF_PRINCIPLED')
    print('    [%s] 求值真值  K=%.4f  spin=%.4f  强度=%.4f  前缘=%.4f  拖尾=%.4f'
          % (label, ev.nodes['条纹数量K'].inputs[1].default_value,
             ev.nodes['旋转相位'].inputs[1].default_value,
             b.inputs['Emission Strength'].default_value,
             ev.nodes['前缘上升'].inputs[2].default_value,
             ev.nodes['拖尾衰减'].inputs[1].default_value))


def bake_drivers():
    """★ 实测必需的保险：把 ctrl 的当前值直接写进各节点的 default_value。
    本机实测：隔离临时场景里，挂在节点树上的驱动不会被渲染 depsgraph 求值
    （evaluated_get() 读到的全对，但渲出来是建材质时的旧 default）。
    直接烘进 default_value 是【双向安全】的：
      · 驱动若被求值 ⇒ 算出来是同一个值，无副作用
      · 驱动若没求值 ⇒ 用的就是我们刚写的正确值
    注意：spin 依赖当前帧，必须在 frame_set 之后调用。"""
    nt = bpy.data.materials['滚动效果网格体_竖条旋转'].node_tree
    nt.nodes['旋转相位'].inputs[1].default_value = -main.frame_current * ctrl['旋转速度']
    nt.nodes['条纹数量K'].inputs[1].default_value = ctrl['条纹数量']
    nt.nodes['前缘上升'].inputs[2].default_value = ctrl['前缘宽度']
    nt.nodes['拖尾衰减'].inputs[1].default_value = ctrl['拖尾起点']
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Emission Strength'].default_value = ctrl['发光强度']


def freeze_drivers():
    """★★ 关键：把节点树上的驱动【全部移除】，只留 default_value 供渲染使用。

    本机实测（隔离临时场景）：节点树上的驱动不会被渲染 depsgraph 求值成 ctrl 的当前值
    —— 渲染出来是建材质时的旧 default（K=1 / spin=0 / 强度=1），
    而 evaluated_get() 读到的却全是正确值，极具迷惑性。
    移除驱动后，渲染才会老实用 default_value。
    脚本最后必须 exec build 脚本把驱动重建回来。"""
    nt = bpy.data.materials['滚动效果网格体_竖条旋转'].node_tree
    n = len(nt.animation_data.drivers) if nt.animation_data else 0
    nt.animation_data_clear()
    bake_drivers()
    return n


def render(tag, fmt):
    jiggle()                       # ★ 必须：见 jiggle 的说明
    main.frame_set(FRAME)
    freeze_drivers()               # ★ 必须：见 freeze_drivers 的说明
    check_ev(tag)
    # ★ 把临时场景设为【活动场景】并驱动到同一帧，让它的 depsgraph 完整求值
    prev = bpy.context.window.scene
    bpy.context.window.scene = sc
    sc.frame_set(FRAME)
    bpy.context.view_layer.update()
    nt_ = bpy.data.materials['滚动效果网格体_竖条旋转'].node_tree
    if nt_.animation_data:
        print('    驱动 is_valid =', [d.driver.is_valid for d in nt_.animation_data.drivers])
    check_ev(tag + '·切场景后')
    sc.render.image_settings.file_format = fmt
    ext = 'exr' if fmt == 'OPEN_EXR' else 'png'
    p = os.path.join(OUTDIR, 'shape_%s_%s.%s' % (tag, RUN, ext))
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True, scene=sc.name)
    bpy.context.window.scene = prev
    assert os.path.exists(p), '渲染未落盘: ' + p
    return p


# ---------- 理论波形（独立重算）----------
def smoothstep01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def theory_mask(phi, A, B, K, speed, frame):
    u = (phi + np.pi) / (2.0 * np.pi)
    f = (u - frame * speed) * K
    p = f - np.floor(f)
    rise = smoothstep01(p / A)                       # MapRange(SMOOTHSTEP, 0..A → 0..1)
    fall = 1.0 - smoothstep01((p - B) / (1.0 - B))   # MapRange(SMOOTHSTEP, B..1 → 1..0)
    return np.minimum(rise, fall), p


# ★★ 实测修正：`ortho_scale` 对应的是【较长边】—— 这里是竖直的 900px，不是水平的 420px！
#     用 RES[0]/ORTHO 会让水平比例小整整一倍，只采到柱面中间一小段，
#     于是把 K=4 的 1.59 个周期误判成"只有 1 个周期"（白排查了很久）。
#     实测佐证：柱子（半径 3.7789）在 420px 宽里占满整幅 ⇒ px/单位 ≈ 55.6，
#     与 900/15.5 = 58.06 吻合，与 420/15.5 = 27.10 差一倍。
PX_PER_UNIT = RES[1] / ORTHO
PHI = np.linspace(-PHI_MAX, PHI_MAX, NPHI)
X_PIX = R_CYL * np.sin(PHI) * PX_PER_UNIT + RES[0] / 2.0


def srgb_to_linear(v):
    """⚠️ 实测：bpy 的 Image.pixels 对 PNG 返回的是【sRGB 编码值】，不是线性值。
    证据：发光强度 0.6 时读数上限 0.7974 = sRGB(0.6)。必须自己反解。"""
    v = np.asarray(v, dtype=np.float64)
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def phi_profile(path, strength):
    # ★ 先清掉同路径的缓存图像，否则 load 会返回旧像素
    base = os.path.basename(path)
    for imx in list(bpy.data.images):
        if imx.filepath and os.path.basename(imx.filepath) == base:
            bpy.data.images.remove(imx)
    im = bpy.data.images.load(path)
    im.reload()
    wpx, hpx = im.size
    n = len(im.pixels)
    ch = n // (hpx * wpx) if hpx * wpx else 0
    print('    图像 %dx%d | 每像素通道数=%d%s'
          % (wpx, hpx, ch, '  ← 不是 4！通道错位' if ch != 4 else ''))
    arr = np.array(im.pixels[:], dtype=np.float32).reshape(hpx, wpx, ch)
    lum = arr[:, :, :3].mean(axis=2)
    row_lo, row_hi = int(hpx * 0.20), int(hpx * 0.80)     # 柱体中段，避开端盖
    band = lum[row_lo:row_hi, :]
    vprof = band.mean(axis=1)
    print('    垂直方向：起伏=%.4f  %s'
          % (vprof.max() - vprof.min(),
             '← 有垂直渐变（竖条纹不正常）' if (vprof.max() - vprof.min()) > 0.05 else 'OK 均匀'))
    col = band.mean(axis=0)                               # 列剖面
    bpy.data.images.remove(im)
    # sRGB 反解 → 线性 → 除以发光强度 ⇒ 还原出 mask
    mask = srgb_to_linear(col) / strength
    return np.interp(X_PIX, np.arange(wpx), mask)


print('--- 渲染（PNG + Standard，用于数值对比）---')
# ⚠️ 实测教训：只改一个属性 + touch() 有时推不到渲染用的 depsgraph
#    （症状：渲染读到的还是建材质时的旧驱动值）。这里把【全部】控件显式重写一遍再刷新。
ctrl['发光强度'] = PROBE_STRENGTH
ctrl['前缘宽度'] = base['前缘宽度']
ctrl['拖尾起点'] = base['拖尾起点']
ctrl['条纹数量'] = base['条纹数量']
ctrl['旋转速度'] = base['旋转速度']
touch()
sc.view_settings.view_transform = 'Standard'
std_png = render('std', 'PNG')
print('   ', os.path.basename(std_png), os.path.getsize(std_png), 'B')

prof = phi_profile(std_png, PROBE_STRENGTH)
A, B, K, SPD = base['前缘宽度'], base['拖尾起点'], base['条纹数量'], base['旋转速度']
theo, pp = theory_mask(PHI, A, B, K, SPD, FRAME)

# 归一化后求相关（对亮度标定/单调变换稳健）
def norm(x):
    lo, hi = float(x.min()), float(x.max())
    return (x - lo) / (hi - lo) if hi - lo > 1e-9 else x * 0.0


pr, th = norm(prof), norm(theo)
corr = float(np.corrcoef(pr, th)[0, 1])
print()
print('--- 对比（φ ∈ ±%.2f rad，%d 点）---' % (PHI_MAX, NPHI))
print('  A=前缘宽度=%.3f  B=拖尾起点=%.3f  K=%d  帧=%d' % (A, B, K, FRAME))
print('  实测剖面  min/mean/max = %.4f/%.4f/%.4f' % (prof.min(), prof.mean(), prof.max()))
print('  理论 mask min/mean/max = %.4f/%.4f/%.4f' % (theo.min(), theo.mean(), theo.max()))
print('  ★ 相关系数 = %.4f' % corr)

# 亮区边界（50% 阈值）对比
def spans(x, thr=0.5):
    m = x >= thr
    out, i = [], 0
    while i < len(m):
        if m[i]:
            j = i
            while j + 1 < len(m) and m[j + 1]:
                j += 1
            out.append((round(float(PHI[i]), 4), round(float(PHI[j]), 4)))
            i = j + 1
        else:
            i += 1
    return out


print('  实测亮区(>50%%) 区间: %s' % spans(pr))
print('  理论亮区(>50%%) 区间: %s' % spans(th))

print()
print('--- 稀疏采样（每 50 点）看形状 ---')
idx = list(range(0, NPHI, 50))
print('  φ     ' + ' '.join('%7.3f' % PHI[i] for i in idx))
print('  实测  ' + ' '.join('%7.4f' % pr[i] for i in idx))
print('  理论  ' + ' '.join('%7.4f' % th[i] for i in idx))
print('  理论p ' + ' '.join('%7.4f' % pp[i] for i in idx))

print()
print('--- 渲染一张 AgX PNG 供目视 ---')
for k, v in base.items():
    ctrl[k] = v
touch()
sc.view_settings.view_transform = 'AgX'
png = render('agx', 'PNG')
print('   ', os.path.basename(png), os.path.getsize(png), 'B')

# ---------- 还原 ----------
for k, v in base.items():
    ctrl[k] = v
touch()
assert abs(ctrl.get('发光强度') - base['发光强度']) < 1e-9, '发光强度未还原'
print()
print('  已还原:', {k: ctrl.get(k) for k in DEF})

# ---------- 清理 ----------
print()
print('--- 清理 ---')
bpy.context.window.scene = main
bpy.data.scenes.remove(sc)
bpy.data.objects.remove(cam, do_unlink=True)
bpy.data.worlds.remove(w)
print('  leftover:', [o.name for o in bpy.data.objects if o.name.startswith('__SH_PV')],
      [s.name for s in bpy.data.scenes if s.name.startswith('__SH_PV')],
      [x.name for x in bpy.data.worlds if x.name.startswith('__SH_PV')])
print('  对象 %d->%d | 场景 %d->%d | 世界 %d->%d'
      % (base_counts[0], len(bpy.data.objects), base_counts[1], len(bpy.data.scenes),
         base_counts[2], len(bpy.data.worlds)))
print()
print('SHAPE_CORR %.4f' % corr)

print()
print('--- 重建驱动（freeze_drivers 临时删掉了它们）---')
exec(compile(io.open(BUILD, encoding='utf-8').read(), BUILD, 'exec'),
     {'__name__': 'builtins'})
print()
print('SHAPE_OK')
