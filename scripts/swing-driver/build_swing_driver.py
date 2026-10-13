"""给一批对象挂「参数化摆动」驱动(单物体自包含版)。

经 9877 桥执行:
    python send.py build_swing_driver.py

原理 / 选型对照 / 实测见 ../../docs/参数化摆动驱动系统.md
配置区改 OBJS / AXIS / PHASE_STEP / DEFAULTS 即可。

★ 桥端 __name__ 是 builtins,结尾禁止 if __name__ == '__main__' 守卫。
★ 与 verify_swing_driver.py 的配置区必须勾稽一致。
"""
import bpy, math

# ===== 配置 =====
OBJS = ['钟表01']            # 要挂驱动的对象名(可多个)
AXIS = 1                     # 旋转轴 0=X 1=Y 2=Z
PHASE_STEP = 0.0             # >0 时按顺序给每个对象递增「相位偏移」= i × PHASE_STEP,用于错开

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
EXPR = ("radians((amin + amax)/2.0 "
        "- (amax - amin)/2.0*cos(2.0*pi*(frame - 1.0 - phs)/dur))")


def action_has_channel(act, path, idx):
    """5.x Slotted Action:曲线住在 layer -> strip -> channelbag -> fcurves"""
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        if fc.data_path == path and fc.array_index == idx:
                            return True
    except Exception:
        pass
    return False


def build(obj, axis, phase=0.0):
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
        if key not in obj:
            obj[key] = float(dv)
        try:
            obj.id_properties_ui(key).update(min=lo, max=hi, soft_min=lo, soft_max=hi,
                                             description=desc, default=float(dv))
        except Exception as e:
            print('   属性 UI 元信息失败:', key, e)
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
    d.expression = EXPR
    return fc, d


def main():
    print('摆动驱动构建 | %s | 轴=%d  相位步长=%g' % (bpy.data.filepath, AXIS, PHASE_STEP))
    ok = 0
    for i, nm in enumerate(OBJS):
        obj = bpy.data.objects.get(nm)
        if obj is None:
            print('!! 找不到对象:', nm)
            continue
        print('  [%s]' % nm)
        fc, d = build(obj, AXIS, PHASE_STEP * i)
        print('   参数:', {k: obj.get(k) for k in DEFAULTS})
        print('   驱动: %s[%d]  type=%s  valid=%s  vars=%s' % (
            fc.data_path, fc.array_index, d.type, d.is_valid,
            [v.name for v in d.variables]))
        ok += 1
    print('完成 %d/%d 个。is_dirty=%s —— 桥只改内存,记得 Ctrl+S' % (
        ok, len(OBJS), bpy.data.is_dirty))
    print('=== BUILD SWING DRIVER DONE ===')


main()
