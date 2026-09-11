# =============================================================================
# transfer_anim.py —— 动画转移到父级空对象(「动态转移」)
#
# 场景: 某个对象(典型是相机)自己带着关键帧动画。想以后改它的运动时不再反复给它
#       本体 K 动画 —— 而是把动画整份搬到新建的空对象上,原对象退化为"纯被驱动"。
#       要求: 搬完之后,原对象的世界运动逐帧完全不变(不是"差不多",是可验证的恒等)。
#
# 最终层级(默认 ZERO_TARGET=True,推荐):
#     原父级 → <目标>_动态(承载原动画) → <目标>_基点(无动画,本地全零) → <目标>(本地全零)
#
# 原理(世界变换恒等式 world = parent.world @ matrix_parent_inverse @ basis):
#   原:  M(t) = P(t) @ mpi_old @ B(t)
#   令 空对象 D 与目标「同父级 + 同 matrix_parent_inverse + 同 basis」→ D.world(t) ≡ M(t)
#   再把动画复制给 D,目标改为:
#     ZERO_TARGET=True : 目标挂在基点 B 下(基点挂在 D 下),三者全用单位 MPI+单位 basis
#                        => M'(t) = D.world(t) @ I @ I @ I @ I = M(t)   ← 恒等(与参考帧无关)
#     ZERO_TARGET=False: 目标挂在 D 下,MPI = B(F)⁻¹,basis = B(F) 静态
#                        => M'(t) = M(t) @ B(F)⁻¹ @ B(F) = M(t)        ← 恒等
#     ⚠️ 注意通用写法是 B(F)⁻¹(局部 basis 的逆),不是 M(F)⁻¹(世界矩阵的逆);
#        只有"F 帧局部==世界"(即 mpi_old·P(F)=I,如 151 帧父级 Z 旋转为 0)时两者才相同。
#
# 用法:
#   1) 改下面 CONFIG 的 TARGET / FRAME
#   2) 先录基线(必做): 把 verify_transfer.py 的 MODE 设为 'record' 跑一次
#   3) 跑本脚本(桥: python send.py transfer_anim.py;或 Scripting 工作区 Run Script)
#   4) 再把 verify_transfer.py 的 MODE 设为 'check' 跑一次逐帧对比基线
#
# 安全: 幂等(目标已挂到 _动态 下则报错退出,不重复建对象);旧 action 默认加假用户留备份
# 注意: 桥接环境 exec 时 __name__ 为 'builtins',不要用 __main__ 守卫
# =============================================================================

import bpy
from mathutils import Matrix, Vector, Euler, Quaternion

# ------------------------------ CONFIG ------------------------------
TARGET = '摄像机x02_151-370'   # 要转移动态的对象名
FRAME = 151                    # 参考帧(取目标当前位姿做快照);None = 用场景起始帧
DRIVER_NAME = None             # 动态空对象名;None = f'{TARGET}_动态'
BASE_NAME = None               # 基点空对象名;None = f'{TARGET}_基点'
ZERO_TARGET = True             # True(推荐): 插基点空对象,目标本地变换彻底归零
KEEP_BACKUP = True             # True: 旧 action 加假用户留作备份(不删数据块)
EMPTY_DISPLAY_SIZE = 2.0
VERBOSE = True


def _log(*a):
    if VERBOSE:
        print(*a)


def _world(obj, dg):
    return obj.evaluated_get(dg).matrix_world.copy()


def _close(a, b, tol=1e-6):
    return max(abs(a[r][c] - b[r][c]) for r in range(4) for c in range(4)) < tol


def _mdiff(a, b):
    return max(abs(a[r][c] - b[r][c]) for r in range(4) for c in range(4))


def _snapshot(obj):
    """把对象本地变换(含 delta)拍成快照。matrix_basis 含 delta,必须一并带走。"""
    mode = obj.rotation_mode
    return {
        'mode': mode,
        'loc': tuple(obj.location),
        'rot_euler': tuple(obj.rotation_euler),
        'rot_quat': tuple(obj.rotation_quaternion),
        'scale': tuple(obj.scale),
        'dloc': tuple(obj.delta_location),
        'drot': tuple(obj.delta_rotation_euler),
        'dscale': tuple(obj.delta_scale),
    }


