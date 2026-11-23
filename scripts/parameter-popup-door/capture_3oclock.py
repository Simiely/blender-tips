# bl_capture_3oclock.py — 只读记录 3点钟方向 子树的位姿基线（含世界变换与轴心）
# 经 9877 桥执行；不修改场景、不存盘。
import bpy, os, json, datetime

OUT_DIR = r"D:\workbuddy\2026-11-23-17-56-14"
OUT_JSON = os.path.join(OUT_DIR, "3oclock_baseline.json")
OUT_TXT = os.path.join(OUT_DIR, "3oclock_baseline.txt")
ROOTS = ["3点钟方向", "10点钟方向"]  # 主目标 + 对照参考

def subtree(root):
    out = []
    stack = [(root, 0)]
    while stack:
        o, d = stack.pop()
        out.append((o, d))
        for ch in o.children:
            stack.append((ch, d + 1))
    return out

def f3(v):
    return [round(float(v[0]), 6), round(float(v[1]), 6), round(float(v[2]), 6)]

def f4(v):
    return [round(float(v[0]), 6), round(float(v[1]), 6), round(float(v[2]), 6), round(float(v[3]), 6)]

data = {
    "filepath": bpy.data.filepath,
    "captured_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "dirty": bpy.data.is_dirty,
    "objects_total": len(bpy.data.objects),
    "roots": {},
}
lines = []
lines.append("=" * 96)
lines.append("3点钟方向 位姿基线  |  " + bpy.data.filepath)
lines.append("捕获时间 " + data["captured_at"] + "  dirty=%s  场景对象 %d" % (
    data["dirty"], data["objects_total"]))
lines.append("=" * 96)

for root_name in ROOTS:
    root = bpy.data.objects.get(root_name)
    if root is None:
        data["roots"][root_name] = {"error": "MISSING"}
        lines.append("MISSING ROOT " + root_name)
        continue
    items = subtree(root)
    recs = []
    lines.append("")
    lines.append("ROOT %s  子树 %d 个对象" % (root_name, len(items)))
    lines.append("-" * 96)
    for o, depth in items:
        mw = o.matrix_world.copy()
        loc, quat, scl = mw.decompose()
        we = quat.to_euler(o.rotation_mode if o.rotation_mode != 'QUATERNION' else 'XYZ')
        ad = o.animation_data
        action = ad.action.name if (ad is not None and ad.action is not None) else None
        rec = {
            "name": o.name,
            "type": o.type,
            "parent": o.parent.name if o.parent else None,
            "depth": depth,
            "rotation_mode": o.rotation_mode,
            "location_local": f3(o.location),
            "rotation_euler_local": f3(o.rotation_euler),
            "rotation_quaternion_local": f4(o.rotation_quaternion),
            "scale_local": f3(o.scale),
            "matrix_world": [round(float(x), 8) for x in
                             [mw[r][c] for r in range(4) for c in range(4)]],
            "world_translation": f3(loc),
            "world_euler": f3(we),
            "world_scale": f3(scl),
            "action": action,
            "children": [c.name for c in o.children],
        }
        recs.append(rec)
        lines.append("%s%-30s %-7s d=%d rotmode=%-10s" % (
            "  " * depth, o.name[:30], o.type, depth, o.rotation_mode))
        lines.append("%slocal loc=%s rotE=%s scale=%s" % (
            "  " * depth, rec["location_local"], rec["rotation_euler_local"], rec["scale_local"]))
        lines.append("%sworld loc=%s rotE=%s scale=%s  action=%s" % (
            "  " * depth, rec["world_translation"], rec["world_euler"], rec["world_scale"],
            action if action else "-"))
        lines.append("%spivot(world)=%s" % ("  " * depth, rec["world_translation"]))
    data["roots"][root_name] = {"count": len(recs), "objects": recs}

with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
with open(OUT_TXT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines))
print("BASELINE -> " + OUT_JSON)
print("=== CAPTURE 3OCLOCK DONE ===")
