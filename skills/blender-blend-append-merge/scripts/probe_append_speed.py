# -*- coding: utf-8 -*-
"""计时对照：追加成本到底跟「对象数」还是「数据量」相关。
   SP_MODE=coll  以 A 为底，追加 B 的一个最小集合（测「打开 B 库」的固定开销）
   SP_MODE=beta  以 B 为底，追加 A 的 SKP Imported Data（测「以少的为底」是否更快）
   SP_MODE=alpha 以 A 为底，追加 B 的 SKP Mesh Objects（= 主路径的主体，复核 458s）
"""
import bpy, os, time

SRC_A = os.environ.get("AMB_SRC_A", "")          # 底文件（对象少的那一边）
SRC_B = os.environ.get("AMB_SRC_B", "")          # 追加来源（对象多的那一边）
for _k in ("AMB_SRC_A", "AMB_SRC_B"):
    if not os.environ.get(_k):
        raise SystemExit("请先设环境变量 %s（传两个 .blend 的绝对路径）" % _k)
MODE = os.environ.get("SP_MODE", "coll")
D = bpy.data

print("[base] %s" % D.filepath, flush=True)
print("[base] objects=%d verts=%d" % (
    len(D.objects), sum(len(o.data.vertices) for o in D.objects if o.type == "MESH")), flush=True)


def app(src, kind, name):
    t = time.time()
    r = bpy.ops.wm.append(filepath=os.path.join(src, kind, name),
                          directory=src + os.sep + kind + os.sep, filename=name,
                          instance_collections=False, set_fake=False, use_recursive=False)
    dt = time.time() - t
    print("[T] append %-26s %8.2f s  %s" % (name, dt, list(r)), flush=True)
    return dt


print("[after] objects=%d" % len(D.objects), flush=True)
tot = 0.0
if MODE == "coll":
    tot += app(SRC_B, "Collection", "SKP Scenes (as Cameras)")
elif MODE == "beta":
    tot += app(SRC_A, "Collection", "SKP Imported Data")
    tot += app(SRC_A, "Collection", "相机")
elif MODE == "alpha":
    tot += app(SRC_B, "Collection", "SKP Mesh Objects")
    tot += app(SRC_B, "Collection", "SKP Scenes (as Cameras)")

print("[after] objects=%d verts=%d"
      % (len(D.objects), sum(len(o.data.vertices) for o in D.objects if o.type == "MESH")), flush=True)
print("[TOTAL] %s = %.2f s" % (MODE, tot), flush=True)
