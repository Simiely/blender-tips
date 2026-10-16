# -*- coding: utf-8 -*-
# 渐变扫过材质 · UV 方向角 —— 独立核验(经 9877 桥执行)
# ===========================================================================
# 三层判据,每层都要有【可证伪的读数】:
#   A. 结构   : 23 条连线逐条比对 + 取模运算类型 + 混合系数 + 色标指纹(只读记录)
#   B. 驱动   : 行为法 —— 改旋钮 → 强刷新 → 看插座值跟不跟(不看 is_valid)
#   C. 渲染   : 四个角度各渲一张,量
#               ① gradX/gradY  朝向读数(>1 竖条 / <1 横条 / ≈1 斜条)
#               ② 沿 t 方向的条数 —— 四个角度【必须相同】★ 这就是"归一化"的可证伪判据
#               ③ 180° 与 0° 的逐像素差:镜像差应 ≪ 同向差(不要拿 t 剖面做,见 C 区注释)
# 临时相机 / 分辨率 / 采样 / 帧 / 扫过角度 全部还原。失败只打印,不抛异常(否则桥会吞掉前面的输出)。
# ===========================================================================
import bpy, os, math, base64

# ═══ 配置(换工程改这里) ═══
PLANE = "平面"
MAT_NAME = "渐变扫过材质"
CTRL_NAME = "渐变控制"
OUT_DIR = "D:/workbuddy/blender_tips_out"      # 报告 / 截图 / 预览落盘目录
RES = 256                                       # 渲染边长
SAMPLES = 16
ANGLES = [0, 45, 90, 180]
HTML_NAME = "渐变角度_预览.html"
# ═════════════════════════

C, D, sc = bpy.context, bpy.data, bpy.context.scene
FPS = float(sc.render.fps)
os.makedirs(OUT_DIR, exist_ok=True)

ob = D.objects[PLANE]
mat = D.materials[MAT_NAME]
ctrl = D.objects[CTRL_NAME]
nt = mat.node_tree
fails = []


def chk(cond, msg):
    print(("  [PASS] " if cond else "  [FAIL] ") + msg)
    if not cond:
        fails.append(msg)


def force_refresh():
    """★ 改完自定义属性必须这样标脏,否则节点树上的驱动器不重算(只 view_layer.update() 不够)"""
    ctrl.update_tag()
    nt.update_tag()
    C.evaluated_depsgraph_get().update()


def node_val(nm):
    force_refresh()
    return D.materials[mat.name].evaluated_get(C.evaluated_depsgraph_get()).node_tree.nodes[nm].outputs[0].default_value


def has_link(a, sa, b, sb):
    for l in nt.links:
        if (l.from_node.name == a and l.from_socket.name == sa
                and l.to_node.name == b and l.to_socket.name == sb):
            return True
    return False


def ramp_sig(n):
    return [(round(e.position, 3), tuple(round(c, 3) for c in e.color[:3]))
            for e in n.color_ramp.elements]


print("RECHECK 目标=%r 材质=%r NODES=%d LINKS=%d FPS=%s 帧=%d"
      % (ob.name, mat.name, len(nt.nodes), len(nt.links), FPS, sc.frame_current))

# ---------------- A. 结构 ----------------
print("--- A. 结构 ---")
PAIRS = [
    ("坐标_纹理", "Generated", "分离_XY", "Vector"),
    ("分离_XY", "X", "数学_方向X", "Value"),
    ("角度_余弦", "Value", "数学_方向X", "Value"),
    ("分离_XY", "Y", "数学_方向Y", "Value"),
    ("角度_正弦", "Value", "数学_方向Y", "Value"),
    ("数学_方向X", "Value", "数学_投影", "Value"),
    ("数学_方向Y", "Value", "数学_投影", "Value"),
    ("数学_投影", "Value", "数学_倍频", "Value"),
    ("条数", "Value", "数学_倍频", "Value"),
    ("数学_倍频", "Value", "数学_相移", "Value"),
    ("相位", "Value", "数学_相移", "Value"),
    ("数学_相移", "Value", "数学_循环", "Value"),
    ("数学_循环", "Value", "颜色渐变_扫过", "Factor"),
    ("分离_XY", "Y", "数学_倍频Y", "Value"),
    ("水平条数", "Value", "数学_倍频Y", "Value"),
    ("数学_倍频Y", "Value", "数学_循环Y", "Value"),
    ("数学_循环Y", "Value", "颜色渐变_水平", "Factor"),
    ("颜色渐变_扫过", "Color", "混合_水平x扫过", "A"),
    ("颜色渐变_水平", "Color", "混合_水平x扫过", "B"),
    ("混合_水平x扫过", "Result", "原理化BSDF", "Base Color"),
    ("混合_水平x扫过", "Result", "原理化BSDF", "Emission Color"),
    ("发光强度", "Value", "原理化BSDF", "Emission Strength"),
    ("原理化BSDF", "BSDF", "材质输出", "Surface"),
]
for a, sa, b, sb in PAIRS:
    chk(has_link(a, sa, b, sb), "%s.%s -> %s.%s" % (a, sa, b, sb))
