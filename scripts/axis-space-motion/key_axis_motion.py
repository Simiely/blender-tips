"""key_axis_motion.py — 让对象沿【自身轴】或【世界轴】位移，并写成 location 关键帧

原理（一句话）：
    matrix_basis = T(location) @ R @ S，平移在最左端
    ⇒ K 出来的 location 分量属于「父空间基底」= 父级世界矩阵 @ matrix_parent_inverse
    想让位移沿哪个坐标系，就把位移量换算到父空间里：
      沿【自身轴】：loc = d · (R_own @ AXIS)          R_own = 本对象 matrix_basis 的旋转
      沿【世界轴】：loc = d · (P_basis_rot⁻¹ @ AXIS)  P_basis = 父级世界矩阵 @ MPI
      沿【父空间】：loc = d · AXIS

经桥跑法：
    python send.py scripts/axis-space-motion/key_axis_motion.py 9877
（建议配套：先跑 axis_report.py 看诊断，写完另开一次请求跑 verify_axis_motion.py）
"""
import bpy
import math
from mathutils import Vector, Matrix

# ==================== 配置 ====================
TARGET = "相机基点"          # 要写位移的对象（建议是"位移层"：自身变换全零）
SPACE = "SELF"               # "SELF" 对象自身轴 | "WORLD" 世界轴 | "PARENT" 父空间轴
AXIS = (0.0, 0.0, 1.0)       # 方向；SELF/PARENT 时是该空间内的向量，WORLD 时是世界向量
KEYS = [(151, 0.0), (480, -30.0)]    # [(帧, 距离)]，距离带符号，中间线性插值
ENGINE = "auto"              # "auto" 自动选 | "direct" 只在 KEYS 帧写 | "bake" 逐帧写
PRESERVE = True              # True = 叠加在原有 location 之上（原值 + 位移）
CLEAR_EXTRA_KEYS = True      # True = 先清掉 location 通道的旧关键帧（避免残留孤立帧）
TOL_DEG = 0.01               # 判定"坐标系是否随时间变"的容差（度）
# ==============================================


def _fcurve_collections(obj):
    ad = obj.animation_data
    if not (ad and ad.action):
        return []
    act = ad.action
    try:
        cols = [act.fcurves]
        return cols
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


