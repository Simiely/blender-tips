# -*- coding: utf-8 -*-
"""只读侦察：径向「内收多脉冲」材质的目标几何与现状

跑法（经 9877 桥）：python send.py probe_target_size.py
不做任何修改。输出可直接用来定「间距」与「计数基准」。

会报告：
  · 每个网格的世界包围盒 / span / 面中心 / 各顶点到圆心的 r
  · 并集中心（= 控制器应该放哪）＝ 与姊妹控制器位置的一致性
  · ★ 内切圆半径（半宽）与角点半径 R_max —— 环数约束的两种基准，比值应 ≈ √2
  · 现有材质槽、控制器候选、文本块（排查命名撞车）
"""
import bpy
from mathutils import Vector

# ============================ 配置区 ============================
COL_NAME  = "立体灯光材质"                    # 目标集合
PLANES    = ["平面.001", "平面.002", "平面.003"]  # 目标网格（按名字精确取）
CTRL_OLD  = "立体灯光_脉冲控制"                # 姊妹控制器（取圆心基准；可留空）
# ==============================================================

D = bpy.data

col = D.collections.get(COL_NAME)
print("=== 集合 ===")
print("  %s 存在 = %s | 直接对象 = %d"
      % (COL_NAME, col is not None, len(col.objects) if col else 0))

print()
print("=== 姊妹控制器（圆心基准）===")
ctl = D.objects.get(CTRL_OLD) if CTRL_OLD else None
CTR = Vector(ctl.location) if ctl is not None else None
print("  %s 存在 = %s | loc = %s"
      % (CTRL_OLD, ctl is not None,
         tuple(round(x, 4) for x in CTR) if CTR else None))

print()
print("=== 目标网格几何 ===")
pts = []
for pn in PLANES:
    ob = D.objects.get(pn)
    if ob is None or ob.type != 'MESH':
        print("  !! 缺失或非网格: %s" % pn)
        continue
    mw = ob.matrix_world
    ps = [mw @ v.co for v in ob.data.vertices]
    pts += ps
    xs = [p.x for p in ps]; ys = [p.y for p in ps]; zs = [p.z for p in ps]
    span = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    ctr = sum(ps, Vector((0, 0, 0))) / len(ps)
    nrm = (mw.to_3x3() @ ob.data.polygons[0].normal).normalized()
    print("  %-12s verts=%-3d faces=%-3d mesh_users=%d"
          % (pn, len(ob.data.vertices), len(ob.data.polygons), ob.data.users))
    print("      span = (%.4f, %.4f, %.4f) | 世界法线 = %s"
          % (span[0], span[1], span[2], tuple(round(x, 4) for x in nrm)))
    print("      面中心 = %s" % (tuple(round(x, 4) for x in ctr),))
    print("      loc=%s scale=%s rot=%s"
          % (tuple(round(x, 4) for x in ob.location),
             tuple(round(x, 4) for x in ob.scale),
             tuple(round(x, 4) for x in ob.rotation_euler)))
    if CTR is not None:
        rs = sorted(round((p - CTR).length, 4) for p in ps)
        print("      到圆心 r（各自）= %s" % rs)
    print("      槽 = %s" % [s.material.name if s.material else None
                            for s in ob.material_slots])

if not pts:
    raise SystemExit("没有量到任何顶点")

print()
print("=== 汇总 ===")
xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
center = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                 (min(zs) + max(zs)) / 2))
span_all = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
print("  并集中心 = (%.4f, %.4f, %.4f)   ← 控制器应该放这里"
      % (center.x, center.y, center.z))
print("  并集 span = (%.4f, %.4f, %.4f)" % span_all)
if CTR is not None:
    print("  与姊妹控制器偏差 = %.4f" % (center - CTR).length)

# ★ 两种计数基准
half_w = max(span_all) / 2.0
R_max = max((p - CTR).length for p in pts) if CTR is not None else None
print()
print("  ★ 内切圆半径（半宽）R_ref(CIRCLE) = %.4f" % half_w)
if R_max is not None:
    print("  ★ 角点半径        R_ref(CORNER) = %.4f" % R_max)
    print("  ★ 两者比值 = %.4f（正方形应为 √2 ≈ 1.4142）" % (R_max / half_w))
    print("  ⇒ 环数约束必须选基准：按角点定 N 条，圆上会只剩约 N/%.3f 条"
          % (R_max / half_w))

print()
print("=== 控制器候选 / 文本块（排查命名撞车）===")
for ob in D.objects:
    if ob.type == 'EMPTY' and ob.keys():
        ks = sorted(k for k in ob.keys() if k != "_RNA_UI")
        print("  EMPTY %-24s keys=%s" % (ob.name, ks))
for t in D.texts:
    print("  文本块 %-28s use_module=%s 行数=%d"
          % (t.name, t.use_module, len(t.lines)))