def _apply(obj, snap):
    obj.rotation_mode = snap['mode']
    obj.location = snap['loc']
    obj.rotation_euler = snap['rot_euler']
    obj.rotation_quaternion = snap['rot_quat']
    obj.scale = snap['scale']
    obj.delta_location = snap['dloc']
    obj.delta_rotation_euler = snap['drot']
    obj.delta_scale = snap['dscale']


def _zero(obj):
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    obj.delta_location = (0.0, 0.0, 0.0)
    obj.delta_rotation_euler = (0.0, 0.0, 0.0)
    obj.delta_scale = (1.0, 1.0, 1.0)


def _basis_matrix(snap):
    """由快照重建 matrix_basis(不含 delta 时即 loc@rot@scale)。"""
    m = Matrix.Translation(Vector(snap['loc']))
    if snap['mode'] == 'QUATERNION':
        m = m @ Quaternion(snap['rot_quat']).to_matrix().to_4x4()
    else:
        m = m @ Euler(snap['rot_euler'], snap['mode']).to_matrix().to_4x4()
    sc = Vector(snap['scale'])
    m = m @ Matrix.Diagonal(sc.to_4d())
    return m


def _new_empty(name, col):
    e = bpy.data.objects.new(name, None)          # None = Empty
    col.objects.link(e)
    e.empty_display_type = 'PLAIN_AXES'
    e.empty_display_size = EMPTY_DISPLAY_SIZE
    e.rotation_mode = 'XYZ'
    return e


def _bind_action(obj, act):
    """5.x Slotted Action: 必须显式绑 slot,否则曲线不生效。"""
    ad = obj.animation_data_create()
    ad.action = act
    try:
        if act.slots:
            ad.action_slot = act.slots[0]
            _log(f'   已绑 action_slot -> {act.slots[0].identifier}')
    except Exception as e:
        _log(f'   slot 绑定跳过: {e}')


