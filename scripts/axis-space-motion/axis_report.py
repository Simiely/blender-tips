"""axis_report.py — 诊断一个对象的「位移坐标系」：K location 到底会往哪个方向走？

只读，不改场景数据。

经桥跑法：
    python send.py scripts/axis-space-motion/axis_report.py 9877

核心结论（本脚本就是在量它）：
    matrix_basis = T(location) @ R @ S      —— 平移在最左端
    ⇒ location 的坐标系 = 父级世界矩阵 @ matrix_parent_inverse（简称"父空间基底"）
      · 不是世界空间
      · 也不是对象自身空间
      · 对象自身的 rotation / delta_rotation 改变不了它
"""
import bpy
import math
from mathutils import Vector, Matrix

# ==================== 配置 ====================
TARGET = "相机基点"        # 要诊断的对象名；留空字符串则用当前活动对象
SAMPLE_FRAMES = None      # None = 自动取 [当前帧, 首帧, 末帧, 各区间中点]
TOL_DEG = 0.01            # 角度容差（度）
# ==============================================


def _fcurves_of(obj):
    ad = obj.animation_data
    if not (ad and ad.action):
        return []
    act = ad.action
    try:
        out = list(act.fcurves)
        if out:
            return out
    except Exception:
        pass
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def _ang(a, b):
    a = Vector(a).normalized()
    b = Vector(b).normalized()
    if a.length < 1e-12 or b.length < 1e-12:
        return float("nan")
    return math.degrees(a.angle(b))


def _rot_angle_deg(r_a, r_b):
    """两个 3x3 旋转之间的小角度差（良态式，不用 2*acos(dot)）。"""
    q = (r_a.to_quaternion() @ r_b.to_quaternion().inverted())
    v = Vector((q.x, q.y, q.z))
    return math.degrees(2.0 * math.asin(min(1.0, v.length)))


def _evaluated(obj, dg):
    try:
        return obj.evaluated_get(dg)
    except Exception:
        return obj


