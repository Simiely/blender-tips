# -*- coding: utf-8 -*-
"""独立核验：立体灯光_径向内收脉冲（另起请求；全新取引用）
重点：① 新材质结构/驱动全对 ② 「最多 3 条脉冲」用**现读的参数**独立复算
      ③ 旧材质 立体灯光_径向脉冲 与旧控制器**完全没被动过**
"""
import bpy
import math

D = bpy.data
C = bpy.context
scn = C.scene

COL_NAME = "立体灯光材质"
PLANES   = ["平面.001", "平面.002", "平面.003"]
MAT_NEW  = "立体灯光_径向内收脉冲"
CTRL_NEW = "立体灯光_内收控制"
MAT_OLD  = "立体灯光_径向脉冲"
CTRL_OLD = "立体灯光_脉冲控制"
CENTER   = (8.9724, 4.1455, 1.7079)
PROPS = ["脉冲间距", "脉冲宽度", "边缘柔和", "循环周期", "相位偏移", "发光强度",
         "底色亮度", "色相半径", "亮面半径", "淡出宽度"]
NODE_OF = {"脉冲间距": "内收_间距", "脉冲宽度": "内收_宽度", "边缘柔和": "内收_边缘",
           "循环周期": "内收_循环周期", "相位偏移": "内收_相位偏移",
           "发光强度": "内收_发光强度", "底色亮度": "内收_底色",
           "色相半径": "内收_色相半径",
           "亮面半径": "内收_亮面半径", "淡出宽度": "内收_淡出宽度"}
READONLY = "可见脉冲数"
MAX_BANDS = 3

ok, bad = [], []


def chk(c, m):
    (ok if c else bad).append(m)


def note(m):
    ok.append(m)


# ---------------------------------------------- 结构
col = D.collections.get(COL_NAME)
chk(col is not None, "集合 %s 存在" % COL_NAME)

ctl = D.objects.get(CTRL_NEW)
chk(ctl is not None, "新控制器 %s 存在" % CTRL_NEW)
if ctl:
    chk(tuple(round(x, 4) for x in ctl.location) == CENTER,
        "新控制器在圆心 %s（实际 %s）" % (CENTER, tuple(round(x, 4) for x in ctl.location)))
    chk(tuple(round(x, 6) for x in ctl.rotation_euler) == (0.0, 0.0, 0.0), "新控制器无旋转")
    chk(tuple(round(x, 6) for x in ctl.scale) == (1.0, 1.0, 1.0), "新控制器 scale=1")
    got = set(ctl.keys())
    chk(set(PROPS) | {READONLY} <= got, "属性齐全（实际 %s）" % sorted(got))
    chk(len([k for k in got if k.isascii()]) == 0,
        "无残留英文字母键（实际 %s）" % sorted(k for k in got if k.isascii()))

# 排查重复/游离的同类控制物体
stray = [o.name for o in D.objects
         if o.type == 'EMPTY' and ("内收" in o.name or "脉冲控制" in o.name)]
note("相关空物体 = %s" % sorted(stray))
chk(sorted(stray) == sorted([CTRL_NEW, CTRL_OLD]),
    "只有两个控制器，无重复（实际 %s）" % sorted(stray))

mat = D.materials.get(MAT_NEW)
chk(mat is not None, "新材质 %s 存在" % MAT_NEW)

