# -*- coding: utf-8 -*-
# 合成器后期辉光(Glare)—— 独立核验:可证伪的像素读数(经 9877 桥执行)
# ===========================================================================
# 三层,共 8 项断言。**先自证工具可靠,再证效果成立**:
#   [0] 自证防护 —— 同一设置渲两次是否逐位相同(不成立的话后面所有像素比对都不作数)
#   [1] 旁路等价 —— 「辉光开关=0」与「完全不加合成器」是否相等
#   [2] 真的出光晕了吗 —— 像素数 / 只加不减
#   [3] 光晕的物理签名 —— 增益是否落在暗部(不是整体提亮)
#   [4] 三个旋钮单调性
# 7 个旋钮值在 finally 里逐个还原;渲染设置(分辨率/采样/降噪/持久化/合成器树/输出路径)同样还原。
#
# ★★ 判据陷阱(实测踩过,务必读):本工程(prescan 里对象数上万的 CAD 场景)的 Cycles
#    **不是逐位确定的** —— 同设置连渲 5 次,差异恒定落在**同一个像素**上、幅度恰好 1/255
#    (实测 y=212,x=255,蓝通道,在 126/255 ⇄ 127/255 间跳)⇒ 真实浮点值正压在
#    **8bit 量化台阶的中点**上。所以 [0] 的"逐位相同"在这类场景会**假报失败**。
#    修法二选一:① 改渲 32 位浮点 EXR 再比;② 把容差放到「≤1/255 且差异分量数极少」。
#    切记:**先怀疑度量,再怀疑被测对象。**
#
# 本脚本只改内存(且全部还原),不存盘。
import bpy, os, time

def P(*a):
    print(*a)

# ═══ 配置(换工程改这里) ═══
CTRL_NAME = "辉光控制"
KNOB_NAMES = ("辉光开关", "辉光强度", "辉光阈值", "辉光尺寸", "辉光饱和度", "辉光最大亮度")
OUT       = "D:/workbuddy/glow_out/v"   # 出图目录(报告的中间产物,可随意改)
VW, VH    = 400, 225                    # 核验分辨率(小一点快)
SAMPLES   = 12

# [0] 自证防护的判据(工具自检:要求严格逐位相同)
# ★ 有些工程(尤其对象上万、含大量高光的 CAD 场景)的 Cycles 不是逐位确定的:
#   差异会恒定落在同一个像素上、幅度恰好 1/255 ⇒ 真实浮点值压在 8bit 量化台阶中点。
#   这时把 DET_MAX_DIFF 设为 1.0/255、DET_MAX_CNT 设为个位数(如 8),判据才反映实际。
#   **但请先看 [0] 的自动诊断再改** —— 诊断会打印差异像素坐标、8bit 台阶数、两侧中点,
#   是"量化台阶"(台阶数≈1 且中点≈x.5/255)还是"真不确定",一眼可辨。
#   **先怀疑度量,再怀疑被测对象。**
DET_MAX_DIFF = 0.0
DET_MAX_CNT  = 0

# [1] 旁路等价的判据(物理结论:允许一个 8bit 量化步)
#   「辉光开关=0」与「完全不加合成器」在数学上必须等价;但若渲染输出是 8bit,
#   落点压在量化台阶上的像素会抖动 1 个 LSB —— 那仍然是**同一张图**。
#   所以这里默认给 1 LSB 容差 + 极少分量数;想抓"管线真的不等价"这类硬错误,
#   这点容差完全不影响(真不等价会让成千上万个分量一起变)。
EQ_MAX_DIFF = 1.0 / 255.0 + 1e-12
EQ_MAX_CNT  = 8
# ═════════════════════════

os.makedirs(OUT, exist_ok=True)
C = bpy.context
sc = C.scene
r = sc.render
ng = sc.compositing_node_group
ctrl = bpy.data.objects[CTRL_NAME]
assert ng is not None and ng.bl_idname == 'CompositorNodeTree', "场景没挂合成器节点组"

