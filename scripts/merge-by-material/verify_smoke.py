# -*- coding: utf-8 -*-
"""
按材质合并 —— 自测台 · 校验(冒烟测试第 3 步)

读 build_smoke_scene.py 记下的基线,逐项比对合并结果。

通过判据(全 OK 才算逻辑正确):
    顶点数一致 / 面数一致 / 对象数=期望分组数 / 世界包围盒最大偏差 < 1e-3

「世界包围盒偏差 ≈ 0」是核心判据 —— 它证明父子 / 旋转 / 缩放都处理对了,
合并没有把模型拆散或位移。

运行位置(系统命令行):
    blender.exe --background --factory-startup <合并产物.blend> --python verify_smoke.py
"""

import bpy, json, os

exp = json.load(open(os.path.join(os.getcwd(), "smoke_expected.json"), encoding="utf-8"))
objs = [o for o in bpy.data.objects if o.type == "MESH" and o.data]

def world_bbox(objs):
    mn = [1e9] * 3; mx = [-1e9] * 3
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            for i in range(3):
                mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
    return [round(x, 4) for x in mn], [round(x, 4) for x in mx]

bpy.context.view_layer.update()
mn, mx = world_bbox(objs)
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
for k in ("verts", "polys"):
    print("==CHECK_%s==" % k, "OK" if exp[k] == got[k] else "FAIL %s -> %s" % (exp[k], got[k]))
    ok = ok and exp[k] == got[k]
print("==CHECK_GROUPCOUNT==", "OK" if got["mesh_objects"] == exp["groups_expected"]
      else "FAIL 期望%s 实际%s" % (exp["groups_expected"], got["mesh_objects"]))
d = max(abs(a - b) for a, b in zip(exp["bbox_min"] + exp["bbox_max"], got["bbox_min"] + got["bbox_max"]))
print("==CHECK_POSITION==", "OK 最大偏差 %.6f" % d if d < 1e-3 else "FAIL 最大偏差 %.6f" % d)
print("==SMOKE_RESULT==", "PASS" if ok and got["mesh_objects"] == exp["groups_expected"] and d < 1e-3 else "FAIL")
print("==DONE==")
