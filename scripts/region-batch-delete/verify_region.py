# -*- coding: utf-8 -*-
"""③ 复核：**重开另存后的新文件**，用同一套判据重算覆盖区残留（判据必须 == 0）。

    blender.exe --background <新文件.blend> --python verify_region.py -- [OUT_DIR]

why 重开：进程内计数 ≠ 文件能正常打开，且存盘会丢弃 `users==0` 的数据块
（本案例内存 177156 → 重开 177155）。只有重开后的数字才是交付数字。
"""
import bpy
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from region_geom import marker_rects, world_xy_bbox, make_judge   # noqa: E402

CONFIG = dict(
    MARKER_KEY=r"Z轴覆盖范围",
    OUT_DIR=r"C:\path\to\workdir",
    EXPECT_OBJECTS=None,        # 干跑数 − 待删数（例如 177156）；允许 ±10 的存盘丢弃
    EXPECT_TOLERANCE=10,
)


def out_dir():
    a = sys.argv
    if "--" in a:
        rest = a[a.index("--") + 1:]
        if rest:
            return rest[0]
    return CONFIG["OUT_DIR"]


def main():
    t0 = time.time()
    objs = list(bpy.data.objects)
    types = {}
    residual = 0
    residual_by_type = {}
    top_level = 0
    bb_min = [1e30] * 3
    bb_max = [-1e30] * 3

    rects = None
    if any(o.type == 'MESH' and CONFIG["MARKER_KEY"] in o.name for o in objs):
        rects = marker_rects(objs, CONFIG["MARKER_KEY"])
    judge = make_judge(rects) if rects else None
    marker_note = "标记体仍在（%d 个）" % len(rects) if rects else "★ 标记体已被删除 ⇒ 无法复算残留，只出计数"

    if judge:
        for o in objs:
            rb = world_xy_bbox(o.matrix_world, o.bound_box)
            if judge(rb):
                residual += 1
                residual_by_type[o.type] = residual_by_type.get(o.type, 0) + 1
    for o in objs:
        types[o.type] = types.get(o.type, 0) + 1
        if o.parent is None:
            top_level += 1
        mw = o.matrix_world
        for c in o.bound_box:
            for i in range(3):
                v = mw[i][0] * c[0] + mw[i][1] * c[1] + mw[i][2] * c[2] + mw[i][3]
                if v < bb_min[i]:
                    bb_min[i] = v
                if v > bb_max[i]:
                    bb_max[i] = v

    res = {
        "blend": bpy.data.filepath,
        "objects": len(objs),
        "objects_by_type": types,
        "top_level_objects": top_level,
        "region_objects_left": residual,
        "region_objects_left_by_type": residual_by_type,
        "marker_note": marker_note,
        "datablocks": {
            "meshes": len(bpy.data.meshes),
            "materials": len(bpy.data.materials),
            "images": len(bpy.data.images),
            "collections": len(bpy.data.collections),
            "cameras": len(bpy.data.cameras),
            "lights": len(bpy.data.lights),
        },
        "region_rects_xy": [list(r) for r in rects] if rects else None,
        "scene_bbox_min": [round(v, 3) for v in bb_min],
        "scene_bbox_max": [round(v, 3) for v in bb_max],
        "seconds": round(time.time() - t0, 2),
    }
    OUT = out_dir()
    if OUT:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, "verify_region.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    print("[VER] " + json.dumps(res, ensure_ascii=False))

    # ---- 判定 ----
    fails = 0
    if judge:
        ok = (residual == 0)
        fails += 0 if ok else 1
        print("[VER] [1] 区内残留 = %d  (判据 0)      %s" % (residual, "OK" if ok else "FAIL"))
    else:
        print("[VER] [1] 区内残留 = 无法复算（标记体已删）")
    if CONFIG["EXPECT_OBJECTS"] is not None:
        d = abs(len(objs) - CONFIG["EXPECT_OBJECTS"])
        ok = d <= CONFIG["EXPECT_TOLERANCE"]
        fails += 0 if ok else 1
        print("[VER] [2] 对象数 %d vs 预期 %d (容差 %d, 实测差 %d)  %s"
              % (len(objs), CONFIG["EXPECT_OBJECTS"], CONFIG["EXPECT_TOLERANCE"], d,
                 "OK" if ok else "FAIL"))
    print("[VER] FAILS=%d  %.1fs" % (fails, time.time() - t0))


main()
