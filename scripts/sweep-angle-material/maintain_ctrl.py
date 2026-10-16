# -*- coding: utf-8 -*-
# 渐变扫过材质 · UV 方向角 —— 非破坏性维护(经 9877 桥执行)
# ===========================================================================
# ★ 只动【驱动器】和【空对象上的旋钮】。绝不新增/删除/改动任何节点、连线、色标。
#   随时可跑,跑完只会打印它做了什么(0 处改动 = 本来就健康)。
#   改过色标之后想"只修驱动/旋钮"就跑这个,别去跑 build_sweep_angle.py(它会重建节点树)。
#
# 为什么需要它:
#   驱动器一旦被"改变量/改目标/改名字"弄坏,Blender 会把它留在 is_valid=False 的僵死状态
#   —— 数值冻结在旧值上,连强制求值都不刷新。只把字段"改对"是救不回来的,必须【原子重建】。
#   本脚本就是干这个的,并且用【行为法】核对结果(改旋钮 → 强刷新 → 看插座值跟不跟)。
# ===========================================================================
import bpy, math

# ═══ 配置(换工程改这里) ═══
PLANE = "平面"
MAT_NAME = "渐变扫过材质"
CTRL_NAME = "渐变控制"
CLEAN_TARGET_LEFTOVERS = False   # True = 顺手删掉目标网格体上的同名残留属性(避免两个真相源)
# ═════════════════════════

C, D, sc = bpy.context, bpy.data, bpy.context.scene
FPS = float(sc.render.fps)
_K = "(abs(cos(radians(ang))) + abs(sin(radians(ang))))"

KNOBS = [
    ("扫过速度", 0.2, dict(min=0.0, soft_max=5.0,
        description="扫过速度(周期/秒)。0 = 静止;负值 = 反向")),
    ("扫过角度", 0.0, dict(min=0.0, soft_min=0.0, soft_max=360.0,
        description="扫过方向(UV 平面角度,单位度)。0° = 沿 +U(即原来的 1);"
                    "90° = 沿 +V;180° = 反向;任意中间角 = 斜扫")),
    ("扫过条数", 1.0, dict(min=1.0, soft_max=20.0,
        description="扫过方向上同时存在的渐变条数")),
    ("水平条数", 1.0, dict(min=1.0, soft_max=20.0,
        description="静态水平渐变(沿 V)的条数;水平层全白时无影响")),
    ("发光强度", 2.0, dict(min=0.0, soft_max=20.0,
        description="合成后的整体发光强度")),
]

WANT = [
    ("相位", "SCRIPTED", [("扫过速度", "spd")], "spd * (frame - 1) / %f" % FPS),
    ("角度_余弦", "SCRIPTED", [("扫过角度", "ang")], "cos(radians(ang)) / %s" % _K),
    ("角度_正弦", "SCRIPTED", [("扫过角度", "ang")], "sin(radians(ang)) / %s" % _K),
    ("条数", "AVERAGE", [("扫过条数", "v")], None),
    ("水平条数", "AVERAGE", [("水平条数", "v")], None),
    ("发光强度", "AVERAGE", [("发光强度", "v")], None),
]

fixed = []
ob = D.objects.get(PLANE)
ctrl = D.objects.get(CTRL_NAME)
mat = D.materials.get(MAT_NAME)
assert ctrl is not None, "找不到控制器空对象 %r" % CTRL_NAME
assert mat is not None and mat.use_nodes, "找不到材质 %r" % MAT_NAME
nt = mat.node_tree


def force_refresh():
    """★ 改完自定义属性必须这样标脏:节点树上的驱动器才会重算。
       只 view_layer.update() 会读到陈旧的 is_valid 与插座值。"""
    ctrl.update_tag()
    nt.update_tag()
    C.evaluated_depsgraph_get().update()


print("--- 体检 ---")
print("  控制器空对象存在: %r (type=%s)" % (ctrl.name, ctrl.type))
print("  材质: %r  NODES=%d LINKS=%d" % (mat.name, len(nt.nodes), len(nt.links)))
missing = [k for k, _, _ in KNOBS if k not in ctrl]
assert not missing, "控制器上缺旋钮 %r" % missing
print("  旋钮: %r" % {k: ctrl[k] for k, _, _ in KNOBS})

# ---------- 1. 旋钮(只补缺,不覆盖已有值) ----------
for name, default, meta in KNOBS:
    if name not in ctrl:
        ctrl[name] = default
        fixed.append("补上旋钮 %r = %r" % (name, default))
    try:
        ctrl.id_properties_ui(name).update(**meta)
    except Exception as e:
        fixed.append("⚠ %r 的 UI 元数据设置失败: %r" % (name, e))

# ---------- 2. 目标对象上的同名残留 ----------
left = [k for k, _, _ in KNOBS if ob is not None and k in ob]
if left:
    if CLEAN_TARGET_LEFTOVERS:
        for k in left:
            del ob[k]
        fixed.append("清掉 %r 上的同名残留属性 %r" % (PLANE, left))
    else:
        print("  ℹ %r 上还留着同名属性 %r —— 两个真相源,建议删掉"
              "(或把 CLEAN_TARGET_LEFTOVERS 改成 True)" % (PLANE, left))

# ---------- 3. 驱动器(对齐规格;不一致就原子重建) ----------
if nt.animation_data is None:
    # 触发一次写入,让节点树建立 animation_data
    for node_name, _, _, _ in WANT:
        n = nt.nodes.get(node_name)
        if n is not None and len(n.outputs):
            n.outputs[0].default_value = n.outputs[0].default_value
            break


