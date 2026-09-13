# -*- coding: utf-8 -*-
# ============================================================================
# 平面验收测试卡（plane test card） v2
#   把「同一材质」挂到一块平面上，沿法线正交正视渲染 → 得到干净、可比的读数。
#   一次跑四件事：
#     A. 对比度扫描（1 / 2 / 5 / 10）→ 暗区占比、十档直方图
#     B. 视图变换对照（AgX vs Standard）→ 证明 AgX 会把读数压扁
#     C. 滚动方向实测（二维相位相关 + 合成自检）→ 定死正速度朝哪边
#     D. 干净性校验（leftover / 帧 / 参数还原）
#
#   ★ 关键设计（每一条都踩过坑）
#     1. ortho_scale = 跨度 × 0.98 ⇒ 平面**溢出**画面，读数 100% 是平面本身
#        （用 ×1.05 会留一圈黑背景，那圈黑会被算进 dark%，读数被污染）
#     2. 平面是 4 顶点满屏物体 ⇒ 暗区占比/直方图**才可信**；
#        细丝灯带只有 ~8% 像素是物体，统计量噪声太大，不适合当验收基准
#     3. 相机放「+法线」侧、朝向 −法线；up 轴向会被对齐世界 +Z ⇒ 图像竖直 = 世界 Z
#     4. 临时场景 + 把「已在主场景里的物体」link 进来（材质才会被求值）
#     5. 换帧用 main.frame_set()；**验收读值要在主场景读**，临时场景的
#        依赖图读出来可能是陈旧值（probe_56 实测）
#     6. 必须先 sc.render.filepath = p 再 render(write_still=True)，否则静默不写盘；
#        跑前删旧文件，别用 os.path.exists 当成功判据
# ============================================================================
import bpy, os, json, time, math
import numpy as np
from mathutils import Vector

WORKDIR = r"C:\path\to\blender_control"          # <<< 改这里
OUTDIR = os.path.join(WORKDIR, "render")
MAT_NAME = "竖向灯001_噪波滚动发光"                 # <<< 材质名
CTRL_NAME = "竖向灯001_噪波控制"                    # <<< 控制器空物体名
PLANE_NAME = "平面"                               # <<< 测试卡平面
BASE = {"噪波密度": 2.0, "噪波种子": 0.0, "Z向速度": 0.02, "噪波对比度": 5.0, "发光强度": 5.0}
CONTRAST_SWEEP = [1.0, 2.0, 5.0, 10.0]
SCROLL_FRAMES = (1, 61)                           # C 项：两帧
SCROLL_SPEED = 0.02
# ★★ 方向实测的参数必须让「位移 ≪ 噪声相关长度」，否则判据失效：
#   密度 2.0 ⇒ 特征 ≈0.5 世界单位；位移 0.6 就是 1.2 个特征 ⇒ fBm 全倍频一起失相关
#   ⇒ 两张图变成两张无关噪波，互相关峰值从 1.0 崩到 0.36，位移估计成噪声（实测踩过）。
#   所以这里把密度降到 0.4（特征 ≈2.5 世界单位）、位移抬到 1.2（≈0.5 个特征）。
SCROLL_OVERRIDE = {"噪波密度": 0.4, "噪波对比度": 2.0, "发光强度": 0.6}
PFX = "__TC"
RES = 720
SAMPLES = 24
OVERSCAN = 0.98                                   # 平面溢出比例（<1 = 溢出）

rep = {"t0": time.time()}
os.makedirs(OUTDIR, exist_ok=True)


def nuke():
    for s in list(bpy.data.scenes):
        if s.name.startswith(PFX):
            try: bpy.data.scenes.remove(s)
            except Exception: pass
    for o in list(bpy.data.objects):
        if o.name.startswith(PFX):
            try: bpy.data.objects.remove(o, do_unlink=True)
            except Exception: pass
    for w in list(bpy.data.worlds):
        if w.name.startswith(PFX):
            try: bpy.data.worlds.remove(w)
            except Exception: pass
    for c in list(bpy.data.cameras):
        if c.name.startswith(PFX):
            try: bpy.data.cameras.remove(c)
            except Exception: pass


