# -*- coding: utf-8 -*-
# 合成器后期辉光(Glare)—— 非破坏性维护(经 9877 桥执行)
# ===========================================================================
# ★ 只动【驱动器】和【空对象上的旋钮 UI】。绝不新增/删除/改动任何节点、连线、Type/Quality。
#   随时可跑,跑完只会打印它做了什么(**0 处改动 = 本来就健康**)。
#   手调过 Type / Quality / Tint / Smoothness,或者改过参数默认值之后,
#   想"只修驱动/只对齐旋钮"就跑这个 —— 别去跑 build_glow.py(它会重建链条 / 恢复默认值)。
#
# 为什么需要它:
#   驱动器一旦被"改变量 / 改目标 / 改名字"弄坏,Blender 会把它留在 is_valid=False 的僵死状态
#   —— 数值冻结在旧值上,连强制求值都不刷新。只把字段"改对"救不回来,必须【原子重建】。
#   本脚本就是干这个的,并用【行为法】核对结果(改旋钮 → 强刷新 → 看插座值跟不跟)。
#
# ★★ 两个必须记住的事实:
#   1. 驱动挂在**合成器节点树**上时,脚本里读插座值必须手工 ng.update_tag() + 依赖图更新,
#      否则读到**陈旧值**(实测:属性 1.0→3.5,插座停在 1.0)。
#      但**渲染路径会自己求值**(全程不 tag,只改开关 1→0,两次渲染相差 120817/230400 分量)。
#   2. AnimData.drivers.new() 是**追加到末尾**、remove() 会让后续元素前移
#      ⇒「第 i 条驱动」索引永远不稳定,一律**按 data_path 匹配**。
import bpy

# ═══ 配置(换工程改这里) ═══
CTRL_NAME  = "辉光控制"
NODE_GLARE = "眩光"
GROUP_NAME = "后期辉光"
ADOPT_DRIVER_STATE = False   # True = 连 is_valid 也一起强制重建(默认只在规格不符时重建)
# ═════════════════════════

# (属性名, 目标插座, 硬min, 硬max, soft_min, soft_max, 变量名, 角色, 说明)
KNOBS = [
    ("辉光开关",   None,        0.0,   1.0, 0.0,   1.0,  "sw", "toggle", "1=开 / 0=关(强度乘 0,与不加合成器逐位相同)"),
    ("辉光强度",   "Strength",  0.0,   4.0, 0.0,   2.0,  "st", "mul",    "眩光强度(会乘辉光开关)"),
    ("辉光阈值",   "Threshold", 0.0,  50.0, 0.0,  20.0,  "th", "direct", "进入辉光的亮度阈值(线性,越高越挑剔)"),
    ("辉光尺寸",   "Size",      0.0,   1.0, 0.0,   1.0,  "sz", "direct", "辉光扩散尺寸(0-1 比例,5.x 是 Factor)"),
    ("辉光饱和度", "Saturation",0.0,   4.0, 0.0,   2.0,  "sa", "direct", "饱和度(1=原色,>1 更艳)"),
    ("辉光最大亮度","Maximum",  0.0, 500.0, 0.0, 100.0,  "mx", "direct", "单像素最大贡献(压过曝)"),
]
STEP, PRECISION = 0.01, 3

DIRECT_SOCK = [
    ("Type",       "可直接改:类型 6 选 1"),
    ("Quality",    "可直接改:Low/Med/High"),
    ("Tint",       "可直接改:辉光染色"),
    ("Smoothness", "可直接改:阈值过渡柔度"),
]
SOCK_DESC_LIMIT = 63   # 实测硬上限:中文 3 字节/字 ⇒ 约 21 字,超了静默截断

C, D = bpy.context, bpy.data
sc = C.scene
vl = C.view_layer

CHANGED = []
def chg(msg):
    CHANGED.append(msg)
    print("  * " + msg)

def unchanged(msg):
    print("  = " + msg)

print("=" * 70)
print("[0] 前置检查")
ng = getattr(sc, "compositing_node_group", None)
if ng is None:
    raise SystemExit("!! 场景没挂合成器节点组 —— 先跑 build_glow.py")
ctrl = D.objects.get(CTRL_NAME)
if ctrl is None:
    raise SystemExit("!! 找不到空对象 %r —— 先跑 build_glow.py" % CTRL_NAME)
n_gl = ng.nodes.get(NODE_GLARE)
if n_gl is None or n_gl.bl_idname != 'CompositorNodeGlare':
    raise SystemExit("!! 节点组里找不到眩光节点 %r —— 先跑 build_glow.py" % NODE_GLARE)
if ng.animation_data is None:
    ng.animation_data_create()
ad = ng.animation_data
print("  节点组=%r (%d 节点 / %d 连线)  眩光节点=%r  驱动=%d 条"
      % (ng.name, len(ng.nodes), len(ng.links), n_gl.name, len(ad.drivers)))
print("  ★ 本脚本不会动任何节点、连线、Type/Quality —— 只修驱动与旋钮 UI")