chk(not has_link("分离_XY", "X", "数学_倍频", "Value"), "旧的一维连线 分离_XY.X -> 数学_倍频 已断开")
chk(len([l for l in nt.links if l.to_node.name == "数学_倍频"]) == 2, "数学_倍频 恰好 2 个输入")
chk(nt.nodes["数学_方向X"].operation == 'MULTIPLY' and nt.nodes["数学_方向Y"].operation == 'MULTIPLY',
    "数学_方向X / 数学_方向Y = MULTIPLY")
chk(nt.nodes["数学_投影"].operation == 'ADD', "数学_投影 = ADD(二维投影的两个乘积累加)")
for nm in ("数学_循环", "数学_循环Y"):
    chk(nt.nodes[nm].operation == 'FLOORED_MODULO' and abs(nt.nodes[nm].inputs[1].default_value - 1.0) < 1e-6,
        "%s = FLOORED_MODULO 1.0(负值不许被裁剪)" % nm)
n_mix = nt.nodes["混合_水平x扫过"]
chk(n_mix.bl_idname in ("ShaderNodeMix", "ShaderNodeMixRGB") and n_mix.blend_type == 'MULTIPLY',
    "混合节点 = %s / MULTIPLY(白 = 中性)" % n_mix.bl_idname)
fac = [s for s in n_mix.inputs if s.name in ("Factor", "Fac") and s.type in ("VALUE",)][0]
chk(abs(fac.default_value - 1.0) < 1e-6, "混合系数 = 1.0(★ 设 0 会退化成只取 A,不是纯相乘)")
for nm in ("颜色渐变_扫过", "颜色渐变_水平"):
    chk(nm in nt.nodes, "%s 存在(色标 %d 档,脚本不碰它)"
        % (nm, len(nt.nodes[nm].color_ramp.elements)))
print("  色标指纹(仅记录,不做断言 —— 这是用户的手调成果):%r"
      % {nm: ramp_sig(nt.nodes[nm]) for nm in ("颜色渐变_扫过", "颜色渐变_水平")})
chk(nt.nodes["颜色渐变_扫过"].inputs[0].name == "Factor", "ColorRamp 输入插座名 = Factor")
drs = list(nt.animation_data.drivers) if nt.animation_data else []
tgt = sorted({(t.id.name if t.id else None) for d in drs
              for v in d.driver.variables for t in v.targets})
chk(len(drs) == 6, "驱动器 6 条")
chk(tgt == [CTRL_NAME], "驱动器源唯一地指向 %r" % CTRL_NAME)
chk(PLANE not in tgt, "材质没有反向依赖目标网格体(可整体搬到别的 mesh)")

# ---------------- B. 驱动(行为法) ----------------
print("--- B. 驱动行为(改旋钮 → 强刷新 → 看跟不跟) ---")
_f0 = sc.frame_current
orig = {k: ctrl[k] for k in ctrl.keys()}
try:
    for a in (0, 30, 45, 90, 135, 180, 270, 360):
        ctrl["扫过角度"] = float(a)
        r = math.radians(a)
        k = 1.0 / (abs(math.cos(r)) + abs(math.sin(r)))
        c = node_val("角度_余弦")
        s = node_val("角度_正弦")
        ok = abs(c - math.cos(r) * k) < 1e-4 and abs(s - math.sin(r) * k) < 1e-4
        print("  %-5s %-4s° 余弦=%+.5f 正弦=%+.5f (期望 %+.5f / %+.5f)"
              % ("[PASS]" if ok else "[FAIL]", a, c, s, math.cos(r) * k, math.sin(r) * k))
        if not ok:
            fails.append("角度 %s° 驱动未跟随" % a)
    ctrl["扫过角度"] = 0.0
    sq = node_val("角度_余弦") ** 2 + node_val("角度_正弦") ** 2
    chk(abs(sq - 1.0) < 1e-4, "0° 时 cos²+sin² = %.6f(方向是单位向量)" % sq)
    for t in (1.0, 2.5, 4.0):
        ctrl["扫过条数"] = t
        chk(abs(node_val("条数") - t) < 1e-4, "扫过条数 %.2f → 条数插座 %.4f" % (t, node_val("条数")))
    for s2 in (0.5, 2.0):
        ctrl["扫过速度"] = s2
        e = s2 * (sc.frame_current - 1) / FPS
        chk(abs(node_val("相位") - e) < 1e-4, "扫过速度 %.2f → 相位 %.6f (期望 %.6f)" % (s2, node_val("相位"), e))
    sc.frame_set(_f0)
    p1 = node_val("相位")
    sc.frame_set(_f0 + 1)
    p2 = node_val("相位")
    chk(abs((p2 - p1) - float(ctrl["扫过速度"]) / FPS) < 1e-5,
        "帧 +1 → 相位步进 %.6f(期望 速度/fps = %.6f)" % (p2 - p1, float(ctrl["扫过速度"]) / FPS))
