# -*- coding: utf-8 -*-
"""查清对不上的几个对象：哪些对象不在任何 bpy.data.collections 里。"""
import bpy, os, io

WORK = os.environ.get("AMB_WORK", os.getcwd())   # 报告/基线/日志都写这里
TAG = os.environ.get("QQ_TAG", "?")
D = bpy.data
sc = bpy.context.scene

L = []
def w(s=""):
    L.append(s)

covered = set()
for c in D.collections:
    for o in c.objects:
        covered.add(o.name)
alln = {o.name for o in D.objects}
miss = sorted(alln - covered)

w("== tag=%s ==" % TAG)
w("  bpy.data.collections (%d): %s" % (len(D.collections), sorted(c.name for c in D.collections)))
w("  场景顶层 children: %s" % sorted(c.name for c in sc.collection.children))
w("  scene.collection.objects (直接挂在场景根): %d %s"
  % (len(sc.collection.objects), sorted(o.name for o in sc.collection.objects)))
w("  对象总数 %d ; 被集合覆盖 %d ; 未被覆盖 %d" % (len(alln), len(covered), len(miss)))
w("  未被覆盖清单: %s" % miss)
w("")
w("  逐集合对象数：")
for c in D.collections:
    w("    %-30s objs=%-6d children=%s  users=%d"
      % (c.name, len(c.objects), sorted(x.name for x in c.children), c.users))
w("")
# 未被覆盖对象详情
for n in miss:
    o = D.objects[n]
    w("  * %-34s type=%-7s mesh=%-20s colls=%s parent=%s"
      % (n, o.type, (o.data.name if o.data else None),
         sorted(c.name for c in o.users_collection),
         o.parent.name if o.parent else None))

with io.open(os.path.join(WORK, "qq_missing_%s.txt" % TAG), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("\n".join(L))
