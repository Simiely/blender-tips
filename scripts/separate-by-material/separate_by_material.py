# -*- coding: utf-8 -*-
"""
按材质拆分为多个网格体 —— 执行脚本（含拆分前基线录制）
================================================================================
把「一个对象、多个材质槽」的网格，拆成「每个材质槽一个独立对象」。

用法：

    MODE = "separate"        # 先自动录基线，再执行拆分（推荐）
    MODE = "baseline_only"   # 只录基线，不动数据（用于先留证据 / 只读核查旧 .blend）

可直接在 Blender 内运行，也可经 blender-control 桥 send.py 远程运行：

    python send.py separate_by_material.py 9877

--------------------------------------------------------------------------------
关键机制（Blender 5.2 LTS 官方手册 + 运行时 API 自省实测）
--------------------------------------------------------------------------------
* 唯一真实可用的算子是 `bpy.ops.mesh.separate(type='MATERIAL')`。
  **不存在** `bpy.ops.mesh.separate_by_material` ——
  `hasattr(bpy.ops.mesh, "separate_by_material")` 会**假阳性返回 True**，
  但真正调 `get_rna_type()` 会 KeyError。判 bpy.ops 算子存在性必须用 get_rna_type()。
* By Material = 「按**材质槽**、对**整个网格**生效、**与当前选择无关**」。
* **原对象保留哪一组几何 —— 规则是「面序中首次出现位置最晚的那一组」**
  （**不是**「最后一个材质槽」，v1.15.2 修正）。源码依据：
  `source/blender/editors/mesh/editmesh_tools.cc` · `mesh_separate_material`
  逐轮取当前第一个面的 `mat_nr`，若该材质已覆盖全部剩余面
  （`tot == bm_old->totface`）则留在原对象并 `break`，否则把这组切走；
  ⇒ 「最后剩下的那组」即「首现位置最晚」的那组。
  推论：**原对象的名字与它拿到的材质常常对不上**，这是既有行为、不是 bug。
  其余各组各生成一个新对象，名字按槽顺序为 `原名.001` / `.002` / `.003` …，
  每个新网格只保留自己那一个材质槽。
* **空材质槽（有材质但零面）**：源码只遍历**面的** `mat_nr`，从不遍历材质槽
  ⇒ 空槽**不产生对象**、也不被保留；`mesh_separate_material_assign_mat_nr`
  把数据块 resize 到 1 个槽 ⇒ 空槽被自动清除。**部件数 = 「有面的」槽数**。
  ⚠️ **风险**：空槽里的材质会变成 `users=0` 的孤儿。拆分算子**不删**它（内存里还在），
  但**存盘时 Blender 会丢弃未被引用的数据块** —— 实测重新打开文件后该材质已不存在。
  若该材质只被本对象引用，拆分 + Ctrl+S 后即**永久丢失**。
  → 需要保留就把 `KEEP_EMPTY_SLOT_MATERIALS = True`（给它们打 `use_fake_user`）。

--------------------------------------------------------------------------------
⚠️ 桥的时序约束（长耗时算子必读）
--------------------------------------------------------------------------------
桥的 `exec` 在 Blender **主线程**执行，客户端 120s 超时后结果即丢失；
而且主线程忙时后续请求只排队不执行 → **算子运行期间无法轮询**。
所以本脚本把执行状态**逐阶段写盘**（STATUS_JSON），超时后从磁盘回捞结论。

--------------------------------------------------------------------------------
⚠️ 本脚本禁止出现 `if __name__ == "__main__"`
--------------------------------------------------------------------------------
桥的 `_env()` 命名空间里**没有 `__name__`**，写了会 `NameError`。
（同一原因：Blender 执行 `scripts/startup/*.py` 时 `__name__` 是模块名而非 "__main__"。）
所以结尾**无条件**调用 `main()`。
================================================================================
"""

import json
import os
import time
import traceback

# ==============================================================================
# ================================ 配置区 ======================================
# ==============================================================================
MODE = "separate"                 # "separate" | "baseline_only"

TARGET = "对象13735"               # ← 要拆分的对象名

