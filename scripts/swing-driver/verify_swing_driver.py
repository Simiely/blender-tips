"""独立核验「参数化摆动」驱动(含摆幅倍率总控)。

必须在【写入完成后的新一次桥请求】里运行(不能与 build 同一次 exec,否则读到未刷新缓存)。
    python send.py verify_swing_driver.py

配置区与 build_swing_driver.py 勾稽一致。
★ 驱动只写 evaluated 数据 => 一切求值都走 obj.evaluated_get(depsgraph)。
★ 倍率本身也可能被 K 帧(逐帧变化)=> 期望值按【逐帧读到的倍率】算,不用常数。
"""
import bpy, math

# ===== 配置 =====
OBJS = ['钟表01']
AXIS = 1
SAMPLE_FRAMES = (1, 26, 51, 76, 101, 151, 201)
MUL_SOURCE = None          # 与 build 一致:None / ('SCENE',键) / ('OBJECT',对象名,键)
TEST_MUL = 5.0             # 倍率测试值(仅在倍率【没被 K 帧】时执行,测完还原)
PERIOD_TOL = 1e-5          # 周期一致性容差(度)
VALUE_TOL = 1e-4           # 逐帧对手算期望值的容差(度)

scn = bpy.context.scene
frame_bak = scn.frame_current


def mul_owner():
    if not MUL_SOURCE:
        return None, None
    if MUL_SOURCE[0] == 'SCENE':
        return scn, MUL_SOURCE[1]
    return bpy.data.objects.get(MUL_SOURCE[1]), MUL_SOURCE[2]


def mul_animated():
    """倍率是否被 K 帧(有 action)——被 K 帧时手改不生效"""
    owner, _ = mul_owner()
    if owner is None:
        return False, None
    ad = owner.animation_data
    if ad is not None and ad.action is not None:
        return True, ad.action.name
    return False, None


def read_mul(fr=None):
    """★ 必须先 frame_set(fr) + dg.update() 再调。
    被 K 帧的自定义属性:动画值只写在【evaluated 副本】上 —— 读原始 datablock 会拿到静态旧值,
    所以必须走 evaluated_get。"""
    owner, key = mul_owner()
    if owner is None:
        return 1.0
    dg = bpy.context.evaluated_depsgraph_get()
    try:
        return float(owner.evaluated_get(dg).get(key, 1.0))
    except Exception:
        return float(owner.get(key, 1.0))


def eval_angle_at(obj, fr):
    scn.frame_set(fr)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return math.degrees(obj.evaluated_get(dg).rotation_euler[AXIS])


def expected(amin, amax, dur, phs, mul, fr):
    """与驱动表达式同式的纯 Python 手算,用于对账"""
    return mul * (amin + (amax - amin) * (0.5 - 0.5 * math.cos(
        2.0 * math.pi * (fr - 1.0 - phs) / dur)))


def sweep(title):
    print('=' * 68)
    print(title)
    ok = True
    for nm in OBJS:
        obj = bpy.data.objects.get(nm)
        print('对象:', nm)
        if obj is None:
            print('  !! 找不到对象')
            ok = False
            continue
        ad = obj.animation_data
        drvs = [f for f in ad.drivers
                if f.data_path == 'rotation_euler' and f.array_index == AXIS] if ad else []
        print('  参数    :', {k: obj.get(k) for k in ('最小角度', '最大角度', '持续时间', '相位偏移')})
        print('  驱动数  :', len(drvs), '| is_valid:', [f.driver.is_valid for f in drvs])
        if not drvs:
            print('  ❌ 该通道没有驱动')
            ok = False
            continue
        d = drvs[0].driver
        if not d.is_valid:
            ok = False
        amin, amax = float(obj.get('最小角度')), float(obj.get('最大角度'))
        dur, phs = float(obj.get('持续时间')), float(obj.get('相位偏移'))
        for fr in SAMPLE_FRAMES:
            got = eval_angle_at(obj, fr)
            mul = read_mul(fr)                    # ★ 逐帧读倍率
            exp = expected(amin, amax, dur, phs, mul, fr)
            good = abs(got - exp) < VALUE_TOL
            ok = ok and good
            print('    帧 %4d -> %10.4f   期望 %10.4f (倍率 %6.3f)  %s' % (
                fr, got, exp, mul, 'OK' if good else '** 偏差 **'))
        mul_anim, _ = mul_animated()
        if mul_anim:
            print('  周期一致性: 跳过 —— 倍率被 K 帧(逐帧变化),f 与 f+%d 本就不同'
                  % int(round(dur)))
        else:
            step = max(1, int(round(dur / 8.0)))
            worst = 0.0
            for fr in range(1, 1 + int(round(dur)) // 2, step):
                worst = max(worst, abs(eval_angle_at(obj, fr)
                                       - eval_angle_at(obj, fr + int(round(dur)))))
            good = worst < PERIOD_TOL
            ok = ok and good
            print('  周期一致性最大差: %.8f 度  %s' % (worst, 'OK' if good else '** 偏差 **'))
        kids = [o for o in bpy.data.objects if o.parent == obj]
        if kids:
            k = sorted(kids, key=lambda o: o.name)[0]

            def kid_pos(fr):
                scn.frame_set(fr)
                dg = bpy.context.evaluated_depsgraph_get()
                dg.update()
                return tuple(round(v, 6) for v in k.evaluated_get(dg).matrix_world.translation)

            moved = kid_pos(1) != kid_pos(1 + int(round(dur / 2)))
            ok = ok and moved
            print('  子对象 %d 个随父级变化: %s' % (len(kids), 'OK' if moved else '** 没动 **'))
    return ok


ok_a = sweep('【A】当前参数')
ok_b = True

if MUL_SOURCE:
    anim, act_name = mul_animated()
    print()
    if anim:
        print('【B】跳过倍率测试 —— 倍率被 K 帧(owner 上是 action「%s」),手改不生效。' % act_name)
        print('     要测倍率请先删掉那条 action,或直接把倍率 K 成想要的值。')
    else:
        owner, key = mul_owner()
        orig_mul = read_mul(scn.frame_current)
        owner[key] = float(TEST_MUL)
        owner.update_tag()
        bpy.context.view_layer.update()
        ok_b = sweep('【B】倍率测试 = %g(角度应 ×%g)' % (TEST_MUL, TEST_MUL))
        owner[key] = float(orig_mul)
        owner.update_tag()
        bpy.context.view_layer.update()
        print()
        print('倍率已还原为原值 =', orig_mul)

scn.frame_set(frame_bak)
print('=' * 68)
print('当前帧已还原为:', frame_bak, '| is_dirty:', bpy.data.is_dirty)
print('VERDICT:', 'PASS' if (ok_a and ok_b) else 'FAIL')
print('=== VERIFY SWING DRIVER DONE ===')
