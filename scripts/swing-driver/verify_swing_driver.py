"""独立核验「参数化摆动」驱动。

必须在【写入完成后的新一次桥请求】里运行(不能与 build 同一次 exec,否则读到未刷新缓存)。
    python send.py verify_swing_driver.py

配置区与 build_swing_driver.py 勾稽一致。
★ 驱动只写 evaluated 数据 => 一切求值都走 obj.evaluated_get(depsgraph)。
"""
import bpy, math

# ===== 配置 =====
OBJS = ['钟表01']
AXIS = 1
SAMPLE_FRAMES = (1, 26, 51, 76, 101, 151, 201)
PERIOD_TOL = 1e-5      # 周期一致性容差(度)
VALUE_TOL = 1e-4       # 逐帧对手算期望值的容差(度)

scn = bpy.context.scene
frame_bak = scn.frame_current


def eval_angle(obj, fr):
    scn.frame_set(fr)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return math.degrees(obj.evaluated_get(dg).rotation_euler[AXIS])


def expected(amin, amax, dur, phs, fr):
    """与驱动表达式同式的纯 Python 手算,用于对账"""
    return amin + (amax - amin) * (0.5 - 0.5 * math.cos(
        2.0 * math.pi * (fr - 1.0 - phs) / dur))


ok_all = True
for nm in OBJS:
    obj = bpy.data.objects.get(nm)
    print('=' * 68)
    print('对象:', nm)
    if obj is None:
        print('  !! 找不到对象')
        ok_all = False
        continue

    ad = obj.animation_data
    drvs = [f for f in ad.drivers
            if f.data_path == 'rotation_euler' and f.array_index == AXIS] if ad else []
    print('  参数    :', {k: obj.get(k) for k in ('最小角度', '最大角度', '持续时间', '相位偏移')})
    print('  驱动数  :', len(drvs), '| is_valid:', [f.driver.is_valid for f in drvs])
    if not drvs:
        print('  ❌ 该通道没有驱动')
        ok_all = False
        continue

    d = drvs[0].driver
    print('  表达式  :', d.expression)
    print('  变量    :', [(v.name, v.targets[0].id.name if v.targets[0].id else None,
                        v.targets[0].data_path) for v in d.variables])
    if not d.is_valid:
        ok_all = False

    amin = float(obj.get('最小角度'))
    amax = float(obj.get('最大角度'))
    dur = float(obj.get('持续时间'))
    phs = float(obj.get('相位偏移'))

    print('  逐帧对账(度):')
    for fr in SAMPLE_FRAMES:
        got = eval_angle(obj, fr)
        exp = expected(amin, amax, dur, phs, fr)
        good = abs(got - exp) < VALUE_TOL
        ok_all = ok_all and good
        print('    帧 %4d -> %10.4f   期望 %10.4f   %s' % (fr, got, exp, 'OK' if good else '** 偏差 **'))

    step = max(1, int(round(dur / 8.0)))
    worst = 0.0
    for fr in range(1, 1 + int(round(dur)) // 2, step):
        worst = max(worst, abs(eval_angle(obj, fr) - eval_angle(obj, fr + int(round(dur)))))
    good = worst < PERIOD_TOL
    ok_all = ok_all and good
    print('  周期一致性(f vs f+%g)最大差: %.8f 度  %s' % (
        dur, worst, 'OK' if good else '** 偏差 **'))

    # 子对象是否跟着动(层级关系没被破坏)
    kids = [o for o in bpy.data.objects if o.parent == obj]
    if kids:
        k = sorted(kids, key=lambda o: o.name)[0]

        def kid_pos(fr):
            scn.frame_set(fr)
            dg = bpy.context.evaluated_depsgraph_get()
            dg.update()
            return tuple(round(v, 6) for v in k.evaluated_get(dg).matrix_world.translation)

        p1, p2 = kid_pos(1), kid_pos(1 + int(round(dur / 2)))
        moved = p1 != p2
        ok_all = ok_all and moved
        print('  子对象 %d 个(取样 %s)随父级变化: %s' % (
            len(kids), k.name, 'OK' if moved else '** 没动 **'))

scn.frame_set(frame_bak)
print('=' * 68)
print('当前帧已还原为:', frame_bak, '| is_dirty:', bpy.data.is_dirty)
print('VERDICT:', 'PASS' if ok_all else 'FAIL')
print('=== VERIFY SWING DRIVER DONE ===')
