# bl_capture_10oclock_now.py — 只读抓取 10点钟方向 当前位姿，并与 19:21 基线对比
import bpy, os, json, datetime

OUT_DIR = r"D:\workbuddy\2026-11-23-17-56-14"
OLD = os.path.join(OUT_DIR, "3oclock_baseline.json")
OUT_JSON = os.path.join(OUT_DIR, "10oclock_baseline_now.json")
OUT_TXT = os.path.join(OUT_DIR, "10oclock_baseline_now.txt")

with open(OLD, "r", encoding="utf-8") as f:
    old = json.load(f)
old_recs = {r["name"]: r for r in old["roots"]["10点钟方向"]["objects"]}

root = bpy.data.objects.get("10点钟方向")
if root is None:
    print("MISSING 10点钟方向")
    raise SystemExit(1)

items = []
stack = [(root, 0)]
while stack:
    o, d = stack.pop()
    items.append((o, d))
    for ch in o.children:
        stack.append((ch, d + 1))

def f3(v):
    return [round(float(v[0]), 6), round(float(v[1]), 6), round(float(v[2]), 6)]

recs = []
lines = []
lines.append("=" * 92)
lines.append("10点钟方向 当前位姿快照  |  " + bpy.data.filepath)
lines.append("捕获 %s  frame=%d  dirty=%s" % (
    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    bpy.context.scene.frame_current, bpy.data.is_dirty))
lines.append("=" * 92)
lines.append("%-30s %-7s %-26s %-26s %s" % ("对象", "类型", "local loc", "local rotE", "与19:21基线"))
lines.append("-" * 92)

for o, d in items:
    mw = o.matrix_world.copy()
    loc, quat, scl = mw.decompose()
    rec = {
        "name": o.name,
        "type": o.type,
        "parent": o.parent.name if o.parent else None,
        "depth": d,
        "rotation_mode": o.rotation_mode,
        "location_local": f3(o.location),
        "rotation_euler_local": f3(o.rotation_euler),
        "scale_local": f3(o.scale),
        "matrix_world": [round(float(x), 8) for x in
                         [mw[r][c] for r in range(4) for c in range(4)]],
        "world_translation": f3(loc),
        "world_euler": f3(quat.to_euler(o.rotation_mode if o.rotation_mode != 'QUATERNION' else 'XYZ')),
        "world_scale": f3(scl),
    }
    recs.append(rec)
    old_r = old_recs.get(o.name)
    if old_r is None:
        verdict = "新增"
    else:
        diffs = []
        for key in ("location_local", "rotation_euler_local"):
            a, b = rec[key], old_r[key]
            if a != b:
                diffs.append("%s %s->%s" % (key, b, a))
        verdict = "一致" if not diffs else "变化: " + "; ".join(diffs)
    lines.append("%-30s %-7s %-26s %-26s %s" % (
        o.name[:30], o.type, str(rec["location_local"])[:26],
        str(rec["rotation_euler_local"])[:26], verdict))
    lines.append("%sworld loc=%s rotE=%s scale=%s" % (
        "  " * 1, rec["world_translation"], rec["world_euler"], rec["world_scale"]))

changed = sum(1 for r in recs if r["name"] in old_recs and (
    r["location_local"] != old_recs[r["name"]]["location_local"] or
    r["rotation_euler_local"] != old_recs[r["name"]]["rotation_euler_local"]))
lines.append("")
lines.append("对象数 %d（其中 MESH %d / EMPTY %d），与 19:21 基线相比变化 %d 个" % (
    len(recs), sum(1 for r in recs if r["type"] == 'MESH'),
    sum(1 for r in recs if r["type"] == 'EMPTY'), changed))

data = {
    "filepath": bpy.data.filepath,
    "captured_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "frame": bpy.context.scene.frame_current,
    "dirty": bpy.data.is_dirty,
    "count": len(recs),
    "changed_vs_1921": changed,
    "objects": recs,
}
with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
with open(OUT_TXT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines))
print("SNAPSHOT -> " + OUT_JSON)
print("=== 10OCLOCK CAPTURE DONE ===")