BASE_JSON = "D:/workbuddy/_blender_sep/baseline.json"    # 拆分前基线落盘
STATUS_JSON = "D:/workbuddy/_blender_sep/status.json"    # 执行状态实时落盘

RENAME_BY_MATERIAL = False        # True = 拆完按材质名重命名「新部件」（原对象名不动）
RENAME_MAXLEN = 40                # 重命名时名字截断长度

KEEP_EMPTY_SLOT_MATERIALS = False  # True = 给「空材质槽」里的材质打 use_fake_user，防止存盘时被当孤儿丢弃
                                   # （空槽材质在拆分后 users=0；Blender 存盘会丢弃未引用的数据块，
                                   #   实测重新打开文件后该材质已不存在 → 只被本对象引用时即永久丢失）

RECORD_SHARP_BY_MAT = True        # True = 额外统计"每个材质组内的锐边数"
                                  # （判断属性层消失有无信息损失的决定性证据；
                                  #   百万面级网格会增加若干秒耗时）
RECORD_FACE_INDEX_RANGES = False  # True = 额外记录每个材质的面索引首尾（更慢）
# ==============================================================================


# ------------------------------------------------------------------ 工具函数 --
def _ensure_dir(p):
    d = os.path.dirname(os.path.abspath(p))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def _stamp(path, t0, stage, **kw):
    """逐阶段写盘。即使客户端 120s 超时，也能从磁盘读回执行到哪一步。"""
    d = {
        "stage": stage,
        "elapsed_s": round(time.time() - t0, 2),
        "clock": time.strftime("%H:%M:%S"),
        **kw,
    }
    try:
        _ensure_dir(path)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass
    print(f"[{d['elapsed_s']:>7.2f}s] {stage} {kw}", flush=True)


def _count_true_attr(me, name):
    """统计布尔型属性里为真的项数（如 sharp_edge）。属性不存在返回 None。"""
    a = me.attributes.get(name)
    if a is None:
        return None
    try:
        return sum(1 for v in a.data if v.value)
    except Exception:
        return None


def _sharp_by_mat(me, mats):
    """
    每个材质组内的锐边数（组内 = 边两端点都被该材质的面用到）。

    为什么需要它：拆分会把「该材质组」单独成体。若某部件的 `sharp_edge`
    属性层消失，只有知道「该组原本锐边数是否为 0」才能判定
    「属性层被丢弃（Blender 丢弃全默认值属性层，无信息损失）」
    还是「真数据丢失」。
    """
    nv = len(me.vertices)
    edges = me.edges
    out = {}
    for k in mats:
        mask = bytearray(nv)
        for p in me.polygons:
            if p.material_index == k:
                for vi in p.vertices:
                    mask[vi] = 1
        n_in = 0
        n_sharp = 0
        for e in edges:
            v0, v1 = e.vertices[0], e.vertices[1]
            if mask[v0] and mask[v1]:
                n_in += 1
                if e.use_edge_sharp:
                    n_sharp += 1
        out[str(k)] = {"edges_inside": n_in, "sharp_inside": n_sharp}
    return out


def _local_extent(me):
    """局部坐标逐顶点真实范围 [[minx,miny,minz],[maxx,maxy,maxz]]。

    用途：作为「几何守恒」的权威判据。比 `obj.bound_box` 变换后的世界包围盒可靠 ——
    后者是**松上界**（局部 AABB 旋转后必然膨胀），拆分后各部件界更紧，
    两者口径不对等，会报出假「漂移」。本指标与帧无关、两侧算法一致，应精确相等。
    """
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


