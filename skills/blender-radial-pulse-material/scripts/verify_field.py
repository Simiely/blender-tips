# -*- coding: utf-8 -*-
"""verify_field.py — 球面径向图案的数值验收（在 Blender 内跑）

三条判据，全部基于正交渲染 + 读像素，不依赖肉眼：

  T1 径向对称性（最强的一条）
     若图案真的只依赖 r = |P|，则单个物体**正对**渲染出来的图必须严格是 ρ 的函数。
     做法：把每个像素映射回世界点 P = R_cam @ (u, v, 0)（正交相机、平面过原点），
     按 ρ=|P| 分箱，报告**箱内标准差**。任意朝向都成立。
     → 这一条同时证明了「球面对称」，不需要真的去旋转物体。

  T2 多物体一致性（是否共享同一个 3D 场）
     让两个物体各自正对渲染，比较它们在**同一条世界轴**上的取值。
     必须做半像素修正（像素中心不在坐标轴上），否则会凭空出现系统差。
     附「沿轴错位」对照 —— 证明这个测试有分辨力，不是"两边全黑所以相等"。

  T3 时间推进（ring / pulse）
     逐帧渲染，算亮度加权质心半径与内边界半径，检查推进方向。
     附「多张图文件大小完全相同」的自动告警 —— 那是"帧没生效"的识别信号。

两个关键实现细节（都踩过坑）：
  · **`film_transparent = True` + 用 alpha 抠出物体**。否则世界背景（很小但非零的灰度）
    会混进像素统计里，把「角点应为 0」测成 0.23，把加权半径彻底搞乱。
  · 必须用**开始时**的快照还原。结尾再取一次快照 = 把"现在的值"当成"原值"，
    帧号/分辨率这类被改过的设置会永久留在场景里。

⚠️ 会建临时相机并改渲染设置，结束时还原。跑完核对末尾「还原」行。
"""
import os
import bpy
import numpy as np
from mathutils import Vector

OUT = r"D:/workbuddy/2026-09-14-17-42-15/_out"
W = H = 1000
HALF = 1.6           # 正交半宽（世界单位）。2x2 平面角点半径 sqrt(2)=1.414，取 1.6 兜住
STEP = 2.0 * HALF / W
SAMPLES = 64
OBJS = {                       # 物体 -> 正对它的观察方向（从物体指向相机）
    "平面":     Vector((0, 0, 1)),
    "平面.001": Vector((0, -1, 0)),
    "平面.002": Vector((1, 0, 0)),
}

log = []
scn = bpy.context.scene
R, VS = scn.render, scn.view_settings

# ---------------- 快照 / 还原 ----------------
def snap():
    return {"res_x": R.resolution_x, "res_y": R.resolution_y, "pct": R.resolution_percentage,
            "samples": scn.eevee.taa_render_samples, "filepath": R.filepath,
            "vt": VS.view_transform, "camera": scn.camera, "frame": scn.frame_current,
            "film": R.film_transparent, "colormode": R.image_settings.color_mode,
            "cams": list(bpy.data.cameras)}

def restore(s):
    R.resolution_x, R.resolution_y, R.resolution_percentage = s["res_x"], s["res_y"], s["pct"]
    scn.eevee.taa_render_samples = s["samples"]
    R.filepath = s["filepath"]
    VS.view_transform = s["vt"]
    R.film_transparent = s["film"]
    R.image_settings.color_mode = s["colormode"]
    scn.camera = s["camera"]
    for c in [c for c in bpy.data.cameras if c not in s["cams"]]:
        bpy.data.cameras.remove(c)
    for o in [o for o in bpy.data.objects if o.name.startswith("_VERIFY")]:
        bpy.data.objects.remove(o)
    if scn.frame_current != s["frame"]:
        scn.frame_set(s["frame"])

# ---------------- 渲染与读像素 ----------------
def render_ortho(cam_dir, path, frame, shifted=True):
    """正对原点渲染一张正交图。shifted=True 时把相机在两个垂直方向各偏半像素，
    使像素中心正好落在整数倍 STEP 上（世界坐标 u = (i - W/2) * STEP）。"""
    d = cam_dir.normalized()
    cd = bpy.data.cameras.new("_VERIFY")
    cam = bpy.data.objects.new("_VERIFY", cd)
    scn.collection.objects.link(cam)
    cd.type = 'ORTHO'
    cd.ortho_scale = 2.0 * HALF
    R3 = d.to_track_quat('Z', 'Y').to_matrix()
    loc = d * 5.0
    if shifted:
        loc = loc + R3 @ Vector((-STEP / 2.0, -STEP / 2.0, 0.0))
    cam.location = loc
    cam.rotation_euler = R3.to_euler()
    scn.camera = cam
    scn.frame_set(frame)
    R.filepath = path
    bpy.ops.render.render(write_still=True)
    scn.collection.objects.unlink(cam)
    bpy.data.objects.remove(cam)
    return R3, os.path.getsize(path)

