# -*- coding: utf-8 -*-
"""诊断：为什么改一个材质/参数，其它网格体跟着一起变？——把三层共享关系全探出来

「改一个、其它跟着变」有三种成因，逐层判别：

  ① 网格数据块共享   判据 mesh.users > 1   ⇒ 改一个对象的【材质槽】全体一起变
  ② 材质数据块共享   判据 material.users > 1 ⇒ 在材质编辑器里改【节点/参数】全体一起变
  ③ 控制器共享       多个材质的 纹理坐标.object 是同一个空物体 ⇒ 拖【控制器参数】全体一起变

用法（经 9877 桥）：python send.py diag_sharing.py
配置区：
  TARGET_OBJECTS  要检查的对象名清单；留空 = 全场景 MESH 对象
  SCOPE_NAME      只统计名字含该关键词的空对象【名下】的网格（按父级链递归）
输出：三类「共享组」清单（组 = 共用同一份数据的对象集合），按组大小降序。
"""
import bpy
import collections

D = bpy.data

# ============================ 配置区 ============================
TARGET_OBJECTS = []        # 要检查的对象名；留空 = 全场景 MESH 对象
SCOPE_NAME = ""            # 只看名字含该关键词的空对象【名下】的网格（递归）；留空 = 不限
TOP_N = 12                 # 每类共享组最多打印几个
# ==============================================================


def walk(o, acc):
    for ch in o.children:
        acc.append(ch)
        walk(ch, acc)


objs = []
if TARGET_OBJECTS:
    objs = [D.objects[n] for n in TARGET_OBJECTS if n in D.objects]
else:
    objs = [o for o in D.objects if o.type == 'MESH']
    if SCOPE_NAME:
        scoped = set()
        for o in D.objects:
            if o.type == 'EMPTY' and SCOPE_NAME in o.name:
                acc = [o]
                walk(o, acc)
                scoped.update(x.name for x in acc)
        objs = [o for o in objs if o.name in scoped]

print("检查对象 %d 个" % len(objs))
if not objs:
    raise SystemExit("没有检查对象")

# ---------- ① 网格数据共享 ----------
g1 = collections.defaultdict(list)
for ob in objs:
    if ob.data is not None:
        g1[ob.data.name].append(ob.name)
print()
print("=== ① 网格数据共享（改材质槽会一起变）===")
n = 0
for dn, lst in sorted(g1.items(), key=lambda x: -len(x[1])):
    if len(lst) <= 1:
        continue
    n += 1
    if n <= TOP_N:
        print("  [%d 个对象共用] %s\n      %s" % (len(lst), dn, lst[:10]))
print("  ⇒ 共享数据 %d 份 / 涉及对象 %d 个" % (n, sum(len(v) for v in g1.values() if len(v) > 1)))

# ---------- ② 材质共享 ----------
g2 = collections.defaultdict(list)
for ob in objs:
    for s in ob.material_slots:
        if s.material:
            g2[s.material.name].append(ob.name)
print()
print("=== ② 材质共享（在材质编辑器里改节点/参数会一起变）===")
n = 0
for mn, lst in sorted(g2.items(), key=lambda x: -len(x[1])):
    if len(lst) <= 1:
        continue
    n += 1
    if n <= TOP_N:
        print("  [%d 个对象共用] %s\n      %s" % (len(lst), mn, lst[:10]))
print("  ⇒ 共享材质 %d 份 / 涉及对象 %d 个" % (n, sum(len(v) for v in g2.values() if len(v) > 1)))

# ---------- ③ 控制器共享（径向类材质：纹理坐标.object）----------
g3 = collections.defaultdict(list)
for ob in objs:
    for s in ob.material_slots:
        m = s.material
        if m is None or m.node_tree is None:
            continue
        for x in m.node_tree.nodes:
            if x.type == 'TEX_COORD' and getattr(x, "object", None):
                g3[x.object.name].append(ob.name)
print()
print("=== ③ 控制器共享（拖控制器参数会一起变）===")
n = 0
for cn, lst in sorted(g3.items(), key=lambda x: -len(x[1])):
    if len(lst) <= 1:
        continue
    n += 1
    if n <= TOP_N:
        print("  [%d 个对象共用] %s\n      %s" % (len(lst), cn, lst[:10]))
print("  ⇒ 共享控制器 %d 个 / 涉及对象 %d 个" % (n, sum(len(v) for v in g3.values() if len(v) > 1)))

print()
print("判读：① 用 ob.data = ob.data.copy() 独立；② 用 material.copy() 独立；")
print("      ③ 给每份材质配自己的控制器（三者正交，可叠加）。")
print("      详见 docs/径向材质多位置部署与时差.md §2.3")
