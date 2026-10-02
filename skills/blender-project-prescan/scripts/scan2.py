# -*- coding: utf-8 -*-
"""
第二轮定向测量（只读）：
  A) 引用源普查（决定算法复杂度）
  B) 单材质铜件：父级归属 / 顶层祖先 / UV 配置
  C) 铜件合并模拟（含世界包围盒基线）
  D) 全量按材质分组模拟（评估"扩到全量合并"的收益）
  E) EMPTY 不动点求解（算出可删数，不执行）
  F) 空集合 / 多实例 / 金色类材质
运行：
  blender.exe --background --factory-startup "<blend>" --python scan2.py
"""
import bpy, os, re, time, traceback
from collections import Counter, defaultdict

# 报告落盘目录：默认取当前工作目录，可用环境变量 BPS_WORK 覆盖
WORK = os.environ.get("BPS_WORK") or os.getcwd()
REPORT_TXT = os.path.join(WORK, "scan2_report.txt")

L = []
def p(s=""):
    L.append(str(s))
def section(t):
    p(""); p("-" * 74); p(t); p("-" * 74)

T0 = time.time()
import numpy as np

# 目标材质的匹配正则 —— 换工程时按本次目标改这两行
COPPER = re.compile(r"铜|[Cc]opper|[Bb]rass")
GOLD = re.compile(r"金")
D = bpy.data
objs = list(D.objects)
meshes = [o for o in objs if o.type == 'MESH']
pc = Counter()

p("=" * 74)
p("定向测量（只读）· 261002x03        " + time.strftime("%Y-%m-%d %H:%M:%S"))
p("=" * 74)

# ------------------------------------------------------- A) 引用源普查
try:
    section("[A] 引用源普查（先看这个，决定要不要扫引用图）")
    n_con = sum(1 for o in objs if len(o.constraints) > 0)
    n_mod = sum(1 for o in objs if len(o.modifiers) > 0)
    n_drv = sum(1 for o in objs if o.animation_data and len(o.animation_data.drivers) > 0)
    n_par = sum(1 for o in objs if len(getattr(o, "particle_systems", [])) > 0)
    n_obj_sock = 0
    sock_owners = []
    for m in D.materials:
        nt = m.node_tree
        if nt is None:
            continue
        for n in nt.nodes:
            for s in n.inputs:
                if s.type == 'OBJECT' and getattr(s, "default_value", None) is not None:
                    n_obj_sock += 1
                    sock_owners.append(m.name + "/" + n.name)
    for g in D.node_groups:
        for n in g.nodes:
            for s in n.inputs:
                if s.type == 'OBJECT' and getattr(s, "default_value", None) is not None:
                    n_obj_sock += 1
                    sock_owners.append("GN:" + g.name + "/" + n.name)
    p("  有约束的对象            : %d" % n_con)
    p("  有修改器的对象          : %d" % n_mod)
    p("  有驱动器的对象          : %d" % n_drv)
    p("  有粒子系统的对象        : %d" % n_par)
    p("  材质/节点组 OBJECT socket: %d  %s" % (n_obj_sock, sock_owners[:8]))
    p("  场景相机                : %s" % (D.scenes[0].camera.name if D.scenes and D.scenes[0].camera else "None"))
    p("  → 若以上多为 0，『引用图』退化为纯结构判定，不动点算法会很快。")
except Exception:
    p("!! " + traceback.format_exc())

# --------------------------------------------------- 内部工具
def used_named(me):
    mats = list(me.materials)
    n = len(me.polygons)
    if n == 0:
        return []
    a = np.empty(n, dtype=np.int32)
    me.polygons.foreach_get('material_index', a)
    used = sorted(set(int(x) for x in np.unique(a)))
    return [mats[i].name for i in used if i < len(mats) and mats[i]]

def wbbox(o):
    from mathutils import Vector
    M = o.matrix_world
    v = [M @ Vector(c) for c in o.bound_box]
    return (min(x.x for x in v), min(x.y for x in v), min(x.z for x in v),
            max(x.x for x in v), max(x.y for x in v), max(x.z for x in v))

