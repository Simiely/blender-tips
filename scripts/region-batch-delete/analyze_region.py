# -*- coding: utf-8 -*-
"""① 干跑（**只读，绝不改工程**）：统计覆盖区内对象，落 JSON 报告 + 名单 + SVG 预览。

    blender.exe --background <工程.blend> --python analyze_region.py -- [OUT_DIR]

输出：
    <OUT_DIR>/region_analysis.json   计数报告（分类口径 + 风险父级样本）
    <OUT_DIR>/inside_names.txt       完全在区内的对象名单（用于执行侧对账）
    <OUT_DIR>/region_preview.svg     俯视预览（青 = 标记矩形，红 = 待删，灰 = 保留）
"""
import bpy
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from region_geom import marker_rects, world_xy_bbox, make_judge, union_bbox   # noqa: E402

CONFIG = dict(
    MARKER_KEY=r"Z轴覆盖范围",          # 标记网格体的名字关键字
    OUT_DIR=r"C:\path\to\workdir",      # 报告 / 名单 / 预览都写这里
    WRITE_SVG=True,                     # 预览体积 = 与区域相交的对象数 × ~70 字节
    EXPECT_INSIDE=None,                 # 填数字则数量不符直接报错（干跑自证）
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
    OUT = out_dir()
    os.makedirs(OUT, exist_ok=True)

    objs = list(bpy.data.objects)
    print("[RUN] loaded %d objects" % len(objs))

    rects = marker_rects(objs, CONFIG["MARKER_KEY"])
    if not rects:
        raise SystemExit("[FATAL] 没找到名字含 %r 的 MESH 标记体" % CONFIG["MARKER_KEY"])
    judge = make_judge(rects)
    ub = union_bbox(rects)
    print("[RUN] marker rects (%d): %s" % (len(rects), rects))

    inside, overlap_only, origin_inside = [], [], []
    inside_by_type, overlap_by_type = {}, {}
    parent_of = {}
    inside_with_parent = 0
    drawn = []           # 与区域粗筛相交的对象，供 SVG 用

    for o in objs:
        rb = world_xy_bbox(o.matrix_world, o.bound_box)
        if judge(rb):
            inside.append(o.name)
            inside_by_type[o.type] = inside_by_type.get(o.type, 0) + 1
            if o.parent is not None:
                inside_with_parent += 1
        else:
            # 部分重叠：矩形与并集有交集但不完全在内
            iw = min(rb[2], ub[2]) - max(rb[0], ub[0])
            ih = min(rb[3], ub[3]) - max(rb[1], ub[1])
            if iw > 1e-9 and ih > 1e-9:
                overlap_only.append(o.name)
                overlap_by_type[o.type] = overlap_by_type.get(o.type, 0) + 1
        cx, cy = (rb[0] + rb[2]) * 0.5, (rb[1] + rb[3]) * 0.5
        for r in rects:
            if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]:
                origin_inside.append(o.name)
                break
        # 粗筛：只画与区域 bbox（外扩 5%）相交的对象，避免 SVG 被 30 万个远处对象撑爆
        pad = max(ub[2] - ub[0], ub[3] - ub[1]) * 0.05
        if rb[2] >= ub[0] - pad and rb[0] <= ub[2] + pad and rb[3] >= ub[1] - pad and rb[1] <= ub[3] + pad:
            drawn.append((o.type, rb, judge(rb)))
        if o.parent is not None:
            parent_of.setdefault(o.parent.name, []).append(o.name)

    inside_set = set(inside)
    victim_parents = [p for p in parent_of if p in inside_set]
    outside_children = sorted({c for p in victim_parents for c in parent_of[p] if c not in inside_set})
    n_children = sum(1 for c in outside_children)

    with open(os.path.join(OUT, "inside_names.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(inside))

    res = {
        "blend": bpy.data.filepath,
        "marker_key": CONFIG["MARKER_KEY"],
        "rects_xy": [list(r) for r in rects],
        "n_total_objects": len(objs),
        "n_fully_inside_total": len(inside),
        "n_fully_inside_by_type": inside_by_type,
        "n_overlap_total": len(overlap_only),
        "n_overlap_by_type": overlap_by_type,
        "n_origin_inside_total": len(origin_inside),
        "n_fully_inside_have_parent": inside_with_parent,
        "n_deleted_parents_of_outside_objects": len(victim_parents),
        "n_outside_children_to_freeze": n_children,
        "victim_parent_sample": sorted(victim_parents)[:15],
        "seconds": round(time.time() - t0, 2),
    }
    with open(os.path.join(OUT, "region_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    if CONFIG["WRITE_SVG"] and drawn:
        write_svg(os.path.join(OUT, "region_preview.svg"), rects, drawn, len(objs) - len(drawn))

    print("[RUN] " + json.dumps(res, ensure_ascii=False))
    if CONFIG["EXPECT_INSIDE"] is not None and len(inside) != CONFIG["EXPECT_INSIDE"]:
        raise SystemExit("[FATAL] 完全在内 %d != 预期 %d" % (len(inside), CONFIG["EXPECT_INSIDE"]))
    print("[RUN] DONE %.2fs" % (time.time() - t0))


def write_svg(path, rects, drawn, skipped):
    """俯视预览：等比例映射到 1600×1600 视口（Y 轴翻转，与俯视图一致）。"""
    x0 = min(r[0] for r in rects)
    x1 = max(r[2] for r in rects)
    y0 = min(r[1] for r in rects)
    y1 = max(r[3] for r in rects)
    for _, rb, _ in drawn:
        x0 = min(x0, rb[0])
        x1 = max(x1, rb[2])
        y0 = min(y0, rb[1])
        y1 = max(y1, rb[3])
    pad = max(x1 - x0, y1 - y0) * 0.03
    x0 -= pad
    y0 -= pad
    x1 += pad
    y1 += pad
    s = 1600.0 / max(x1 - x0, y1 - y0)

    def X(v):
        return (v - x0) * s

    def Y(v):
        return 1600 - (v - y0) * s

    L = ['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1600" viewBox="0 0 1600 1600">',
         '<rect width="1600" height="1600" fill="#111"/>']
    for _, rb, ins in drawn:
        w = max((rb[2] - rb[0]) * s, 0.8)
        h = max((rb[3] - rb[1]) * s, 0.8)
        L.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity="%s"/>'
                 % (X(rb[0]), Y(rb[3]), w, h,
                    "#e04040" if ins else "#5a5a5a", ".75" if ins else ".35"))
    for r in rects:
        L.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" '
                 'stroke="#33d5ff" stroke-width="3"/>'
                 % (X(r[0]), Y(r[3]), (r[2] - r[0]) * s, (r[3] - r[1]) * s))
    L.append('<text x="16" y="28" fill="#888" font-size="18" font-family="monospace">'
             'cyan = marker rects, red = to delete, gray = keep (skipped %d far objects)</text>'
             % skipped)
    L.append('</svg>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


main()