FAIL = []
def check(cond, msg):
    P("  [%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        FAIL.append(msg)

def force_refresh():
    ctrl.update_tag(); ng.update_tag(); sc.update_tag()
    C.evaluated_depsgraph_get().update()

def set_knobs(**kw):
    for k, v in kw.items():
        ctrl[k] = float(v)
    force_refresh()

def load(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = img.pixels[:]
    bpy.data.images.remove(img)
    return w, h, px

def lum_of(px):
    return [0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2]
            for i in range(0, len(px), 4)]

sav = dict(rx=r.resolution_x, ry=r.resolution_y, rp=r.resolution_percentage,
           fp=r.filepath, samples=sc.cycles.samples,
           denoise=sc.cycles.use_denoising, adaptive=sc.cycles.use_adaptive_sampling,
           persist=r.use_persistent_data)
sav_props = {k: float(ctrl[k]) for k in KNOB_NAMES}

shots = {}
try:
    r.resolution_x, r.resolution_y, r.resolution_percentage = VW, VH, 100
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = False
    sc.cycles.use_adaptive_sampling = False
    r.use_persistent_data = False

    def shot(tag, comp=True, **knobs):
        if knobs:
            set_knobs(**knobs)
        sc.compositing_node_group = ng if comp else None
        force_refresh()
        r.filepath = "%s/%s.png" % (OUT, tag)
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        shots[tag] = load(r.filepath)
        P("    %-10s %.2fs" % (tag, time.time() - t0))

    P("=" * 70)
    P("[出图] %dx%d @ %d samples,无降噪/无自适应/无持久化(排除缓存)" % (VW, VH, SAMPLES))
    base_knobs = dict(辉光开关=1.0, 辉光强度=1.0, 辉光阈值=1.0,
                      辉光尺寸=0.5, 辉光饱和度=1.0, 辉光最大亮度=10.0)
    shot("A1_nocomp", comp=False, **base_knobs)
    shot("A2_nocomp", comp=False)
    shot("B_off", comp=True, 辉光开关=0.0)
    shot("C_on", comp=True, 辉光开关=1.0)
    shot("D_big", comp=True, 辉光尺寸=1.0)
    shot("E_thr", comp=True, 辉光尺寸=0.5, 辉光阈值=5.0)
    shot("F_half", comp=True, 辉光阈值=1.0, 辉光强度=0.5)

    P("=" * 70)
    P("[0] 自证防护:Cycles 自身确定性")
    w, h, p1 = shots["A1_nocomp"]; _, _, p2 = shots["A2_nocomp"]
    n = min(len(p1), len(p2))
    md = max(abs(p1[i] - p2[i]) for i in range(n))
    cnt = sum(1 for i in range(n) if abs(p1[i] - p2[i]) > 1e-6)
    P("    A1 vs A2 (同设置两次): max=%.8f 差异分量=%d/%d" % (md, cnt, n))
    ok_det = (md <= DET_MAX_DIFF + 1e-12) and (cnt <= DET_MAX_CNT)
    check(ok_det, "Cycles 同设置重复渲染逐位相同(否则后面所有比对都不成立)")
    if md > 1e-6:
        # ★ 自动诊断:差异落在哪?是不是压在 8bit 量化台阶的中点?
        worst = max(range(n), key=lambda i: abs(p1[i] - p2[i]))
        pix, ch = worst // 4, worst % 4
        P("    ── 差异诊断 ──")
        P("    最大差异在 分量 k=%d(像素 %d,通道 %d,y=%d x=%d): A1=%.8f A2=%.8f"
          % (worst, pix, ch, pix // w, pix % w, p1[worst], p2[worst]))
        q = abs(p1[worst] - p2[worst]) * 255.0
        P("    差值的 8bit 台阶数 = %.6f  (≈1.000 就是整整一个量化步)" % q)
        lo, hi = min(p1[worst], p2[worst]), max(p1[worst], p2[worst])
        mid = (lo + hi) / 2.0
        P("    两侧中点 = %.8f  (= %.4f/255)" % (mid, mid * 255.0))
        P("    ⇒ 若台阶数≈1 且差异分量极少,是**真实浮点值压在量化台阶中点**,")
        P("      不是渲染不确定。把 DET_MAX_DIFF 设 1.0/255、DET_MAX_CNT 设个位数即可;")
        P("      想要更硬的证据,就把渲染格式改成 32 位浮点 EXR 再比。")

    L = {k: lum_of(v[2]) for k, v in shots.items()}
    NPIX = len(L["A1_nocomp"])
    srt = sorted(L["A1_nocomp"])
    med = srt[NPIX // 2]
    p99 = srt[int(NPIX * 0.99)]
    P("    基准亮度: 中位=%.4f 99%%=%.4f 最大=%.4f" % (med, p99, srt[-1]))

    P("-" * 70)
    P("[1] 旁路 = 无合成器? (强度=0 必须是真旁路)")
    mx = mn = 0.0; cnt = 0
    for i in range(n):
        d = abs(shots["B_off"][2][i] - p1[i])
        if d > mx: mx = d
        if d > 1e-6: cnt += 1
    P("    B_off vs A1_nocomp: max=%.8f 差异分量=%d/%d" % (mx, cnt, n))
    check(mx <= EQ_MAX_DIFF and cnt <= EQ_MAX_CNT,
          "「辉光开关=0」与「完全不加合成器」等价(容差 = 1 个 8bit 量化步 / %d 个分量)"
          % EQ_MAX_CNT)
    if mx > 0.0:
        P("    ⇒ 差异 %.8f = %.4f 个 8bit 台阶、%d 个分量;判据给的是 1 台阶 ×%d 分量"
          % (mx, mx * 255.0, cnt, EQ_MAX_CNT))
        P("      (真「管线不等价」会让**成千上万**个分量一起变,这点容差抓不住它才有问题)")

    P("-" * 70)
    P("[2] 默认档真的出辉光了吗? (C vs B)")
    gC = [L["C_on"][i] - L["B_off"][i] for i in range(NPIX)]
    gain_all = sum(x for x in gC if x > 0)
    cnt_gain = sum(1 for x in gC if x > 0.02)
    neg = min(gC)
    P("    总增益=%.3f  增益>0.02 的像素=%d/%d (%.2f%%)  最大变暗=%.5f" % (
        gain_all, cnt_gain, NPIX, 100.0 * cnt_gain / NPIX, neg))
    check(cnt_gain > 500, "辉光影响了足够多的像素(>500 个增益 >0.02)")
    check(neg > -0.02, "辉光只加不减(没有像素被明显压暗)")

    P("-" * 70)
    P("[3] 是「光晕铺到暗部」还是「整体变亮」? —— 辉光的物理签名")
    dark = [i for i in range(NPIX) if L["B_off"][i] <= med]
    hi = [i for i in range(NPIX) if L["B_off"][i] >= p99]
    gd = sum(gC[i] for i in dark if gC[i] > 0)
    gh = sum(gC[i] for i in hi if gC[i] > 0)
    md_dark = max(gC[i] for i in dark)
    share = gd / gain_all if gain_all else 0.0
    P("    暗半区(<=中位)像素 %d 个、增益合计=%.3f、最大单点增益=%.4f" % (len(dark), gd, md_dark))
    P("    最亮 1%% 像素 %d 个、增益合计=%.3f" % (len(hi), gh))
    P("    暗部占总增益 = %.1f%%" % (100.0 * share))
    check(share > 0.10, "暗部拿到了可观份额的增益(>10%) ⇒ 是光晕不是整体提亮")
    check(md_dark > 0.02, "至少有一个暗部像素被提亮 >0.02 ⇒ 光晕确实溢出到高光之外")
    check(gh > 0.0, "高光本身也被加强(不是把高光搬走)")

    P("-" * 70)
    P("[4] 旋钮单调性")
    def gain_vs_B(tag):
        g = [L[tag][i] - L["B_off"][i] for i in range(NPIX)]
        return sum(x for x in g if x > 0), sum(g[i] for i in dark if g[i] > 0)
    tot_C, dark_C = gain_vs_B("C_on")
    tot_D, dark_D = gain_vs_B("D_big")
    tot_E, dark_E = gain_vs_B("E_thr")
    tot_F, dark_F = gain_vs_B("F_half")
    P("    尺寸 0.5 -> 1.0 : 总增益 %.3f -> %.3f ; 暗部增益 %.3f -> %.3f" % (
        tot_C, tot_D, dark_C, dark_D))
    P("    阈值 1.0 -> 5.0 : 总增益 %.3f -> %.3f" % (tot_C, tot_E))
    P("    强度 1.0 -> 0.5 : 总增益 %.3f -> %.3f" % (tot_C, tot_F))
    check(dark_D > dark_C, "「辉光尺寸」调大 ⇒ 暗部光晕更多(0.5->1.0)")
    check(tot_E < tot_C, "「辉光阈值」调高 ⇒ 辉光变少(1.0->5.0)")
    check(tot_F < tot_C, "「辉光强度」调低 ⇒ 辉光变少(1.0->0.5)")

    P("=" * 70)
    P("FAIL_COUNT=%d" % len(FAIL))
    for m in FAIL:
        P("   FAIL: %s" % m)
    P("VERIFY_GLOW_OK" if not FAIL else "VERIFY_GLOW_FAILED")
finally:
    sc.compositing_node_group = ng
    r.resolution_x, r.resolution_y, r.resolution_percentage = sav['rx'], sav['ry'], sav['rp']
    r.filepath = sav['fp']
    sc.cycles.samples = sav['samples']
    sc.cycles.use_denoising = sav['denoise']
    sc.cycles.use_adaptive_sampling = sav['adaptive']
    r.use_persistent_data = sav['persist']
    for k, v in sav_props.items():
        ctrl[k] = v
    force_refresh()
    P("已还原: %dx%d @%d%% samples=%d denoise=%s persist=%s | comp=%s | 旋钮=%s" % (
        r.resolution_x, r.resolution_y, r.resolution_percentage, sc.cycles.samples,
        sc.cycles.use_denoising, r.use_persistent_data,
        sc.compositing_node_group.name, {k: float(ctrl[k]) for k in sav_props}))
