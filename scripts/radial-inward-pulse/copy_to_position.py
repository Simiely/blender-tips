# -*- coding: utf-8 -*-
"""径向材质【位置副本】：把当前三个测试面槽里的材质各复制一份，圆心搬到网格新位置

用法（经 9877 桥）：python send.py copy_to_position.py

特点：
  · 动态定位 —— 从材质槽里读材质、顺 纹理坐标.object 找控制器（用户会改名/挪动，不猜名字）
  · 自动编号 —— 新后缀 = 现有 _位N 的最大值 +1（_副本 记作 位2），不用每次手改
  · 幂等 —— 重复跑只更新这一处
  · 带关键帧的源材质：丢弃带过来的 action，原地 keyframe_insert 重建
    （复制 action + 重绑 slot 实测无效 ⇒ 评估值冻结，见 docs/径向材质多位置部署与时差.md §2.2）
  · 源材质只读不写
"""
import bpy
import collections
import re
from mathutils import Vector

# ============================ 配置区 ============================
COL_NAME = "立体灯光材质"
PLANES = ["平面.001", "平面.002", "平面.003"]
SLOT_IDX = (0, 1)          # 这三个面的第 0/1 槽 = 要复制的两套材质
SLOT_IDX_NEW = (0, 1)      # 副本放回槽 0/1（槽 0 = 显示）
# 留空 = 自动编号（推荐）。要指定就写 "_位7" 这种
NEW_TAG = ""
DUTY_DEFAULT = 0.94
# ==============================================================

D = bpy.data
C = bpy.context
scn = C.scene
FRAME0 = scn.frame_current
log = []
fails = []


def chk(cond, msg):
    (log if cond else fails).append(("  ok " if cond else "  xx ") + msg)


def strip_suffix(name):
    return re.sub(r"(_位\d+|_副本|_面\d+)+$", "", name)


def auto_tag(mats):
    """扫径向材质名里的 _位N/_副本，取最大编号 +1 ⇒ 本处后缀"""
    mx = 0
    for m in mats:
        if "径向" not in m.name:
            continue
        for mt in re.finditer(r"_位(\d+)", m.name):
            mx = max(mx, int(mt.group(1)))
        if "_副本" in m.name:
            mx = max(mx, 2)          # _副本 相当于 位2
    return "_位%d" % (mx + 1)


col = D.collections.get(COL_NAME)
if col is None:
    raise RuntimeError("找不到集合 %s" % COL_NAME)

# ---------------------------------------------- 0. 实测新圆心
pts = []
for pn in PLANES:
    ob = D.objects.get(pn)
    if ob is None:
        raise RuntimeError("网格 %s 不存在" % pn)
    mw = ob.matrix_world
    pts += [mw @ v.co for v in ob.data.vertices]
xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
CENTER = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                 (min(zs) + max(zs)) / 2))
half_w = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2.0
R_max = max((p - CENTER).length for p in pts)
log.append("实测新圆心 = (%.4f, %.4f, %.4f)" % (CENTER.x, CENTER.y, CENTER.z))
log.append("内切圆 = %.4f | 角点 = %.4f（比值 %.4f）"
           % (half_w, R_max, R_max / half_w if half_w else 0))

# ---------------------------------------------- 1. 定位源（不猜名字）
pairs = []                     # [(槽序, 源材质, 源控制器)]
seen = set()
for i in SLOT_IDX:
    mn = None
    for pn in PLANES:
        ob = D.objects.get(pn)
        s = ob.material_slots[i] if i < len(ob.material_slots) else None
        if s is not None and s.material is not None:
            mn = s.material.name
            break
    if mn is None:
        continue
    nt = D.materials[mn].node_tree
    tex = [n for n in nt.nodes if n.type == 'TEX_COORD' and getattr(n, "object", None)]
    cn = tex[0].object.name if tex and tex[0].object else None
    pairs.append((i, mn, cn))
log.append("动态定位到 %d 个源：%s" % (len(pairs), pairs))
if len(pairs) < len(SLOT_IDX):
    raise RuntimeError("槽里没有可复制的材质")

NEW_TAG = NEW_TAG or auto_tag(list(D.materials))
log.append("本处后缀 = %s" % NEW_TAG)


def new_name(name):
    return strip_suffix(name) + NEW_TAG


# ---------------------------------------------- 2. 幂等清理本处旧副本
for _i, mn, _c in pairs:
    nn = new_name(mn)
    if D.materials.get(nn) is not None:
        for me in D.meshes:
            if nn in [x.name for x in me.materials if x]:
                while len(me.materials) > 0:
                    me.materials.pop(index=len(me.materials) - 1)
        D.materials.remove(nn)
        log.append("清理旧材质 %s" % nn)
for _i, _m, cn in pairs:
    nn = new_name(cn)
    o = D.objects.get(nn)
    if o is not None:
        D.objects.remove(o, do_unlink=True)
        log.append("清理旧控制器 %s" % nn)
a_old = D.actions.get([m for m in D.materials if True] and "") if False else None