def main():
    scene = bpy.context.scene
    tgt = bpy.data.objects.get(TARGET)
    if tgt is None:
        print(f'ERR 目标对象不存在: {TARGET}')
        return

    drv_name = DRIVER_NAME or (TARGET + '_动态')
    base_name = BASE_NAME or (TARGET + '_基点')

    # ---------------- 0) 前置检查 ----------------
    _log('=== 0. 前置检查 ===')
    if tgt.animation_data is None or tgt.animation_data.action is None:
        print('ERR 目标没有 action 动画 —— 没有可转移的动态。'
              '(先给它做动画,或改用 build_* 类脚本挂驱动)')
        return
    if bpy.data.objects.get(drv_name) or bpy.data.objects.get(base_name):
        print(f'ERR 已存在 {drv_name} 或 {base_name} —— 本脚本不覆盖已有对象,请先改名或清理')
        return
    if tgt.parent and tgt.parent.name == drv_name:
        print(f'ERR 目标已挂在 {drv_name} 下 —— 看起来转移过了,中止')
        return
    if tgt.constraints:
        print(f'⚠️ 目标有 {len(tgt.constraints)} 个约束,本脚本不搬运约束 —— 请自行评估')
    if tgt.animation_data.drivers:
        print(f'⚠️ 目标有 {len(tgt.animation_data.drivers)} 条驱动,本脚本只搬 action,不搬驱动')

    saved_frame = scene.frame_current
    F = FRAME if FRAME is not None else scene.frame_start
    old_act = tgt.animation_data.action
    old_parent = tgt.parent
    mpi_old = tgt.matrix_parent_inverse.copy()
    col = tgt.users_collection[0] if tgt.users_collection else scene.collection

    _log(f'目标      : {tgt.name} (type={tgt.type}, parent={old_parent.name if old_parent else None})')
    _log(f'旧 action : {old_act.name}  frame_range={tuple(old_act.frame_range)}')
    _log(f'参考帧 F  : {F}   场景范围: {scene.frame_start} -> {scene.frame_end}')

    # ---------------- 1) 在 F 帧取世界位姿 + 本地快照 ----------------
    scene.frame_set(F)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    M_F = _world(tgt, dg)
    snap = _snapshot(tgt)
    loc = M_F.to_translation()
    _log('=== 1. F 帧世界位姿 ===')
    _log(f'M(F) 平移 = ({loc.x:.6f}, {loc.y:.6f}, {loc.z:.6f})')

    # ---------------- 2) 建「动态」空对象:D 与目标同父级/同 MPI/同 basis ----------------
    _log('=== 2. 建动态空对象(复刻目标世界运动) ===')
    D = _new_empty(drv_name, col)
    D.rotation_mode = snap['mode']
    D.parent = old_parent                  # ⚠️ 先 parent
    D.parent_type = 'OBJECT'
    D.matrix_parent_inverse = mpi_old.copy()   # ⚠️ 再 MPI(反序会被 parent 赋值重置为单位阵)
    _apply(D, snap)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    d_w = _world(D, dg)
    _log(f'    D.world(F) vs M(F)  max|Δ| = {_mdiff(d_w, M_F):.3e}')
    if not _close(d_w, M_F, 1e-5):
        # 回滚:把刚建的动态空对象删掉,不留半成品
        bpy.data.objects.remove(D, do_unlink=True)
        print('ERR 动态空对象与目标在 F 帧世界位姿不一致(父级/MPI/basis 没对齐),已回滚,中止')
        return

    # ---------------- 3) 复制动画给 D(独立副本 + 绑 slot) ----------------
    _log('=== 3. 复制动画 ===')
    new_act = old_act.copy()
    new_act.name = drv_name + '动作'
    _bind_action(D, new_act)
    _log(f'    新 action={new_act.name} 与源独立: {new_act is not old_act}')

    # ---------------- 4) 目标改挂 D(或基点)+ 摘掉自身动画 ----------------
    _log('=== 4. 重挂目标并冻结自身动画 ===')
    if KEEP_BACKUP:
        old_act.use_fake_user = True
        _log(f'    旧 action 已加假用户(保留备份): {old_act.name}')
    tgt.animation_data_clear()

    if ZERO_TARGET:
        B = _new_empty(base_name, col)
        B.parent = D
        B.parent_type = 'OBJECT'
        B.matrix_parent_inverse = Matrix.Identity(4)
        _zero(B)
        tgt.parent = B                              # ⚠️ 先 parent
        tgt.parent_type = 'OBJECT'
        tgt.matrix_parent_inverse = Matrix.Identity(4)   # ⚠️ 再 MPI
        _zero(tgt)
        _log(f'    基点 {B.name}: parent=D, 单位 MPI/单位 basis')
    else:
        tgt.parent = D                              # ⚠️ 先 parent
        tgt.parent_type = 'OBJECT'
        # 通用解 = B(F)⁻¹(basis 的逆);M(F)⁻¹ 只在"F 帧局部==世界"时等价
        bm = _basis_matrix(snap)
        tgt.matrix_parent_inverse = bm.inverted()   # ⚠️ 再 MPI
        _apply(tgt, snap)
        _log(f'    MPI = B(F)⁻¹ 平移 = {tuple(round(v, 6) for v in tgt.matrix_parent_inverse.to_translation())}')

    bpy.context.view_layer.update()

    # ---------------- 5) 回读自检(同请求内为缓存值,仅作粗检) ----------------
    _log('=== 5. 自检(粗检,精确验证请用 verify_transfer.py) ===')
    dg = bpy.context.evaluated_depsgraph_get()
    _log(f'    目标 parent={tgt.parent.name}  MPI平移='
         f'{tuple(round(v, 6) for v in tgt.matrix_parent_inverse.to_translation())}')
    _log(f'    目标 loc/scale={tuple(round(v, 6) for v in tgt.location)} / '
         f'{tuple(round(v, 6) for v in tgt.scale)}')
    _log(f'    目标 anim_data={tgt.animation_data}  (None = 已摘掉自身动画)')
    _log(f'    动态空对象 anim_data={D.animation_data.action.name if D.animation_data else None}')
    _log(f'    目标世界(F) vs M(F) max|Δ| = {_mdiff(_world(tgt, dg), M_F):.3e}')

    scene.frame_set(saved_frame)
    print('DONE —— 请 Ctrl+S 存盘,再跑 verify_transfer.py(MODE=\'check\')逐帧验证')


main()
