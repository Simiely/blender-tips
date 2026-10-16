# -*- coding: utf-8 -*-
# 渐变扫过材质 · 坐标源是不是真的吃 UV —— 决定性核验(经 9877 桥执行)
# ===========================================================================
# 为什么需要这个脚本:
#   把 分离_XY.Vector 的来源从 坐标_纹理.Generated 换成 坐标_纹理.UV 之后,
#   结构断言只能证明"线接在 UV 插座上",证明不了"求值真的走了 UV"。
#   而对这个平面来说 Generated 与 UV 的数值恰好都不难看,渲染读数还可能撞上。
#
# ★★ 决定性判据(能失败的):临时把 UV 层每个点的 (u,v) 互换再渲染。
#     Generated 是「按物体包围盒归一化的局部坐标」——**完全不看 UV**,
#     所以 UV 怎么改它都纹丝不动。若图案的朝向真的跟着翻 90°,就证明确实读 UV。
#     测完**逐点还原**并断言与原值逐位相同,再渲一次确认读数回到原样(证明还原干净)。
#
# A. 结构:分离_XY.Vector 恰好 1 条入线,且来自 坐标_纹理.UV;Generated 必须已断开
# B. 行为:原始 UV → 渲 0°(应竖条) / u,v 互换 → 渲 0°(应横条) / 还原 → 渲 0°(应回竖条)
# 临时相机 / 分辨率 / 采样 / 帧 / 扫过角度 / UV 坐标 全部还原。
# 失败只打印不抛异常(桥会吞掉异常前的输出)。
# ===========================================================================
import bpy, os, math, base64

# ═══ 配置(换工程改这里) ═══
PLANE = "平面"
MAT_NAME = "渐变扫过材质"
CTRL_NAME = "渐变控制"
OUT_DIR = "D:/workbuddy/blender_tips_out"
RES = 192                        # 本脚本渲 3 张,用小一点更稳(桥有 120s 硬超时)
SAMPLES = 8
THETA = 0.0                      # 只在 0° 测:此时 t ≡ u,竖条方向最灵敏
HTML_NAME = "UV坐标源_核验.html"
# ═════════════════════════

C, D, sc = bpy.context, bpy.data, bpy.context.scene
os.makedirs(OUT_DIR, exist_ok=True)
ob = D.objects[PLANE]
mat = D.materials[MAT_NAME]
ctrl = D.objects[CTRL_NAME]
nt = mat.node_tree
me = ob.data
fails = []


def chk(cond, msg):
    print(("  [PASS] " if cond else "  [FAIL] ") + msg)
    if not cond:
        fails.append(msg)


def force_refresh():
    ob.update_tag()
    nt.update_tag()
    ctrl.update_tag()
    C.evaluated_depsgraph_get().update()


# ---------------------------------------------------------------- UV 读写(5.x 两套 API 都试)
def get_uv():
    l = me.uv_layers.active
    try:
        return [tuple(d.uv) for d in l.data]
    except AttributeError:
        return [tuple(d.vector) for d in l.uv]


def set_uv(vals):
    l = me.uv_layers.active
    try:
        for d, uv in zip(l.data, vals):
            d.uv = uv
    except AttributeError:
        for d, uv in zip(l.uv, vals):
            d.vector = uv
    me.update()
    force_refresh()


print("RECHECK 目标=%r 材质=%r NODES=%d LINKS=%d  帧=%d"
      % (ob.name, mat.name, len(nt.nodes), len(nt.links), sc.frame_current))

# ---------------- A. 结构 ----------------
print("--- A. 结构(线接在哪个插座上) ---")
ins = [l for l in nt.links if l.to_node.name == "分离_XY" and l.to_socket.name == "Vector"]
chk(len(ins) == 1, "分离_XY.Vector 恰好 1 条入线(实际 %d)" % len(ins))
src = (ins[0].from_node.name, ins[0].from_socket.name) if ins else (None, None)
print("  当前入线来源 = %s.%s" % src)
chk(src == ("坐标_纹理", "UV"), "入线来自 坐标_纹理.UV")
chk(not any(l.from_node.name == "坐标_纹理" and l.from_socket.name == "Generated"
            for l in nt.links), "★ 坐标_纹理.Generated 已断开(不能两处都接)")
