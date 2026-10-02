# -*- coding: utf-8 -*-
"""
只读体检：整理工程前的**第一段**扫描（不修改任何数据）

运行：
  blender.exe --background --factory-startup "<blend>" --python scan_project.py
产物（写到 WORK，默认当前工作目录）：
  <WORK>/scan_report.txt 与 scan_report.json
"""
import bpy, os, re, json, time, traceback
from collections import Counter, defaultdict

# 报告落盘目录：默认取当前工作目录，可用环境变量 BPS_WORK 覆盖
WORK = os.environ.get("BPS_WORK") or os.getcwd()
os.makedirs(WORK, exist_ok=True)
REPORT_TXT = os.path.join(WORK, "scan_report.txt")
REPORT_JSON = os.path.join(WORK, "scan_report.json")

L = []
def p(s=""):
    s = str(s)
    L.append(s)

def section(title):
    p("")
    p("-" * 72)
    p(title)
    p("-" * 72)

DATA = {}
T0 = time.time()

try:
    import numpy as np
except Exception:
    np = None

D = bpy.data
objs = list(D.objects)
meshes = [o for o in objs if o.type == 'MESH']

p("=" * 72)
p("只读体检报告  ·  261002x03")
p("filepath : " + (bpy.data.filepath or "<未命名>"))
p("Blender  : " + bpy.app.version_string + "   (--factory-startup 无头只读)")
p("生成时间 : " + time.strftime("%Y-%m-%d %H:%M:%S"))
p("=" * 72)

# ---------------------------------------------------------------- 0) 总量
try:
    section("[0] 总量")
    by_type = Counter(o.type for o in objs)
    p("  对象 %d   网格对象 %d" % (len(objs), len(meshes)))
    p("  类型分布: " + ", ".join("%s=%d" % (k, v) for k, v in by_type.most_common()))
    p("  场景 %d | 集合 %d | 网格数据块 %d | 材质 %d | 图像 %d | 动作 %d | 节点组 %d"
      % (len(D.scenes), len(D.collections), len(D.meshes), len(D.materials),
         len(D.images), len(D.actions), len(D.node_groups)))
    p("  顶点合计 %d | 面合计 %d"
      % (sum(len(o.data.vertices) for o in meshes),
         sum(len(o.data.polygons) for o in meshes)))
    DATA["objects_total"] = len(objs)
    DATA["by_type"] = dict(by_type)
    DATA["meshes"] = len(meshes)
    DATA["materials"] = len(D.materials)
    DATA["images"] = len(D.images)
except Exception:
    p("!! 失败: " + traceback.format_exc())

# ------------------------------------------------- 1) 层级 / 集合归属
try:
    section("[1] 层级与集合归属（先看这两条，决定清单算不算数）")
    child_count = Counter()
    parent_map = {}
    for o in objs:
        if o.parent:
            parent_map[o.name] = o.parent.name
            child_count[o.parent.name] += 1
    empties = [o for o in objs if o.type == 'EMPTY']
    empty_no_child = [o for o in empties if child_count.get(o.name, 0) == 0]
    no_coll = [o for o in objs if len(o.users_collection) == 0]
    p("  EMPTY %d 个（其中【无子级】%d 个）" % (len(empties), len(empty_no_child)))
    p("  有父级的对象 %d 个（合并时要处理世界变换烘焙）" % len(parent_map))
    p("  ★ 无集合归属对象 %d 个" % len(no_coll))
    if no_coll:
        p("     → 这类对象不被场景引用，存盘/重载会直接消失（等价于不存在）")
        p("     按类型: " + str(dict(Counter(o.type for o in no_coll).most_common())))
        p("     按命名族 top10: " + str(Counter(re.sub(r'[\.\-_]?\d+$', '', o.name)
                                                 for o in no_coll).most_common(10)))
    DATA["empty"] = len(empties)
    DATA["empty_no_child"] = len(empty_no_child)
    DATA["objects_with_parent"] = len(parent_map)
    DATA["objects_no_collection"] = len(no_coll)
    DATA["no_collection_by_type"] = dict(Counter(o.type for o in no_coll))
except Exception:
    p("!! 失败: " + traceback.format_exc())