def read_px(path):
    """返回 (亮度, 掩码)。用 alpha 抠出物体本身，背景一律置 0 —— 否则世界背景的
    非零灰度会污染所有统计（本项目实测：会把「角点应为 0」测成 0.23）。"""
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    a = buf.reshape(h, w, 4)
    bpy.data.images.remove(img)
    mask = a[:, :, 3] > 0.5
    lum = np.where(mask, a[:, :, :3].mean(axis=2), 0.0)
    return lum, mask

def sample_line(lum, mask, R3, world_dir, ts):
    """沿世界方向 world_dir 采样：P = world_dir * t。
    像素在相机平面内的坐标 = R3^T @ P，再换算成像素索引（半像素已修正）。"""
    dl = R3.transposed() @ world_dir.normalized()
    us = np.asarray(ts, dtype=np.float64)
    i = us * dl.x / STEP + W / 2.0
    j = us * dl.y / STEP + H / 2.0
    i0 = np.clip(np.floor(i).astype(int), 0, W - 2)
    j0 = np.clip(np.floor(j).astype(int), 0, H - 2)
    fi, fj = i - i0, j - j0
    def bil(arr):
        return ((arr[j0, i0] * (1 - fi) + arr[j0, i0 + 1] * fi) * (1 - fj)
                + (arr[j0 + 1, i0] * (1 - fi) + arr[j0 + 1, i0 + 1] * fi) * fj)
    return bil(lum), bil(mask.astype(np.float64)) > 0.5

# ==========================================================
S0 = snap()                               # ★ 必须在改任何设置之前取快照

R.image_settings.file_format = 'PNG'
R.image_settings.color_mode = 'RGBA'      # 要 alpha 抠背景，必须 RGBA
R.image_settings.color_depth = '8'
R.resolution_x = R.resolution_y = W
R.resolution_percentage = 100
R.film_transparent = True
scn.eevee.taa_render_samples = SAMPLES

# 每个像素 -> 世界点：正交相机的像素 (i,j) 对应相机平面坐标 (u,v)，
# 而物体平面过原点且垂直于视线 => 世界点 P = R3 @ (u, v, 0)，因此 rho = sqrt(u^2+v^2)。
ii, jj = np.meshgrid(np.arange(W), np.arange(H))
uu = (ii - W / 2.0) * STEP
vv = (jj - H / 2.0) * STEP
rho = np.sqrt(uu ** 2 + vv ** 2)
rho_f = rho.ravel()

# ---------------- T1 径向对称性 ----------------
log.append("### T1 径向对称性（像素按 rho 分箱，报告箱内标准差）")
edges = np.linspace(0.0, 1.5, 31)
idx = np.digitize(rho_f, edges) - 1
for name, cdir in OBJS.items():
    if name not in bpy.data.objects:
        log.append("  %-10s 跳过（对象不存在）" % name)
        continue
    path = os.path.join(OUT, "verify_t1_%s.png" % name.replace(".", "_"))
    render_ortho(cdir, path, 1)
    lum, mask = read_px(path)
    lf, mf = lum.ravel(), mask.ravel()
    stds = []
    for b in range(len(edges) - 1):
        sel = lf[(idx == b) & mf]
        if sel.size >= 40:
            stds.append(sel.std())
    band = lf[(rho_f > 1.05) & (rho_f < 1.40) & mf]      # 内切圆之外、方片之内
    core = lf[(rho_f < 0.03) & mf]
    log.append("  %-10s 最大箱内标准差=%.4f  中位=%.4f  （0~1 亮度；中位<0.01 即严格径向）"
               % (name, max(stds) if stds else -1, float(np.median(stds)) if stds else -1))
    log.append("             圆外交集带均值=%.4f（应≈该材质的镜面底噪，约 0.01）  中心均值=%.4f  物体像素=%d/%d"
               % (band.mean() if band.size else -1, core.mean() if core.size else -1,
                  int(mask.sum()), W * H))

# ---------------- T2 多物体一致性 ----------------
log.append("")
log.append("### T2 多物体一致性（同一世界轴上的取值比对）")
AXES = [("世界X", Vector((1, 0, 0)), "平面", "平面.001"),
        ("世界Y", Vector((0, 1, 0)), "平面", "平面.002"),
        ("世界Z", Vector((0, 0, 1)), "平面.001", "平面.002")]
imgs = {}
for name, cdir in OBJS.items():
    if name not in bpy.data.objects:
        continue
    path = os.path.join(OUT, "verify_t2_%s.png" % name.replace(".", "_"))
    R3, _ = render_ortho(cdir, path, 1)
    l, m = read_px(path)
    imgs[name] = (l, m, R3)
ts = np.linspace(-1.4, 1.4, 281)
for axname, axdir, na, nb in AXES:
    if na not in imgs or nb not in imgs:
        log.append("  %s 跳过" % axname)
        continue
    va, oka = sample_line(imgs[na][0], imgs[na][1], imgs[na][2], axdir, ts)
    vb, okb = sample_line(imgs[nb][0], imgs[nb][1], imgs[nb][2], axdir, ts)
    ok = oka & okb & (np.abs(ts) > 0.02)          # 近中心的角向结构被压到亚像素，排除
    d = np.abs(va - vb)[ok] * 255.0
    ctrl = []
    for sh in (3, 10, 30, 80):
        vc, _ = sample_line(imgs[nb][0], imgs[nb][1], imgs[nb][2], axdir, ts + sh * STEP)
        ctrl.append("%dpx:%.0f" % (sh, np.abs(va - vc)[ok].mean() * 255))
    log.append("  %s  %s vs %s  n=%d  最大=%.1f/255 平均=%.3f/255 超差(>2)=%d  |对照 %s" % (
        axname, na, nb, int(ok.sum()), d.max() if d.size else -1,
        d.mean() if d.size else -1, int((d > 2).sum()), "  ".join(ctrl)))
