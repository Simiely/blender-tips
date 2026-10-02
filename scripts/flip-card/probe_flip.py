# -*- coding: utf-8 -*-
"""
分体翻页牌 —— 只读诊断

排查两类高发问题:
  A. 重开后卡片歪斜 → 看「残留角度」(正常应为 0 或 360 的整数倍;61879° 说明驱动漏了 radians)
  B. 卡片姿态是不是竖直 → 看 bbox 尺寸(竖直时应为 0.01 / 0.08 / 0.12)
另报:当前帧、处理器是否还在(重开必丢)、驱动是否装了、use_scripts_auto_execute 状态。
"""
import bpy
import math
from mathutils import Vector

scene = bpy.context.scene
print("文件:", bpy.data.filepath or "(未保存)")
print("当前帧:", scene.frame_current, "| is_dirty:", bpy.data.is_dirty)
print("use_scripts_auto_execute:", bpy.context.preferences.filepaths.use_scripts_auto_execute,
      "  ← False 表示 SCRIPTED 驱动被静默屏蔽")
print("frame_change 处理器:", [getattr(h, "__name__", "?") for h in bpy.app.handlers.frame_change_post])

pivots = sorted([o for o in bpy.data.objects if 'flip_delay' in o], key=lambda p: p.name)
print("轴数量:", len(pivots))

bad = []
for p in pivots:
    ang = math.degrees(p.rotation_euler[1])
    mod = round(ang % 360, 1)
    if 0.5 < mod < 359.5:
        bad.append((p.name, round(ang, 1), mod))
print("A. 残留非整数圈角度: %d / %d %s" % (len(bad), len(pivots),
      "(若数值 ~61879 就是驱动漏 radians)" if bad else ""))
for b in bad[:8]:
    print("     ", b)

print("B. 卡片姿态抽样(dev=0 为竖直轴对齐):")
for p in pivots[:4] + pivots[-2:]:
    c = bpy.data.objects.get(p.get("flip_card", "")) if "flip_card" in p else None
    if c:
        cs = [c.matrix_world @ Vector(v) for v in c.bound_box]
        d = tuple(round(max(v[i] for v in cs) - min(v[i] for v in cs), 4) for i in range(3))
        dev = max(abs(c.matrix_world[i][j] - (1.0 if i == j else 0.0))
                  for i in range(3) for j in range(3))
        print("   %s -> %s | 尺寸 %s (竖直 0.01/0.08/0.12) | 旋转偏差 %.4f"
              % (p.name, c.name, d, dev))
print("[PROBE DONE]")