def rebuild_keyframes(nt_new, nt_old):
    ad_new, ad_old = nt_new.animation_data, nt_old.animation_data
    if ad_new is None or ad_new.action is None:
        return "没带 action"
    old = ad_new.action.name
    want = []
    if ad_old and ad_old.action:
        for lay in getattr(ad_old.action, 'layers', []):
            for st in lay.strips:
                for cb in getattr(st, 'channelbags', []):
                    for fc in cb.fcurves:
                        if 'TVAL' in fc.data_path:
                            want = [(round(kp.co[0], 3), round(kp.co[1], 3))
                                    for kp in fc.keyframe_points]
    ad_new.action = None
    tv = nt_new.nodes.get("TVAL")
    if tv is None:
        return "丢弃 %s（无 TVAL 节点）" % old
    tv.outputs[0].default_value = 1.0
    tv.outputs[0].keyframe_insert('default_value', frame=1)
    tv.outputs[0].default_value = 250.0
    tv.outputs[0].keyframe_insert('default_value', frame=250)
    adn = nt_new.animation_data
    n = 0
    if adn and adn.action:
        for lay in adn.action.layers:
            for st in lay.strips:
                for cb in st.channelbags:
                    for fc in cb.fcurves:
                        if 'TVAL' in fc.data_path:
                            n += 1
                            for kp in fc.keyframe_points:
                                kp.interpolation = 'LINEAR'
                            fc.extrapolation = 'LINEAR'
    return "丢弃 %s ⇒ 重建 %s | fcurve %d | 原件关键帧 %s" % (old, adn.action.name, n, want)


# ---------------------------------------------- 3. 逐个复制
made = []
for slot_i, mn, cn in pairs:
    log.append("")
    log.append("=== 复制 %s（控制器 %s）→ 槽 %d ===" % (mn, cn, slot_i))
    om, oc = D.materials[mn], D.objects[cn]
    src_nodes = len(om.node_tree.nodes)
    src_drvs = (len(om.node_tree.animation_data.drivers) if om.node_tree.animation_data else 0)
    src_users = om.users

    new_cn = new_name(cn)
    nc = oc.copy()
    nc.name = new_cn
    if nc.name not in [o.name for o in col.objects]:
        col.objects.link(nc)
    nc.location = CENTER
    nc.rotation_euler = (0.0, 0.0, 0.0)
    nc.scale = (1.0, 1.0, 1.0)

    new_mn = new_name(mn)
    nm = om.copy()
    nm.name = new_mn
    nt_new, nt_old = nm.node_tree, om.node_tree

    texs = [n for n in nt_new.nodes if n.type == 'TEX_COORD']
    for t in texs:
        if t.object is oc:
            t.object = nc
    chk(bool(texs) and all(t.object is nc for t in texs),
        "纹理坐标.Object → %s" % (nc.name if texs else None))

    moved = cmoved = 0
    if nt_new.animation_data:
        for d in nt_new.animation_data.drivers:
            for v in d.driver.variables:
                for t in v.targets:
                    if t.id_type == 'OBJECT' and t.id is oc:
                        t.id = nc
                        moved += 1
    if nc.animation_data:
        for d in nc.animation_data.drivers:
            for v in d.driver.variables:
                for t in v.targets:
                    if t.id_type == 'OBJECT' and (t.id is oc or t.id is None):
                        t.id = nc
                        cmoved += 1
    log.append("  驱动变量改指：材质 %d / 控制器 %d" % (moved, cmoved))

    note = rebuild_keyframes(nt_new, nt_old)
    log.append("  关键帧: %s" % note)

    now = {k: nc[k] for k in nc.keys() if k != "_RNA_UI"}
    src_props = {k: oc[k] for k in oc.keys() if k != "_RNA_UI"}
    chk(set(now) == set(src_props) and
        all(abs(float(now[k]) - float(src_props[k])) < 1e-9 for k in src_props),
        "参数逐项不变")
    chk((nc.location - CENTER).length < 1e-6, "新控制器在新圆心")
    chk(len(nt_new.nodes) == src_nodes, "节点数 = %d" % src_nodes)
    nd = len(nt_new.animation_data.drivers) if nt_new.animation_data else 0
    chk(nd == src_drvs, "驱动数 = %d" % nd)

    made.append((slot_i, nm, nc, mn, cn, src_users))

# ---------------------------------------------- 4. 挂回三个面
for pn in PLANES:
    ob = D.objects.get(pn)
    me = ob.data
    if me.users > 1:
        ob.data = me = me.copy()
    while len(me.materials) > 0:
        me.materials.pop(index=len(me.materials) - 1)
    for _i, _nm, _nc, _mn, _cn, _u in sorted(made, key=lambda x: x[0]):
        me.materials.append(D.materials[_nm.name])
    for p in me.polygons:
        p.material_index = 0
    log.append("  %s → 槽 = %s"
               % (pn, [s.material.name if s.material else None for s in ob.material_slots]))

C.view_layer.update()

# ---------------------------------------------- 5. 原件只读对拍
log.append("")
for slot_i, nm, nc, mn, cn, src_users in made:
    om = D.materials[mn]
    log.append("  %-34s users=%d（复制前 %d）| 节点=%d | 驱动=%d"
               % (mn, om.users, src_users, len(om.node_tree.nodes),
                  len(om.node_tree.animation_data.drivers) if om.node_tree.animation_data else 0))
    chk(0 <= src_users - om.users <= len(PLANES),
        "%s users %d → %d（测试面改用新副本，属预期）" % (mn, src_users, om.users))

log.append("")
log.append("对象 %d | 材质 %d" % (len(D.objects), len(D.materials)))
for slot_i, nm, nc, mn, cn, _u in made:
    log.append("  新增材质 %-34s（槽%d）← %s" % (nm.name, slot_i, mn))
    log.append("  新增控制器 %-30s ← %s" % (nc.name, cn))

print("\n".join(log))
print()
print("FAILS=%d" % len(fails))
for f in fails:
    print(f)