def force_refresh():
    ctrl.update_tag()
    ng.update_tag()
    sc.update_tag()
    C.evaluated_depsgraph_get().update()

# ================= 1. 旋钮:补齐 + 滑块化 =================
print("-" * 70)
print("[1] 旋钮与滑块 UI")
for prop, sock, hmn, hmx, smn, smx, var, role, desc in KNOBS:
    if prop not in ctrl.keys():
        ctrl[prop] = 0.0
        chg("%s 缺失,补为 0.0(值请自行调)" % prop)
    try:
        before = ctrl.id_properties_ui(prop).as_dict()
    except Exception:
        before = {}
    try:
        ctrl.id_properties_ui(prop).update(min=hmn, max=hmx, soft_min=smn, soft_max=smx,
                                           step=STEP, precision=PRECISION, description=desc)
        after = ctrl.id_properties_ui(prop).as_dict()
    except Exception as e:
        chg("%s 的 UI 设置失败: %r" % (prop, e))
        continue
    drift = []
    for k, want in (("min", hmn), ("max", hmx), ("soft_min", smn), ("soft_max", smx),
                    ("step", STEP)):
        got = after.get(k)
        if got is None or abs(float(got) - float(want)) > 1e-9:
            drift.append("%s %s->%s" % (k, got, want))
    if drift:
        chg("%s UI 对齐: %s" % (prop, "; ".join(drift)))
    else:
        unchanged("%-14s UI 已就位 (硬[%g~%g] 软[%g~%g] step=%g) = %.4f"
                  % (prop, hmn, hmx, smn, smx, STEP, float(ctrl[prop])))

# ================= 2. 驱动器(原子重建) =================
print("-" * 70)
print("[2] 驱动器")
spec_paths = {}
for prop, sock, hmn, hmx, smn, smx, var, role, desc in KNOBS:
    if sock is None:
        continue
    if sock not in n_gl.inputs:
        chg("!! 眩光节点没有 %r 插座,跳过它的驱动" % sock)
        continue
    spec_paths['nodes["%s"].inputs["%s"].default_value' % (NODE_GLARE, sock)] = (prop, sock, var, role)

def describe(d):
    """★ DriverVariable 本身没有 data_path/id —— 都在 v.targets[0] 上。
    读错了就永远判"规格不符"、每跑必重建(数值仍对,但幂等报告失效)。"""
    try:
        vs = []
        for v in d.driver.variables:
            tg = v.targets[0] if len(v.targets) else None
            vs.append((v.name, v.type,
                       (tg.id.name if tg is not None and tg.id else None),
                       (tg.data_path if tg is not None else None)))
    except Exception as e:
        vs = "读变量失败: %r" % (e,)
    return (d.driver.type, d.driver.expression, vs)

for d in ad.drivers:
    if d.data_path not in spec_paths:
        print("  ! 保留一条非本规格的驱动: %s" % d.data_path)

# 悬空驱动(id 已失效)先清掉 —— 那是节点重建后的残骸,留着只会报 is_valid=False
n_dead = 0
for d in list(ad.drivers):
    t, e, vs = describe(d)
    if isinstance(vs, str):
        continue
    if any(v[2] is None for v in vs):
        ad.drivers.remove(d)
        n_dead += 1
if n_dead:
    chg("清掉 %d 条悬空驱动(id 已失效)" % n_dead)

n_ok = 0
for path, (prop, sock, var, role) in sorted(spec_paths.items()):
    want_expr = "(sw * st)" if role == "mul" else var
    want_vars = [("sw", "辉光开关"), (var, prop)] if role == "mul" else [(var, prop)]
    want_sig = sorted((vn, 'SINGLE_PROP', CTRL_NAME, '["%s"]' % vp) for vn, vp in want_vars)

    existing = [d for d in ad.drivers if d.data_path == path]
    if len(existing) == 1 and not ADOPT_DRIVER_STATE:
        # ★ 用 existing[0],不要用别的分支残留的变量 d
        t, e, vs = describe(existing[0])
        vs_sig = sorted((v[0], v[1], v[2], v[3]) for v in vs) if isinstance(vs, list) else vs
        if t == 'SCRIPTED' and e == want_expr and vs_sig == want_sig:
            n_ok += 1
            unchanged("%-14s 已符合规格(不重建) expr=%r" % (sock, e))
            continue
        chg("%-14s 规格不符,原子重建 (旧: type=%s expr=%r vars=%s)" % (sock, t, e, vs))
        ad.drivers.remove(existing[0])
    elif len(existing) > 1:
        chg("%-14s 有 %d 条重复驱动,全删后重建" % (sock, len(existing)))
        for d in existing:
            ad.drivers.remove(d)
    elif len(existing) == 1:
        chg("%-14s ADOPT_DRIVER_STATE=True,强制重建" % sock)
        ad.drivers.remove(existing[0])

    d = ad.drivers.new(path)
    d.driver.type = 'SCRIPTED'
    for vn, vp in want_vars:
        v = d.driver.variables.new()
        v.name = vn
        v.type = 'SINGLE_PROP'
        tgt = v.targets[0]
        tgt.id_type = 'OBJECT'      # ★ 必须先 id_type 再 id
        tgt.id = ctrl
        tgt.data_path = '["%s"]' % vp
    d.driver.expression = want_expr
    chg("%-14s 新建驱动 expr=%r vars=%s" % (sock, want_expr, [v[0] for v in want_vars]))

