# -*- coding: utf-8 -*-
"""
按材质拆分为多个网格体 —— 独立验证脚本（读磁盘基线逐项比对）
================================================================================
在**新的请求**里读磁盘基线，逐项核对拆分结果。

⚠️ 为什么必须另开一次请求：同一次 exec 内刚改完就读 `matrix_world` 等求值结果，
   读到的是**未刷新缓存**，数值可能不对（数据其实是对的）。
   而且本脚本的价值就在于「与录制基线的那次执行相互独立」。

用法：

    MODE = "check"     # 逐项比对并输出判定

配置 BASE_JSON 指向 separate_by_material.py 录的基线；
部件名单默认自动发现（原名 + 原名.001/...），也会读 STATUS_JSON 里记录的结果
（重命名过后依然能正确找到）。
================================================================================
"""

import json
import os

# ==============================================================================
# ================================ 配置区 ======================================
# ==============================================================================
TARGET = "对象13735"
BASE_JSON = "D:/workbuddy/_blender_sep/baseline.json"
STATUS_JSON = "D:/workbuddy/_blender_sep/status.json"   # 可留空 "" 跳过

PART_NAMES = []            # 留空 = 自动发现（优先读 STATUS_JSON，其次按名字前缀）

TOL_MAT = 1.0e-6           # 矩阵元素差阈值
TOL_BBOX = 1.0e-4          # 世界包围盒阈值 —— 仅用于旧格式基线的降级提示；第 7 节已改用局部坐标判据
# ==============================================================================


C = None
D = None
PASS = []
FAIL = []
NOTE = []
WARN = []


def ok(msg):
    PASS.append(msg)
    print(f"  ✅ {msg}")


def bad(msg):
    FAIL.append(msg)
    print(f"  ❌ {msg}")


def warn(msg):
    """预期之内、但确实改变了数据/需要知悉 —— 不计入 FAIL"""
    WARN.append(msg)
    print(f"  ⚠️  {msg}")


def note(msg):
    NOTE.append(msg)
    print(f"  ℹ️  {msg}")


def maxdiff(a, b):
    return max(abs(a[r][c] - b[r][c]) for r in range(4) for c in range(4))


def bbox_of(mw, bound_box):
    pts = [mw @ __import__("mathutils").Vector(c) for c in bound_box]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def local_extent_of(me):
    """局部坐标真实范围（逐顶点 min/max）。与帧无关，且不依赖「局部 AABB 变换」这种松上界。"""
    n = len(me.vertices)
    if n == 0:
        return None
    try:
        import numpy as np
        a = np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get("co", a)
        a = a.reshape(-1, 3)
        return [a.min(axis=0).tolist(), a.max(axis=0).tolist()]
    except Exception:
        lo = [1e30, 1e30, 1e30]
        hi = [-1e30, -1e30, -1e30]
        for v in me.vertices:
            c = v.co
            for i in range(3):
                if c[i] < lo[i]:
                    lo[i] = c[i]
                if c[i] > hi[i]:
                    hi[i] = c[i]
        return [lo, hi]


def discover_parts():
    names = list(PART_NAMES)
    if not names and STATUS_JSON and os.path.isfile(STATUS_JSON):
        try:
            with open(STATUS_JSON, "r", encoding="utf-8") as fh:
                st = json.load(fh)
            names = [p["object"] for p in st.get("parts", []) if p.get("object")]
        except Exception:
            names = []
    if not names:
        names = [o.name for o in D.objects
                 if o.name == TARGET or o.name.startswith(TARGET + ".")]
    names = [n for n in names if D.objects.get(n) is not None]
    names.sort(key=lambda n: (n != TARGET, n))
    return names


