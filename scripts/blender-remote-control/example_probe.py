# ============================================================
#  示例:探查场景中所有相机及其动画关键帧
#  兼容 Blender 5.2(Slotted Action API)与旧版(4.x fcurves)
#
#  用法:
#    python send.py example_probe.py
#  输出:
#    每个相机: 名称 / 所属 Action / 曲线条数 / 每通道关键帧(帧号+插值)
# ============================================================

import bpy

print('=== 场景相机与动画探查 ===')
print('Blender 版本:', bpy.app.version_string)
print('当前文件:', bpy.data.filepath or '(未保存)')
print()

cams = [o for o in bpy.data.objects if o.type == 'CAMERA']
if not cams:
    print('场景中没有相机对象')
else:
    for cam in cams:
        print(f'相机: {cam.name} | 位置: {cam.location[:]}')

# 关键帧曲线读取(兼容 5.2 slotted action 与 4.x)
def get_fcurves(datablock, action):
    """返回 (channel_label, frame, interpolation) 列表。"""
    out = []
    if action is None:
        return out
    try:
        # Blender 5.2+: slotted action
        if hasattr(action, 'fcurve_ensure_for_datablock'):
            # 常见动画通道:位置/旋转/缩放
            paths = [
                ('location',       (0, 1, 2), 'X', 'Y', 'Z'),
                ('rotation_euler', (0, 1, 2), 'X', 'Y', 'Z'),
                ('scale',          (0, 1, 2), 'X', 'Y', 'Z'),
            ]
            for data_path, idxs, *labels in paths:
                for i, label in zip(idxs, labels):
                    fcu = action.fcurve_ensure_for_datablock(
                        datablock, data_path, index=i)
                    if fcu is not None and fcu.keyframe_points:
                        frames = [(kp.co[0], kp.interpolation)
                                  for kp in fcu.keyframe_points]
                        out.append((f'{data_path}[{label}]', frames))
        # Blender 4.x: 传统 fcurves
        elif hasattr(action, 'fcurves'):
            for fcu in action.fcurves:
                if fcu.keyframe_points:
                    frames = [(kp.co[0], kp.interpolation)
                              for kp in fcu.keyframe_points]
                    out.append((fcu.data_path, frames))
    except Exception as e:
        out.append(('ERROR', [(str(e), '')]))
    return out

print()
for cam in cams:
    anim = cam.animation_data
    if anim is None or anim.action is None:
        print(f'相机 {cam.name}: 无动画')
        continue
    action = anim.action
    print(f'相机 {cam.name}: Action = {action.name}')
    for label, frames in get_fcurves(cam, action):
        detail = ', '.join(f'帧{f[0]:.0f}={f[1]}' for f in frames)
        print(f'  {label}: {len(frames)} 个关键帧 | {detail}')
    print()

print('=== 完成 ===')
