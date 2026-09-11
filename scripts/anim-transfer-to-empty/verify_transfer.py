# =============================================================================
# verify_transfer.py —— 动态转移的「改前录基线 / 改后逐帧对基线」验证器
#
# 为什么需要: 转移动画最怕"看起来对、其实差一点"。唯一可靠的做法是把改动前的
#             逐帧世界矩阵存成磁盘基线,改完再逐帧比对。本脚本就是这个工具。
#
# 用法(两次请求,顺序不能反):
#   1) 转移前: MODE='record' 跑一次 → 写出基线 JSON
#   2) 转移后: MODE='check'  跑一次 → 逐帧对比,输出位置/旋转/角度最大偏差与结论
#
# 判读标准(实测参考值,场景坐标量级 ~25 单位):
#   位置偏差   ≤ 1e-5 单位   → float32 精度级,可视为不变(约 2 ulp)
#   旋转块元素 ≤ 1e-6        → float32 机器精度 eps = 1.19e-07,正常应在 1e-7 量级
#   角度偏差   ≤ 1e-4 度     → 良态指标,正常应在 1e-5 度量级
#
# ⚠️ 验收指标的坑: 不要用 2*acos(qa.dot(qb)) 算角度差 —— dot≈1 时 acos 病态放大,
#    实测会把 3.8e-06 的矩阵差虚报成 0.04°(放大 100+ 倍),误判成"有漂移"。
#    本脚本用旋转矩阵元素最大差 + 良态式 2*asin(sqrt(x²+y²+z²))。
#
# 注意: 桥接环境 exec 时 __name__ 为 'builtins',不要用 __main__ 守卫
# =============================================================================

import bpy
import json
import math
from mathutils import Matrix

# ------------------------------ CONFIG ------------------------------
TARGET = '摄像机x02_151-370'                        # 要验证的对象名
MODE = 'record'                                     # 'record' 录基线 | 'check' 对基线
JSON_PATH = '//_anim_transfer_baseline.json'        # 相对 // = 工程文件目录(仓库规范)
STEP = 1                                            # 采样步长(1 = 逐帧;大场景可调 5)
VERBOSE = True


def _abs_path(p):
    return p if not p.startswith('//') else bpy.path.abspath(p)


def _load(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return {int(k): v for k, v in json.load(fh).items()}


def _record(obj, scene, path):
    frames = list(range(scene.frame_start, scene.frame_end + 1, max(1, STEP)))
    if frames[-1] != scene.frame_end:
        frames.append(scene.frame_end)
    data = {}
    for f in frames:
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        mw = obj.evaluated_get(dg).matrix_world
        data[str(f)] = [[mw[i][j] for j in range(4)] for i in range(4)]
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh)
    print(f'基线已写出: {path}')
    print(f'  对象: {obj.name}  帧数: {len(data)}  范围: {frames[0]} -> {frames[-1]}')
    print('  (下一步: 改 CONFIG 的 MODE 为 \'check\' 再跑一次)')


def _check(obj, scene, path):
    base = _load(path)
    worst_pos = (0.0, None)     # 位置分量最大差
    worst_rot = (0.0, None)     # 旋转块元素最大差
    worst_ang = (0.0, None)     # 良态角度偏差(度)
    for f in sorted(base):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        mw = obj.evaluated_get(dg).matrix_world
        b = Matrix([[base[f][r][c] for c in range(4)] for r in range(4)])
        pos = max(abs(mw[r][3] - b[r][3]) for r in range(3))
        rot = max(abs(mw[r][c] - b[r][c]) for r in range(3) for c in range(3))
        qr = mw.to_quaternion() @ b.to_quaternion().inverted()
        ang = math.degrees(2.0 * math.asin(
            min(1.0, math.sqrt(qr.x ** 2 + qr.y ** 2 + qr.z ** 2))))
        if pos > worst_pos[0]:
            worst_pos = (pos, f)
        if rot > worst_rot[0]:
            worst_rot = (rot, f)
        if ang > worst_ang[0]:
            worst_ang = (ang, f)
        if VERBOSE:
            print(f'  f={f:>4}  位置 max|Δ|={pos:.3e}  旋转块 max|Δ|={rot:.3e}  角度={ang:.3e}°')

    print('=== 结论 ===')
    print(f'对比帧数           : {len(base)}')
    print(f'位置分量最大偏差   : {worst_pos[0]:.3e} @f{worst_pos[1]}')
    print(f'旋转块元素最大偏差 : {worst_rot[0]:.3e} @f{worst_rot[1]}')
    print(f'角度最大偏差       : {worst_ang[0]:.3e} 度 @f{worst_ang[1]}')
    ok = worst_pos[0] <= 1e-5 and worst_rot[0] <= 1e-6 and worst_ang[0] <= 1e-4
    print('判定: ' + ('✅ 通过 —— 世界运动逐帧不变(float32 精度级)'
                     if ok else '❌ 未通过 —— 有真实漂移,回查 父级/MPI/参考帧/是否摘净动画'))


def main():
    scene = bpy.context.scene
    obj = bpy.data.objects.get(TARGET)
    if obj is None:
        print(f'ERR 对象不存在: {TARGET}')
        return
    path = _abs_path(JSON_PATH)
    saved = scene.frame_current

    print('=== 层级现状 ===')
    chain, o = [], obj
    while o:
        chain.append(o.name)
        o = o.parent
    print('  ' + ' -> '.join(chain))
    print(f'  {obj.name}: action='
          f'{obj.animation_data.action.name if (obj.animation_data and obj.animation_data.action) else None}'
          f'  MPI平移={tuple(round(v, 6) for v in obj.matrix_parent_inverse.to_translation())}')
    print(f'  本地 loc={tuple(round(v, 6) for v in obj.location)} '
          f'rot={tuple(round(v, 6) for v in obj.rotation_euler)} '
          f'scale={tuple(round(v, 6) for v in obj.scale)}')
    print(f'  场景帧范围: {scene.frame_start} -> {scene.frame_end}   fps={scene.render.fps}')

    if MODE == 'record':
        _record(obj, scene, path)
    elif MODE == 'check':
        if not __import__('os').path.exists(path):
            print(f'ERR 基线不存在: {path}(请先在转移前跑 MODE=\'record\')')
            return
        _check(obj, scene, path)
    else:
        print(f'ERR MODE 只能是 record / check,当前为 {MODE}')

    scene.frame_set(saved)


main()
