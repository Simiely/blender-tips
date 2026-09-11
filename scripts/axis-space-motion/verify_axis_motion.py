"""verify_axis_motion.py — 逐帧验证「位移是否真的沿目标轴」

做法（自证，不需要事先录基线）：
    1) 静音本对象的 location 曲线 → 逐帧采"基准世界位置"（= 没有这段位移动画时的位置）
    2) 取消静音 → 逐帧采"实际世界位置"
    3) 理想轨迹 = 基准 + 目标轴(世界方向) × d(f)，逐帧比实际 vs 理想
    4) 另算"逐帧位移增量方向 vs 目标轴"的夹角（更直观）

经桥跑法（必须与 key_axis_motion.py 分两次请求）：
    python send.py scripts/axis-space-motion/verify_axis_motion.py 9877
"""
import bpy
import math
from mathutils import Vector, Matrix

# ==================== 配置（与 key_axis_motion.py 保持一致）====================
TARGET = "相机基点"
SPACE = "SELF"               # "SELF" | "WORLD" | "PARENT"
AXIS = (0.0, 0.0, 1.0)
KEYS = [(151, 0.0), (480, -30.0)]
MODE = "check"               # "check" 逐帧自证 | "record" 只录实际世界位置到 JSON
JSON_PATH = ""               # MODE="record" 时的落盘路径
TOL_POS = 1.0e-4             # 位置/投影/垂轴 偏差阈值（单位）
# ==============================================================================


def _fcurve_collections(obj):
    ad = obj.animation_data
    if not (ad and ad.action):
        return []
    act = ad.action
    try:
        return [act.fcurves]
    except Exception:
        pass
    cols = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                cols.append(cb.fcurves)
    return cols


def _fcurves_of(obj, data_path=None):
    out = []
    for col in _fcurve_collections(obj):
        for fc in col:
            if data_path is None or fc.data_path == data_path:
                out.append(fc)
    return out


def _evaluated(obj, dg):
    try:
        return obj.evaluated_get(dg)
    except Exception:
        return obj


def _interp_d(f, keys):
    if f <= keys[0][0]:
        return keys[0][1]
    if f >= keys[-1][0]:
        return keys[-1][1]
    for i in range(len(keys) - 1):
        f0, d0 = keys[i]
        f1, d1 = keys[i + 1]
        if f0 <= f <= f1:
            t = 0.0 if f1 == f0 else (f - f0) / (f1 - f0)
            return d0 + (d1 - d0) * t
    return keys[-1][1]


