# -*- coding: utf-8 -*-
"""第三轮精查（只读）：修改器构成 / 分组口径对比 / 共享网格的其它使用者"""
import bpy, os, re, time, traceback
from collections import Counter, defaultdict

# 报告落盘目录：默认取当前工作目录，可用环境变量 BPS_WORK 覆盖
WORK = os.environ.get("BPS_WORK") or os.getcwd()
L = []
def p(s=""):
    L.append(str(s))
def section(t):
    p(""); p("-" * 74); p(t); p("-" * 74)

T0 = time.time()
import numpy as np
COPPER = re.compile(r"铜|[Cc]opper|[Bb]rass")   # 目标材质正则 —— 换工程时改这里
D = bpy.data
objs = list(D.objects)
meshes = [o for o in objs if o.type == 'MESH']

def used_named(me):
    mats = list(me.materials)
    n = len(me.polygons)
    if n == 0:
        return []
    a = np.empty(n, dtype=np.int32)
    me.polygons.foreach_get('material_index', a)
    return [mats[i].name for i in sorted(set(int(x) for x in np.unique(a)))
            if i < len(mats) and mats[i]]

def top_ancestor(o, depth=999):
    x = o
    while x.parent and depth > 0:
        x = x.parent
        depth -= 1
    return x.name

p("=" * 74)
p("第三轮精查（只读）· 261002x03   " + time.strftime("%Y-%m-%d %H:%M:%S"))
p("=" * 74)

# 铜件集合（单材质含铜）
solo = []
for _o in meshes:
    _named = used_named(_o.data)
    if len(_named) == 1 and COPPER.search(_named[0]):
        solo.append((_o, _named[0]))

# ------------------------------------------------- 1) 修改器构成
try:
    section("[1] 修改器构成（合并会不会丢东西）")
    mod_type = Counter()
    mod_name = Counter()
    n_mod_objs = 0
    for o in objs:
        ms = list(o.modifiers)
        if ms:
            n_mod_objs += 1
        for m in ms:
            mod_type[m.type] += 1
            mod_name[m.name] += 1
    p("  带修改器的对象 %d / %d" % (n_mod_objs, len(objs)))
    p("  修改器类型分布: %s" % dict(mod_type.most_common()))
    p("  修改器名字分布: %s" % dict(mod_name.most_common(10)))
    p("  节点组名: %s" % [g.name for g in D.node_groups])
    p("")
    p("  ★ 风险评估：join() 只保留【活动对象】的修改器，其余成员的修改器被丢弃。")
    p("    若修改器是『按角度平滑/Smooth by Angle』→ 合并后着色(锐边)会变。")
    # 铜件是否带修改器
    withmod = [o for o, _ in solo if o.modifiers]
    p("  铜件中带修改器的: %d / %d  %s"
      % (len(withmod), len(solo),
         dict(Counter(m.type for o, _ in solo for m in o.modifiers).most_common())))
except Exception:
    p("!! " + traceback.format_exc())

# ------------------------------------------------- 2) 三种分组口径对比
try:
    section("[2] 三种分组口径对比（决定'合并成几个'）")
    by_mat = defaultdict(list)
    by_mat_par = defaultdict(list)
    by_mat_top = defaultdict(list)
    for o, mn in solo:
        uv = tuple(l.name for l in o.data.uv_layers)
        vc = len(getattr(o.data, "color_attributes", []) or [])
        sk = bool(o.data.shape_keys)
        by_mat[(mn, uv, vc, sk)].append(o)
        by_mat_par[(mn, uv, vc, sk, o.parent.name if o.parent else "<无父级>")].append(o)
        by_mat_top[(mn, uv, vc, sk, top_ancestor(o))].append(o)

    p("  口径① 只按【材质+UV配置】：          %d 组 → 结果 %d 个对象" % (len(by_mat), len(by_mat)))
    p("  口径② 按【材质+UV配置+父级】：       %d 组 → 结果 %d 个对象" % (len(by_mat_par), len(by_mat_par)))
    p("  口径③ 按【材质+UV配置+顶层祖先】：   %d 组 → 结果 %d 个对象" % (len(by_mat_top), len(by_mat_top)))
    p("")
    p("  口径② 明细：")
    for k in sorted(by_mat_par, key=lambda x: (-len(by_mat_par[x]), x[0])):
        g = by_mat_par[k]
        multi = sum(1 for o in g if o.data.users > 1)
        p("    %-30s 父级=%-26s %2d个对象%s"
          % (k[0][:30], k[4][:26], len(g), ("  ⚠多实例%d" % multi) if multi else ""))
    p("")
    p("  各口径能省下的对象数:")
    p("    ① %d ｜ ② %d ｜ ③ %d" % (len(solo) - len(by_mat),
                                    len(solo) - len(by_mat_par),
                                    len(solo) - len(by_mat_top)))
except Exception:
    p("!! " + traceback.format_exc())

# ------------------------------------------------- 3) 共享网格的其它使用者
try:
    section("[3] 铜件里 12 个多实例对象 —— 共享网格还被谁用着")
    share = defaultdict(list)
    for o in meshes:
        if o.data.users > 1:
            share[o.data.name].append(o)
    solo_names = set(o.name for o, _ in solo)
    for mname, group in share.items():
        hit = [x for x in group if x.name in solo_names]
        if not hit:
            continue
        p("  网格 %-22s 被 %d 个对象共用:" % (mname[:22], len(group)))
        for x in group:
            mark = " ← 铜件" if x.name in solo_names else ""
            p("      %-28s 材质=%s%s"
              % (x.name[:28], ",".join(m.name for m in x.data.materials if m)[:34], mark))
except Exception:
    p("!! " + traceback.format_exc())

# ------------------------------------------------- 4) 无相机 / 其它
try:
    section("[4] 其它")
    p("  场景 camera 属性: %s（工程里有 CAMERA 对象 %d 个）"
      % (D.scenes[0].camera, sum(1 for o in objs if o.type == 'CAMERA')))
    p("  渲染分辨率: %dx%d  引擎=%s"
      % (D.scenes[0].render.resolution_x, D.scenes[0].render.resolution_y,
         D.scenes[0].render.engine))
    p("  输出路径: %s" % D.scenes[0].render.filepath)
    p("  顶层集合: %s" % [c.name for c in D.scenes[0].collection.children])
    p("  集合清单: %s" % [(c.name, len(c.objects)) for c in D.collections])
    p("  自定义属性(对象级)带键的对象数: %d"
      % sum(1 for o in objs if len(o.keys()) > 0))
    keys = Counter()
    for o in objs:
        for k in o.keys():
            keys[k] += 1
    p("  自定义属性键 top: %s" % dict(keys.most_common(12)))
except Exception:
    p("!! " + traceback.format_exc())

p(""); p("=" * 74); p("用时 %.1f 秒" % (time.time() - T0)); p("=" * 74)
with open(os.path.join(WORK, "scan3_report.txt"), "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(L))
print("\n".join(L))