log.append("  注：纯径向图案（spot/ring/pulse）对**小**位移是二阶不敏感的"
           "（dr ≈ dx^2/2t），所以要给够位移量（几十像素）对照才有分辨力；")
log.append("      带角向结构的 spike 图案在 1px 错位上就能看出差别。")

# ---------------- T3 时间推进 ----------------
log.append("")
log.append("### T3 时间推进（从径向剖面直接读内/外边界，与解析式对照）")
# 不要用「亮度加权质心半径」：Principled 会镜面反射世界光，整个平面有个约 0.01 的
# 底噪，它的面积远大于图案本身，会把质心半径彻底带偏（实测 f1 反而 > f30）。
# 正确做法是给一个远高于底噪的阈值，在径向剖面上找内外两条边界。
P_ANALYTIC = {"prog0": 0.06, "prog1": 1.00, "split": 0.38,
              "R_out_cap": 1.05, "R_in_cap": 1.30, "soft": 0.09, "f0": 1, "f1": 250}

def analytic(f):
    pr = (P_ANALYTIC["prog0"] + (P_ANALYTIC["prog1"] - P_ANALYTIC["prog0"])
          * (f - P_ANALYTIC["f0"]) / float(P_ANALYTIC["f1"] - P_ANALYTIC["f0"]))
    cl = lambda x: 0.0 if x < 0 else (1.0 if x > 1 else x)
    ko = cl(pr / P_ANALYTIC["split"])
    ki = cl((pr - P_ANALYTIC["split"]) / (1.0 - P_ANALYTIC["split"]))
    return ko * P_ANALYTIC["R_out_cap"], ki * P_ANALYTIC["R_in_cap"]

name = "平面"
if name in bpy.data.objects:
    cdir = OBJS[name]
    frames = [1, 30, 60, 88, 130, 180, 250]
    sizes, routs, rins = [], [], []
    rr = np.linspace(0.0, 1.5, 400)
    for f in frames:
        path = os.path.join(OUT, "verify_t3_f%03d.png" % f)
        _, sz = render_ortho(cdir, path, f)
        sizes.append(sz)
        lum, mask = read_px(path)
        prof = np.array([lum[(np.abs(rho - r) < STEP) & mask].mean()
                         if ((np.abs(rho - r) < STEP) & mask).any() else 0.0 for r in rr])
        thr = max(0.06, 0.15 * float(prof.max()))
        above = prof > thr
        ao, ai = analytic(f)
        if not above.any():
            log.append("  f%3d 文件=%dB  全黑  解析: R_out=%.3f R_in=%.3f" % (f, sz, ao, ai))
            continue
        k0 = int(np.argmax(above))
        tail = above[k0:]
        k1 = k0 + (len(tail) - 1 - int(np.argmax(tail[::-1])))
        r_in, r_out = float(rr[k0]), float(rr[k1])
        routs.append((f, r_out))
        if r_in > 0.02:
            rins.append((f, r_in))
        log.append("  f%3d 文件=%dB  实测 R_in=%.3f R_out=%.3f | 解析 R_in=%.3f R_out=%.3f | 偏差 %.3f/%.3f"
                   % (f, sz, r_in, r_out, ai, ao, abs(r_in - ai), abs(r_out - ao)))
    if len(set(sizes)) == 1:
        log.append("  !! 多张图尺寸完全相同 = 「帧没生效」的识别信号，先查 frame_set")
    else:
        log.append("  文件大小各帧不同（说明 frame 参数真的生效了）")
    def mono(name, seq, tol=0.04):
        bad = [seq[k][0] for k in range(len(seq) - 1) if seq[k + 1][1] < seq[k][1] - tol]
        return "OK（单调不减）" if not bad else "**FAIL** 回退于帧 %s" % bad
    log.append("  R_out 推进：%s   序列=%s" % (mono("out", routs),
               " ".join("%.2f@%d" % (r, f) for f, r in routs)))
    log.append("  R_in  推进：%s   序列=%s" % (mono("in", rins),
               " ".join("%.2f@%d" % (r, f) for f, r in rins) or "（全程无黑腔）"))

restore(S0)
log.append("")
log.append("### 还原（应与你原来的设置一致）")
log.append("  camera=%s  res=%dx%d  taa_render=%d  view_transform=%s  frame=%d  film_transparent=%s"
           % (scn.camera.name if scn.camera else None, R.resolution_x, R.resolution_y,
              scn.eevee.taa_render_samples, VS.view_transform, scn.frame_current,
              R.film_transparent))
print("\n".join(log))
