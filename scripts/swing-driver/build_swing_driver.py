"""给一批对象挂「参数化摆动」驱动(单物体自包含版,可选「摆幅倍率」总控)。

经 9877 桥执行:
    python send.py build_swing_driver.py

原理 / 选型对照 / 实测见 ../../docs/参数化摆动驱动系统.md
★ 桥端 __name__ 是 builtins,结尾禁止 if __name__ == '__main__' 守卫。
★ 与 verify_swing_driver.py 的配置区必须勾稽一致。
"""
import bpy, math

# ===== 配置 =====
OBJS = ['钟表01']            # 要挂驱动的对象名(可多个)
AXIS = 1                     # 旋转轴 0=X 1=Y 2=Z
PHASE_STEP = 0.0             # >0 时按顺序给每个对象递增「相位偏移」= i × PHASE_STEP,用于错开

# 摆幅倍率总控:
#   None                        = 不启用(表达式里没有 mul 项)
#   ('SCENE',  '键名')           = 挂在 Scene 上 —— ★ 免疫「空物体收敛清理」
#   ('OBJECT', '对象名', '键名')  = 挂在一个控制空物体上 —— 好找,但见 README「注意」
MUL_SOURCE = None
MUL_COL = None               # OBJECT 模式下,控制空物体放进哪个集合(None = 场景根)
MUL_DEF, MUL_MIN, MUL_MAX = 1.0, 0.0, 10.0

# 参数键名(= 显示名,Blender 没有独立 label;带 min/max 才是滑块) -> (默认值, 最小, 最大, 说明)
DEFAULTS = {
    '最小角度': (-5.0, -180.0, 180.0, '摆动最小角(度)'),
    '最大角度': (5.0, -180.0, 180.0, '摆动最大角(度)'),
    '持续时间': (100.0, 1.0, 2000.0, '一个完整周期(帧)'),
    '相位偏移': (0.0, -2000.0, 2000.0, '整体前后挪动(帧),0 = 帧1 在最小角'),
}
VARS = [('amin', '最小角度'), ('amax', '最大角度'),
        ('dur', '持续时间'), ('phs', '相位偏移')]

# 与主题 46 的写法代数恒等: amin + (amax-amin)*(0.5 - 0.5*cos θ)
BODY = "(amin + amax)/2.0 - (amax - amin)/2.0*cos(2.0*pi*(frame - 1.0 - phs)/dur)"
# ★ 倍率必须把整个 BODY 括起来写 `mul*(BODY)`。
#   写成 `mul*BODY` 会被运算符优先级解析成 `(mul*(amin+amax)/2.0) - (amax-amin)/2.0*cos(...)`,
#   即 mul 只乘了「中心项」—— 对称角度(amin+amax=0)时中心项恒为 0 ⇒ 倍率**完全失效且不报错**。
EXPR = ("radians(mul*(" + BODY + "))") if MUL_SOURCE else ("radians(" + BODY + ")")


def set_slider(owner, key, default, lo, hi, desc):
    """幂等建自定义属性 + 滑块元信息(min/max 才是滑块,键名即显示名)"""
    if key not in owner:
        owner[key] = float(default)
    try:
        owner.id_properties_ui(key).update(min=lo, max=hi, soft_min=lo, soft_max=hi,
                                           description=desc, default=float(default))
    except Exception as e:
        print('   属性 UI 元信息失败:', key, e)


def ensure_mul():
    """返回 (driver 目标 id, data_path);未启用返回 (None, None)"""
    if not MUL_SOURCE:
        return None, None
    kind = MUL_SOURCE[0]
    if kind == 'SCENE':
        scn = bpy.context.scene
        key = MUL_SOURCE[1]
        set_slider(scn, key, MUL_DEF, MUL_MIN, MUL_MAX, '所有目标摆幅的倍率(1 = 原样)')
        return scn, '["%s"]' % key
    if kind == 'OBJECT':
        name, key = MUL_SOURCE[1], MUL_SOURCE[2]
        ctrl = bpy.data.objects.get(name)
        if ctrl is None:
            ctrl = bpy.data.objects.new(name, None)
            col = bpy.data.collections.get(MUL_COL) if MUL_COL else None
            (col.objects if col else bpy.context.scene.collection.objects).link(ctrl)
            print('   新建控制空物体: %s (集合 %s)' % (name, MUL_COL or '<场景根>'))
        set_slider(ctrl, key, MUL_DEF, MUL_MIN, MUL_MAX, '所有目标摆幅的倍率(1 = 原样)')
        return ctrl, '["%s"]' % key
    raise SystemExit('MUL_SOURCE 只能是 None / (SCENE,键) / (OBJECT,对象名,键)')