if mat and ctl:
    nt = mat.node_tree
    chk(nt is not None, "新材质有节点树")
    chk(len(nt.nodes) == 39, "节点数 = 39（实际 %d）" % len(nt.nodes))
    chk(len(nt.links) == 48, "连线数 = 48（实际 %d）" % len(nt.links))
    for w in list(NODE_OF.values()) + ["内收_纹理坐标", "内收_映射", "内收_半径r",
                                       "内收_归一化r", "内收_帧号", "内收_相位推进",
                                       "内收_相位", "内收_相位叠加", "内收_周期取模",
                                       "内收_上升沿", "内收_下降沿", "内收_脉冲",
                                       "内收_色相归一", "内收_色相", "内收_外缘",
                                       "内收_掩码", "内收_裁切距离", "内收_裁切归一",
                                       "内收_裁切", "内收_掩码裁切", "内收_底色混合",
                                       "内收_自发光", "内收_底色亮度", "内收_发光主体", "材质输出"]:
        chk(w in [n.name for n in nt.nodes], "节点存在: %s" % w)

    tcs = [n for n in nt.nodes if n.type == 'TEX_COORD']
    chk(len(tcs) == 1, "TEX_COORD 节点 = 1（实际 %d）" % len(tcs))
    if tcs:
        chk(tcs[0].object is ctl, "纹理坐标.Object is 新控制器")
        # 上游链（按名字回溯，别比 RNA 对象身份）
        up = {}
        for l in nt.links:
            up[(l.to_node.name, l.to_socket.name)] = (l.from_node.name, l.from_socket.name)
        lens = [n for n in nt.nodes if n.type == 'VECT_MATH' and n.operation == 'LENGTH']
        chk(len(lens) == 1, "VectorMath/LENGTH = 1（实际 %d）" % len(lens))
        if lens:
            walk, seen = lens[0], []
            for _ in range(4):
                k = (walk.name, walk.inputs[0].name)
                if k not in up:
                    break
                fn, fs = up[k]
                seen.append("%s.%s" % (fn, fs))
                if fn == tcs[0].name and fs == 'Object':
                    break
                walk = nt.nodes[fn]
            chk(any(s == tcs[0].name + ".Object" for s in seen),
                "半径上游可追到 纹理坐标.Object（链 %s）" % " ← ".join(seen))

    lo = [n.name for n in nt.nodes if n.type in ('SEPARATE_XYZ', 'COMBINE_XYZ')]
    chk(not lo, "无 SeparateXYZ/CombineXYZ（真 3D 距离场）实际 %s" % lo)
    mrs = [n.name for n in nt.nodes if n.type == 'MAP_RANGE']
    chk(sorted(mrs) == ["内收_上升沿", "内收_下降沿", "内收_裁切"],
        "MapRange 恰为 上升沿/下降沿/裁切（实际 %s）" % mrs)

    # ★★ 配色链：颜色必须来自色相 ColorRamp，且色标与旧材质【逐项一致】
    ramps = [n for n in nt.nodes if n.type == 'VALTORGB']
    chk(len(ramps) == 2, "ColorRamp 恰 2 个（色相 + 外缘）实际 %d" % len(ramps))
    ec = [l for l in nt.links
          if l.to_node.name == "内收_发光主体" and l.to_socket.name == 'Emission Color']
    chk(bool(ec) and ec[0].from_node.name == "内收_色相",
        "Emission Color 来自「内收_色相」色带（实际 %s）"
        % ([l.from_node.name for l in ec] or "未连线"))
    new_ramps = {n.name: n for n in ramps}
    for rn_, kw in (("内收_色相", "色相"), ("内收_外缘", "外缘")):
        chk(rn_ in new_ramps, "ColorRamp 存在: %s（%s）" % (rn_, kw))
    # 与旧材质对拍
    oldm = D.materials.get(MAT_OLD)
    if oldm and oldm.node_tree:
        for src_name, new_name, kw in (("COL", "内收_色相", "色相"),
                                       ("RIM", "内收_外缘", "外缘轻收")):
            so = oldm.node_tree.nodes.get(src_name)
            sn = new_ramps.get(new_name)
            chk(so is not None and sn is not None, "对拍对象齐全: %s / %s" % (src_name, new_name))
            if so is not None and sn is not None:
                a = [(round(e.position, 4), tuple(round(c, 4) for c in e.color))
                     for e in so.color_ramp.elements]
                b = [(round(e.position, 4), tuple(round(c, 4) for c in e.color))
                     for e in sn.color_ramp.elements]
                chk(a == b, "★ %s 色标与旧材质 %s 逐项一致（旧 %d / 新 %d）"
                    % (kw, src_name, len(a), len(b)))
                chk(so.color_ramp.interpolation == sn.color_ramp.interpolation,
                    "%s 插值一致 = %s" % (kw, sn.color_ramp.interpolation))
    # 掩码 = 脉冲 × 外缘；★ 发光/底色必须取自【裁切后】的掩码
    mk = nt.nodes.get("内收_掩码")
    if mk is not None:
        srcs = sorted(l.from_node.name for l in nt.links if l.to_node == mk)
        chk(srcs == ["内收_外缘", "内收_脉冲"],
            "掩码 = 脉冲 × 外缘（实际 %s）" % srcs)
    mkc = nt.nodes.get("内收_掩码裁切")
    if mkc is not None:
        srcs = sorted(l.from_node.name for l in nt.links if l.to_node == mkc)
        chk(srcs == ["内收_掩码", "内收_裁切"],
            "掩码裁切 = 掩码 × 裁切（实际 %s）" % srcs)
    for tgt in ("内收_自发光", "内收_底色亮度"):
        n_ = nt.nodes.get(tgt)
        if n_ is not None:
            frm = [l.from_node.name for l in nt.links if l.to_node == n_]
            chk("内收_掩码裁切" in frm, "%s 取自【裁切后】掩码（实际入线 %s）" % (tgt, frm))
    # 亮面裁切参数
    gr = float(ctl["亮面半径"])
    gf = float(ctl["淡出宽度"])
    chk(gr > 0, "亮面半径 = %.4f（> 0，裁切生效）" % gr)
    chk(gf > 0, "淡出宽度 = %.4f" % gf)
    note("亮面裁切：r ≤ %.4f 全亮，到 %.4f 渐隐为全黑（角点 2.8491 落在裁切外）"
         % (gr, gr + gf))
    # 自发光强度与旧材质对齐
    oc = D.objects.get(CTRL_OLD)
    if oc is not None and "自发光强度" in oc.keys():
        note("旧材质 自发光强度 = %.3f | 新材质 发光强度 = %.3f"
             % (float(oc["自发光强度"]), float(ctl["发光强度"])))

    # 驱动
    dvs = list(nt.animation_data.drivers) if nt.animation_data else []
    chk(len(dvs) == 11, "材质驱动 = 11（实际 %d）" % len(dvs))
    inval = [d.data_path for d in dvs if not d.driver.is_valid]
    chk(not inval, "★ 全部驱动 is_valid=True（无效 %s）" % inval)
    # ★★ 守卫：所有材质驱动都必须挂在【Value 节点】输出上。
    #    挂在 Math/MapRange 这类「计算节点」的输出上 = 被节点运算覆盖 = 等于没写
    #    （本机就是这条没守：相位推进恒 0，用户拖时间轴画面完全静止）
    _bad = []
    for d in dvs:
        pth = d.data_path
        _nm = pth.split('"')[1] if '"' in pth else None
        _n = nt.nodes.get(_nm) if _nm else None
        if _n is None or _n.type != 'VALUE':
            _bad.append((pth, _n.type if _n else None))
    chk(not _bad, "★ 所有驱动都挂在 Value 节点输出上（挂错的：%s）" % _bad)

    # 帧号驱动：恰有 1 条，变量指向 SCENE.frame_current
    frd = []
    for d in dvs:
        for v in d.driver.variables:
            t0 = v.targets[0]
            if v.type == 'SINGLE_PROP' and t0.id_type == 'SCENE' \
               and t0.data_path == 'frame_current':
                frd.append(d)
    chk(len(frd) == 1, "恰有 1 条驱动读 SCENE.frame_current（实际 %d）" % len(frd))
    if frd:
        tgt = frd[0].data_path.split('"')[1]
        chk(tgt == "内收_帧号", "帧号驱动的目标节点 = 内收_帧号（实际 %s）" % tgt)

    cdrv = list(ctl.animation_data.drivers) if ctl.animation_data else []
    chk(len(cdrv) == 1, "控制器驱动 = 1（实际 %d）" % len(cdrv))
    if cdrv:
        chk(cdrv[0].driver.is_valid, "只读「可见脉冲数」驱动 is_valid=True")
        note("只读驱动表达式 = %r" % cdrv[0].driver.expression)

    # 指派：槽0 新 / 槽1 旧
    for pn in PLANES:
        ob = D.objects.get(pn)
        slots = [s.material.name if s.material else None for s in ob.material_slots]
        chk(slots[:2] == [MAT_NEW, MAT_OLD],
            "%s 槽 = [新, 旧]（实际 %s）" % (pn, slots))
        chk(sorted({p.material_index for p in ob.data.polygons}) == [0],
            "%s 面 index 全 0" % pn)

    # ------------------------------------------ 行为（读驱动直接写入的插槽）
    def touch():
        ctl.update_tag()
        mat.update_tag()
        mat.node_tree.update_tag()
        C.view_layer.update()

    def ev(nm):
        dg = C.evaluated_depsgraph_get()
        return mat.evaluated_get(dg).node_tree.nodes[nm].outputs[0].default_value

    ORIG = {k: ctl[k] for k in PROPS}
    PROBE = {"脉冲间距": 1.234, "脉冲宽度": 0.876, "边缘柔和": 0.111,
             "循环周期": 27.0, "相位偏移": 0.321, "发光强度": 4.4,
             "底色亮度": 0.6, "色相半径": 1.8, "亮面半径": 1.5, "淡出宽度": 0.22}
    for k, v in PROBE.items():
        ctl[k] = v
        touch()
        g = float(ev(NODE_OF[k]))
        chk(abs(g - v) < 1e-4, "%s=%s → %s = %.4f" % (k, v, NODE_OF[k], g))
    for k, v in ORIG.items():
        ctl[k] = v
    touch()
    chk(all(abs(float(ctl[k]) - float(v)) < 1e-9 for k, v in ORIG.items()), "7 个属性已还原")
    note("只读「可见脉冲数」= %.4f" % float(ctl[READONLY]))

    # ★ 帧号响应：拖时间轴有没有动态，全看这条链通不通
    _f0 = scn.frame_current
    for f in (330, 360, 400, 450):
        scn.frame_set(f)
        C.view_layer.update()
        gv = float(ev("内收_帧号"))
        chk(abs(gv - float(f)) < 1e-3,
            "★ 帧 %d → 内收_帧号 = %.3f（拖时间轴会动）" % (f, gv))
    scn.frame_set(int(_f0))
    C.view_layer.update()
    chk(int(scn.frame_current) == int(_f0), "帧已还原为 %d" % int(_f0))

    # ------------------------------------------ ★ 独立复算「最多 3 条」
    pts = []
    for pn in PLANES:
        ob = D.objects.get(pn)
        mw = ob.matrix_world
        pts += [mw @ v.co for v in ob.data.vertices]
    from mathutils import Vector
    ctr = Vector(CENTER)
    R_max = max((p - ctr).length for p in pts)
    # 内切圆半径 = 各面在自身平面内的最大半宽
    _spans = []
    for pn in PLANES:
        ob = D.objects.get(pn)
        mw = ob.matrix_world
        ps = [mw @ v.co for v in ob.data.vertices]
        _spans.append(max(max(p.x for p in ps) - min(p.x for p in ps),
                          max(p.y for p in ps) - min(p.y for p in ps),
                          max(p.z for p in ps) - min(p.z for p in ps)) / 2.0)
    R_REF = max(_spans)                # ★ 计数基准 = 内切圆（「看圆」）
    d_live = float(ctl["脉冲间距"])
    w_live = float(ctl["脉冲宽度"])
    e_live = float(ctl["边缘柔和"])
    duty = min(w_live / d_live, 1.0)
    eu_n = e_live / d_live
    FILTER_FRAC = 0.01          # 「看得见」的最小宽度（占周期），与构建脚本同一判据
    note("现读：R_ref(内切圆)=%.4f  R_max(角点)=%.4f  间距=%.4f 宽度=%.4f 边缘=%.4f"
         % (R_REF, R_max, d_live, w_live, e_live))
    note("duty=%.5f 软边=%.5f  暗区感知 = 纯黑 %.1f%% + 2×软边 %.1f%% = %.1f%%"
         % (duty, eu_n, 100 * (1 - duty), 100 * 2 * eu_n,
            100 * ((1 - duty) + 2 * eu_n)))
    for _lbl, _rr in (("内切圆（看圆）", R_REF), ("角点（看对角）", R_max)):
        _L = _rr / d_live
        note("%s：L=%.5f ⇒ 可见带窗口 = %.5f"
             % (_lbl, _L, _L + duty - eu_n - 2 * FILTER_FRAC))
    chk(R_REF / d_live + duty - eu_n - 2 * FILTER_FRAC <= MAX_BANDS + 1e-9,
        "以内切圆计的可见带窗口 ≤ %d（超过就会多出第 %d 条）" % (MAX_BANDS, MAX_BANDS + 1))
    chk(abs(float(ctl[READONLY]) - R_max / d_live) < 1e-6,
        "只读「可见脉冲数」= R_max/间距 = %.4f（实际 %.4f）"
        % (R_max / d_live, float(ctl[READONLY])))

    def band_of(t):
        up = min(1.0, max(0.0, t / eu_n)) if eu_n > 0 else 1.0
        dn = min(1.0, max(0.0, (duty - t) / eu_n)) if eu_n > 0 else 1.0
        return up * dn

    def scan_counts(r_hi, n_ph=600, n_s=4000):
        """在半径 [0, r_hi] 上扫相位 ⇒ (最小环数, 最大环数, 恰为 MAX_BANDS 的相位占比)"""
        st = r_hi / n_s
        w_, l_, ne = 0, 99, 0
        for k in range(n_ph):
            ph = k / n_ph
            prev = False
            runs, cur = [], 0
            for i in range(n_s + 1):
                r = r_hi * i / n_s
                t = math.fmod(r / d_live + ph, 1.0)
                if t < 0:
                    t += 1.0
                b = band_of(t) > 0.5
                if b:
                    cur += 1
                elif prev:
                    runs.append(cur)
                    cur = 0
                prev = b
            if cur:
                runs.append(cur)
            cnt = len([x for x in runs if x * st >= FILTER_FRAC * d_live])
            if cnt == MAX_BANDS:
                ne += 1
            w_ = max(w_, cnt)
            l_ = min(l_, cnt)
        return l_, w_, ne / float(n_ph)

    _c_l, _c_w, _c_f = scan_counts(R_REF)
    _k_l, _k_w, _k_f = scan_counts(R_max)
    chk(_c_w <= MAX_BANDS, "以内切圆计数：环数从不超过 %d（最大 %d）" % (MAX_BANDS, _c_w))
    chk(_c_f >= 0.99, "★ 以内切圆计数：环数【恒为】%d ⇒ 占 %.2f%%（最小 %d）"
        % (MAX_BANDS, 100 * _c_f, _c_l))
    note("内切圆 r≤%.4f（看圆）：最小 %d / 最大 %d；恰 %d 条占 %.2f%%"
         % (R_REF, _c_l, _c_w, MAX_BANDS, 100 * _c_f))
    note("到角点 r≤%.4f（看对角）：最小 %d / 最大 %d；恰 %d 条占 %.2f%%"
         % (R_max, _k_l, _k_w, MAX_BANDS, 100 * _k_f))

