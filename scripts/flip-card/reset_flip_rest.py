# -*- coding: utf-8 -*-
"""
分体翻页牌 —— 存盘前必跑:角度归零 + 跳到静止帧

为什么必须跑:
  frame_change 处理器是**运行时**注册的,不会写进 .blend。保存那一刻各轴停在什么角度,
  文件里就是什么角度;重开后没有处理器、驱动又被信任机制挡着 ⇒ 卡片僵在半翻姿态(实测:
  全部残留 61879° 是因为驱动表达式漏了 radians 换算,双重问题叠加)。

本脚本:
  1. 所有轴 rotation_euler 归零(== 初始朝向)
  2. 播放头跳到一个"所有卡都翻完"的静止帧
  3. 核验卡片 bbox 回到竖直尺寸
"""
import bpy
from mathutils import Vector

scene = bpy.context.scene
pivots = sorted([o for o in bpy.data.objects if 'flip_delay' in o], key=lambda p: p.name)
print("轴数量:", len(pivots))

for p in pivots:
    p.rotation_euler = (0.0, 0.0, 0.0)

period = int(pivots[0].get("flip_period", 60)) if pivots else 60
rest = period - 1
scene.frame_set(rest)


def dims(c):
    cs = [c.matrix_world @ Vector(v) for v in c.bound_box]
    return tuple(round(max(v[i] for v in cs) - min(v[i] for v in cs), 4) for i in range(3))


bad = []
for p in pivots:
    c = bpy.data.objects.get(p.get("flip_card", "")) if "flip_card" in p else None
    if c:
        d = dims(c)
        if abs(d[0] - 0.01) > 0.004 or abs(d[1] - 0.08) > 0.004 or abs(d[2] - 0.12) > 0.004:
            bad.append((p.name, c.name, d))
print("静止帧 %d 核验:" % rest, "全部竖直 OK (%d 张)" % len(pivots) if not bad else "FAIL → %s" % bad[:5])
print("[RESET DONE] 现在可以 Ctrl+S 保存了")