def top_ancestor(o, depth=99):
    x, chain = o, []
    while x.parent and len(chain) < depth:
        x = x.parent
        chain.append(x.name)
    return x.name, chain

solo, skip = [], []

# --------------------------------------------------- B) 铜件清单
try:
    section("[B] 单材质铜件清单")
    for o in meshes:
        named = used_named(o.data)
        if not any(COPPER.search(x) for x in named):
            continue
        if len(named) == 1:
            solo.append((o, named[0]))
        else:
            skip.append((o, named))

    p("  可合并(【有面的材质】恰好 1 个且含铜) %d 个 ｜ 跳过(有面材质 >1 且含铜) %d 个"
      % (len(solo), len(skip)))
    # ---- 口径差异：严格按"材质槽总数" vs 按"有面的槽数"
    strict_slot1 = [o for o, _ in solo if len(o.data.materials) == 1]
    slot_gt1 = [o for o, _ in solo if len(o.data.materials) > 1]
    p("  口径 A（严格按【材质槽总数】==1）: %d 个" % len(strict_slot1))
    p("  口径 B（按【有面的槽】==1）      : %d 个  ← 含空槽被忽略的情况" % len(solo))
    if slot_gt1:
        p("  ⚠ 差集 %d 个：槽数 >1 但只有一个槽有面（空槽无几何）——" % len(slot_gt1))
        p("     这些按你的字面规则'多材质就跳过'应当【跳过】，请确认:")
        for o in slot_gt1[:20]:
            used = used_named(o.data)
            p("       %-30s 槽数=%d 有面=%s" % (o.name[:30], len(o.data.materials), used))
    empty_mat_faces = []
    for o in meshes:
        mats = list(o.data.materials)
        n = len(o.data.polygons)
        if not n:
            continue
        a = np.empty(n, dtype=np.int32)
        o.data.polygons.foreach_get('material_index', a)
        for i in set(int(x) for x in np.unique(a)):
            if i >= len(mats) or mats[i] is None:
                empty_mat_faces.append(o.name)
                break
    p("  有面但材质槽为空(None)的对象: %d %s" % (len(empty_mat_faces), empty_mat_faces[:10]))
    p("")
    p("  %-28s %-30s %-11s %5s %7s  %s" % ("对象名", "材质", "父级", "users", "缩放X", "UV层"))
    for o, mn in sorted(solo, key=lambda x: (x[1], x[0].name)):
        p("  %-28s %-30s %-11s %5d %7.3f  %s"
          % (o.name[:28], mn[:30], (o.parent.name[:11] if o.parent else "<无>"),
             o.data.users, o.scale.x, ",".join(l.name for l in o.data.uv_layers) or "-"))

    p("")
    p("  【铜件挂在哪 —— 父级分布】")
    for k, v in Counter((o.parent.name if o.parent else "<无父级>") for o, _ in solo).most_common():
        p("    %3d×  父级 %s" % (v, k))
    p("")
    p("  【顶层祖先分布（整棵树的根）】")
    for k, v in Counter(top_ancestor(o)[0] for o, _ in solo).most_common(20):
        p("    %3d×  顶层 %s" % (v, k))
    p("")
    p("  【brass_candleholders 为什么分成 3 组 —— UV 配置】")
    bc = [(o, mn) for o, mn in solo if mn.startswith("brass_candle")]
    for k, v in Counter((mn, tuple(l.name for l in o.data.uv_layers)) for o, mn in bc).most_common():
        p("    %d×  材质=%s  UV=%s" % (v, k[0][:44], list(k[1])))
except Exception:
    p("!! " + traceback.format_exc())