nuke()
mat = bpy.data.materials[MAT_NAME]
ctrl = bpy.data.objects[CTRL_NAME]
main = bpy.context.scene
ORIG_FRAME = main.frame_current
plane = bpy.data.objects[PLANE_NAME]
pbb = [plane.matrix_world @ Vector(c) for c in plane.bound_box]
psp = [max(p[i] for p in pbb) - min(p[i] for p in pbb) for i in range(3)]
pfa = [i for i, s in enumerate(psp) if s < 1e-5]
rep["testcard"] = {
    "name": plane.name, "verts": len(plane.data.vertices), "polys": len(plane.data.polygons),
    "world_size": [round(s, 4) for s in psp],
    "flat_axes_world": ["XYZ"[i] for i in pfa],
    "rot_deg": [round(math.degrees(v), 2) for v in plane.rotation_euler],
    "scale": [round(v, 4) for v in plane.scale],
    "uv_layers": [u.name for u in plane.data.uv_layers],
    "is_flat": bool(pfa),
}


def face_normal(o):
    n = Vector((0, 0, 0))
    mw3 = o.matrix_world.to_3x3()
    for p in o.data.polygons:
        n += (mw3 @ p.normal) * p.area
    return n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))


sc = bpy.data.scenes.new(PFX + "_SCENE__")
sc.render.engine = 'CYCLES'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = False
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_depth = '16'      # ★ 16 位，减少量化台阶
sc.render.dither_intensity = 0.0                 # ★★ 默认 1.0！会给每个像素加 ±1/255 抖动，
                                                 #    相位相关会被它打散（峰值 1.0 → 0.38），
                                                 #    位移就测不出来了。必须关掉。
sc.render.film_transparent = False
sc.render.stamp_font_size = 20
sc.render.stamp_background = (0, 0, 0, 0.7)
sc.render.use_stamp = True
for _f in ("use_stamp_date", "use_stamp_time", "use_stamp_render_time", "use_stamp_frame",
           "use_stamp_frame_range", "use_stamp_camera", "use_stamp_scene", "use_stamp_filename",
           "use_stamp_lens", "use_stamp_marker", "use_stamp_memory", "use_stamp_hostname",
           "use_stamp_sequencer_strip"):
    if hasattr(sc.render, _f):
        setattr(sc.render, _f, False)
sc.render.use_stamp_note = True
sc.render.use_stamp_labels = False
sc.view_settings.look = main.view_settings.look
sc.view_settings.exposure = main.view_settings.exposure
w2 = bpy.data.worlds.new(PFX + "_WORLD__")
w2.use_nodes = True
_bg = next(n for n in w2.node_tree.nodes if n.type == 'BACKGROUND')   # ⚠️ 别按名字找
_bg.inputs[0].default_value = (0, 0, 0, 1)
_bg.inputs[1].default_value = 0.0
sc.world = w2

cd = bpy.data.cameras.new(PFX + "_CAM__")
cam = bpy.data.objects.new(PFX + "_CAM__", cd)
sc.collection.objects.link(cam)
sc.camera = cam
cd.type = 'ORTHO'