def main():
    scene = bpy.context.scene
    saved_frame = scene.frame_current
    obj = bpy.data.objects.get(TARGET) if TARGET else bpy.context.object
    if obj is None:
        print("ERR 找不到对象:", TARGET)
        return

    parent = obj.parent
    mpi = obj.matrix_parent_inverse.copy()
    axis = Vector(AXIS).normalized()
    key_frames = [f for f, _ in KEYS]
    f_start, f_end = min(key_frames), max(key_frames)
    frames = list(range(f_start, f_end + 1))

    print("=" * 66)
    print("位移方向逐帧验证")
    print("=" * 66)
    print("对象:", obj.name, " 父级:", parent.name if parent else "(无)")
    print("目标轴: SPACE =", SPACE, " AXIS =", tuple(round(v, 6) for v in axis))
    print("范围:", f_start, "->", f_end, f"({len(frames)} 帧)")

    loc_fcs = _fcurves_of(obj, "location")
    if not loc_fcs:
        print("ERR 该对象没有 location 曲线，无可验证内容")
        return
    print("location 曲线:", [(fc.array_index, len(fc.keyframe_points), fc.mute) for fc in loc_fcs])

    def mean(samples):
        n = len(samples)
        out = Matrix.Identity(4)
        for m in samples:
            for r in range(4):
                for c in range(4):
                    out[r][c] += m[r][c]
        for r in range(4):
            for c in range(4):
                out[r][c] /= n
        return out

    def axis_world(f, mw_obj, R_basis_world):
        if SPACE == "WORLD":
            return axis.copy()
        if SPACE == "SELF":
            return (mw_obj.to_3x3() @ axis).normalized()
        return (R_basis_world @ axis).normalized()

    # ---------- record 模式 ----------
    if MODE == "record":
        import json
        data = {}
        for f in frames:
            scene.frame_set(f)
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            mw = _evaluated(obj, dg).matrix_world
            data[str(f)] = [[mw[r][c] for c in range(4)] for r in range(4)]
        with open(JSON_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        print("已写出基线:", JSON_PATH, len(data), "帧")
        scene.frame_set(saved_frame)
        return

    # ---------- 1) 静音，采基准 ----------
    orig_mute = [(fc, fc.mute) for fc in loc_fcs]
    for fc, _ in orig_mute:
        fc.mute = True

    base = {}
    basisR = {}
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = _evaluated(obj, dg)
        base[f] = ev.matrix_world.to_translation().copy()
        pw = _evaluated(parent, dg).matrix_world if parent else Matrix.Identity(4)
        basisR[f] = (pw @ mpi).to_3x3()

    # ---------- 2) 取消静音，采实际 ----------
    for fc, m in orig_mute:
        fc.mute = m

    real = {}
    ownR = {}
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = _evaluated(obj, dg)
        real[f] = ev.matrix_world.to_translation().copy()
        ownR[f] = ev.matrix_world.to_3x3()

    # ---------- 3) 逐帧比对 ----------
    # 判读用三个量（⚠️ 不要用"逐帧步进方向 vs 轴方向"：目标轴随时间旋转时，
    #   位移向量本身就在转，基准轨迹也在动，该指标必然误报）
    #   ① 位置 vs 理想轨迹
    #   ② 沿轴投影 vs 期望距离
    #   ③ 垂轴分量（= 真正判断"有没有跑偏轴"的量）
    worst_pos = 0.0
    worst_pos_f = None
    worst_along = 0.0
    worst_along_f = None
    worst_perp = 0.0
    worst_perp_f = None
    worst_perp_rel = 0.0
    for f in frames:
        mw = Matrix.Translation(real[f]) @ ownR[f].to_4x4()
        target_dir = axis_world(f, mw, basisR[f])
        dd = _interp_d(f, KEYS)
        ideal = base[f] + target_dir * dd
        e = (real[f] - ideal).length
        if e > worst_pos:
            worst_pos, worst_pos_f = e, f
        disp = real[f] - base[f]
        along = disp.dot(target_dir)
        perp = (disp - target_dir * along).length
        if abs(along - dd) > worst_along:
            worst_along, worst_along_f = abs(along - dd), f
        if perp > worst_perp:
            worst_perp, worst_perp_f = perp, f
        if abs(dd) > 1e-6:
            worst_perp_rel = max(worst_perp_rel, perp / abs(dd))

    samp = [frames[0]] + [f for f in frames if (f - frames[0]) % max(1, len(frames) // 6) == 0][1:] + [frames[-1]]
    samp = sorted(set(samp))
    print()
    print("--- 采样点 ---")
    for f in samp:
        mw = Matrix.Translation(real[f]) @ ownR[f].to_4x4()
        target_dir = axis_world(f, mw, basisR[f])
        disp = real[f] - base[f]
        along = disp.dot(target_dir)
        perp = (disp - target_dir * along).length
        print(f"  f={f:>4}  期望距离={_interp_d(f, KEYS):+9.4f}  实际位移="
              f"({disp.x:+.4f},{disp.y:+.4f},{disp.z:+.4f}) |{disp.length:8.4f}|"
              f"  沿轴={along:+9.4f}  垂轴={perp:.6f}  轴方向="
              f"({target_dir.x:+.4f},{target_dir.y:+.4f},{target_dir.z:+.4f})")

    print()
    print("--- 判定 ---")
    print(f"① 位置 vs 理想轨迹 最大偏差        : {worst_pos:.6e} 单位 @f{worst_pos_f}"
          f"   {'✅' if worst_pos < TOL_POS else '❌'}")
    print(f"② 沿轴投影 vs 期望距离 最大误差    : {worst_along:.6e} 单位 @f{worst_along_f}"
          f"   {'✅' if worst_along < TOL_POS else '❌'}")
    print(f"③ 垂轴分量 最大绝对值              : {worst_perp:.6e} 单位 @f{worst_perp_f}"
          f"   （相对位移最大 {worst_perp_rel * 100:.4f}%）   {'✅' if worst_perp < TOL_POS else '❌'}")
    print(f"(阈值: 位置/投影/垂轴 {TOL_POS:g} 单位)")
    print("判读要点：③ 垂轴分量才是「有没有偏离目标轴」的直接量；")
    print("         目标轴随时间旋转时，逐帧步进方向必然不等于轴方向（轴自己在转），别用那个指标判失败。")

    scene.frame_set(saved_frame)
    print()
    print("(已恢复原帧:", saved_frame, " 静音状态已还原)")


main()