def make_baseline(obj, extra=None):
    """只读快照。"""
    import bpy
    from collections import Counter
    from mathutils import Vector

    me = obj.data
    mw = obj.matrix_world.copy()

    cnt = Counter()
    first = {}
    last = {}
    for i, p in enumerate(me.polygons):
        k = p.material_index
        cnt[k] += 1
        if k not in first:
            first[k] = i
        last[k] = i

    snap = {
        "object": obj.name,
        "data": me.name,
        "data_users": me.users,
        "collections": [c.name for c in obj.users_collection],
        "parent": obj.parent.name if obj.parent else None,
        "parent_type": obj.parent_type,
        "mpi": [list(r) for r in obj.matrix_parent_inverse],
        "matrix_world": [list(r) for r in mw],
        "local_loc": list(obj.location),
        "local_rot_euler": list(obj.rotation_euler),
        "local_rot_quat": list(obj.rotation_quaternion),
        "local_scale": list(obj.scale),
        "delta_loc": list(obj.delta_location),
        "delta_rot": list(obj.delta_rotation_euler),
        "delta_scale": list(obj.delta_scale),
        "rotation_mode": obj.rotation_mode,
        "hide_viewport": obj.hide_viewport,
        "hide_render": obj.hide_render,
        "display_type": obj.display_type,
        "counts": {
            "verts": len(me.vertices),
            "edges": len(me.edges),
            "polys": len(me.polygons),
        },
        "slots": [
            {
                "i": i,
                "link": s.link,
                "material": s.material.name if s.material else None,
                "mat_users": (s.material.users if s.material else None),
                "mat_fake": (s.material.use_fake_user if s.material else None),
            }
            for i, s in enumerate(obj.material_slots)
        ],
        "face_by_mat": {str(k): v for k, v in sorted(cnt.items())},
        # 有面的槽 / 空槽（有材质但零面）。空槽不产生对象，拆分时被清掉。
        "used_slot_indices": sorted(cnt),
        "empty_slot_indices": [i for i in range(len(obj.material_slots)) if i not in cnt],
        # 几何守恒的权威判据（局部坐标逐顶点真实范围）
        "local_extent": _local_extent(me),
        "uv_layers": [l.name for l in me.uv_layers],
        "attributes": [
            {"name": a.name, "domain": a.domain, "type": a.data_type}
            for a in me.attributes
        ],
        "attr_names": sorted(a.name for a in me.attributes),
        "sharp_total": _count_true_attr(me, "sharp_edge"),
        "has_custom_normals": me.has_custom_normals,
        "shape_keys": me.shape_keys.name if me.shape_keys else None,
        "modifiers": [(m.name, m.type) for m in obj.modifiers],
        "object_anim": (
            obj.animation_data.action.name
            if (obj.animation_data and obj.animation_data.action)
            else None
        ),
        "mesh_anim": (
            me.animation_data.action.name
            if (me.animation_data and me.animation_data.action)
            else None
        ),
        # 世界包围盒：8 个局部角点乘矩阵（避免遍历百万顶点）
        "world_bbox": [list(mw @ Vector(c)) for c in obj.bound_box],
        "mesh_names_before": sorted(m.name for m in bpy.data.meshes),
        "object_names_before": sorted(x.name for x in bpy.data.objects),
        "scene_object_count": len(bpy.data.objects),
        "scene_mesh_count": len(bpy.data.meshes),
    }

    if RECORD_SHARP_BY_MAT and cnt:
        snap["sharp_by_mat"] = _sharp_by_mat(me, sorted(cnt))

    if RECORD_FACE_INDEX_RANGES:
        snap["face_index_by_mat"] = {
            str(k): {"count": int(cnt[k]), "first": first[k], "last": last[k]}
            for k in sorted(cnt)
        }
    if extra:
        snap.update(extra)
    return snap


def _write_baseline(obj, stamp, t0, extra=None):
    snap = make_baseline(obj, extra=extra)
    _ensure_dir(BASE_JSON)
    with open(BASE_JSON, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, ensure_ascii=False, indent=1)
    return snap


def _discover_parts(target):
    """按名字前缀发现所有部件（原名 + 原名.001/.002/...）。"""
    import bpy
    names = [
        o.name for o in bpy.data.objects
        if o.name == target or o.name.startswith(target + ".")
    ]
    names.sort(key=lambda n: (n != target, n))
    return names


def _sanitize(name, maxlen):
    import re
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", name).strip(" ._")
    return (s or "mat")[:maxlen]