def main():
    scene = bpy.context.scene
    saved_frame = scene.frame_current
    obj = bpy.data.objects.get(TARGET) if TARGET else bpy.context.object
    if obj is None:
        print("ERR 找不到对象:", TARGET)
        return

    print("=" * 66)
    print("位移坐标系诊断")
    print("=" * 66)
    print("场景帧:", saved_frame, " 范围:", scene.frame_start, "->", scene.frame_end)

    parent = obj.parent
    mpi = obj.matrix_parent_inverse.copy()

    print()
    print("--- 对象 ---")
    print("名称      :", obj.name, f"({obj.type})")
    print("父级      :", parent.name if parent else "(无父级 → 父空间基底 = 世界)")
    print("parent_type:", obj.parent_type)
    print("rotation_mode:", obj.rotation_mode)
    print("location  :", tuple(round(v, 8) for v in obj.location))
    print("euler(度) :", tuple(round(math.degrees(v), 6) for v in obj.rotation_euler))
    print("scale     :", tuple(round(v, 8) for v in obj.scale))
    print("delta_loc :", tuple(round(v, 8) for v in obj.delta_location))
    print("delta_rot(度):", tuple(round(math.degrees(v), 6) for v in obj.delta_rotation_euler))
    print("MPI 平移  :", tuple(round(v, 6) for v in mpi.to_translation()))
    print("MPI 旋转(度):", tuple(round(math.degrees(v), 4) for v in mpi.to_euler('XYZ')))
    act = obj.animation_data.action if obj.animation_data else None
    print("action    :", act.name if act else None)
    loc_fcs = [fc for fc in _fcurves_of(obj) if fc.data_path == "location"]
    if loc_fcs:
        for fc in loc_fcs:
            kps = [(round(k.co[0], 4), round(k.co[1], 6)) for k in fc.keyframe_points]
            print(f"   location[{fc.array_index}]  n={len(fc.keyframe_points)}  kps={kps[:10]}")
    else:
        print("   (location 无关键帧)")
    print("constraints:", [(c.type, c.name) for c in obj.constraints] or "无")

    frames = SAMPLE_FRAMES or sorted({scene.frame_start, saved_frame,
                                      scene.frame_end,
                                      (scene.frame_start + scene.frame_end) // 2})

    print()
    print("--- 采样帧:", frames, "---")

    def basis_rot(f, dgl=None):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        p = _evaluated(parent, dg) if parent else None
        pw = p.matrix_world.copy() if p else Matrix.Identity(4)
        return (pw @ mpi).to_3x3()

    def own_rot(f):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        return _evaluated(obj, dg).matrix_basis.to_3x3()

    rows = []
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = _evaluated(obj, dg)
        mw = ev.matrix_world.copy()          # ⚠️ 必须 .copy()：不拷贝则循环结束后所有行都读到最后一帧的值
        pw = _evaluated(parent, dg).matrix_world if parent else Matrix.Identity(4)
        R_basis = (pw @ mpi).to_3x3()
        R_own = ev.matrix_basis.to_3x3()
        rows.append((f, mw, R_basis, R_own))

    R0 = rows[0][2]
    own0 = rows[0][3]
    print("父空间基底（= K location 所在的坐标系）:")
    for f, mw, R_basis, R_own in rows:
        ax = R_basis @ Vector((1, 0, 0))
        az = R_basis @ Vector((0, 0, 1))
        print(f"  f={f:>4}  X→世=({ax.x:+.4f},{ax.y:+.4f},{ax.z:+.4f})"
              f"  Z→世=({az.x:+.4f},{az.y:+.4f},{az.z:+.4f})")
    print("对象自身的轴（在世界里）：")
    for f, mw, R_basis, R_own in rows:
        az = mw.to_3x3() @ Vector((0, 0, 1))
        print(f"  f={f:>4}  自身Z→世=({az.x:+.4f},{az.y:+.4f},{az.z:+.4f})")

    basisZ = (R0 @ Vector((0, 0, 1))).normalized()
    ownZ = (rows[0][1].to_3x3() @ Vector((0, 0, 1))).normalized()
    worldZ = Vector((0, 0, 1))

    basis_var = max(_rot_angle_deg(R0, r[2]) for r in rows)
    own_var = max(_rot_angle_deg(own0, r[3]) for r in rows)

    print()
    print("--- 判据（K location[2] 实际会往哪走）---")
    a_own = _ang(basisZ, ownZ)
    a_world = _ang(basisZ, worldZ)
    print(f"K location[2] 方向 vs 对象自身Z : {a_own:8.4f} 度"
          f"   {'← 一致，K location[2] 就是「沿自身轴」' if a_own < TOL_DEG else '← 不一致，K location[2] 走的是父空间轴，不是自身轴'}")
    print(f"K location[2] 方向 vs 世界Z    : {a_world:8.4f} 度"
          f"   {'← 一致，K location[2] 就是「沿世界轴」' if a_world < TOL_DEG else '← 不一致，K location[2] 不是世界轴'}")
    print(f"对象自身Z轴 vs 世界Z           : {_ang(ownZ, worldZ):8.4f} 度"
          f"   （这就是「物体轴向与世界轴不一致」的偏角）")
    print(f"父空间基底朝向随时间变化(采样内最大) : {basis_var:.4f} 度"
          f"   {'（恒定 → 换算一次即可）' if basis_var < TOL_DEG else '（随时间变 → 世界轴方案必须 bake 或约束）'}")
    print(f"对象自身朝向随时间变化(采样内最大)   : {own_var:.4f} 度"
          f"   {'（恒定）' if own_var < TOL_DEG else '（随时间变 → 自身轴方案也要 bake）'}")

    print()
    print("--- 建议 ---")
    if a_own < TOL_DEG:
        print("· 沿【自身轴】位移：直接 K", obj.name + ".location 即可")
        print("  （该对象自身旋转为 0 ⇒ 自身轴与父空间轴重合，K location[2] 就是沿自身轴）")
    else:
        print("· 沿【自身轴】位移：对象自身有旋转 → 推荐「朝向层 + 位移层」分层")
        print("  （朝向放上层、位移层自身旋转恒 0，然后 K 位移层的 location[2]）")
        print("  不想加层就用换算：location = R_own @ AXIS * d（本包 key_axis_motion.py 的 SPACE='SELF' 自动算）")
    if a_world < TOL_DEG:
        print("· 沿【世界轴】位移：直接 K location 即可（父空间基底已与世界一致）")
    else:
        print("· 沿【世界轴】位移：父空间基底与世界差 %.2f 度 → 三选一" % a_world)
        print("  1) 换算：key_axis_motion.py 的 SPACE='WORLD'（基底恒定时 direct，随时间变自动 bake）")
        print("  2) 约束：加一个无父级的世界空间空对象 K 好动画 + 本对象 Copy Location")
        print("     （owner_space='WORLD', target_space='WORLD', use_offset=True）—— 动态也精确")
        print("  3) 静态父级时可插一层「抵消旋转」的空对象，把位移层变成世界对齐")

    scene.frame_set(saved_frame)
    print()
    print("(已恢复原帧:", saved_frame, ")")


main()