nrm = face_normal(plane)
xs = [p.x for p in pbb]; ys = [p.y for p in pbb]; zs = [p.z for p in pbb]
cent = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
span_x, span_z = max(xs) - min(xs), max(zs) - min(zs)
cd.ortho_scale = max(max(span_x, span_z) * OVERSCAN, 0.05)
cam.location = cent + nrm * 30.0
cam.rotation_euler = (cent - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.resolution_x = RES
sc.render.resolution_y = max(64, int(round(RES * span_z / max(span_x, 1e-6))))
sc.collection.objects.link(plane)                      # ★ 额外 link，别 unlink 主场景
WPP = cd.ortho_scale / max(sc.render.resolution_x, sc.render.resolution_y)   # 世界单位/像素
rep["camera"] = {"normal": [round(v, 5) for v in nrm],
                 "location": [round(v, 4) for v in cam.location],
                 "ortho_scale": round(cd.ortho_scale, 4),
                 "resolution": [sc.render.resolution_x, sc.render.resolution_y],
                 "world_per_px": round(WPP, 6),
                 "overscan": OVERSCAN,
                 "up_axis_note": "相机 local +Y 对齐世界 +Z ⇒ 图像竖直方向 = 世界 Z",
                 "array_note": "pixels 行 0 = 图像最底行 = 世界 z 最小"}


def apply(frame, over=None):
    vals = dict(BASE)
    vals.update(over or {})
    for k, v in vals.items():
        ctrl[k] = float(v)
    ctrl.update_tag(); mat.update_tag(); mat.node_tree.update_tag()
    main.frame_set(frame)
    bpy.context.view_layer.update()


def load_arr(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    n = w * h
    buf = np.empty(n * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)                 # ★ 直通 numpy，比 list 快一个量级
    bpy.data.images.remove(img)
    b = buf.reshape(n, 4).astype(np.float64)
    lum = 0.2126 * b[:, 0] + 0.7152 * b[:, 1] + 0.0722 * b[:, 2]
    return lum.reshape(h, w)          # arr[row, col]，row 0 = 世界 z 最小


def stats(a):
    flat = a.reshape(-1)
    n = flat.size
    s = np.sort(flat)
    hist = np.histogram(flat, bins=10, range=(0.0, 1.0))[0]
    return {
        "min": round(float(s[0]), 4), "p10": round(float(s[n // 10]), 4),
        "p50": round(float(s[n // 2]), 4), "p90": round(float(s[n * 9 // 10]), 4),
        "max": round(float(s[-1]), 4),
        "dark%": round(100.0 * float((flat < 0.05).sum()) / n, 2),
        "mid%": round(100.0 * float(((flat >= 0.05) & (flat <= 0.95)).sum()) / n, 2),
        "blown%": round(100.0 * float((flat > 0.95).sum()) / n, 2),
        "hist_0.0-1.0": [round(100.0 * float(x) / n, 2) for x in hist],
    }


def shift_estimate(A, B):
    """估计「把 A 平移多少得到 B」。返回 (dy, dx)，dy>0 表示向 +行号(=+世界Z) 方向。"""
    a = A - A.mean()
    b = B - B.mean()
    F = np.fft.rfft2(a) * np.conj(np.fft.rfft2(b))
    den = np.abs(F)
    den[den < 1e-12] = 1.0
    r = np.fft.irfft2(F / den, a.shape)
    idx = int(np.argmax(r))
    dy, dx = np.unravel_index(idx, r.shape)
    dy, dx = int(dy), int(dx)
    if dy > r.shape[0] // 2:
        dy -= r.shape[0]
    if dx > r.shape[1] // 2:
        dx -= r.shape[1]
    # 相位相关的符号约定：B[n]=A[n-s] ⇒ F[k]=|A|²·exp(+2πi·k·s/N) ⇒ 峰值落在 −s
    peak = float(r.max())
    return -dy, -dx, peak


# ---------- 相位相关估计器的合成自检（先证明工具是对的，再用它下结论）----------
try:
    rng = np.random.default_rng(20260913)
    base = rng.random((128, 128))          # 白噪声：相位相关最准、也最能暴露符号约定
    for (sy, sx) in [(7, 0), (-11, 0), (0, 5), (13, -9), (-4, -4)]:
        shifted = np.roll(np.roll(base, sy, axis=0), sx, axis=1)
        ey, ex, pk = shift_estimate(base, shifted)
        rep.setdefault("estimator_selftest", []).append(
            {"true": [sy, sx], "estimated": [ey, ex], "peak": round(pk, 4),
             "ok": (ey == sy and ex == sx)})
except Exception as e:
    rep["estimator_selftest"] = [{"error": repr(e)}]

# ---------- 渲染任务 ----------
# ★ 滚动方向那两张必须「无蒙特卡洛噪声」，否则相位相关会被高频噪声打散
#   （实测：24 采样时峰值只有 0.378，方向测不出来）。
#   纯发光材质 + 黑世界 ⇒ 每条相机射线直接返回 emission，**1 采样即为精确值**；
#   再把 film filter 压到 0.01 去掉抗锯齿模糊 ⇒ 图像是完全确定的。
JOBS = []
for c in CONTRAST_SWEEP:
    JOBS.append(("ctr%s" % ("%g" % c).replace(".", "p"), 1, {"噪波对比度": c}, "AgX", False))
JOBS.append(("ctr5_standard", 1, {}, "Standard", False))
for fr in SCROLL_FRAMES:
    JOBS.append(("scroll_f%d" % fr, fr, SCROLL_OVERRIDE, "Standard", True))
# 空对照：同一帧再渲一次。两张应当【完全一致】⇒ 互相关峰值≈1、位移=0。
# 它证明「渲染→像素→相位相关」这条链路本身没有引入假位移。
JOBS.append(("scroll_null", SCROLL_FRAMES[0], SCROLL_OVERRIDE, "Standard", True))

def read_eval_brief():
    """从【主场景】求值依赖图读回 6 条驱动的真值，确认材质确实看到了新参数"""
    dg = bpy.context.evaluated_depsgraph_get()
    nte = mat.evaluated_get(dg).node_tree
    out = {}
    for n in nte.nodes:
        if n.type == 'MAPPING':
            out["mapZ"] = round(float(n.inputs[1].default_value[2]), 4)
        if n.type == 'TEX_NOISE':
            out["scale"] = round(float(n.inputs[2].default_value), 4)
            out["W"] = round(float(n.inputs[1].default_value), 4)
        if n.type == 'VALTORGB':
            out["ramp"] = [round(float(e.position), 4) for e in n.color_ramp.elements]
        if n.type == 'MATH' and n.operation == 'MULTIPLY':
            out["mult"] = round(float(n.inputs[1].default_value), 4)
    return out


jobs = []
arrs = {}
rep["render_modes"] = {"stats_jobs": {"samples": SAMPLES, "filter_size": 1.5},
                       "scroll_jobs": {"samples": 1, "filter_size": 0.01,
                                       "dither": 0.0, "color_depth": "16",
                                       "why": "纯发光+黑世界 ⇒ 1 采样即精确值；关抖动+16位"
                                              "才不会被输出量化噪声打散相位相关"}}
for name, frame, over, vt, clean in JOBS:
    apply(frame, over)
    sc.view_settings.view_transform = vt
    sc.cycles.samples = 1 if clean else SAMPLES
    sc.render.filter_size = 0.01 if clean else 1.5
    sc.render.stamp_note_text = "%s | f%s | %s | ortho %.2f" % (name, frame, vt, cd.ortho_scale)
    p = os.path.join(OUTDIR, "tc_%s.png" % name)
    if os.path.exists(p):
        os.remove(p)
    sc.render.filepath = p
    t1 = time.time()
    r = {"name": name, "frame": frame, "params": over, "view_transform": vt,
         "samples": sc.cycles.samples, "clean": clean, "path": p,
         "evaluated": read_eval_brief()}
    try:
        bpy.ops.render.render(write_still=True, scene=sc.name)
        r["sec"] = round(time.time() - t1, 2)
        r["ok"] = os.path.exists(p) and os.path.getsize(p) > 1024
        if r["ok"]:
            arr = load_arr(p)
            r.update(stats(arr))
            arrs[name] = arr
    except Exception as e:
        r["ok"] = False
        r["error"] = repr(e)
    jobs.append(r)
rep["jobs"] = jobs

# ---------- C. 滚动方向实测（先空对照，再实测）----------
def _prep(x):
    H, W = x.shape
    return x[:H - int(H * 0.12), :]          # 掐掉左上角 stamp，免得文字干扰互相关


def _down(x, f=8):
    """块平均降采样：抹掉 FBM 高频斑点，让「主亮块」可被 argmax 稳定抓到"""
    H, W = x.shape
    H2, W2 = H // f, W // f
    return x[:H2 * f, :W2 * f].reshape(H2, f, W2, f).mean(axis=(1, 3))


def coarse_peak_shift(A, B, f=8, r=22):
    """第二种独立判据：找 A 的主亮块在 B 里的位置，差值即位移（块尺度 = f 像素）"""
    a, b = _down(A, f), _down(B, f)
    ay, ax = np.unravel_index(int(np.argmax(a)), a.shape)
    H, W = b.shape
    y0, y1 = max(0, ay - r), min(H, ay + r + 1)
    x0, x1 = max(0, ax - r), min(W, ax + r + 1)
    by, bx = np.unravel_index(int(np.argmax(b[y0:y1, x0:x1])), (y1 - y0, x1 - x0))
    by += y0
    bx += x0
    return int((by - ay) * f), int((bx - ax) * f), int((by - ay)), int((bx - ax))


try:
    ndy, ndx, npk = shift_estimate(
        _prep(arrs["scroll_f%d" % SCROLL_FRAMES[0]]), _prep(arrs["scroll_null"]))
    rep["scroll_null_test"] = {
        "how": "同一帧渲两次，应当完全一致",
        "expect": [0, 0], "got": [ndy, ndx], "peak": round(npk, 4),
        "pass": bool(ndy == 0 and ndx == 0 and npk > 0.9),
        "note": "峰值≈1 且位移=0 ⇒ 渲染→像素→相位相关 这条链路没有引入假位移",
    }
except Exception as e:
    rep["scroll_null_test"] = {"error": repr(e), "pass": False}

try:
    A = _prep(arrs["scroll_f%d" % SCROLL_FRAMES[0]])
    B = _prep(arrs["scroll_f%d" % SCROLL_FRAMES[1]])
    dy, dx, pk = shift_estimate(A, B)
    cy, cx, cby, cbx = coarse_peak_shift(A, B)
    dL = SCROLL_SPEED * (SCROLL_FRAMES[1] - SCROLL_FRAMES[0])
    exp_px = dL / WPP
    null_ok = rep.get("scroll_null_test", {}).get("pass", False)
    votes = [v for v in (dy, cy) if abs(v) >= max(4.0, exp_px * 0.25)]
    if not null_ok:
        verdict = "空对照未通过 ⇒ 位移不可信"
    elif not votes:
        verdict = "两种判据都没测出可信位移"
    elif all(v < 0 for v in votes):
        verdict = "与手册 POINT 语义一致：正速度 ⇒ 图案朝 −Z 移动"
    elif all(v > 0 for v in votes):
        verdict = "与手册 POINT 语义相反：正速度 ⇒ 图案朝 +Z 移动"
    else:
        verdict = "两种判据符号不一致 ⇒ 存疑，别下结论"
    rep["scroll_test"] = {
        "frames": list(SCROLL_FRAMES), "speed": SCROLL_SPEED,
        "Location_Z_delta": round(dL, 4),
        "method1_phase_corr": {"shift_py": [dy, dx], "peak": round(pk, 4)},
        "method2_coarse_peak": {"shift_px": [cy, cx], "block_shift": [cby, cbx],
                                "block": 8},
        "expected_px_if_known_geometry": round(exp_px, 2),
        "method1_shift_world_Z": round(dy * WPP, 4),
        "method2_shift_world_Z": round(cy * WPP, 4),
        "null_test_passed": null_ok,
        "manual_prediction_POINT_type":
            "Mapping Vector Type=POINT ⇒ 坐标沿 +Z 平移时纹理朝 −Z 移动（官方手册）",
        "verdict": verdict,
    }
except Exception as e:
    rep["scroll_test"] = {"error": repr(e)}

# ---------- 还原 + 清理 ----------
for k, v in BASE.items():
    ctrl[k] = float(v)
ctrl.update_tag(); mat.update_tag(); mat.node_tree.update_tag()
main.frame_set(ORIG_FRAME)
bpy.context.view_layer.update()
try:
    sc.collection.objects.unlink(plane)
except Exception:
    pass
try:
    bpy.data.scenes.remove(sc); rep["scene_removed"] = True
except Exception as e:
    rep["scene_removed"] = repr(e)
nuke()
rep["leftover"] = {k: [x.name for x in v if x.name.startswith(PFX)] for k, v in
                   (("objects", bpy.data.objects), ("scenes", bpy.data.scenes),
                    ("worlds", bpy.data.worlds), ("cameras", bpy.data.cameras))}
rep["scene_now"] = bpy.context.scene.name
rep["frame_after"] = main.frame_current
rep["ctrl_after"] = {k: ctrl.get(k) for k in BASE}
rep["object_count"] = len(bpy.data.objects)
rep["total_sec"] = round(time.time() - rep["t0"], 2)
print("TC_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("TC_END")
