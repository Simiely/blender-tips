# -*- coding: utf-8 -*-
"""
按材质合并 —— 自测台 · 校验（冒烟测试第 3 步）

读 build_smoke_scene.py 记下的基线，逐项比对合并结果。

通过判据（全 OK 才算逻辑正确）：
    顶点数一致 / 面数一致 / 对象数 = 期望值 / 世界包围盒最大偏差 < 1e-3
    / 空物体收敛正确 / 被跳过的风险组成员原样保留

「世界包围盒偏差 ≈ 0」是核心判据 —— 它证明父子 / 旋转 / 缩放都处理对了，
合并没有把模型拆散或位移。

运行位置（系统命令行）：
    blender.exe --background --factory-startup <合并产物.blend> --python verify_smoke.py
"""

import bpy, json, os

exp = json.load(open(os.path.join(os.getcwd(), "smoke_expected.json"), encoding="utf-8"))
objs = [o for o in bpy.data.objects if o.type == "MESH" and o.data]


def world_bbox(objs):
    mn = [1e9] * 3
    mx = [-1e9] * 3
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
    return [round(x, 4) for x in mn], [round(x, 4) for x in mx]


bpy.context.view_layer.update()
# ★ 只统计**视图层内**的对象（与 build_smoke_scene.py 同口径）：
#   躺在 excluded 集合里的对象，depsgraph 不会求值，matrix_world 停在旧值。
vl_names = {o.name for o in bpy.context.view_layer.objects}
mn, mx = world_bbox([o for o in objs if o.name in vl_names])
got = {
    "mesh_objects": len(objs),
    "verts": sum(len(o.data.vertices) for o in objs),
    "polys": sum(len(o.data.polygons) for o in objs),
    "bbox_min": mn, "bbox_max": mx,
    "empties": len([o for o in bpy.data.objects if o.type == "EMPTY"]),
}
print("==EXPECTED==", json.dumps(exp, ensure_ascii=False))
print("==GOT=======", json.dumps(got, ensure_ascii=False))
print("==NAMES=====", sorted(o.name for o in objs))
print("==VERSION_LIST==")
for o in objs:
    print("  ", o.name, "| verts", len(o.data.vertices), "| polys", len(o.data.polygons),
          "| mats", [m.name if m else None for m in o.data.materials])

ok = True


def chk(label, cond, detail=""):
    global ok
    print("==CHECK_%s==" % label, "OK" if cond else "FAIL " + str(detail))
    ok = ok and cond


chk("verts", exp["verts"] == got["verts"], "%s -> %s" % (exp["verts"], got["verts"]))
chk("polys", exp["polys"] == got["polys"], "%s -> %s" % (exp["polys"], got["polys"]))
chk("groupcount", got["mesh_objects"] == exp["groups_expected"],
    "期望 %s 实际 %s（合并前 %s）"
    % (exp["groups_expected"], got["mesh_objects"], exp.get("mesh_objects_before")))

d = max(abs(a - b) for a, b in
        zip(exp["bbox_min"] + exp["bbox_max"], got["bbox_min"] + got["bbox_max"]))
chk("position", d < 1e-3, "最大偏差 %.6f" % d)
print("      世界包围盒最大偏差 %.6f" % d)

chk("empties", got["empties"] == exp["empties"],
    "期望 %s 实际 %s" % (exp["empties"], got["empties"]))

# 风险组（跨集合 / 不在视图层）必须**原样保留**：对象还在，且顶点 / 面一个不差
for n, vp in (exp.get("risky_kept") or {}).items():
    o = bpy.data.objects.get(n)
    good = (o is not None and o.type == "MESH"
            and len(o.data.vertices) == vp[0] and len(o.data.polygons) == vp[1])
    chk("risky_kept_" + n, good,
        "应原样保留 %s (顶点%d/面%d)" % (n, vp[0], vp[1]))

# 排除对象必须还在
for n in exp.get("excluded") or []:
    chk("excluded_kept_" + n, n in bpy.data.objects, "排除对象丢失")

print("==SMOKE_RESULT==", "PASS" if ok else "FAIL")
print("==DONE==")
