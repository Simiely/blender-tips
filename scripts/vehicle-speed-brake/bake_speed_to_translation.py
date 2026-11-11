# -*- coding: utf-8 -*-
"""
bake_speed_to_translation.py —— 速度曲线 → 积分 → 位移烘焙 → 相机补偿

用途:
  MODE='report' 只读:打印曲线关键帧、区间、平均倍率、总位移、刹车段行程、末帧预测
  MODE='apply'  烘焙:清空 root 的位置曲线 → 逐帧写位移(LINEAR) → 重建相机补偿驱动

要点:
  * 区间取【速度曲线自身的首末关键帧】,不用 scene.frame_start/end(用户常拉长场景做静帧)
  * 每帧满速位移 REF = D / REF_FRAMES 是常量,【不能】写成 D / (F1 - F0)
    —— 后者在区间变长时会把已有段整体压缩,静默改掉用户认可的部分
  * 相机补偿 = D - REF×∫total,按【最终位置】补,保证末帧构图与原方案一致
  * 写后必须 view_layer.update();验证要【另起一次请求】

经桥执行:
  python bl.py bake_speed_to_translation.py
"""

import bpy

# ============================== CONFIG ==============================
MODE = 'report'                    # 'report' | 'apply'
CTRL = "控制_车速"                 # 挂着速度曲线 / 进度 的空物体
PROP = '["速度倍率"]'               # 速度曲线所在的属性路径
ROOT = "绑定_车辆根"                # 被烘焙位移的对象
COMP = "控制_相机补偿"              # 相机补偿空物体
PROG = '["进度"]'                  # 补偿用的 0→1 进度属性
X0, X1 = 7.297282, 2.621750        # 原方案车根首末帧的世界 X
REF_FRAMES = 60.0                  # 原方案时长,定义"倍率 1.0"的速度
AXIS = 0                           # 行驶轴:0=X, 1=Y, 2=Z
STEP = 0.25                        # 积分步长(帧),必须能整除区间
# ====================================================================

D = abs(X1 - X0)
REF = D / REF_FRAMES


def iter_fcurves(ad):
    a = ad.action
    slot = getattr(ad, "action_slot", None)
    for layer in a.layers:
        for strip in layer.strips:
            bags = getattr(strip, "channelbags", None) or []
            for cb in bags:
                if slot is not None and getattr(cb, "slot", None) is not None and cb.slot != slot:
                    continue
                for fc in cb.fcurves:
                    yield cb, fc


def find_fc(ad, path, idx):
    for cb, fc in iter_fcurves(ad):
        if fc.data_path == path and fc.array_index == idx:
            return cb, fc
    return None, None


def main():
    sc = bpy.context.scene
    ctrl = bpy.data.objects[CTRL]
    root = bpy.data.objects[ROOT]
    comp = bpy.data.objects[COMP]

    cb, fsp = find_fc(ctrl.animation_data, PROP, 0)
    assert fsp is not None, "%s 没有 %s 曲线" % (CTRL, PROP)
    pts = list(fsp.keyframe_points)
    F0, F1 = float(pts[0].co[0]), float(pts[-1].co[0])

    print("区间取自曲线: %.2f - %.2f（场景 %d - %d，不用它）" % (F0, F1, sc.frame_start, sc.frame_end))
    print("关键帧:", [(round(k.co[0], 2), round(k.co[1], 4)) for k in pts])
    print("REF = D/%.0f = %.6f m/帧（与区间长度无关）" % (REF_FRAMES, REF))

    n = int(round((F1 - F0) / STEP))
    assert abs(n * STEP - (F1 - F0)) < 1e-9, "区间不是 %.2f 的整数倍" % STEP
    samples = [fsp.evaluate(F0 + i * STEP) for i in range(n + 1)]
    cum, prev = 0.0, samples[0]
    cum_at = {F0: 0.0}
    for i in range(1, n + 1):
        cum += (prev + samples[i]) * 0.5 * STEP
        prev = samples[i]
        f = F0 + i * STEP
        if abs(f - round(f)) < 1e-9:
            cum_at[float(round(f))] = cum
    total = cum
    print("平均倍率 %.4f  全程位移 %.4f m（原方案 %.4f）" % (total / (F1 - F0), REF * total, D))

    # 单调性:曲线回升 = 车会往前窜
    bad = [f for f in range(int(F0), int(F1))
           if fsp.evaluate(float(f)) < fsp.evaluate(float(f + 1)) - 1e-9]
    print("单调不增:", "OK" if not bad else ("失败 @ f%s" % bad[:5]))

    if MODE != 'apply':
        shift = D - REF * total
        print("相机补偿应为 %.6f × 进度" % shift)
        print("REPORT ONLY")
        return

    # ---- 烘焙位移 ----
    _, fc0 = find_fc(root.animation_data, "location", AXIS)
    if fc0 is None:
        for cbx, f in iter_fcurves(root.animation_data):
            cbx.fcurves.new("location", index=AXIS)
        _, fc0 = find_fc(root.animation_data, "location", AXIS)
    while len(fc0.keyframe_points):
        fc0.keyframe_points.remove(fc0.keyframe_points[0], fast=True)

    for f in range(int(F0), int(F1) + 1):
        val = X0 + (X1 - X0) / D * (REF * cum_at[float(f)])
        if AXIS == 1:
            root.location.y = val
        elif AXIS == 2:
            root.location.z = val
        else:
            root.location.x = val
        root.keyframe_insert("location", index=AXIS, frame=float(f))

    _, fc0 = find_fc(root.animation_data, "location", AXIS)
    for k in fc0.keyframe_points:
        k.interpolation = "LINEAR"
    fc0.update()
    print("烘焙 %d 帧: %.6f → %.6f" % (
        len(fc0.keyframe_points), fc0.keyframe_points[0].co[1], fc0.keyframe_points[-1].co[1]))

    # ---- 相机补偿 ----
    shift = D - REF * total
    for fc in list(comp.animation_data.drivers):
        if fc.data_path == "location" and fc.array_index == AXIS:
            comp.animation_data.drivers.remove(fc)
    fc = comp.driver_add("location", AXIS)
    d = fc.driver
    d.type = "SCRIPTED"
    d.expression = "%.6f * prog" % shift
    while d.variables:
        d.variables.remove(d.variables[0])
    v = d.variables.new()
    v.name = "prog"
    v.type = "SINGLE_PROP"
    v.targets[0].id = ctrl
    v.targets[0].data_path = PROG
    print("相机补偿 %.6f  valid=%s" % (shift, d.is_valid))

    bpy.context.view_layer.update()
    print("BAKE DONE —— 另起一次请求做核验")


main()
