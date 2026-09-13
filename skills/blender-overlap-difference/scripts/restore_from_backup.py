# -*- coding: utf-8 -*-
"""restore_from_backup.py — 撤回「面级剔除」等直改 mesh 数据的操作，把原始网格还回去。

面级剔除是直改 mesh 数据，undo 栈未必吃到 ⇒ 撤回只能靠执行时留下的隐藏备份对象 `__BAK__<对象>__`。

流程（顺序不可颠倒）：
  1) 先比后换：把备份 mesh 与「同统计量的其它同源副本」逐一比对四个 sha1，确认备份可信
  2) 与 EXPECT（来自当时操作基线）逐项核对，任一不符立即中止
  3) obj.data = bak.data → 删备份对象 → 清掉本次产生的 orphan mesh（按「本次编号下界」筛，绝不碰历史遗留）
  4) mesh 数据块名还原成原编号 / 独立核验由外部脚本另起一次请求做

依赖：走 9877 桥在 Blender 主线程执行（见 blender-bridge-ops skill）。
"""

import bpy
import hashlib
import json
import struct

# ============================ 配置区 ============================
TARGET = "对象A"                 # ← 被误改的对象
BAK_NAME = ""                    # 留空 = 自动用 __BAK__<TARGET>__
ORIG_MESH_NAME = ""              # 原始 mesh 数据块名（从操作基线里取，如 "Mesh.6213"）；留空则不改名

# 可选：从当时操作基线抄来的期望值，任一不符即中止。留空 {} 则只做「同源副本互比」。
EXPECT = {}
# 例：
# EXPECT = {"polys": 84208, "verts": 45428, "edges": 126312, "loops": 252624,
#           "sha_co": "12c09c00...", "sha_loop_vidx": "4f23fb1a...",
#           "sha_poly_range": "1c48e1e2...", "sha_mat_idx": "d0b8ce24...",
#           "uv": ["UVChannel_1"], "materials": ["灯光光.004"]}

# 本工程「拆分前既有」的历史遗留孤儿 mesh —— 一律不碰（拿不到名单就留空，见下方 FLOOR 兜底）
KEEP_ORPHANS = set()
# orphan mesh 清理下界：只删 `Mesh.<n>` 且 n >= ORPHAN_FLOOR 的无引用 mesh（本次操作一定用新编号）
ORPHAN_FLOOR = 0                 # 0 = 不按编号清理，只删「换下来的那张旧 mesh」
# ===============================================================

rep = {"target": TARGET}
if not BAK_NAME:
    BAK_NAME = "__BAK__%s__" % TARGET
rep["bak_name"] = BAK_NAME


def mesh_sig(m):
    d = {"name": m.name, "verts": len(m.vertices), "edges": len(m.edges),
         "polys": len(m.polygons), "loops": len(m.loops)}
    h = hashlib.sha1(); buf = bytearray()
    for v in m.vertices:
        buf += struct.pack("<3f", v.co.x, v.co.y, v.co.z)
    h.update(bytes(buf)); d["sha_co"] = h.hexdigest()
    h = hashlib.sha1(); buf = bytearray()
    for l in m.loops:
        buf += struct.pack("<i", l.vertex_index)
    h.update(bytes(buf)); d["sha_loop_vidx"] = h.hexdigest()
    h = hashlib.sha1(); buf = bytearray()
    for p in m.polygons:
        buf += struct.pack("<2i", p.loop_start, p.loop_total)
    h.update(bytes(buf)); d["sha_poly_range"] = h.hexdigest()
    h = hashlib.sha1(); buf = bytearray()
    for p in m.polygons:
        buf += struct.pack("<i", p.material_index)
    h.update(bytes(buf)); d["sha_mat_idx"] = h.hexdigest()
    d["uv"] = [l.name for l in m.uv_layers]
    d["materials"] = [ms.name if ms else None for ms in m.materials]
    d["has_custom_normals"] = bool(getattr(m, "has_custom_normals", False))
    return d