def spec_problems(old, dtype, vars_, expr):
    if old is None:
        return ["驱动器不存在"]
    why = []
    if old.driver.type != dtype:
        why.append("类型 %s != %s" % (old.driver.type, dtype))
    got = [(v.name, v.targets[0].id.name if v.targets[0].id else None, v.targets[0].data_path)
           for v in old.driver.variables]
    want = [(vn, CTRL_NAME, '["%s"]' % p) for p, vn in vars_]
    if got != want:
        why.append("变量 %r != %r" % (got, want))
    if dtype == 'SCRIPTED' and old.driver.expression != expr:
        why.append("表达式 %r != %r" % (old.driver.expression, expr))
    return why


for node_name, dtype, vars_, expr in WANT:
    n = nt.nodes.get(node_name)
    if n is None or not len(n.outputs):
        fixed.append("⚠ 找不到节点 %r(驱动器无法搭建,请人工确认)" % node_name)
        continue
    sock = n.outputs[0]
    path = 'nodes["%s"].outputs[0].default_value' % node_name
    ad = nt.animation_data
    old = ad.drivers.find(path) if ad else None
    why = spec_problems(old, dtype, vars_, expr)
    if not why:
        continue
    # ★ 原子重建:整条删掉再加。只改字段会留下 is_valid=False 的僵死驱动器。
    if old is not None:
        ad.drivers.remove(old)
    drv = sock.driver_add("default_value").driver
    drv.type = dtype
    for v in list(drv.variables):
        drv.variables.remove(v)
    for prop, var_name in vars_:          # ★ 顺序: (属性键, 变量名);反了会造出悬空变量
        var = drv.variables.new()
        var.name = var_name
        var.type = 'SINGLE_PROP'
        t = var.targets[0]
        t.id_type = 'OBJECT'              # ★ 必须先 id_type 再 id
        t.id = ctrl
        t.data_path = '["%s"]' % prop
    if dtype == 'SCRIPTED':
        drv.expression = expr
    fixed.append("重建驱动器 %s (原因: %s)" % (node_name, "; ".join(why)))

print("--- 本次改动(%d 处) ---" % len(fixed))
for f in fixed:
    print("  %s" % f)
if not fixed:
    print("  (无 —— 本来就是对的状态)")

# ---------- 4. 现状 ----------
force_refresh()
drs = list(nt.animation_data.drivers) if nt.animation_data else []
bad = 0
tgt = set()
print("--- 现状 ---")
print("  DRIVERS=%d" % len(drs))
for d in drs:
    if not d.driver.is_valid:
        bad += 1
    for v in d.driver.variables:
        for t in v.targets:
            tgt.add(t.id.name if t.id else "<None>")
    print("    %-8s %-9s valid=%s" % (d.data_path[7:].split('"')[0], d.driver.type, d.driver.is_valid))
print("  DRIVER_TARGETS=%r" % sorted(tgt))
print("  INVALID=%d" % bad)
print("  REFERENCES_PLANE=%s" % (PLANE in tgt))

# ---------- 5. 数值核对(行为法:改值看跟不跟,不看 is_valid) ----------
print("--- 数值核对(驱动是否真把值送进来了) ---")
_f0 = sc.frame_current
orig = {k: ctrl[k] for k, _, _ in KNOBS}
ok_all = True


def node_val(nm):
    force_refresh()
    return D.materials[mat.name].evaluated_get(C.evaluated_depsgraph_get()).node_tree.nodes[nm].outputs[0].default_value


def check(label, got, want_v, tol=1e-5):
    global ok_all
    good = abs(got - want_v) < tol
    ok_all = ok_all and good
    print("  %-10s 插座=%+.6f  期望=%+.6f  => %s" % (label, got, want_v, "OK" if good else "不符"))


try:
    for nm, prop in (("条数", "扫过条数"), ("水平条数", "水平条数"), ("发光强度", "发光强度")):
        check(nm, node_val(nm), float(ctrl[prop]))
    for a in (0.0, 45.0, 90.0, 180.0):
        ctrl["扫过角度"] = a
        r = math.radians(a)
        k = 1.0 / (abs(math.cos(r)) + abs(math.sin(r)))
        check("余弦 %g°" % a, node_val("角度_余弦"), math.cos(r) * k)
        check("正弦 %g°" % a, node_val("角度_正弦"), math.sin(r) * k)
    ctrl["扫过角度"] = orig["扫过角度"]
    for f in (1, 49):
        sc.frame_set(f)
        got = node_val("相位")
        check("相位 f=%d" % f, got, float(ctrl["扫过速度"]) * (f - 1) / FPS)
finally:
    for k, v in orig.items():
        ctrl[k] = v
    sc.frame_set(_f0)
    force_refresh()

print("  VALUE_CHECK=%s" % ("OK" if ok_all else "FAILED"))
print("  NODES=%d LINKS=%d (本脚本不会改动这两个数)" % (len(nt.nodes), len(nt.links)))
print("  ACTIVE=%r" % (C.view_layer.objects.active.name if C.view_layer.objects.active else None))
print("  ★ 桥只改内存,记得在 Blender 里 Ctrl+S")
assert ok_all, "数值核对未通过 —— 驱动器虽已重建但没把值送进去"
print("MAINTAIN_OK")
