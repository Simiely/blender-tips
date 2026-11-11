# -*- coding: utf-8 -*-
"""
set_speed_curve.py —— 用一张 KEYS 表重建速度倍率曲线（含刹车拐点）

用途:
  MODE='report' 只读:打印现有曲线、按 KEYS 预测速度/位移剖面
  MODE='apply'  重建:清空该属性所有关键帧 → 按 KEYS 重插 → 设插值与手柄

要点:
  * 全清后重建,避免"移动关键帧"时手柄被自动钳制;重建后必须回读校验 co 与 handle
  * 刹车"顿一下"= 起刹帧进柄近乎水平、出柄猛压,让减速度在 1 帧内跳到 7~8 m/s²
  * KEYS 的 y 值单调不增,否则车会往前窜;脚本会断言
  * 改完必须重跑 bake_speed_to_translation.py,否则画面不动

经桥执行:
  python bl.py set_speed_curve.py
"""

import bpy

# ============================== CONFIG ==============================
MODE = 'report'                     # 'report' | 'apply'
CTRL = "控制_车速"
PROP = '["速度倍率"]'
X0 = 7.297282
REF = 0.077926                      # 倍率 1.0 时每帧位移 = D / 原方案帧数
FPS = 30.0

# (帧, 值, 左手柄, 右手柄)  —— y 必须单调不增
KEYS = [
    (30.0, 1.000, (24.0, 1.060), (44.0, 0.820)),      # 起点（右手柄略平 = 缓一点的开局）
    (92.0, 0.680, (80.0, 0.740), (95.5, 0.260)),      # ★ 起刹拐点:进柄水平 / 出柄猛压
    (105.0, 0.000, (100.0, 0.000), (110.0, 0.000)),   # 停稳
]
# ====================================================================


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
    ctrl = bpy.data.objects[CTRL]
    cb, fsp = find_fc(ctrl.animation_data, PROP, 0)
    assert fsp is not None, "%s 没有 %s 曲线" % (CTRL, PROP)

    print("现有曲线:", [(round(k.co[0], 2), round(k.co[1], 4)) for k in fsp.keyframe_points])

    vals = [k[1] for k in KEYS]
    assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1)), "KEYS 的 y 必须单调不增"

    if MODE != 'apply':
        print("\n将写入的关键帧（倍率 → 速度 → 每帧位移）:")
        for f, v, hl, hr in KEYS:
            print("  f%-6.1f  %.3f  %6.2f km/h  %5.2f cm/帧" % (f, v, v * REF * FPS * 3.6, v * REF * 100))
        print("\nREPORT ONLY（改 MODE='apply' 才写入）")
        return

    while len(fsp.keyframe_points):
        fsp.keyframe_points.remove(fsp.keyframe_points[0], fast=True)
    for f, v, hl, hr in KEYS:
        kp = fsp.keyframe_points.insert(f, v)
        kp.interpolation = 'BEZIER'
        kp.handle_left_type = 'FREE'
        kp.handle_right_type = 'FREE'
        kp.handle_left = hl
        kp.handle_right = hr
    fsp.update()

    # 回读校验:手柄有可能被钳制
    K = list(fsp.keyframe_points)
    assert len(K) == len(KEYS)
    for i, (f, v, hl, hr) in enumerate(KEYS):
        k = K[i]
        assert abs(k.co[0] - f) < 1e-6 and abs(k.co[1] - v) < 1e-6, "关键帧 %d 值不对" % i
        assert abs(k.handle_left[0] - hl[0]) < 1e-6 and abs(k.handle_right[0] - hr[0]) < 1e-6, \
            "关键帧 %d 手柄被钳制" % i
    print("已重建:", [(round(k.co[0], 1), round(k.co[1], 4)) for k in K])

    # 拐点强度:起刹帧前后逐帧下降量的跳变倍数
    print("\n f     倍率     逐帧Δ      km/h     cm/帧")
    prev = None
    for f in range(int(K[-1].co[0]) - 14, int(K[-1].co[0]) + 1):
        v = fsp.evaluate(float(f))
        d = "" if prev is None else "%+0.5f" % (v - prev)
        print("  %-4d %.4f  %8s  %6.2f  %6.2f" % (f, v, d, v * REF * FPS * 3.6, v * REF * 100))
        prev = v
    print("\nCURVE APPLIED —— 必须再跑 bake_speed_to_translation.py")


main()