# ------------------------------------------------------------ 2) 材质清单
COPPER_RE = re.compile(r"铜|[Cc]opper|[Bb]rass|B[Rr]ASS|金属|metal", re.UNICODE)
COPPER_STRICT_RE = re.compile(r"铜|[Cc]opper|[Bb]rass", re.UNICODE)

def bsdf_info(mat):
    """取材质里【真正生效】的输出连着的 Principled 的基色/金属度/粗糙度"""
    try:
        nt = mat.node_tree
        if nt is None:
            return None
        out = None
        for n in nt.nodes:
            if n.type == 'OUTPUT_MATERIAL' and getattr(n, "is_active_output", True):
                out = n
                break
        if out is None:
            return None
        src = None
        sock = out.inputs.get("Surface")
        if sock and sock.is_linked:
            src = sock.links[0].from_node
        if src is None:
            return None
        g = lambda k: (tuple(round(v, 3) for v in src.inputs[k].default_value)
                       if k in src.inputs and hasattr(src.inputs[k].default_value, "__len__")
                       else (round(src.inputs[k].default_value, 3)
                             if k in src.inputs else None))
        return {"node": src.name, "type": src.type, "base_color": g("Base Color"),
                "metallic": g("Metallic"), "roughness": g("Roughness")}
    except Exception:
        return None

try:
    section("[2] 材质清单（按被引用的网格对象数排序）")
    mat_use = Counter()
    mat_solo = Counter()           # 作为【唯一有面槽】被使用
    mat_multi = Counter()          # 与其他材质同在一个网格上
    for o in meshes:
        me = o.data
        mats = [m for m in me.materials]
        used = set()
        n = len(me.polygons)
        if n:
            if np is not None:
                a = np.empty(n, dtype=np.int32)
                me.polygons.foreach_get('material_index', a)
                used = set(int(x) for x in np.unique(a))
            else:
                used = set(pg.material_index for pg in me.polygons)
        named = [mats[i] for i in sorted(used) if i < len(mats) and mats[i]]
        for m in set(named):
            mat_use[m.name] += 1
        if len(named) == 1:
            mat_solo[named[0].name] += 1
        elif len(named) > 1:
            for m in set(named):
                mat_multi[m.name] += 1

    p("  全部材质 %d 个（含 0 引用者）" % len(D.materials))
    p("")
    p("  %-4s %-38s %6s %6s %6s %8s" % ("#", "材质名", "引用对象", "独占", "共享", "users"))
    ranked = sorted(D.materials, key=lambda m: (-mat_use.get(m.name, 0), m.name))
    for i, m in enumerate(ranked[:50], 1):
        flag = " ★铜" if COPPER_STRICT_RE.search(m.name) else ""
        p("  %-4d %-38s %6d %6d %6d %8d%s"
          % (i, m.name[:38], mat_use.get(m.name, 0), mat_solo.get(m.name, 0),
             mat_multi.get(m.name, 0), m.users, flag))
    if len(ranked) > 50:
        p("  ...（其余 %d 个材质引用对象数为 0 或极少）" % (len(ranked) - 50))

    copper = [m for m in D.materials if COPPER_RE.search(m.name)]
    p("")
    p("  >>> 名字含「铜/copper/brass/金属/metal」的材质 %d 个：" % len(copper))
    copper_rows = []
    for m in copper:
        info = bsdf_info(m)
        row = {"name": m.name, "users": m.users,
               "ref_obj": mat_use.get(m.name, 0),
               "solo": mat_solo.get(m.name, 0),
               "multi": mat_multi.get(m.name, 0),
               "strict_copper": bool(COPPER_STRICT_RE.search(m.name)),
               "node": info}
        copper_rows.append(row)
        p("    - %-34s 引用%-5d 独占%-5d 共享%-5d users=%-4d %s"
          % (m.name[:34], row["ref_obj"], row["solo"], row["multi"], m.users,
             ("| 生效节点 %s(%s) 色%s 金属%s 粗糙%s"
              % (info["node"], info["type"], info["base_color"], info["metallic"], info["roughness"]))
             if info else "| ⚠ 没取到生效的 Principled（可能是发射/其他节点）"))
    DATA["copper_materials"] = copper_rows
except Exception:
    p("!! 失败: " + traceback.format_exc())