finally:
    for k, v in orig.items():
        ctrl[k] = v
    sc.frame_set(_f0)
    force_refresh()

# ---------------- C. 渲染 ----------------
print("--- C. 渲染实测 ---")
# 平面世界范围(不用 dimensions —— 脚本里刚设完可能没刷新,用网格顶点算)
mw = ob.matrix_world
pts = [mw @ v.co for v in ob.data.vertices]
xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
W, H = max(xs) - min(xs), max(ys) - min(ys)
cx, cy = (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0
chk((max(zs) - min(zs)) < 1e-4 * max(W, H, 1.0), "目标网格体是水平面(XY 平面)⇒ 正交俯视即可")
print("  平面世界范围 X %.4f / Y %.4f,Z 跨度 %.6f" % (W, H, max(zs) - min(zs)))

snap = dict(rx=sc.render.resolution_x, ry=sc.render.resolution_y, rp=sc.render.resolution_percentage,
            fp=sc.render.filepath, fmt=sc.render.image_settings.file_format, cam=sc.camera,
            fr=sc.frame_current, samples=getattr(sc.cycles, "samples", None),
            den=getattr(sc.cycles, "use_denoising", None))
cam_data = D.cameras.new("__tmp_sweep_cam__")
cam = D.objects.new("__tmp_sweep_cam__", cam_data)
sc.collection.objects.link(cam)
cam_data.type = 'ORTHO'
cam_data.ortho_scale = max(W, H)          # ★ 不留边距 ⇒ 像素 (x,y) 与 Generated (u,v) 一一对应
cam.location = (cx, cy, max(zs) + 10.0)
cam.rotation_euler = (0.0, 0.0, 0.0)
sc.camera = cam
sc.render.image_settings.file_format = 'PNG'
sc.render.resolution_x = sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
if getattr(sc, "cycles", None):
    sc.cycles.samples = SAMPLES
    if snap["den"] is not None:
        sc.cycles.use_denoising = False

shots = {}


def shoot(a):
    ctrl["扫过角度"] = float(a)
    force_refresh()
    path = "%s/angle_%03d.png" % (OUT_DIR, a)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = D.images.load(path, check_existing=False)
    w, h = img.size
    pix = tuple(img.pixels[:])
    D.images.remove(img)
    return path, w, h, pix


def grads(pix, w, h):
    gx = gy = 0.0
    n = 0
    for y in range(1, h - 1):
        row = y * w
        for x in range(1, w - 1):
            i = (row + x) * 4
            c = pix[i]
            gx += abs(pix[i + 4] - c)
            gy += abs(pix[i + w * 4] - c)
            n += 1
    return gx / n, gy / n


def profile_t(pix, w, h, theta, bins=128):
    """沿角度方向的坐标 t 取剖面 —— 归一化是否成立,看不同角度的「条数」是否相同

    ★ 必须先按 1.0 取模,再分箱。θ 超过 90° 时 t 会变成负数(180° 就是 t = −u),
      若不取模,`if 0 <= bi < bins` 会把绝大多数采样点直接丢掉,
      于是「条数」塌成 1、镜像相关也退化到 0 —— 本项目已实测踩过这个坑。
      取模与材质自身的 FLOORED_MODULO 1.0 完全同构,而且是周期函数在接缝处连续,
      所以不会引入假的跳变边。
    """
    r = math.radians(theta)
    cs, sn = math.cos(r), math.sin(r)
    k = 1.0 / (abs(cs) + abs(sn))
    acc = [0.0] * bins
    cnt = [0] * bins
    for y in range(h):
        v = y / float(h - 1)
        base = y * w
        for x in range(w):
            t = (((x / float(w - 1)) * cs + v * sn) * k) % 1.0
            bi = int(t * bins)
            if bi >= bins:          # 浮点误差可能让 t 恰好落在 1.0 上
                bi = bins - 1
            acc[bi] += pix[(base + x) * 4]
            cnt[bi] += 1
    return [a / c if c else 0.0 for a, c in zip(acc, cnt)]


def count_bands(prof, frac=0.5):
    lo, hi = min(prof), max(prof)
    if hi - lo < 0.02:
        return 0
    thr = lo + frac * (hi - lo)
    bands, inside = 0, False
    for v in prof:
        if v >= thr and not inside:
            bands, inside = bands + 1, True
        elif v < thr:
            inside = False
    return bands


try:
    for a in ANGLES:
        path, w, h, pix = shoot(a)
        gx, gy = grads(pix, w, h)
        prof = profile_t(pix, w, h, a)
        shots[a] = dict(path=path, w=w, h=h, pix=pix, gx=gx, gy=gy, prof=prof,
                        bands=count_bands(prof))
        print("  %-4s° %dx%d gradX=%.5f gradY=%.5f 比值=%7.3f 沿 t 条数=%d"
              % (a, w, h, gx, gy, gx / max(gy, 1e-9), shots[a]["bands"]))
finally:
    ctrl["扫过角度"] = orig.get("扫过角度", 0.0)
    force_refresh()
    sc.camera = snap["cam"]
    D.objects.remove(cam, do_unlink=True)
    if cam_data.users == 0:
        D.cameras.remove(cam_data)
    sc.render.resolution_x, sc.render.resolution_y = snap["rx"], snap["ry"]
    sc.render.resolution_percentage = snap["rp"]
    sc.render.filepath = snap["fp"]
    sc.render.image_settings.file_format = snap["fmt"]
    if snap["samples"] is not None and getattr(sc, "cycles", None):
        sc.cycles.samples = snap["samples"]
    if snap["den"] is not None and getattr(sc, "cycles", None):
        sc.cycles.use_denoising = snap["den"]
    sc.frame_set(snap["fr"])
    print("  (临时相机 / 分辨率 / 采样 / 帧 已还原)")

if len(shots) == len(ANGLES):
    r0 = shots[0]["gx"] / max(shots[0]["gy"], 1e-9)
    r45 = shots[45]["gx"] / max(shots[45]["gy"], 1e-9)
    r90 = shots[90]["gx"] / max(shots[90]["gy"], 1e-9)
    r180 = shots[180]["gx"] / max(shots[180]["gy"], 1e-9)
    chk(r0 > 1.5, "0° 是竖条(gradX/gradY = %.2f > 1.5)⇒ 沿 U 变化" % r0)
    chk(r90 < 0.67, "90° 是横条(gradX/gradY = %.2f < 0.67)⇒ 沿 V 变化" % r90)
    chk(0.67 <= r45 <= 1.5, "45° 近似各向同性(%.2f)⇒ 斜条" % r45)
    chk(r180 > 1.5, "180° 又是竖条(%.2f)⇒ 方向翻转后仍是同一根轴" % r180)

    # ★ 归一化的可证伪判据:四个角度「沿 t 方向的条数」必须相同
    bc = [shots[a]["bands"] for a in ANGLES]
    print("  四角度沿 t 的条数 = %r" % (bc,))
    chk(len(set(bc)) == 1 and bc[0] > 0,
        "★ 归一化成立:四个角度的条数完全相同 %r(不除 (|cos|+|sin|) 时 45° 会多出 1.41 倍)" % (bc,))

    # 180° 应 = 0° 沿 U 的逐点镜像
    # ★ 不要拿「沿 t 的剖面」来做这个判据:profile_t 的采样方向本身就跟着 t 翻,
    #   所以 0° / 180° 的 t 剖面天生重合(实测同向相关 +1.0000 / 镜像 −0.3014),
    #   再手工 [::-1] 一次等于翻了两次 —— 这是个自证式陷阱。直接比像素最干净。
    P0, P180 = shots[0]["pix"], shots[180]["pix"]
    w0, h0 = shots[0]["w"], shots[0]["h"]
    npx = float(w0 * h0)
    same = mir = 0.0
    for yy in range(h0):
        b = yy * w0
        for x in range(w0):
            i = (b + x) * 4
            same += abs(P180[i] - P0[i])
            mir += abs(P180[i] - P0[(b + (w0 - 1 - x)) * 4])
    same, mir = same / npx, mir / npx
    selfm = 0.0
    for yy in range(h0):
        b = yy * w0
        for x in range(w0):
            i = (b + x) * 4
            selfm += abs(P0[i] - P0[(b + (w0 - 1 - x)) * 4])
    selfm /= npx
    print("  平均逐像素差:同向 %.6f / 镜像 %.6f / 0° 图自身左右不对称度 %.6f"
          % (same, mir, selfm))
    chk(selfm > 20.0 * mir,
        "可证伪前提:0° 图本身左右强不对称(%.6f ≫ %.6f)⇒ 镜像判据不会自动成立" % (selfm, mir))
    chk(mir < 0.1 * same,
        "180° = 0° 的左右镜像(镜像差 %.6f ≪ 同向差 %.6f,小 %.0f 倍)"
        % (mir, same, same / max(mir, 1e-9)))

    # ---------------- 预览 HTML ----------------
    try:
        LAB = {0: "0° —— 沿 +U(等价于原来的「方向 = 1」)", 45: "45° —— 斜扫",
               90: "90° —— 沿 +V", 180: "180° —— 沿 −U(等价于原来的「方向 = −1」)"}
        cards = []
        for a in ANGLES:
            s = shots[a]
            b64 = base64.b64encode(open(s["path"], "rb").read()).decode("ascii")
            cards.append(
                '<figure><img src="data:image/png;base64,' + b64 + '" alt="' + str(a) + '°">'
                '<figcaption><b>' + LAB[a] + '</b><span>gradX&divide;gradY = '
                + ("%.3f" % (s["gx"] / max(s["gy"], 1e-9))) + ' · 条数 ' + str(s["bands"])
                + '</span></figcaption></figure>')
        knobs = " · ".join("%s = %s" % (k, ctrl[k]) for k in
                           ("扫过角度", "扫过速度", "扫过条数", "水平条数", "发光强度"))
        CSS = """
 body{margin:0;padding:28px 32px;background:#f6f7f9;color:#1a1c1f;
      font:15px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
 h1{font-size:20px;margin:0 0 6px}
 p.sub{margin:0 0 22px;color:#5b6270;font-size:13px}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px}
 figure{margin:0;background:#fff;border:1px solid #e3e6ea;border-radius:10px;overflow:hidden;
        box-shadow:0 1px 3px rgba(16,24,40,.06)}
 img{display:block;width:100%;image-rendering:pixelated;background:#111}
 figcaption{padding:10px 12px;font-size:13px;display:flex;justify-content:space-between;
            gap:8px;align-items:baseline;border-top:1px solid #eef0f3}
 figcaption span{color:#5b6270;font-variant-numeric:tabular-nums;white-space:nowrap}
 code{background:#eef1f4;padding:1px 5px;border-radius:4px;font-size:12px}
 footer{margin-top:22px;color:#5b6270;font-size:13px;line-height:1.8}
"""
        # ⚠ 别用 % 格式化拼 —— CSS 里的 width:100% 会撞 "unsupported format character"
        HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>扫过角度 · 方向实测</title>
<style>__CSS__</style></head><body>
<h1>扫过角度 · 方向实测</h1>
<p class="sub">同一个网格体、同一帧、同一套色标,只改空对象 <code>__CTRL__</code> 上的「扫过角度」。
判据 <code>gradX&divide;gradY</code>:&gt;1 条纹竖着(沿 U 变化),&lt;1 条纹横着(沿 V 变化),&asymp;1 斜条。</p>
<div class="grid">__CARDS__</div>
<footer>当前旋钮:__KNOBS__<br>
渲染:Cycles __RES__&times;__RES__ / __SAMPLES__ 采样,临时正交相机俯视(不留边距 ⇒ 像素与 Generated 一一对应);
渲完相机、分辨率、采样、帧、扫过角度均已还原。</footer>
</body></html>"""
        html = (HTML.replace("__CSS__", CSS).replace("__CARDS__", "\n".join(cards))
                .replace("__KNOBS__", knobs).replace("__CTRL__", CTRL_NAME)
                .replace("__RES__", str(RES)).replace("__SAMPLES__", str(SAMPLES)))
        hp = os.path.join(OUT_DIR, HTML_NAME)
        with open(hp, "w", encoding="utf-8") as f:
            f.write(html)
        print("  预览已写出: %s (%d 字节, %d 张图内嵌)" % (hp, len(html), len(cards)))
    except Exception as e:
        print("  生成预览失败(non-fatal): %r" % e)

print("FAIL_COUNT=%d" % len(fails))
for m in fails:
    print("   FAILED: %s" % m)
print("VERIFY_SWEEP_%s" % ("OK" if not fails else "FAILED"))