# --------------------------------------------------- C) 合并模拟
try:
    section("[C] 铜件合并模拟")
    groups = defaultdict(list)
    for o, mn in solo:
        key = (mn, tuple(l.name for l in o.data.uv_layers),
               len(getattr(o.data, "color_attributes", []) or []), bool(o.data.shape_keys))
        groups[key].append(o)

    p("  %-34s %4s %9s %9s %6s %6s %7s"
      % ("材质", "对象", "顶点", "面", "多实例", "有父级", "非单位缩放"))
    tot_v = tot_f = multiset = 0
    for k in sorted(groups, key=lambda x: -len(groups[x])):
        g = groups[k]
        nv = sum(len(x.data.vertices) for x in g)
        nf = sum(len(x.data.polygons) for x in g)
        tot_v += nv; tot_f += nf
        mi = sum(1 for x in g if x.data.users > 1)
        multiset += mi
        p("  %-34s %4d %9d %9d %6d %6d %7d"
          % (k[0][:34], len(g), nv, nf, mi,
             sum(1 for x in g if x.parent),
             sum(1 for x in g if any(abs(s - 1) > 1e-6 for s in x.scale))))
    p("")
    p("  合计 对象 %d ｜ 顶点 %d ｜ 面 %d ｜ 多实例对象 %d" % (len(solo), tot_v, tot_f, multiset))
    p("  结果对象数: %d → %d（省 %d 个，占总对象 50622 的 %.3f%%）"
      % (len(solo), len(groups), len(solo) - len(groups),
         (len(solo) - len(groups)) / 50622 * 100))

    xs = [wbbox(o) for o, _ in solo]
    p("  铜件整体世界包围盒（合并前基线）:")
    p("    min(%.4f, %.4f, %.4f)   max(%.4f, %.4f, %.4f)"
      % (min(b[0] for b in xs), min(b[1] for b in xs), min(b[2] for b in xs),
         max(b[3] for b in xs), max(b[4] for b in xs), max(b[5] for b in xs)))
    p("  ★ 合并后必须逐位一致（判据：世界包围盒偏差 ≈ 0）")
    p("")
    p("  【合并会摘掉父级 —— 影响评估】")
    np_ = sum(1 for o, _ in solo if o.parent)
    p("    有父级的铜件 %d / %d（%.0f%%）" % (np_, len(solo), np_ / len(solo) * 100))
    p("    这些父级是: " + ", ".join(k for k, v in pc.most_common(12) if False) or "")
except Exception:
    p("!! " + traceback.format_exc())

# --------------------------------------------------- D) 全量合并模拟
try:
    section("[D] 全量按材质合并模拟（评估是否值得扩大范围）")
    allg = defaultdict(list)
    for o in meshes:
        named = used_named(o.data)
        key = ((tuple(named) if named else ("<无有面材质>",)),
               tuple(l.name for l in o.data.uv_layers),
               len(getattr(o.data, "color_attributes", []) or []), bool(o.data.shape_keys))
        allg[key].append(o)
    n_obj = len(meshes)
    p("  当前网格对象 %d → 按(有面材质列表 + UV配置)分组后 %d 组" % (n_obj, len(allg)))
    p("  模拟合并后对象数: %d → %d（省 %.1f%%）"
      % (n_obj, len(allg), (n_obj - len(allg)) / n_obj * 100))
    p("")
    p("  %-56s %6s %9s" % ("组（材质组合）", "对象数", "预估耗时"))
    for k in sorted(allg, key=lambda x: -len(allg[x]))[:12]:
        g = allg[k]
        p("  %-56s %6d %8.0fs" % (" + ".join(k[0])[:56], len(g), len(g) * 0.015))
    p("")
    p("  ★ 全量合并预估总耗时 ~%.0f 秒（15ms/对象 保守估）"
      % sum(len(g) * 0.015 for g in allg.values()))
    big_k = max(allg, key=lambda x: len(allg[x]))
    big = allg[big_k]
    p("  ★ 最大组 %d 个对象，单独就约占 %.0f 秒" % (len(big), len(big) * 0.015))
    p("  ★ 最大组材质 = %s" % (" + ".join(big_k[0])[:70]))
    p("  ★ 最大组 UV 配置 = %s ｜ 顶点色 %d ｜ 形态键 %s"
      % (list(big_k[1]) or "无", big_k[2], big_k[3]))
    p("  ★ 最大组里多实例(data.users>1)对象 = %d / %d"
      % (sum(1 for o in big if o.data.users > 1), len(big)))
    p("  ★ 若真的全量合并，父级会被摘掉的网格对象 = %d / %d"
      % (sum(1 for o in meshes if o.parent), n_obj))
