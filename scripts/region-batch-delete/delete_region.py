# -*- coding: utf-8 -*-
"""② 执行：把覆盖区内的对象全部删除，**另存为新文件**（原文件分毫不动）。

    blender.exe --background <工程.blend> --python delete_region.py -- [NEW_PATH]

安全设计（三重闸）：
  闸 1  只写新文件，**绝不覆盖当前文件**（NEW == 当前路径 直接退出）
  闸 2  删除前重算名单，数量与干跑（region_analysis.json）不一致 ⇒ 退出，不动手
  闸 3  删前先把"父级在内、自己在外"的子级做 keep-transform 冻结，世界坐标逐位不变

进度打点统一用 `[DEL]` 前缀 —— progress_dashboard/ 直接认这个前缀。
"""
import bpy
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from region_geom import marker_rects, world_xy_bbox, make_judge   # noqa: E402

CONFIG = dict(
    MARKER_KEY=r"Z轴覆盖范围",
    NEW=None,                 # None = 在当前路径旁自动派生 "<名>_已删除覆盖区对象.blend"
    EXPECT_INSIDE=None,       # 强烈建议填干跑数（例如 143318），不一致就退出
    CHUNK=10000,              # batch_remove 的分块大小（决定打点密度）
    PURGE_PASSES=2,           # orphans_purge 跑几遍（do_recursive=False，每遍都很便宜）
)
SUFFIX = "_已删除覆盖区对象.blend"


def argv_new():
    a = sys.argv
    if "--" in a:
        rest = a[a.index("--") + 1:]
        if rest:
            return rest[0]
    return None


def main():
    t0 = time.time()
    SRC = bpy.data.filepath
    if not SRC:
        raise SystemExit("[FATAL] 没有打开工程（要用 --background <file> 传）")
    NEW = argv_new() or CONFIG["NEW"] or (os.path.splitext(SRC)[0] + SUFFIX)
    if os.path.abspath(NEW) == os.path.abspath(SRC):
        raise SystemExit("[FATAL] 输出路径与当前工程相同，拒绝执行（闸 1）")
    log("start  src=%s" % SRC)
    log("target new=%s" % NEW)

    objs = list(bpy.data.objects)
    log("loaded %d objects" % len(objs))

    rects = marker_rects(objs, CONFIG["MARKER_KEY"])
    judge = make_judge(rects)
    log("region rects: %s" % (rects,))

    # ---- 算名单（与干跑同一套 region_geom，逐字节同源）----
    victims = [o for o in objs if judge(world_xy_bbox(o.matrix_world, o.bound_box))]
    log("victims: %d" % len(victims))
    if CONFIG["EXPECT_INSIDE"] is not None and len(victims) != CONFIG["EXPECT_INSIDE"]:
        raise SystemExit("[FATAL] 名单 %d != 干跑预期 %d ⇒ 判据分叉了，退出（闸 2）"
                         % (len(victims), CONFIG["EXPECT_INSIDE"]))
    log("count verified == %d" % len(victims))

    victim_names = {o.name for o in victims}

    # ---- 冻结：父级在区内、自己在外 ⇒ 摘父级并保持世界变换（闸 3）----
    tf = time.time()
    frozen = 0
    for o in objs:
        p = o.parent
        if p is not None and p.name in victim_names and o.name not in victim_names:
            mw = o.matrix_world.copy()
            o.parent = None
            o.matrix_parent_inverse.identity()
            o.matrix_world = mw
            frozen += 1
    log("frozen (keep-transform) outside children: %d %.1f s" % (frozen, time.time() - tf))

    # ---- 分块删除（batch_remove 是本场景实测最快的方法，~23 ms/对象）----
    CHUNK = CONFIG["CHUNK"]
    tot = len(victims)
    for i in range(0, tot, CHUNK):
        bpy.data.batch_remove(victims[i:i + CHUNK])
        log("removed %d / %d elapsed %.1fs" % (min(i + CHUNK, tot), tot, time.time() - t0))
    log("all removed. objects remaining: %d %.1f s" % (len(bpy.data.objects), time.time() - t0))

    # ---- 孤儿数据块（删对象会连带产生孤儿 mesh / material / image）----
    for k in range(CONFIG["PURGE_PASSES"]):
        n = bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=False)
        log("orphans_purge pass %d -> %d %.1f s" % (k + 1, n, time.time() - t0))
    log("after purge -> objects: %d meshes: %d materials: %d images: %d"
        % (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.materials), len(bpy.data.images)))

    # ---- 另存（存盘会丢弃 users==0 且无 fake user 的数据块，故重开后计数可能少几个）----
    bpy.ops.wm.save_as_mainfile(filepath=NEW, check_existing=False, compress=False)
    size = os.path.getsize(NEW) / 1048576.0
    log("saved -> %s %.1f MB %.1f s" % (NEW, size, time.time() - t0))
    log("DONE")


def log(msg):
    print("[DEL] %s" % msg, flush=True)


main()