print("  驱动总数 = %d(其中本规格 %d 条未改动)" % (len(ad.drivers), n_ok))

# ================= 3. 可发现性:节点标题 + 插座提示 =================
print("-" * 70)
print("[3] 可发现性标注(紫色插座 = 被驱动,不是锁死)")
want_label = "参数在空对象「%s」上" % CTRL_NAME
if n_gl.label != want_label:
    n_gl.label = want_label          # 只改 label,node.name 不变 ⇒ 驱动地址不受影响
    chg("眩光节点 label = %r" % want_label)
else:
    unchanged("眩光节点 label 已就位 = %r" % want_label)

n_tip = 0
for prop, sock, hmn, hmx, smn, smx, var, role, desc in KNOBS:
    if sock is None or sock not in n_gl.inputs:
        continue
    txt = "被驱动 →「%s」的%s" % (CTRL_NAME, prop)
    if len(txt.encode("utf-8")) > SOCK_DESC_LIMIT:
        chg("%s 的提示超 %d 字节,跳过" % (sock, SOCK_DESC_LIMIT))
        continue
    if n_gl.inputs[sock].description != txt:
        n_gl.inputs[sock].description = txt
        chg("%s 提示 <- %r" % (sock, txt))
    else:
        n_tip += 1
for sock, txt in DIRECT_SOCK:
    if sock not in n_gl.inputs:
        continue
    if len(txt.encode("utf-8")) > SOCK_DESC_LIMIT:
        continue
    if n_gl.inputs[sock].description != txt:
        n_gl.inputs[sock].description = txt
        chg("%s 提示 <- %r" % (sock, txt))
    else:
        n_tip += 1
print("  未改动的提示 = %d 条(上限 %d 字节)" % (n_tip, SOCK_DESC_LIMIT))

# ================= 4. 行为法验收(不看 is_valid,看插座跟不跟) =================
print("-" * 70)
print("[4] 行为法验收:改旋钮 → 强刷新 → 看插座(★ 不 tag 会读到陈旧值)")
FAIL = []
def read_sock(sock_name):
    force_refresh()
    return float(n_gl.inputs[sock_name].default_value)

for prop, sock, hmn, hmx, smn, smx, var, role, desc in KNOBS:
    if sock is None:
        continue
    orig = float(ctrl[prop])
    # 挑一个与原值不同的探针值,且留在硬范围内(优先取中间值,避免 0 这种弱探针)
    cands = [(hmn + hmx) / 2.0, hmn, hmx]
    probe = next((c for c in cands if abs(c - orig) > 1e-6), hmx)
    ctrl[prop] = probe
    got = read_sock(sock)
    ctrl[prop] = orig
    back = read_sock(sock)
    if role == "mul":
        sw = float(ctrl["辉光开关"])
        expect = probe * sw
        ok = abs(got - expect) < 1e-5
        note = "(=%s × 开关 %s)" % (probe, sw)
    else:
        ok = abs(got - probe) < 1e-5
        note = ""
    ok_back = abs(back - orig * (float(ctrl["辉光开关"]) if role == "mul" else 1.0)) < 1e-5
    print("  %-14s 属性 %s->%s 时插座=%.6f %s ; 还原后=%.6f"
          % (sock, orig, probe, got, note, back))
    if not ok:
        FAIL.append("%s 驱动不跟随(期望 %s)" % (sock, probe if role != "mul" else probe * float(ctrl["辉光开关"])))
    if not ok_back:
        FAIL.append("%s 还原失败" % sock)

# 开关=0 必须把强度乘成 0
sw_orig, st_orig = float(ctrl["辉光开关"]), float(ctrl["辉光强度"])
if "Strength" in [s[1] for s in KNOBS if s[1]]:
    ctrl["辉光开关"] = 0.0
    z = read_sock("Strength")
    ctrl["辉光开关"] = sw_orig
    read_sock("Strength")
    print("  开关=0 时 Strength = %.6f (必须 0)" % z)
    if abs(z) > 1e-6:
        FAIL.append("辉光开关=0 时强度没归零")

print("=" * 70)
print("CHANGED=%d" % len(CHANGED))
for m in CHANGED:
    print("   * %s" % m)
print("行为验收 FAIL=%d %s" % (len(FAIL), FAIL if FAIL else ""))
print("MAINTAIN_GLOW_OK" if not FAIL else "MAINTAIN_GLOW_FAILED")
print("★ 改动只在内存 —— 记得回 Blender 按 Ctrl+S")
