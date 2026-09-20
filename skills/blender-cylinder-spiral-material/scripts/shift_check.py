# s72_shift.py —— v3 运动方向验证：条纹在两帧之间往哪个方向移？
#   原理：斜条纹沿自身方向平移看不出变化，所以取【固定高度的一行】，
#         看这一行的亮暗分布随时间往左还是往右移 —— 那就是条纹的横向位移。
#   预期：上升偏移 = -frame×0.01（正速度）⇒ 条纹往【左下】水平移动同时上移，
#         视觉上即「右下 → 左上」。
import bpy
import glob
import os
import numpy as np

OUTDIR = r'D:\workbuddy\2026-09-20-09-39-42\_liantiao\preview'
PAT = 'hx_f%03d_*.png'
FRAMES = [365, 400, 435]


def load(path):
    base = os.path.basename(path)
    for imx in list(bpy.data.images):
        if imx.filepath and os.path.basename(imx.filepath) == base:
            bpy.data.images.remove(imx)
    im = bpy.data.images.load(path)
    im.reload()
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, :3].mean(axis=2)
    bpy.data.images.remove(im)
    return a[::-1]                       # 行 0 = 图像顶部


rows = {}
for f in FRAMES:
    g = sorted(glob.glob(os.path.join(OUTDIR, PAT % f)))
    if not g:
        print('缺文件: f%d' % f); continue
    rows[f] = load(g[-1])
    print('读了 f%-4d %s' % (f, os.path.basename(g[-1])))

if len(rows) < 2:
    print('SHIFT_ERR 文件不足'); raise SystemExit(1)

H, W = rows[FRAMES[0]].shape
print('图像 %dx%d' % (W, H))


def band_centers(profile, thr_lo=0.15):
    """返回一行里【暗带】(低于阈值) 的连续段中心（归一化 x）"""
    dark = profile < thr_lo
    out, i = [], 0
    while i < W:
        if dark[i]:
            j = i
            while j + 1 < W and dark[j + 1]:
                j += 1
            if j - i >= 3:
                out.append(((i + j) / 2.0) / W)
            i = j + 1
        else:
            i += 1
    return out


print()
print('--- 固定高度行上的暗带中心（归一化 0=左 1=右）---')
for frac in (0.30, 0.45, 0.60):
    r = int(H * frac)
    print('  高度 %.0f%%' % ((1 - frac) * 100))
    prev = None
    for f in FRAMES:
        if f not in rows:
            continue
        cs = band_centers(rows[f][r, :])
        s = '    f%-4d 暗带: %s' % (f, ' '.join('%.3f' % c for c in cs))
        if prev is not None and cs:
            # 找最接近上一帧某个暗带的那个（配对追踪）
            best = min(cs, key=lambda c: min(abs(c - p) for p in prev))
            d = best - min(prev, key=lambda p: abs(p - best))
            s += '   ← 相对上一帧 %+.3f (%s)' % (d, '左移' if d < -0.004 else ('右移' if d > 0.004 else '基本不动'))
        print(s)
        prev = cs

print()
print('--- 结论 ---')
print('  条纹为 / 形（左下→右上）；若上面显示【左移】，则运动方向 = 右下→左上 ✔')
print('SHIFT_OK')
