"""独立核验「循环三角波关键帧动画」：关键帧帧号/值、插值类型、CYCLES 修饰器、逐帧循环求值抽样。

必须在【写入完成后的新一次桥请求】里运行（不能和写入脚本同一次 exec，否则读到未刷新缓存）。
用法：python send.py skills/blender-loop-keyframe-anim/scripts/verify_loop_anim.py"""
import bpy

# ===== 配置（与 write_loop_anim.py 保持一致）=====
TARGET_OBJ = "竖向灯001_噪波控制"
ANIMS = {
    # 属性名 -> (峰值帧, 峰值, 周期补帧帧, 周期尾值)  用于抽样核对
    "面光统一强度": ("16", 13.0, "31", 8.0),
    "发光强度":     ("11", 50.0, "21", 5.0),
}
FRAME_END = 450

def find_fc(cb, datapath):
    for fc in cb.fcurves:
        if fc.data_path == datapath:
            return fc
    return None

def main():
    obj = bpy.data.objects.get(TARGET_OBJ)
    if not obj:
        raise SystemExit(f"找不到对象: {TARGET_OBJ}")
    cb = obj.animation_data.action.layers[0].strips[0].channelbags[0]

    all_ok = True
    for prop, (peak_str, peak, end_str, end_val) in ANIMS.items():
        path = f'["{prop}"]'
        fc = find_fc(cb, path)
        if not fc:
            print(f"[❌] {path}: 找不到 fcurve")
            all_ok = False
            continue
        # 1) 关键帧
        kframes = [(k.co[0], k.co[1]) for k in fc.keyframe_points]
        interps = {round(k.co[0]): k.interpolation for k in fc.keyframe_points}
        ok_bezier = all(v == 'BEZIER' for v in interps.values())
        # 2) 修饰器
        has_cycles = any(getattr(m, 'type', '') == 'CYCLES' for m in fc.modifiers)
        # 3) 循环求值抽样：周期起点=8/5, 峰值, 周期尾(≈首值)
        peak_f = int(peak_str)
        c_start = fc.evaluate(1)
        c_peak = fc.evaluate(peak_f)
        c_tail = fc.evaluate(int(end_str))
        c_end  = fc.evaluate(FRAME_END)
        sample_ok = (abs(c_peak - peak) < 0.02)  # 峰值应≈目标
        print(f"[{'OK' if ok_bezier and has_cycles and sample_ok else '❌'}] {path}")
        print(f"    keys={[(round(x,1), round(y,2)) for x, y in kframes]}  interps={interps}")
        print(f"    mods={'CYCLES' if has_cycles else 'NONE'}")
        print(f"    帧1={c_start:.2f} 帧{peak_f}={c_peak:.2f}(期望~{peak}) 帧{end_str}={c_tail:.2f} 帧{FRAME_END}={c_end:.2f}")
        all_ok = all_ok and ok_bezier and has_cycles and sample_ok

    print("\n结论:", "✅ 全部通过" if all_ok else "❌ 存在异常")

main()  # 桥 exec 命名空间无 __name__,必须无条件调用