# ------------------------------------------- 3) 合并候选（单材质铜网格）
try:
    section("[3] 合并候选判定（规则：网格【有面的材质】恰好 1 个，且是铜材质 → 可合并）")
    solo_cu, skip_cu, solo_other = [], [], []
    for o in meshes:
        me = o.data
        mats = [m for m in me.materials]
        n = len(me.polygons)
        used = set()
        if n:
            if np is not None:
                a = np.empty(n, dtype=np.int32)
                me.polygons.foreach_get('material_index', a)
                used = set(int(x) for x in np.unique(a))
            else:
                used = set(pg.material_index for pg in me.polygons)
        named = [mats[i].name for i in sorted(used) if i < len(mats) and mats[i]]
        is_cu = any(COPPER_STRICT_RE.search(x) for x in named)
        if len(named) == 1 and is_cu:
            solo_cu.append((o, named[0]))
        elif len(named) > 1 and is_cu:
            skip_cu.append((o, named))
        else:
            solo_other.append(o)

    p("  单材质铜网格（可合并）      : %d 个对象" % len(solo_cu))
    p("  多材质且含铜（按规则跳过）  : %d 个对象" % len(skip_cu))
    p("  其它（不含铜 / 无面）       : %d 个对象" % len(solo_other))

    groups = defaultdict(list)
    for o, mn in solo_cu:
        uv = tuple(l.name for l in o.data.uv_layers)
        vc = len(getattr(o.data, "color_attributes", []) or [])
        sk = bool(o.data.shape_keys)
        groups[(mn, uv, vc, sk)].append(o)

    p("")
    p("  按【材质名 + UV层 + 顶点色 + 形态键】分组 → %d 组" % len(groups))
    p("  %-34s %6s %10s %10s %8s" % ("材质", "对象数", "顶点", "面", "预计耗时"))
    LOG = open(os.path.join(WORK, "merge_perf.log"), "a", encoding="utf-8")
    for k in sorted(groups, key=lambda x: -len(groups[x])):
        g = groups[k]
        nv = sum(len(x.data.vertices) for x in g)
        nf = sum(len(x.data.polygons) for x in g)
        # join 开销看对象数：实测 24137 对象 ≈ 322s ⇒ 约 13.3 ms/对象（保守取 15ms）
        est = len(g) * 0.015
        p("  %-34s %6d %10d %10d %7.1fs" % (k[0][:34], len(g), nv, nf, est))
    LOG.close()

    total_est = sum(len(g) for g in groups.values()) * 0.015
    p("")
    p("  合并后对象数预测: %d → %d（%d 组，每组 1 个）"
      % (len(solo_cu), len(groups), len(groups)))
    p("  预计合并耗时量级: 约 %.0f 秒（按对象数 × 15ms 保守估）" % total_est)

    # ---- 红线与风险项
    p("")
    p("  【红线 / 风险项】")
    def diag(name, lst, fn):
        hit = [x for x in lst if fn(x)]
        p("    %-28s %4d 个 %s" % (name, len(hit),
                                  ("｜例: " + ", ".join(o.name for o in hit[:5])) if hit else ""))
        return hit
    diag("mesh 多实例 (data.users>1)", [x[0] for x in solo_cu], lambda o: o.data.users > 1)
    diag("有父级（世界变换需烘焙）", [x[0] for x in solo_cu], lambda o: o.parent is not None)
    diag("非单位缩放", [x[0] for x in solo_cu],
         lambda o: any(abs(s - 1.0) > 1e-6 for s in o.scale))
    diag("非单位旋转", [x[0] for x in solo_cu],
         lambda o: any(abs(r) > 1e-6 for r in o.rotation_euler))
    diag("有形态键 shape_keys", [x[0] for x in solo_cu], lambda o: bool(o.data.shape_keys))
    diag("有顶点色", [x[0] for x in solo_cu],
         lambda o: len(getattr(o.data, "color_attributes", []) or []) > 0)
    diag("有 UV 层", [x[0] for x in solo_cu], lambda o: len(o.data.uv_layers) > 0)
    diag("无集合归属", [x[0] for x in solo_cu], lambda o: len(o.users_collection) == 0)
    diag("在隐藏集合/自身隐藏", [x[0] for x in solo_cu],
         lambda o: o.hide_viewport or o.hide_render)
    diag("有动画 (animation_data)", [x[0] for x in solo_cu],
         lambda o: o.animation_data is not None and
                   (o.animation_data.action is not None or len(o.animation_data.drivers) > 0))
    diag("多材质被跳过·有父级", [x[0] for x in skip_cu], lambda o: o.parent is not None)

    p("")
    p("  【被跳过的多材质网格 —— 材质组合 top10】")
    combos = Counter(tuple(sorted(x[1])) for x in skip_cu)
    for c, n in combos.most_common(10):
        p("    %3d×  %s" % (n, " + ".join(c)))
    p("")
    p("  【被跳过的多材质网格 —— 单看铜材质占比】")
    cui = Counter()
    for o, named in skip_cu:
        for x in named:
            if COPPER_STRICT_RE.search(x):
                cui[x] += 1
    for c, n in cui.most_common(10):
        p("    %3d×  含 %s" % (n, c))

    DATA["solo_copper_objects"] = len(solo_cu)
    DATA["skip_multi_copper_objects"] = len(skip_cu)
    DATA["merge_groups"] = len(groups)
    DATA["merge_group_detail"] = [
        {"material": k[0], "n_objects": len(groups[k]),
         "verts": sum(len(x.data.vertices) for x in groups[k]),
         "faces": sum(len(x.data.polygons) for x in groups[k])}
        for k in sorted(groups, key=lambda x: -len(groups[x]))]
    DATA["redline_multi_instance"] = sum(1 for x in solo_cu if x[0].data.users > 1)
    DATA["with_parent"] = sum(1 for x in solo_cu if x[0].parent is not None)
    DATA["non_unit_scale"] = sum(1 for x in solo_cu if any(abs(s - 1) > 1e-6 for s in x[0].scale))
    DATA["with_uv"] = sum(1 for x in solo_cu if len(x[0].data.uv_layers) > 0)
    DATA["with_vcol"] = sum(1 for x in solo_cu
                            if len(getattr(x[0].data, "color_attributes", []) or []) > 0)
    DATA["with_shapekey"] = sum(1 for x in solo_cu if x[0].data.shape_keys)