def action_has_channel(act, path, idx):
    """5.x Slotted Action:曲线住在 layer -> strip -> channelbag -> fcurves"""
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for f in cb.fcurves:
                        if f.data_path == path and f.array_index == idx:
                            return True
    except Exception:
        pass
    return False


def build(obj, axis, mul_id, mul_path, phase=0.0):
    if obj.rotation_mode != 'XYZ':
        obj.rotation_mode = 'XYZ'
    ad = obj.animation_data_create()

    # 1) 摘掉同通道的关键帧动画(改名 + fake user 留成孤儿,可回退,不删数据块)
    if ad.action is not None and action_has_channel(ad.action, 'rotation_euler', axis):
        act = ad.action
        act.name = act.name + '_旧关键帧版'
        act.use_fake_user = True
        ad.action = None
        print('   摘除旧 action(保留为孤儿 + fake user):', act.name)

    # 2) 幂等:清同通道旧驱动
    n = 0
    for f in list(ad.drivers):
        if f.data_path == 'rotation_euler' and f.array_index == axis:
            ad.drivers.remove(f)
            n += 1
    if n:
        print('   清掉同通道旧驱动:', n)

    # 3) 基准角复位
    obj.rotation_euler[axis] = 0.0

    # 4) 参数(幂等:已有则保留现值,只补 UI 元信息)
    for key, (dv, lo, hi, desc) in DEFAULTS.items():
        set_slider(obj, key, dv, lo, hi, desc)
    if phase:
        obj['相位偏移'] = float(phase)

    # 5) 驱动
    fc = obj.driver_add('rotation_euler', axis)
    d = fc.driver
    d.type = 'SCRIPTED'
    for name, key in VARS:
        v = d.variables.new()
        v.name = name
        v.type = 'SINGLE_PROP'
        t = v.targets[0]
        t.id_type = 'OBJECT'          # 指向对象自身 => 用默认 OBJECT
        t.id = obj
        t.data_path = '["%s"]' % key
    if mul_id is not None:
        v = d.variables.new()
        v.name = 'mul'
        v.type = 'SINGLE_PROP'
        t = v.targets[0]
        # ★ id_type 必须先设,再赋 id(5.2:不设的话 id 只接受 Object)
        t.id_type = 'SCENE' if MUL_SOURCE[0] == 'SCENE' else 'OBJECT'
        t.id = mul_id
        t.data_path = mul_path
    d.expression = EXPR
    return fc, d


def main():
    print('摆动驱动构建 | %s | 轴=%d  相位步长=%g' % (bpy.data.filepath, AXIS, PHASE_STEP))
    mul_id, mul_path = ensure_mul()
    if mul_id is not None:
        print('   倍率总控: %s %s' % (mul_id.name, mul_path))
    ok = 0
    for i, nm in enumerate(OBJS):
        obj = bpy.data.objects.get(nm)
        if obj is None:
            print('!! 找不到对象:', nm)
            continue
        print('  [%s]' % nm)
        fc, d = build(obj, AXIS, mul_id, mul_path, PHASE_STEP * i)
        print('   参数:', {k: obj.get(k) for k in DEFAULTS})
        print('   驱动: %s[%d]  type=%s  valid=%s  vars=%s' % (
            fc.data_path, fc.array_index, d.type, d.is_valid, [v.name for v in d.variables]))
        ok += 1
    print('完成 %d/%d 个。is_dirty=%s —— 桥只改内存,记得 Ctrl+S' % (
        ok, len(OBJS), bpy.data.is_dirty))
    print('=== BUILD SWING DRIVER DONE ===')


main()