chk(len(me.uv_layers) >= 1, "网格体有 UV 层:%r(active=%r)"
    % ([l.name for l in me.uv_layers],
       me.uv_layers.active.name if me.uv_layers.active else None))
uv0 = get_uv()
us = [p[0] for p in uv0]; vs = [p[1] for p in uv0]
print("  UV 逐点 %d 个:u %.4f~%.4f  v %.4f~%.4f" % (len(uv0), min(us), max(us), min(vs), max(vs)))
A0 = float(ctrl["扫过角度"])

# ---------------------------------------------------------------- 渲染脚手架
mw = ob.matrix_world
pts = [mw @ v.co for v in me.vertices]
xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
W, H = max(xs) - min(xs), max(ys) - min(ys)
cx, cy = (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0

snap = dict(rx=sc.render.resolution_x, ry=sc.render.resolution_y, rp=sc.render.resolution_percentage,
            fp=sc.render.filepath, fmt=sc.render.image_settings.file_format, cam=sc.camera,
            fr=sc.frame_current, samples=getattr(sc.cycles, "samples", None),
            den=getattr(sc.cycles, "use_denoising", None))
cam_data = D.cameras.new("__tmp_uv_cam__")
cam = D.objects.new("__tmp_uv_cam__", cam_data)
sc.collection.objects.link(cam)
cam_data.type = 'ORTHO'
cam_data.ortho_scale = max(W, H)          # 不留边距 ⇒ 像素 (x,y) 与 UV 一一对应
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


def grads(pix, w, h):
    """平均绝对梯度:横向 gradX / 纵向 gradY。>1 = 竖条,<1 = 横条,≈1 = 斜条"""
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


def shoot(tag):
    ctrl["扫过角度"] = float(THETA)
    force_refresh()
    path = "%s/uvsrc_%s.png" % (OUT_DIR, tag)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = D.images.load(path, check_existing=False)
    w, h = img.size
    pix = tuple(img.pixels[:])
    D.images.remove(img)
    gx, gy = grads(pix, w, h)
    print("  %-10s %dx%d gradX=%.5f gradY=%.5f  比值=%7.3f" % (tag, w, h, gx, gy, gx / max(gy, 1e-9)))
    return dict(path=path, w=w, h=h, gx=gx, gy=gy, ratio=gx / max(gy, 1e-9))


# ---------------- B. 行为:UV 一改,图案必须跟着变 ----------------
print("--- B. 行为:临时互换 UV 的 (u,v)(Generated 不受此影响) ---")
shots = {}
restored_ok = False
try:
    shots["原始UV"] = shoot("orig")
    r0 = shots["原始UV"]["ratio"]

    set_uv([(v, u) for (u, v) in uv0])
    back = get_uv()
    chk(max(abs(a - b) for p, q in zip(back, [(v, u) for (u, v) in uv0])
            for a, b in zip(p, q)) < 1e-6,
        "UV 互换已写入(逐点比对)")
    shots["UV互换"] = shoot("swap")
    r1 = shots["UV互换"]["ratio"]

    set_uv(uv0)                                     # 逐点还原
    back = get_uv()
    maxd = max(abs(a - b) for p, q in zip(back, uv0) for a, b in zip(p, q))
    chk(maxd == 0.0, "★ UV 坐标已逐点还原(最大偏差 %.1e,必须 0)" % maxd)
    restored_ok = (maxd == 0.0)
    shots["还原后"] = shoot("back")
    r2 = shots["还原后"]["ratio"]

    print("  三个比值:%s=%.3f  %s=%.3f  %s=%.3f"
          % ("原始UV", r0, "UV互换", r1, "还原后", r2))
    chk(r0 > 1.5, "原始 UV 下 0° 是竖条(%.2f > 1.5)⇒ 沿 U 变化" % r0)
    chk(r1 < 0.67, "★ 互换 UV 后 0° 变横条(%.2f < 0.67)⇒ 图案确实由 UV 驱动(Generated 不受 UV 改动影响)" % r1)
    chk(r0 / max(r1, 1e-9) > 10, "★ 方向翻转幅度 %.0f 倍(不是靠噪声蒙的)" % (r0 / max(r1, 1e-9)))
    chk(abs(r2 - r0) / r0 < 0.02, "★ 还原后读数回到原样(%.3f vs %.3f,偏差 %.2f%%)⇒ 还原干净"
        % (r2, r0, abs(r2 - r0) / r0 * 100))
finally:
    if not restored_ok:
        set_uv(uv0)                                 # 兜底还原
        print("  (兜底:UV 已再次还原)")
    ctrl["扫过角度"] = A0
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
    print("  (临时相机 / 分辨率 / 采样 / 帧 / 扫过角度已还原)")

# ---------------- 预览 HTML ----------------
try:
    def b64(p):
        return base64.b64encode(open(p, "rb").read()).decode("ascii")

    CAP = [("原始UV", "当前 UV 层 —— 0° 沿 +U,竖条"),
           ("UV互换", "★ 临时把 UV 的 (u,v) 互换 —— 竖条变横条 ⇒ 图案由 UV 驱动"),
           ("还原后", "UV 逐点还原 —— 读数回到原样")]
    cards = []
    for tag, desc in CAP:
        s = shots.get(tag)
        if not s:
            continue
        cards.append('<figure><img src="data:image/png;base64,' + b64(s["path"])
                     + '" alt="' + tag + '"><figcaption><b>' + tag
                     + '</b><span>gradX&divide;gradY = ' + ("%.3f" % s["ratio"])
                     + '</span></figcaption><p>' + desc + '</p></figure>')
    CSS = """
 body{margin:0;padding:28px 32px;background:#f6f7f9;color:#1a1c1f;
      font:15px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
 h1{font-size:20px;margin:0 0 6px}
 p.sub{margin:0 0 22px;color:#5b6270;font-size:13px}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px}
 figure{margin:0;background:#fff;border:1px solid #e3e6ea;border-radius:10px;overflow:hidden;
        box-shadow:0 1px 3px rgba(16,24,40,.06)}
 img{display:block;width:100%;image-rendering:pixelated;background:#111}
 figcaption{padding:10px 12px 4px;font-size:13px;display:flex;justify-content:space-between;
            gap:8px;align-items:baseline}
 figcaption span{color:#5b6270;font-variant-numeric:tabular-nums;white-space:nowrap}
 figure p{margin:0;padding:0 12px 12px;color:#5b6270;font-size:12px;line-height:1.5}
 code{background:#eef1f4;padding:1px 5px;border-radius:4px;font-size:12px}
 footer{margin-top:22px;color:#5b6270;font-size:13px;line-height:1.8}
"""
    HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>坐标源核验 —— 材质到底吃不吃 UV</title>
<style>__CSS__</style></head><body>
<h1>坐标源核验 —— 材质到底吃不吃 UV</h1>
<p class="sub">判据 <code>gradX&divide;gradY</code>:&gt;1 条纹竖着(沿 U 变化),&lt;1 条纹横着(沿 V 变化)。
<code>坐标_纹理.Generated</code> 是按物体**包围盒**归一化的局部坐标,<b>完全不看 UV</b>;
所以只要「互换 UV 的 u/v」能让条纹翻转 90°,就证明确实读的是 <code>坐标_纹理.UV</code>。</p>
<div class="grid">__CARDS__</div>
<footer>材质 <code>__MAT__</code> · 目标网格体 <code>__OBJ__</code> · UV 层 <code>__UVL__</code><br>
渲:Cycles __RES__&times;__RES__ / __SAMPLES__ 采样,临时正交相机俯视(不留边距 ⇒ 像素与 UV 一一对应);
渲完相机 / 分辨率 / 采样 / 帧 / 扫过角度 / UV 坐标均已还原。</footer>
</body></html>"""
    html = (HTML.replace("__CSS__", CSS).replace("__CARDS__", "\n".join(cards))
            .replace("__MAT__", MAT_NAME).replace("__OBJ__", PLANE)
            .replace("__UVL__", (me.uv_layers.active.name if me.uv_layers.active else "-"))
            .replace("__RES__", str(RES)).replace("__SAMPLES__", str(SAMPLES)))
    hp = os.path.join(OUT_DIR, HTML_NAME)
    with open(hp, "w", encoding="utf-8") as f:
        f.write(html)
    print("  预览已写出: %s (%d 字节)" % (hp, len(html)))
except Exception as e:
    print("  生成预览失败(non-fatal): %r" % e)

print("FAIL_COUNT=%d" % len(fails))
for m in fails:
    print("   FAILED: %s" % m)
print("VERIFY_UVSRC_%s" % ("OK" if not fails else "FAILED"))
