# -*- coding: utf-8 -*-
"""覆盖区框选判定的**共享几何核**。

`analyze_region.py` / `delete_region.py` / `verify_region.py` 三个脚本共用本模块，
**保证"干跑判据"与"执行判据"与"复核判据"逐字节同源** —— 判据分叉会出现
"算 143318、删 143317"这类最难查的偏差（见 docs/覆盖区框选批量删除对象.md 坑 7）。
"""


def world_xy_bbox(mw, bb):
    """对象的世界 XY 包围矩形 (x0, y0, x1, y1)。

    - `bb` 是 `Object.bound_box`（**对象局部坐标**的 8 个角）——必须过 `matrix_world`。
    - 按矩阵前两行直接展开叉乘：不构造 Vector、不调 `matrix_world @ Vector(...)`，
      30 万对象 × 8 角下这能省掉全部对象分配开销（实测整个干跑只要几秒）。
    """
    r0, r1 = mw[0], mw[1]
    x0 = y0 = 1e30
    x1 = y1 = -1e30
    for c in bb:
        x = r0[0] * c[0] + r0[1] * c[1] + r0[2] * c[2] + r0[3]
        y = r1[0] * c[0] + r1[1] * c[1] + r1[2] * c[2] + r1[3]
        if x < x0:
            x0 = x
        if x > x1:
            x1 = x
        if y < y0:
            y0 = y
        if y > y1:
            y1 = y
    return (x0, y0, x1, y1)


def marker_rects(objs, key):
    """按名字关键字挑出标记网格体，返回它们的世界 XY 矩形列表。"""
    out = []
    for o in objs:
        if o.type == 'MESH' and key in o.name:
            out.append(world_xy_bbox(o.matrix_world, o.bound_box))
    return out


def union_bbox(rects):
    """若干个矩形的总包围矩形（画预览 / 粗筛用）。"""
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[2] for r in rects)
    y1 = max(r[3] for r in rects)
    return (x0, y0, x1, y1)


def make_judge(rects, rel_tol=1e-6):
    """构造判定函数：`judge(rb) -> bool`，`rb` = 世界 XY 矩形。

    「完全落在若干矩形的**并集**内」= 对象矩形与并集的交面积 == 自身面积。

    并集不是矩形，不能拆成"在 R1 里 **或** 在 R2 里"逐条判（那样会把"横跨两块、
    中间悬空"的对象误判成在内）。做法：用**所有矩形边界的 x/y 坐标**把整个平面切成
    互不重叠的**格网** —— 轴对齐矩形必然由若干整格组成，所以每格"整格在内 / 整格在外"
    必然成立。于是：

        area(R ∩ 并集) = Σ 各"在并集内"的格子 ∩ R 的面积

    对 2 块矩形，这等价于容斥式 `area(R∩R1) + area(R∩R2) − area(R∩R1∩R2)`；
    格网写法对 N 块任意形状的并集都精确（容斥高阶项不会漏）。
    """
    if not rects:
        raise SystemExit("[FATAL] 没找到标记网格体（名字关键字不对？）")

    xs = sorted({r[0] for r in rects} | {r[2] for r in rects})
    ys = sorted({r[1] for r in rects} | {r[3] for r in rects})
    cells = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx0, cx1 = xs[i], xs[i + 1]
            cy0, cy1 = ys[j], ys[j + 1]
            if cx1 - cx0 <= 0 or cy1 - cy0 <= 0:
                continue
            mx, my = (cx0 + cx1) * 0.5, (cy0 + cy1) * 0.5
            if any(r[0] <= mx <= r[2] and r[1] <= my <= r[3] for r in rects):
                cells.append((cx0, cy0, cx1, cy1))

    def pin(x, y):
        for r in rects:
            if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
                return True
        return False

    def judge(rb):
        w = rb[2] - rb[0]
        h = rb[3] - rb[1]
        if w <= 1e-9 or h <= 1e-9:
            # ★ 退化矩形（EMPTY / CAMERA / 灯光 / 点数据对象的 bound_box 是零尺寸）：
            #   面积判据两侧恒等 ⇒ 任何位置都会判成"包含"，会把全工程的空物体与相机都删掉。
            #   必须走四角点判定。
            return (pin(rb[0], rb[1]) and pin(rb[2], rb[1])
                    and pin(rb[0], rb[3]) and pin(rb[2], rb[3]))
        a = 0.0
        for c in cells:
            cw = min(rb[2], c[2]) - max(rb[0], c[0])
            ch = min(rb[3], c[3]) - max(rb[1], c[1])
            if cw > 0 and ch > 0:
                a += cw * ch
        return abs(a - w * h) <= rel_tol * max(1.0, w * h)

    return judge