except Exception:
    p("!! " + traceback.format_exc())

# --------------------------------------------------- E) EMPTY 不动点
try:
    section("[E] EMPTY 不动点模拟（只算不删）")
    keep = set()
    for o in objs:
        if o.type != 'EMPTY':
            keep.add(o.name)
    for o in objs:
        for c in o.constraints:
            if c.target:
                keep.add(c.target.name)
        if o.animation_data:
            for d in o.animation_data.drivers:
                for v in d.variables:
                    for t in v.targets:
                        try:
                            if t.id:
                                keep.add(t.id.name)
                        except Exception:
                            pass
        for ps in getattr(o, "particle_systems", []):
            try:
                if ps.settings.dupli_object:
                    keep.add(ps.settings.dupli_object.name)
                if ps.settings.instance_object:
                    keep.add(ps.settings.instance_object.name)
            except Exception:
                pass
    for m in D.materials:
        if m.node_tree:
            for n in m.node_tree.nodes:
                for s in n.inputs:
                    if s.type == 'OBJECT' and getattr(s, "default_value", None):
                        keep.add(s.default_value.name)
    for sc in D.scenes:
        if sc.camera:
            keep.add(sc.camera.name)
    for c in D.cameras:
        try:
            if c.dof and c.dof.focus_object:
                keep.add(c.dof.focus_object.name)
        except Exception:
            pass
    seed_n = len(keep)
    rounds = 0
    while True:
        rounds += 1
        add = set()
        for o in objs:
            if o.name in keep and o.parent and o.parent.name not in keep:
                add.add(o.parent.name)
        if not add:
            break
        keep |= add
        if rounds > 300:
            p("  ⚠ 未收敛（>300 轮）")
            break
    empties = [o for o in objs if o.type == 'EMPTY']
    removable = [o for o in empties if o.name not in keep]
    p("  引用种子 %d 个 ｜ 不动点 %d 轮收敛" % (seed_n, rounds))
    p("  EMPTY %d 个 → 保留 %d ｜ ★ 可删 %d"
      % (len(empties), len(empties) - len(removable), len(removable)))
    if removable:
        p("  可删名单按命名族:")
        for k, v in Counter(re.sub(r'[\.\-_]?\d+$', '', o.name) for o in removable).most_common(30):
            p("    %3d×  %s" % (v, k))
        p("  示例: " + ", ".join(o.name for o in removable[:10]))
    p("  ⚠ 删前后『非 EMPTY 对象数』必须完全相等 —— 最强断言")
except Exception:
    p("!! " + traceback.format_exc())

# --------------------------------------------------- F) 其它
try:
    section("[F] 其它顺带项")
    p("  孤儿网格/材质/图像 (users==0): %d / %d / %d"
      % (sum(1 for m in D.meshes if m.users == 0),
         sum(1 for m in D.materials if m.users == 0),
         sum(1 for m in D.images if m.users == 0)))
    root_children = [x.name for x in D.scenes[0].collection.children]
    for c in D.collections:
        if len(c.objects) == 0 and len(c.children) == 0:
            p("  空集合: %s  users=%d  挂场景根=%s" % (c.name, c.users, c.name in root_children))
    p("  多实例网格对象总数 (data.users>1): %d" % sum(1 for o in meshes if o.data.users > 1))
    p("  材质槽数分布（网格对象）: %s"
      % dict(Counter(len(o.data.materials) for o in meshes).most_common()))
    p("  『金色』类材质（含金、不含铜/brass/copper）:")
    use = Counter()
    for o in meshes:
        for m in set(x for x in o.data.materials if x):
            use[m.name] += 1
    for m in D.materials:
        if GOLD.search(m.name) and not COPPER.search(m.name) and use.get(m.name, 0):
            p("    %-42s 引用对象 %d" % (m.name[:42], use[m.name]))
except Exception:
    p("!! " + traceback.format_exc())

p(""); p("=" * 74); p("用时 %.1f 秒" % (time.time() - T0)); p("=" * 74)

with open(REPORT_TXT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(L))
print("\n".join(L))