# ---------------------------------------------- 旧系统必须原封不动
old = D.materials.get(MAT_OLD)
chk(old is not None, "旧材质仍存在")
if old:
    chk(old.users == 31, "旧材质 users = 31（实际 %d）" % old.users)
    chk(len(old.node_tree.nodes) == 38, "旧材质节点数 = 38（实际 %d）" % len(old.node_tree.nodes))
    chk(len(old.node_tree.animation_data.drivers) == 9
        if old.node_tree.animation_data else False,
        "旧材质驱动仍为 9")
    chk(old.node_tree.nodes.get("TVAL") is not None, "旧材质 TVAL 仍在")
    chk(old.node_tree.nodes.get("内收_间距") is None, "旧材质未被混入新节点")
octl = D.objects.get(CTRL_OLD)
chk(octl is not None, "旧控制器仍存在")
if octl:
    chk(tuple(round(x, 4) for x in octl.location) == CENTER, "旧控制器位置未变")
    chk("扩散速度" not in octl.keys() and "循环周期" in ctl.keys(),
        "两个控制器的属性各自独立")

import collections as _c
cnt = _c.Counter(o.type for o in D.objects)
note("对象构成 = %s | 总计 %d" % (dict(cnt), len(D.objects)))
note("材质总数 = %d | 文本块 = %s" % (len(D.materials), [t.name for t in D.texts]))

print("=" * 60)
print("通过 %d 项 / 失败 %d 项" % (len(ok), len(bad)))
print("=" * 60)
if bad:
    print("!!! 失败项:")
    for b in bad:
        print("   x", b)
print()
print("--- 明细 ---")
for m in ok:
    print("  ok", m)
