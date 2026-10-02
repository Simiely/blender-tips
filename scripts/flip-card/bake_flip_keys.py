# -*- coding: utf-8 -*-
"""
分体翻页牌 —— 烘焙成关键帧(跨工程复制 / 存盘自愈的唯一可靠方案)

为什么必须烘焙:
  frame_change 处理器是**运行时注册**的,只在当前 Blender 进程生效 ——
  存盘不带走、复制到另一个 Blender 也不带走;SCRIPTED 驱动在非受信任文件里又被静默屏蔽。
  只有 **fcurve 关键帧是纯数据**:复制、存盘、重开、Append 全部跟着走,不需要任何 Python 执行权限。

代价: 参数不能实时改了,改完要重跑本脚本重新烘焙(自定义属性保留,脚本读它们)。

本脚本:
  1. 清驱动 + 清处理器(避免两套系统打架)
  2. 按同一公式把 0→1080(3 圈)的 smoothstep 逐帧写进 rotation_euler fcurve
  3. 推帧核验角度 + 静止帧竖直核验
"""
import bpy
import math
from mathutils import Vector

scene = bpy.context.scene
pivots = sorted([o for o in bpy.data.objects if 'flip_delay' in o], key=lambda p: p.name)
print("轴数量:", len(pivots))

F0, F1 = int(scene.frame_start), int(scene.frame_end)
print("烘焙帧范围:", F0, "-", F1)

# 1. 清驱动与处理器
for p in pivots:
    if p.animation_data:
        for d_ in list(p.animation_data.drivers):
            p.animation_data.driver_remove(d_.data_path, d_.array_index)
MARK = "flip_all_cards"
for h in list(bpy.app.handlers.frame_change_post):
    if getattr(h, "__name__", "") == MARK:
        bpy.app.handlers.frame_change_post.remove(h)
print("已清驱动与处理器")

# 2. 逐轴烘焙
total_pts = 0
for p in pivots:
    per = int(p.get("flip_period", 60))
    dur = float(p.get("flip_dur", 16))
    turns = int(p.get("flip_turns", 3))
    delay = int(p.get("flip_delay", 0))
    total = math.radians(360.0 * turns)      # 弧度!
    axis = int(p.get("flip_axis", 1))

    if not p.animation_data:
        p.animation_data_create()
    act = p.animation_data.action
    if act is None:
        act = bpy.data.actions.new("FLIP_" + p.name)
        p.animation_data.action = act
    fc = act.fcurve_ensure_for_datablock(p, "rotation_euler", index=axis)   # 5.x Slotted Action 正确入口
    fc.keyframe_points.clear()

    for f in range(F0, F1 + 1):
        t = (f - delay) % per
        u = t / dur
        v = total * (3.0*u*u - 2.0*u*u*u) if u < 1.0 else total
        if u < 1.0 or t == dur or t == per - 1 or f == F0 or f == F1:   # 翻页段逐帧,静止段只打首尾
            fc.keyframe_points.insert(f, v)
            total_pts += 1
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'
    fc.update()
print("烘焙关键帧总数:", total_pts)

# 3. 推帧核验
print("--- 推帧核验(度) ---")
for f in (1, 5, 8, 16, 40, 61):
    scene.frame_set(f)
    print("frame %4d | %s" % (f, " ".join("%s:%8.1f" % (p.name[-5:], math.degrees(p.rotation_euler[1]))
                                         for p in pivots[:3])))

# 4. 静止帧竖直核验
scene.frame_set(40)
bad = []
for p in pivots:
    c = bpy.data.objects.get(p.get("flip_card", "")) if "flip_card" in p else None
    if c:
        cs = [c.matrix_world @ Vector(v) for v in c.bound_box]
        d = tuple(round(max(v[i] for v in cs) - min(v[i] for v in cs), 4) for i in range(3))
        if abs(d[0]-0.01) > 0.004 or abs(d[1]-0.08) > 0.004 or abs(d[2]-0.12) > 0.004:
            bad.append((p.name, d))
print("frame40 竖直核验:", "全部 OK (%d 张)" % len(pivots) if not bad else "FAIL → %s" % bad[:5])
scene.frame_set(1)
print("[BAKE DONE] 复制 / 存盘 / 重开都能带走动画")