def obj_snap(o):
    if not o:
        return None
    return {"obj": o.name, "mesh": o.data.name, "polys": len(o.data.polygons),
            "verts": len(o.data.vertices),
            "slots": [s.material.name if s.material else None for s in o.material_slots],
            "hide_viewport": o.hide_viewport, "hide_render": o.hide_render,
            "parent": o.parent.name if o.parent else None,
            "matrix_world": [round(v, 6) for row in o.matrix_world for v in row],
            "collections": [c.name for c in o.users_collection]}


obj = bpy.data.objects.get(TARGET)
bak = bpy.data.objects.get(BAK_NAME)
rep["before_target"] = obj_snap(obj)
rep["before_backup"] = obj_snap(bak)
rep["bak_mesh_sig"] = mesh_sig(bak.data) if bak else None

abort = None
if obj is None:
    abort = "找不到目标对象 %s" % TARGET
elif bak is None:
    abort = "找不到备份对象 %s（没有还原点 ⇒ 撤回无门，只能 File > Revert）" % BAK_NAME
elif len(bak.children) > 0:
    abort = "备份对象竟有子对象 %d 个，中止" % len(bak.children)
elif bak.data.users != 1:
    abort = "备份 mesh users=%d，非独占，中止" % bak.data.users
elif obj.data == bak.data:
    abort = "目标已指向备份 mesh，无需恢复"
elif EXPECT:
    sig = mesh_sig(bak.data)
    diff = {}
    for k, v in EXPECT.items():
        if sig.get(k) != v:
            diff[k] = [sig.get(k), v]
    rep["expect_diff"] = diff
    if diff:
        abort = "备份 mesh 与 EXPECT 不符，中止：%s" % diff

# 同源副本互比：找出所有与备份统计量相同、且四个哈希全等的其它 mesh（独立副本互证）
rep["same_source_copies"] = []
if not abort:
    base = mesh_sig(bak.data)
    for m in bpy.data.meshes:
        if m == bak.data:
            continue
        try:
            s = mesh_sig(m)
        except Exception:
            continue
        if s["polys"] == base["polys"] and s["sha_co"] == base["sha_co"] \
           and s["sha_loop_vidx"] == base["sha_loop_vidx"] and s["sha_poly_range"] == base["sha_poly_range"] \
           and s["sha_mat_idx"] == base["sha_mat_idx"]:
            rep["same_source_copies"].append({"mesh": m.name, "users": m.users})

if abort:
    rep["abort"] = abort
    print("ABORT:", abort)
else:
    orig_mesh = bak.data
    old_mesh = obj.data
    old_name = old_mesh.name

    obj.data = orig_mesh                                  # 1) 换回原始 mesh
    bpy.data.objects.remove(bak, do_unlink=True)          # 2) 删掉备份对象

    removed = []                                          # 3) 清理本次产生的 orphan mesh
    if old_mesh.users == 0:
        removed.append(old_mesh.name)
        bpy.data.meshes.remove(old_mesh)
    if ORPHAN_FLOOR > 0:
        for m in list(bpy.data.meshes):
            if m.users != 0 or m.name in KEEP_ORPHANS or not m.name.startswith("Mesh."):
                continue
            try:
                num = int(m.name.split(".")[-1])
            except Exception:
                continue
            if num >= ORPHAN_FLOOR:
                removed.append(m.name)
                bpy.data.meshes.remove(m)
    rep["purged_meshes"] = removed

    if ORIG_MESH_NAME and obj.data.name != ORIG_MESH_NAME \
       and ORIG_MESH_NAME not in [m.name for m in bpy.data.meshes]:
        obj.data.name = ORIG_MESH_NAME                    # 4) mesh 数据块名还原
    rep["after_target"] = obj_snap(obj)

rep["bak_left"] = [o.name for o in bpy.data.objects if o.name.startswith("__BAK__")]
rep["orphans_now"] = sorted([m.name for m in bpy.data.meshes if m.users == 0])
rep["scene"] = {"objects": len(bpy.data.objects), "meshes": len(bpy.data.meshes),
                "materials": len(bpy.data.materials)}

print("RESTORE_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("RESTORE_END")