def _rename_by_material(parts, target, stamp, t0):
    """把「新部件」按材质名重命名（原对象名字保持不变）。"""
    import bpy
    renamed = []
    for nm in parts:
        if nm == target:
            continue
        ob = bpy.data.objects.get(nm)
        if ob is None or not ob.material_slots:
            continue
        mat = ob.material_slots[0].material
        if mat is None:
            continue
        base = _sanitize(mat.name, RENAME_MAXLEN)
        cand = base
        i = 1
        while True:
            ex = bpy.data.objects.get(cand)
            if ex is None or ex.name == ob.name:
                break
            cand = f"{base}.{i:03d}"
            i += 1
        old = ob.name
        ob.name = cand
        renamed.append({"from": old, "to": ob.name, "material": mat.name})
    if renamed:
        stamp(t0, "renamed_by_material", renamed=renamed)
    return renamed


def _part_info(ob):
    return {
        "object": ob.name,
        "data": ob.data.name,
        "polys": len(ob.data.polygons),
        "verts": len(ob.data.vertices),
        "edges": len(ob.data.edges),
        "slots": [s.material.name if s.material else None for s in ob.material_slots],
        "collections": [c.name for c in ob.users_collection],
        "parent": ob.parent.name if ob.parent else None,
        "attrs": sorted(a.name for a in ob.data.attributes),
        "sharp_edge_count": _count_true_attr(ob.data, "sharp_edge"),
        "has_custom_normals": ob.data.has_custom_normals,
    }


# ---------------------------------------------------------------- 两种模式 --
def run_baseline_only(stamp, t0):
    import bpy
    obj = bpy.data.objects.get(TARGET)
    if obj is None:
        stamp(t0, "abort", reason=f"找不到对象 {TARGET}")
        return
    snap = _write_baseline(obj)
    stamp(
        t0, "baseline_done",
        baseline=BASE_JSON,
        filepath=bpy.data.filepath or "(未存盘)",
        object=snap["object"],
        counts=snap["counts"],
        slots=[(s["i"], s["material"]) for s in snap["slots"]],
        face_by_mat=snap["face_by_mat"],
        sharp_by_mat=snap.get("sharp_by_mat"),
        attributes=snap["attr_names"],
        has_custom_normals=snap["has_custom_normals"],
        scene_object_count=snap["scene_object_count"],
    )


