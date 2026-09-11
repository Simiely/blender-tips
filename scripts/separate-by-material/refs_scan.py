# -*- coding: utf-8 -*-
"""
按材质拆分为多个网格体 —— 下游引用扫描（拆分后收尾用）
================================================================================
拆分后，目标对象只剩「最后一个材质槽」的几何。若场景里有别的系统
（修改器 / 约束 / 粒子 / 驱动 / 材质节点 / 几何节点）引用过它，
语义就变了 —— 必须在收尾时扫一遍，明确告知有没有下游影响。

扫描项：
  1. 修改器引用的对象（object/origin/target/mirror_object/offset_object/…）
  2. 约束引用的对象（target/space_object）
  3. 粒子系统的 instance_object / dupligroup
  4. 顶点父级 / 实例化父级
  5. 驱动（drivers）里以目标对象为变量源的
  6. 材质节点 / 几何节点里引用对象的输入（Object Info 等）

用法：
    TARGET = "对象13735"
    PART_NAMES = []        # 留空 = 按名字前缀自动发现（原名 + 原名.001/...）
    CHECK_COLLECTIONS = [] # 想额外体检的集合名（如 ["水晶走廊"]）
================================================================================
"""

import json
import os

# ==============================================================================
# ================================ 配置区 ======================================
# ==============================================================================
TARGET = "对象13735"
STATUS_JSON = "D:/workbuddy/_blender_sep/status.json"   # 可留空 "" 跳过
PART_NAMES = []                     # 留空 = 自动发现
CHECK_COLLECTIONS = []              # 例：["水晶走廊"]
MAX_PRINT = 60                      # 结果最多打印这么多行
# ==============================================================================


def main():
    import bpy
    D = bpy.data

    parts = set(PART_NAMES)
    if not parts:
        if STATUS_JSON and os.path.isfile(STATUS_JSON):
            try:
                with open(STATUS_JSON, "r", encoding="utf-8") as fh:
                    st = json.load(fh)
                parts = {p["object"] for p in st.get("parts", []) if p.get("object")}
            except Exception:
                parts = set()
        if not parts:
            parts = {o.name for o in D.objects
                     if o.name == TARGET or o.name.startswith(TARGET + ".")}

    print("=" * 78)
    print("下游引用扫描（对象组共 %d 个）：%s" % (len(parts), sorted(parts)))
    print("=" * 78)
    hits = []

    def note(kind, owner, detail):
        hits.append((kind, owner, detail))

    # 收集所有可能的"对象引用"属性名（不同修改器/约束名字不同，穷举 + getattr 容错）
    MOD_ATTRS = ("object", "origin", "target", "mirror_object", "offset_object",
                 "start_cap", "end_cap", "curve_object", "texture_coords_object",
                 "project_object", "object_center", "hook_object")
    CON_ATTRS = ("target", "space_object")

    for o in D.objects:
        for m in o.modifiers:
            for attr in MOD_ATTRS:
                v = getattr(m, attr, None)
                if v is not None and getattr(v, "name", None) in parts:
                    note("修改器", o.name, f"{m.name}[{m.type}].{attr} = {v.name}")
        for con in o.constraints:
            for attr in CON_ATTRS:
                v = getattr(con, attr, None)
                if v is not None and getattr(v, "name", None) in parts:
                    note("约束", o.name,
                         f"{con.name}[{con.type}].{attr} = {v.name}"
                         f" (subtarget={getattr(con, 'subtarget', '')!r})")
        for ps in getattr(o, "particle_systems", []):
            for attr in ("instance_object", "dupli_object"):
                v = getattr(ps.settings, attr, None)
                if v is not None and getattr(v, "name", None) in parts:
                    note("粒子", o.name, f"{ps.name}.{attr} = {v.name}")
        if o.parent is not None and o.parent.name in parts and o.parent_type in ("VERTEX", "VERTEX_3"):
            note("顶点父级", o.name, f"parent={o.parent.name} type={o.parent_type}")
    print("  [1/4] 对象级引用（修改器/约束/粒子/父级）扫描完成")

    # 驱动
    blocks = list(D.objects) + list(D.materials) + list(D.node_groups) + list(D.meshes)
    for blk in blocks:
        ad = getattr(blk, "animation_data", None)
        if not ad:
            continue
        for d in ad.drivers:
            for var in d.drivers:
                for tg in (getattr(var, "targets", None) or []):
                    id_ = getattr(tg, "id", None)
                    if id_ is not None and getattr(id_, "name", None) in parts:
                        note("驱动", blk.name,
                             f"{d.data_path}[{d.array_index}] <- {id_.name}.{tg.data_path}")
    print("  [2/4] 驱动扫描完成（%d 个数据块）" % len(blocks))

    # 节点里引用对象的输入
    def scan_nodes(owner_kind, nodes, owner_name):
        for nd in nodes:
            for inp in getattr(nd, "inputs", []):
                try:
                    dv = inp.default_value
                    nm = getattr(dv, "name", None)
                    if nm in parts:
                        note(owner_kind, f"{owner_name}/{nd.name}",
                             f"input {inp.name!r} = {nm}")
                except Exception:
                    pass

    for ng in D.node_groups:
        scan_nodes("几何节点引用", ng.nodes, ng.name)
    for mat in D.materials:
        # 注意：不要用 mat.use_nodes 判断 —— Blender 5.2 起会抛
        # DeprecationWarning（use_nodes 预计 6.0 移除）。直接看 node_tree。
        if mat.node_tree is not None:
            scan_nodes("材质节点引用", mat.node_tree.nodes, mat.name)
    print("  [3/4] 节点引用扫描完成（%d 节点组 / %d 材质）"
          % (len(D.node_groups), len(D.materials)))

    # 集合体检
    print("  [4/4] 集合体检")
    for cname in CHECK_COLLECTIONS:
        col = D.collections.get(cname)
        if col is None:
            print(f"    (集合 {cname!r} 不存在)")
            continue
        inside = sorted(x.name for x in col.objects if x.name in parts)
        print(f"    集合 {cname!r}: 直属对象 {len(col.objects)} 个，"
              f"其中属于本次拆分组的: {inside}")

    print()
    print("=" * 78)
    if not hits:
        print("✅ 没有任何其他对象/系统引用本组对象（下游零影响）")
    else:
        print(f"⚠️ 发现 {len(hits)} 处引用 —— 注意：{TARGET} 现在只剩最后一个材质槽的几何")
        for k, o, d in hits[:MAX_PRINT]:
            print(f"   [{k}] {o} -> {d}")
        if len(hits) > MAX_PRINT:
            print(f"   ...（还有 {len(hits) - MAX_PRINT} 处未显示）")
    print("=" * 78)


main()