def main():
    global C, D
    import bpy
    from collections import Counter

    C = bpy.context
    D = bpy.data

    if not os.path.isfile(BASE_JSON):
        print(f"❌ 基线文件不存在: {BASE_JSON}（先跑 separate_by_material.py 录基线）")
        return
    with open(BASE_JSON, "r", encoding="utf-8") as fh:
        b = json.load(fh)

    print("=" * 78)
    print("按材质拆分 —— 独立验证")
    print("=" * 78)
    print(f"目标对象      : {TARGET}")
    print(f"基线文件      : {BASE_JSON}")
    print(f"基线录制时对象: {b['object']}  data={b['data']}  users={b['data_users']}")
    print()

    parts = discover_parts()
    objs = [D.objects[n] for n in parts]

    # ---------------------------------------------------------------- 1) 存在性
    #
    # ⚠️ 判据必须是「**有面的**材质槽数」而不是「材质槽总数」。
    #    源码依据（editors/mesh/editmesh_tools.cc · mesh_separate_material）：
    #    它只遍历**面的** mat_nr，从不遍历材质槽 ⇒ 空槽（有材质但零面）
    #    既不产生新对象，也不会被原对象保留；各自的部件数量只会等于「有面的槽数」。
    #    若拿槽总数当判据，凡有空槽的对象都会被误报为「部件数不符」。
    print("=== 1) 部件清单 ===")
    used_idx = sorted(int(k) for k in b["face_by_mat"])
    exp_n = len(used_idx)
    all_idx = [s["i"] for s in b["slots"]]
    empty_idx = [i for i in all_idx if i not in used_idx]
    if len(objs) == exp_n:
        ok(f"部件数 {len(objs)} == 基线「有面的」材质槽数 {exp_n}"
           f"  (有面槽={used_idx} / 全部槽={all_idx})")
    else:
        bad(f"部件数 {len(objs)} != 基线「有面的」材质槽数 {exp_n}"
            f"  (有面槽={used_idx} / 全部槽={all_idx})")
    if empty_idx:
        note(f"基线里有 {len(empty_idx)} 个「空材质槽」(有材质但零面) index={empty_idx} —— "
             f"按源码它们不产生对象，且会在拆分时被清掉，属预期，不是异常")
    for s in b["slots"]:
        if s["i"] in empty_idx:
            print(f"    (空槽 {s['i']}: 材质={s['material']!r} — 拆分后不再被任何部件引用)")
    for o in objs:
        mats = [s.material.name if s.material else None for s in o.material_slots]
        print(f"    {o.name:<26} data={o.data.name:<26} polys={len(o.data.polygons):>9}"
              f"  verts={len(o.data.vertices):>9}  slots={mats}")
    # ---------------------------------------------------------------- 2) 几何守恒
    print()
    print("=== 2) 几何守恒 ===")
    base_fm = {int(k): v for k, v in b["face_by_mat"].items()}
    base_polys = b["counts"]["polys"]
    base_verts = b["counts"]["verts"]
    base_edges = b["counts"]["edges"]
    now_polys = sum(len(o.data.polygons) for o in objs)
    now_verts = sum(len(o.data.vertices) for o in objs)
    now_edges = sum(len(o.data.edges) for o in objs)
    print(f"    基线 面/顶点/边 = {base_polys} / {base_verts} / {base_edges}")
    print(f"    现在 面/顶点/边 = {now_polys} / {now_verts} / {now_edges}")
    if now_polys == base_polys:
        ok(f"面数精确守恒 ({base_polys})")
    else:
        bad(f"面数不守恒：{base_polys} -> {now_polys}（差 {now_polys - base_polys}）")
    if now_verts == base_verts:
        ok(f"顶点数精确守恒 ({base_verts}) → 材质组之间拓扑独立，跨材质边界不共享顶点")
    else:
        note(f"顶点数 {base_verts} -> {now_verts}（+{now_verts - base_verts}）："
             f"材质边界处共享顶点被各自复制，属正常，非数据损坏")
    print(f"    V-E+F 现在合计 = {now_verts - now_edges + now_polys}"
          f"（基线 {base_verts - base_edges + base_polys}）")

    # ---------------------------------------------------- 3) 每部件材质槽映射
    print()
    print("=== 3) 每部件材质槽与面数映射 ===")
    base_slot = {s["i"]: s["material"] for s in b["slots"]}
    seen_slots = Counter()
    for o in objs:
        mats = [s.material.name if s.material else None for s in o.material_slots]
        if len(mats) != 1:
            bad(f"{o.name}: 材质槽数 = {len(mats)}，应为 1")
            continue
        nm = mats[0]
        idx = [k for k, v in base_slot.items() if v == nm]
        if not idx:
            bad(f"{o.name}: 材质 {nm!r} 不在基线材质槽里")
            continue
        k = idx[0]
        seen_slots[k] += 1
        exp = base_fm.get(k)
        act = len(o.data.polygons)
        if act == exp:
            ok(f"{o.name:<26} 材质={nm!r} 面数={act} == 基线槽{k}的面数")
        else:
            bad(f"{o.name:<26} 材质={nm!r} 面数={act} != 基线槽{k}的 {exp}")
    missing = [k for k in base_fm if seen_slots[k] == 0]
    if missing:
        bad(f"这些材质槽没有对应部件: {[(k, base_slot.get(k)) for k in missing]}")
    else:
        ok("基线每个材质槽都有且仅有一个对应部件")

    # ---------------------------------------------------- 4) 父级/位姿一致性
    print()
    print("=== 4) 父级 / MPI / 世界矩阵 ===")
    b_mw = b["matrix_world"]
    b_mpi = b["mpi"]
    b_par = b["parent"]
    for o in objs:
        d_mw = maxdiff(o.matrix_world, b_mw)
        d_mpi = maxdiff(o.matrix_parent_inverse, b_mpi)
        par_now = o.parent.name if o.parent else None
        flags = (d_mw < TOL_MAT) and (d_mpi < TOL_MAT) and (par_now == b_par)
        t = o.matrix_world.to_translation()
        msg = (f"{o.name:<26} parent={par_now} (基线 {b_par})"
               f"  max|Δworld|={d_mw:.3e}  max|ΔMPI|={d_mpi:.3e}"
               f"  世界平移=({t.x:.4f},{t.y:.4f},{t.z:.4f})")
        ok(msg) if flags else bad(msg)

    # ---------------------------------------------------- 5) 数据层属性保留
    print()
    print("=== 5) 数据层属性（UV / 自定义法线 / 其它载荷层）===")
    # 这些层「消失」属正常：编辑器选择掩码会被压缩掉；material_index 在
    # 每部件只剩 1 个材质槽时无意义；sharp_edge 由第 6 节单独判定。
    IGNORABLE = {
        "material_index", "sharp_edge", "sharp_face",
        ".select_edge", ".select_poly", ".select_vert",
        ".uv_select_edge", ".uv_select_face", ".uv_select_vert",
    }
    b_uv = b["uv_layers"]
    b_cn = b["has_custom_normals"]
    b_attrs = set(b["attr_names"])
    for o in objs:
        uv = [l.name for l in o.data.uv_layers]
        cn = o.data.has_custom_normals
        an = set(a.name for a in o.data.attributes)
        lost = sorted(b_attrs - an)
        notable = [x for x in lost if x not in IGNORABLE]
        uv_ok = set(uv) == set(b_uv)
        cn_ok = (not b_cn) or (cn == b_cn)
        msg = (f"{o.name:<26} uv={uv} custom_normals={cn}"
               f"  正常消失层={[x for x in lost if x in IGNORABLE]}"
               f"  异常消失层={notable if notable else '无'}")
        if uv_ok and cn_ok and not notable:
            ok(msg)
        else:
            bad(msg + f"  ← uv基线={b_uv} custom_normals基线={b_cn}")

    # ------------------------------------------- 6) 锐边逐组核对（决定性判据）
    sharp_by_mat = b.get("sharp_by_mat")
    if sharp_by_mat:
        print()
        print("=== 6) 锐边(sharp_edge) 逐组核对 —— 属性层消失是不是信息损失？ ===")
        print(f"    基线 全网格锐边总数 = {b['sharp_total']}")
        for o in objs:
            mats = [s.material.name if s.material else None for s in o.material_slots]
            nm = mats[0] if mats else None
            idx = [k for k, v in base_slot.items() if v == nm]
            if not idx:
                continue
            exp = sharp_by_mat.get(str(idx[0]), {}).get("sharp_inside")
            act = o.data.attributes.get("sharp_edge")
            act_n = (sum(1 for v in act.data if v.value) if act is not None else None)
            if act_n is None:
                if exp == 0:
                    ok(f"{o.name:<26} sharp_edge 属性层不存在，但基线该组锐边数 = 0"
                       f" → Blender 丢弃「全默认值」属性层，**无信息损失**")
                else:
                    bad(f"{o.name:<26} sharp_edge 属性层丢失，而基线该组锐边数 = {exp}"
                        f" → **真数据丢失**")
            else:
                if act_n == exp:
                    ok(f"{o.name:<26} 锐边数={act_n} == 基线该组 {exp}")
                else:
                    bad(f"{o.name:<26} 锐边数={act_n} != 基线该组 {exp}")
    else:
        print()
        print("=== 6) 锐边逐组核对：跳过（基线未记录 sharp_by_mat）===")

    # ------------------------------------------- 7) 几何范围守恒（局部坐标，权威判据）
    #
    # ⚠️ 为什么用「局部坐标真实范围」而不是「世界包围盒」？
    #   旧做法两侧口径不对等：
    #     基线侧 = obj.bound_box（局部 AABB）→ 乘 matrix_world，得到的是**松上界**；
    #     拆分后 = 各部件局部 AABB 变换后取并集，每个部件跨度更小 ⇒ 上界更紧。
    #   两者不是同一个量，几何上并集必然 ⊆ 原上界，于是会报出「漂移」——
    #   这不是数据变化，是**判据本身不对等**。
    #   正确判据：两侧都用「逐顶点局部坐标的 min/max」，算法一致、与帧无关，应精确相等。
    print()
    print("=== 7) 几何范围守恒（局部坐标逐顶点真实范围）===")
    b_ext = b.get("local_extent")
    if b_ext:
        lo_e = [1e30, 1e30, 1e30]
        hi_e = [-1e30, -1e30, -1e30]
        for o in objs:
            e = local_extent_of(o.data)
            if e is None:
                continue
            for i in range(3):
                lo_e[i] = min(lo_e[i], e[0][i])
                hi_e[i] = max(hi_e[i], e[1][i])
        print(f"    基线 局部 min={[round(v, 6) for v in b_ext[0]]} max={[round(v, 6) for v in b_ext[1]]}")
        print(f"    现在 局部 min={[round(v, 6) for v in lo_e]} max={[round(v, 6) for v in hi_e]}")
        d = max(max(abs(lo_e[i] - b_ext[0][i]), abs(hi_e[i] - b_ext[1][i])) for i in range(3))
        if d < TOL_BBOX:
            ok(f"局部坐标范围零漂移  max|Δ|={d:.3e}（阈值 {TOL_BBOX:g}）—— 几何精确守恒")
        else:
            bad(f"局部坐标范围漂移 max|Δ|={d:.3e}（阈值 {TOL_BBOX:g}）—— 几何可能被改动")
    else:
        note("基线未记录 local_extent（旧版基线）→ 跳过局部范围判据；"
             "如需该项判定，请用当前版本脚本重新录制基线")

    # 世界包围盒：仅作参考输出，**不参与判定**（见上方口径说明）
    print()
    print("=== 7b) 世界包围盒（仅供参考，不参与判定）===")
    try:
        lo_b = [min(p[i] for p in b["world_bbox"]) for i in range(3)]
        hi_b = [max(p[i] for p in b["world_bbox"]) for i in range(3)]
        los, his = [], []
        for o in objs:
            lo, hi = bbox_of(o.matrix_world, o.bound_box)
            los.append(lo)
            his.append(hi)
        if los:
            lo_n = [min(x[i] for x in los) for i in range(3)]
            hi_n = [max(x[i] for x in his) for i in range(3)]
            print(f"    基线 min={[round(v, 5) for v in lo_b]} max={[round(v, 5) for v in hi_b]}")
            print(f"    现在 min={[round(v, 5) for v in lo_n]} max={[round(v, 5) for v in hi_n]}")
            note("两侧口径不等价（基线=局部AABB变换的松上界；现在=各部件更紧界的并集），"
                 "故本项只打印不判定；几何守恒以第 7 节局部坐标判据为准")
    except Exception as e:
        note(f"世界包围盒参考输出跳过（{type(e).__name__}: {e}）")

    # ---------------------------------------------------- 8) 集合归属
    print()
    print("=== 8) 集合归属 ===")
    b_cols = b["collections"]
    for o in objs:
        cols = sorted(c.name for c in o.users_collection)
        same = set(cols) == set(b_cols)
        (ok if same else bad)(f"{o.name:<26} 集合={cols}  (基线 {b_cols})")

    # ---------------------------------------------------- 9) 材质数据块
    print()
    print("=== 9) 材质数据块引用计数 ===")
    #    分级判据（v1.15.2）：
    #      · 「有面的」槽里的材质丢失 / users=0  ⇒ ❌ 真问题
    #      · 「空槽」里的材质 users=0 但仍存在  ⇒ ⚠️ 未存盘时的中间态（存盘后会丢）
    #      · 「空槽」里的材质已不存在          ⇒ ⚠️ 预期内的滞后效应，但**确实丢了数据**
    #        机制（实测三级分辨）：拆分算子**不删**材质，只把它变成 users=0；
    #        Blender 落盘时丢弃未被引用的数据块 ⇒ 重新打开文件后该材质消失。
    #        所以空槽里「只被本对象引用」的材质，拆分 + 存盘后即永久丢失。
    #        要保留：拆分前 `use_fake_user=True`（见 separator 的 KEEP_EMPTY_SLOT_MATERIALS）。
    lost_used, lost_empty, orphan_empty = [], [], []
    for s in b["slots"]:
        nm = s["material"]
        m = D.materials.get(nm) if nm else None
        usr = m.users if m else None
        fake = m.use_fake_user if m else None
        is_empty = s["i"] in empty_idx
        tag = "空槽" if is_empty else "有面槽"
        msg = (f"[{tag} {s['i']}] {str(nm)[:40]:<42} 基线 users={s['mat_users']}"
               f" -> 现在 users={usr}  fake={fake}")
        if m is None:
            if is_empty:
                lost_empty.append(msg)
            else:
                lost_used.append(msg + "  ← 材质丢失")
        elif usr and usr >= 1:
            ok(msg)
        else:
            if is_empty:
                orphan_empty.append(msg)
            else:
                lost_used.append(msg + "  ← users=0，材质变成孤儿")
    for m_ in lost_used:
        bad(m_)
    for m_ in lost_empty:
        warn(m_ + "  ← 数据块已不存在（拆分+存盘后按孤儿丢弃）")
    for m_ in orphan_empty:
        warn(m_ + "  ← 当前 users=0（尚未存盘；存盘后会按孤儿丢弃）")
    if empty_idx:
        note("空槽材质处置说明：拆分算子不会删它们，只让 users 归零；"
             "**Blender 存盘时会丢弃未被引用的数据块**，故重新打开文件后它们会消失。"
             "若该材质只被本对象引用，等于「拆分 + Ctrl+S = 永久丢失」。"
             "空槽索引=" + str(empty_idx) + "；要保留请在拆分前打 use_fake_user"
             "（separator 的 KEEP_EMPTY_SLOT_MATERIALS = True）")

    # ---------------------------------------------------- 10) 动画/修改器/形态键
    print()
    print("=== 10) 动画 / 修改器 / 形态键 ===")
    print(f"    基线 object_anim={b['object_anim']}  mesh_anim={b['mesh_anim']}"
          f"  modifiers={b['modifiers']}  shape_keys={b['shape_keys']}")
    for o in objs:
        oa = o.animation_data.action.name if (o.animation_data and o.animation_data.action) else None
        ma = o.data.animation_data.action.name if (o.data.animation_data and o.data.animation_data.action) else None
        mods = [(m.name, m.type) for m in o.modifiers]
        sk = o.data.shape_keys.name if o.data.shape_keys else None
        if (oa, ma, mods, sk) == (b["object_anim"], b["mesh_anim"], b["modifiers"], b["shape_keys"]):
            ok(f"{o.name:<26} 与基线一致（anim={oa}, mods={mods}, shape_keys={sk}）")
        else:
            bad(f"{o.name:<26} anim={oa}/{ma} mods={mods} sk={sk}"
                f"  ← 与基线不同（基线 {b['object_anim']}/{b['mesh_anim']}/{b['modifiers']}/{b['shape_keys']}）")

    # ---------------------------------------------------- 11) 场景统计/孤儿
    print()
    print("=== 11) 场景统计与孤儿数据 ===")
    before_objs = set(b["object_names_before"])
    before_meshes = set(b["mesh_names_before"])
    new_objs = sorted(set(o.name for o in D.objects) - before_objs)
    new_meshes = set(m.name for m in D.meshes) - before_meshes
    print(f"    基线 对象数={b['scene_object_count']} mesh数={b['scene_mesh_count']}")
    print(f"    现在 对象数={len(D.objects)} mesh数={len(D.meshes)}")
    print(f"    新增对象={new_objs}")
    print(f"    新增 mesh={sorted(new_meshes)}")
    miss = sorted(n for n in before_objs if n not in D.objects)
    if miss:
        bad(f"基线里的这些对象已消失: {miss}")
    else:
        ok("基线里原有对象全部仍存在")
    if len(new_objs) == exp_n - 1:
        ok(f"新增对象数 {len(new_objs)} == 材质槽数-1 ({exp_n - 1})")
    else:
        note(f"新增对象数 {len(new_objs)} != 材质槽数-1 ({exp_n - 1})")
    orphan_mesh = [m.name for m in D.meshes if m.users == 0]
    if orphan_mesh:
        bad(f"存在 users=0 的孤儿 mesh: {orphan_mesh}")
    else:
        ok("无 users=0 的孤儿 mesh")

    # ---------------------------------------------------- 判定汇总
    print()
    print("=" * 78)
    if FAIL:
        print(f"❌ 判定：不通过 —— {len(FAIL)} 项异常 / {len(PASS)} 项通过")
        for m in FAIL:
            print(f"   - {m}")
    else:
        print(f"✅ 判定：全部通过 —— {len(PASS)} 项检查全绿")
    if WARN:
        print(f"⚠️  需知悉 {len(WARN)} 条（预期内，但确实变了数据）：")
        for m in WARN:
            print(f"   - {m}")
    if NOTE:
        print(f"ℹ️  提示 {len(NOTE)} 条：")
        for m in NOTE:
            print(f"   - {m}")
    print("=" * 78)


main()