def run_separate(stamp, t0):
    import bpy

    C = bpy.context
    D = bpy.data

    o = D.objects.get(TARGET)
    if o is None:
        stamp(t0, "abort", reason=f"找不到对象 {TARGET}")
        return
    if o.type != "MESH":
        stamp(t0, "abort", reason=f"对象类型是 {o.type}，不是 MESH")
        return

    stamp(
        t0, "found",
        blender=bpy.app.version_string,
        object=o.name, data=o.data.name, data_users=o.data.users,
        polys=len(o.data.polygons), verts=len(o.data.vertices),
        slots=[s.material.name if s.material else None for s in o.material_slots],
    )

    # ------------------------------------------------ 前置自检（不通过就中止）
    if o.data.users != 1:
        stamp(t0, "abort",
              reason=f"网格数据被 {o.data.users} 个对象共享；"
                     f"先做单用户化（Object > Make Single User / make_independent）再拆")
        return

    n_slots = len(o.material_slots)
    used = sorted(set(p.material_index for p in o.data.polygons))
    # 空材质槽 = 有材质、但不被任何面引用（源码从不遍历材质槽 ⇒ 不产生对象、且会被自动清除）
    empty_slots = [i for i in range(n_slots)
                   if o.material_slots[i].material and i not in used]
    empty_mats = [o.material_slots[i].material.name for i in empty_slots]
    stamp(t0, "precheck",
          material_slots=n_slots,
          slots_with_material=sum(1 for s in o.material_slots if s.material),
          slots_used_by_faces=len(used), used_indices=used,
          empty_slot_indices=empty_slots, empty_slot_materials=empty_mats,
          expected_parts=len(used))
    if empty_slots:
        stamp(t0, "warn_empty_slots",
              indices=empty_slots, materials=empty_mats,
              note="空槽不产生对象、且会被自动清除（正常）。但这些槽里的材质拆分后 users=0；"
                   "Blender 存盘会丢弃未引用的数据块 —— 实测重新打开文件后该材质已不存在。"
                   "若某材质只被本对象引用，拆分 + Ctrl+S 后即永久丢失。"
                   "要保留请设 KEEP_EMPTY_SLOT_MATERIALS = True（给它们打 use_fake_user），"
                   "或拆分前先手工清空/移走这些槽。")
    if n_slots < 2:
        stamp(t0, "abort", reason=f"只有 {n_slots} 个材质槽，无需拆分")
        return
    if len(used) < 2:
        stamp(t0, "abort",
              reason=f"所有面都指向同一个材质槽 index={used[0]}，拆了也只有一个部件")
        return

    # ------------------------------------------------ 空槽材质保命（可选）
    if empty_slots and KEEP_EMPTY_SLOT_MATERIALS:
        kept = []
        for i in empty_slots:
            m = o.material_slots[i].material
            m.use_fake_user = True
            kept.append({"slot": i, "material": m.name, "users": m.users})
        stamp(t0, "empty_slot_materials_kept", kept=kept,
              note="已给空槽材质打 use_fake_user=True → 存盘不会被当孤儿丢弃")

    # ------------------------------------------------ 拆分前基线（只读）
    saved_frame = C.scene.frame_current
    snap = _write_baseline(o, stamp, t0, extra={"frame_current": saved_frame})
    stamp(t0, "baseline_written", baseline=BASE_JSON,
          counts=snap["counts"], face_by_mat=snap["face_by_mat"],
          sharp_by_mat=snap.get("sharp_by_mat"), attributes=snap["attr_names"])

    before_objs = set(x.name for x in D.objects)
    before_meshes = set(m.name for m in D.meshes)

    # ------------------------------------------------ 上下文准备
    if C.mode != "OBJECT":
        stamp(t0, "force_object_mode", from_mode=C.mode)
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    C.view_layer.objects.active = o
    stamp(t0, "selected",
          active=C.object.name if C.object else None,
          selected=[x.name for x in C.selected_objects])

    # ------------------------------------------------ 执行
    stamp(t0, "calling_separate", operator="bpy.ops.mesh.separate(type='MATERIAL')")
    bpy.ops.object.mode_set(mode="EDIT")
    res = bpy.ops.mesh.separate(type="MATERIAL")
    bpy.ops.object.mode_set(mode="OBJECT")
    stamp(t0, "separate_returned", result=sorted(res))

    # ------------------------------------------------ 结果盘点
    new_objs = sorted(set(x.name for x in D.objects) - before_objs)
    new_meshes = sorted(set(m.name for m in D.meshes) - before_meshes)

    parts = _discover_parts(TARGET)
    renamed = []
    if RENAME_BY_MATERIAL and len(parts) > 1:
        renamed = _rename_by_material(parts, TARGET, stamp, t0)
        parts = [TARGET] + [r["to"] for r in renamed]

    info = []
    for nm in parts:
        ob = D.objects.get(nm)
        if ob is not None:
            info.append(_part_info(ob))

    C.scene.frame_set(saved_frame)
    tot_polys = sum(p["polys"] for p in info)
    tot_verts = sum(p["verts"] for p in info)
    stamp(
        t0, "done",
        new_objects=new_objs, new_meshes=new_meshes,
        renamed=renamed,
        parts=info,
        total_polys=tot_polys, base_total_polys=snap["counts"]["polys"],
        polys_conserved=(tot_polys == snap["counts"]["polys"]),
        total_verts=tot_verts, base_total_verts=snap["counts"]["verts"],
        verts_conserved=(tot_verts == snap["counts"]["verts"]),
        scene_object_count=len(D.objects),
        scene_mesh_count=len(D.meshes),
    )


def main():
    t0 = time.time()
    _stamp(STATUS_JSON, t0, "start", mode=MODE, target=TARGET)
    try:
        if MODE == "baseline_only":
            run_baseline_only(_stamp_wrapper, t0)
        else:
            run_separate(_stamp_wrapper, t0)
    except Exception:
        _stamp(STATUS_JSON, t0, "error", traceback=traceback.format_exc())
        raise


def _stamp_wrapper(t0, stage, **kw):
    _stamp(STATUS_JSON, t0, stage, **kw)


# 无条件调用（不要写 if __name__ == "__main__"，见文件头说明）
main()