def _rot_angle_deg(q_a, q_b):
    q = q_a @ q_b.inverted()
    v = Vector((q.x, q.y, q.z))
    return math.degrees(2.0 * math.asin(min(1.0, v.length)))


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

    print("=" * 66)
    print("沿指定坐标系写位移动画")
    print("=" * 66)
    print("对象:", obj.name, " 父级:", parent.name if parent else "(无 → 父空间基底 = 世界)")
    print("SPACE =", SPACE, " AXIS =", tuple(round(v, 6) for v in axis))
    print("KEYS  =", KEYS)
    print("修改前 location:", tuple(round(v, 8) for v in obj.location))
    old_fcs = _fcurves_of(obj, "location")
    for fc in old_fcs:
        kps = [(round(k.co[0], 4), round(k.co[1], 6)) for k in fc.keyframe_points]
        print(f"  旧 location[{fc.array_index}] n={len(fc.keyframe_points)} kps={kps[:10]}")

    # ---------- 坐标系采样 ----------
    def sample(f):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = _evaluated(obj, dg)
        pw = _evaluated(parent, dg).matrix_world if parent else Matrix.Identity(4)
        R_basis = (pw @ mpi).to_3x3()
        R_own = ev.matrix_basis.to_3x3()
        return R_basis, R_own, ev

    key_frames = [f for f, _ in KEYS]
    probe = sorted(set(key_frames + [(key_frames[0] + key_frames[-1]) // 2]))

    def dir_of(f):
        R_basis, R_own, _ = sample(f)
        if SPACE == "PARENT":
            return axis.copy()
        if SPACE == "SELF":
            return (R_own @ axis).normalized()
        return (R_basis.inverted() @ axis).normalized()

    dirs = {f: dir_of(f) for f in probe}
    f_ref = probe[0]
    q_ref = dirs[f_ref].to_track_quat('Z', 'Y')
    var = max(_rot_angle_deg(dirs[f].to_track_quat('Z', 'Y'), q_ref) for f in probe)

    engine = ENGINE
    if engine == "auto":
        engine = "direct" if var < TOL_DEG else "bake"
    print()
    print("位移坐标系在采样帧内的最大方向变化: %.4f 度 → ENGINE = %s%s"
          % (var, engine, "（auto 判定）" if ENGINE == "auto" else "（手动指定）"))
    print("换算出方向（父空间向量）:", tuple(round(v, 6) for v in dirs[f_ref]))
    if engine == "bake" and var >= TOL_DEG:
        print("  原因：坐标系随时间变化，两关键帧之间只做直线插值会走偏 → 逐帧写")

    # ---------- 采样原 location（PRESERVE）----------
    if engine == "direct":
        write_frames = sorted(set(key_frames))
    else:
        write_frames = list(range(min(key_frames), max(key_frames) + 1))

    dirs_w = {}
    base = {}
    for f in write_frames:
        R_basis, R_own, ev = sample(f)
        if SPACE == "PARENT":
            dv = axis.copy()
        elif SPACE == "SELF":
            dv = (R_own @ axis).normalized()
        else:
            dv = (R_basis.inverted() @ axis).normalized()
        dirs_w[f] = dv
        base[f] = Vector(ev.location) if PRESERVE else Vector((0.0, 0.0, 0.0))

    # ---------- 清旧曲线 ----------
    if CLEAR_EXTRA_KEYS:
        removed = 0
        for col in _fcurve_collections(obj):
            try:
                victims = [fc for fc in col if fc.data_path == "location"]
            except Exception:
                continue
            for fc in victims:
                col.remove(fc)
                removed += 1
        print("已清除旧 location 曲线:", removed, "条")

    # ---------- 写入 ----------
    for f in write_frames:
        d = _interp_d(f, KEYS)
        scene.frame_set(f)
        obj.location = base[f] + dirs_w[f] * d
        obj.keyframe_insert("location", frame=f)

    for fc in _fcurves_of(obj, "location"):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
        fc.update()

    new_fcs = _fcurves_of(obj, "location")
    print()
    print("写入完成：关键帧", len(write_frames), "个 × 通道", len(new_fcs), "条")
    for fc in sorted(new_fcs, key=lambda c: c.array_index):
        ks = fc.keyframe_points
        print(f"  location[{fc.array_index}]  n={len(ks)}  首=({ks[0].co[0]:.0f}, {ks[0].co[1]:.6f})"
              f"  末=({ks[-1].co[0]:.0f}, {ks[-1].co[1]:.6f})")
    d_first = _interp_d(write_frames[0], KEYS)
    d_last = _interp_d(write_frames[-1], KEYS)

    # ---------- 同请求粗检（精确验证请另开请求跑 verify_axis_motion.py）----------
    print()
    print("--- 粗检（同请求内，可能读到未刷新缓存，仅作参考）---")
    for f in (write_frames[0], write_frames[-1]):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        loc = Vector(_evaluated(obj, dg).location)
        exp = base[f] + dirs_w[f] * _interp_d(f, KEYS)
        print(f"  f={f:>4}  实际loc={tuple(round(v, 6) for v in loc)}"
              f"  期望={tuple(round(v, 6) for v in exp)}"
              f"  max|Δ|={max(abs(loc[i] - exp[i]) for i in range(3)):.3e}")

    scene.frame_set(saved_frame)
    print()
    print("距离: f%d = %.4f → f%d = %.4f" % (write_frames[0], d_first, write_frames[-1], d_last))
    print("提醒：桥只改内存不落盘 → 记得 Ctrl+S")
    print("下一步：另开一次请求跑 verify_axis_motion.py 做逐帧精确验证")


main()