except Exception:
    p("!! 失败: " + traceback.format_exc())

# ------------------------------------------------------- 4) 清理类项目
try:
    section("[4] 顺带能清的项目（本次不一定做，先给数）")
    orph_mesh = [m for m in D.meshes if m.users == 0]
    orph_mat = [m for m in D.materials if m.users == 0 and not m.use_fake_user]
    orph_img = [m for m in D.images if m.users == 0 and not m.use_fake_user]
    orph_coll = [c for c in D.collections if len(c.objects) == 0 and len(c.children) == 0]
    empties = [o for o in objs if o.type == 'EMPTY']
    cc = Counter()
    for o in objs:
        if o.parent:
            cc[o.parent.name] += 1
    en = [o for o in empties if cc.get(o.name, 0) == 0]
    miss = []
    for im in D.images:
        try:
            if im.source == 'FILE' and im.filepath and im.packed_file is None:
                if not os.path.exists(bpy.path.abspath(im.filepath)):
                    miss.append(im.name)
        except Exception:
            pass
    p("  孤儿网格数据块 (users==0) : %d" % len(orph_mesh))
    p("  孤儿材质    (users==0 无fake): %d" % len(orph_mat))
    p("  孤儿图像    (users==0 无fake): %d" % len(orph_img))
    p("  空集合 (无对象无子集合)     : %d  %s"
      % (len(orph_coll), [c.name for c in orph_coll[:10]]))
    p("  无子级 EMPTY 数             : %d  （收敛清理的候选）" % len(en))
    p("  真缺失贴图 (未打包且磁盘无) : %d  %s" % (len(miss), miss[:10]))
    DATA["orphan_mesh"] = len(orph_mesh)
    DATA["orphan_material"] = len(orph_mat)
    DATA["orphan_image"] = len(orph_img)
    DATA["empty_collections"] = len(orph_coll)
    DATA["missing_images"] = len(miss)
except Exception:
    p("!! 失败: " + traceback.format_exc())

p("")
p("=" * 72)
p("扫描完成，用时 %.1f 秒" % (time.time() - T0))
p("=" * 72)

txt = "\n".join(L)
with open(REPORT_TXT, "w", encoding="utf-8", newline="\n") as f:
    f.write(txt)
with open(REPORT_JSON, "w", encoding="utf-8", newline="\n") as f:
    json.dump(DATA, f, ensure_ascii=False, indent=2)
print(txt)
print("\n[report] " + REPORT_TXT)
