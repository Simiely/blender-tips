import bpy
import json
import math

OUT = r"D:/workbuddy/2026-11-23-17-56-14/bubble_speed_multiplier_verify_report.json"
TXT = r"D:/workbuddy/2026-11-23-17-56-14/bubble_speed_multiplier_verify_report.txt"
BACKUP = r"D:/workbuddy/2026-11-23-17-56-14/bubble_scene_backup_before.json"

CTRL = "泡泡控制"
SRC = "泡泡_源球"
NG = "泡泡发射_GN"
FRAMES = [0, 20, 60, 150, 240, 300]

EXPECTED = {
    "泡泡数量": 600,
    "泡泡半径": 0.03,
    "扩散半径": 4.1,
    "上升高度": 1.0,
    "生命周期": 96.0,
    "起始帧": 0.0,
    "随机种子": 1,
    "边界余量": 0.15,
    "范围匹配": 1.0,
    "下落消散": 0.35,
    "顶点比例": 0.5,
    "慢速倍率": 2.5,
}


def f(v, nd=6):
    return round(float(v), nd)


def names(inst):
    out = []
    for attr in ("object", "instance_object", "parent"):
        o = getattr(inst, attr, None)
        if o is None:
            continue
        try:
            out.append(o.original.name)
        except Exception:
            pass
    return out


def collect(dg):
    rows = []
    for inst in dg.object_instances:
        if not getattr(inst, "is_instance", False) or SRC not in names(inst):
            continue
        p = inst.matrix_world.translation
        sc = inst.matrix_world.to_scale()
        rows.append({
            "x": f(p.x), "y": f(p.y), "z": f(p.z),
            "r": f(max(abs(sc.x), abs(sc.y), abs(sc.z))),
        })
    return rows


def stats(rows, cx, cy, cr, floor_z):
    if not rows:
        return {"count": 0, "visible_count": 0}
    dists = [math.hypot(r["x"] - cx, r["y"] - cy) for r in rows]
    zs = [r["z"] for r in rows]
    near_floor = [r for r in rows if r["z"] < floor_z + 0.25]
    return {
        "count": len(rows),
        "visible_count": sum(1 for r in rows if r["r"] > 1e-5),
        "max_center_distance": f(max(dists)),
        "z_min": f(min(zs)),
        "z_max": f(max(zs)),
        "z_mean": f(sum(zs) / len(zs)),
        "outside_range_count": sum(1 for r, d in zip(rows, dists) if d + r["r"] > cr + 0.001),
        "below_floor_count": sum(1 for r in rows if r["z"] - r["r"] < floor_z - 0.001),
        "near_floor_full_scale_count": sum(1 for r in near_floor if r["r"] > 0.03 * 0.8),
        "near_floor_max_scale": f(max((r["r"] for r in near_floor), default=0.0)),
    }


def main():
    scene = bpy.context.scene
    saved_frame = scene.frame_current
    ctrl = bpy.data.objects.get(CTRL)
    ng = bpy.data.node_groups.get(NG)
    src = bpy.data.objects.get(SRC)
    emitter = bpy.data.objects.get("发射口")
    area = bpy.data.objects.get("泡泡范围")
    checks = []
    failures = []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            failures.append(name)

    for nm, o in (("ctrl", ctrl), ("ng", ng), ("src", src),
                  ("emitter", emitter), ("area", area)):
        check("exists:" + nm, o is not None)
    if any(x is None for x in (ctrl, ng, src, emitter, area)):
        raise RuntimeError("missing object")

    props = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")}
    for k, v in EXPECTED.items():
        check("prop:" + k, k in props and abs(float(props[k]) - float(v)) < 1e-5,
              "got=%s" % props.get(k))

    drivers = [d.data_path for d in ng.animation_data.drivers] if ng.animation_data else []
    check("driver_count==12", len(drivers) == 12, "count=%d" % len(drivers))
    check("speed_driver", any("慢速倍率" in d for d in drivers))

    with open(BACKUP, "r", encoding="utf-8") as fp:
        backup = json.load(fp)
    moved = []
    for old in backup["objects"]:
        o = bpy.data.objects.get(old["name"])
        if o is None or any(abs(f(o.matrix_world.translation[i]) - float(old["world_translation"][i])) > 1e-5
                            for i in range(3)):
            moved.append(old["name"])
    check("original_objects_unmoved", not moved, ";".join(moved))

    pts = [area.matrix_world @ v.co for v in area.data.vertices]
    cx = f((min(p.x for p in pts) + max(p.x for p in pts)) * 0.5)
    cy = f((min(p.y for p in pts) + max(p.y for p in pts)) * 0.5)
    cr = f((max(p.x for p in pts) - min(p.x for p in pts)) * 0.5)
    floor_z = f(min(p.z for p in pts))
    emitter_z = f(emitter.matrix_world.translation.z)

    frame_stats = {}
    for fr in FRAMES:
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        frame_stats[str(fr)] = stats(collect(dg), cx, cy, cr, floor_z)

    check("gradual_birth",
          frame_stats["0"]["count"] <= frame_stats["20"]["count"] <= frame_stats["60"]["count"] <= frame_stats["240"]["count"],
          "0/20/60/240=%d/%d/%d/%d" % (
              frame_stats["0"]["count"], frame_stats["20"]["count"],
              frame_stats["60"]["count"], frame_stats["240"]["count"]))
    check("steady_state_count",
          500 <= frame_stats["300"]["count"] <= 580,
          "f300=%d" % frame_stats["300"]["count"])

    for fr in (20, 60, 150, 240, 300):
        s = frame_stats[str(fr)]
        if s["count"]:
            check("frame%d_within_range" % fr, s["outside_range_count"] == 0)
            check("frame%d_no_ground_full_jump" % fr, s["near_floor_full_scale_count"] == 0,
                  "near_max=%s" % s["near_floor_max_scale"])

    scene.frame_set(20)
    bpy.context.view_layer.update()
    slow_rows = collect(bpy.context.evaluated_depsgraph_get())
    old_mul = ctrl["慢速倍率"]
    ctrl["慢速倍率"] = 1.0
    ctrl.update_tag(refresh={"OBJECT"})
    ng.update_tag()
    bpy.context.view_layer.update()
    fast_rows = collect(bpy.context.evaluated_depsgraph_get())
    ctrl["慢速倍率"] = old_mul
    ctrl.update_tag(refresh={"OBJECT"})
    ng.update_tag()
    bpy.context.view_layer.update()
    check("speed_multiplier_effective",
          len(fast_rows) > len(slow_rows),
          "mul2.5=%d mul1=%d" % (len(slow_rows), len(fast_rows)))

    scene.frame_set(300)
    bpy.context.view_layer.update()
    kill_rows = collect(bpy.context.evaluated_depsgraph_get())
    old_kill = ctrl["下落消散"]
    ctrl["下落消散"] = 0.0
    ctrl.update_tag(refresh={"OBJECT"})
    ng.update_tag()
    bpy.context.view_layer.update()
    no_kill_rows = collect(bpy.context.evaluated_depsgraph_get())
    ctrl["下落消散"] = old_kill
    ctrl.update_tag(refresh={"OBJECT"})
    ng.update_tag()
    bpy.context.view_layer.update()
    check("kill_still_effective",
          len(kill_rows) < len(no_kill_rows) and len(no_kill_rows) == 600,
          "kill=%d none=%d" % (len(kill_rows), len(no_kill_rows)))

    scene.frame_set(saved_frame)
    bpy.context.view_layer.update()

    report = {
        "file": bpy.data.filepath,
        "pass": not failures,
        "failures": failures,
        "checks": checks,
        "props": props,
        "range": {"center": [cx, cy], "radius": cr, "floor_z": floor_z},
        "emitter_z": emitter_z,
        "frame_stats": frame_stats,
        "speed_test": {
            "frame": 20,
            "mul_2_5": len(slow_rows),
            "mul_1": len(fast_rows),
            "restored": old_mul,
        },
        "kill_test": {"kill_0_35": len(kill_rows), "kill_0": len(no_kill_rows)},
    }
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    lines = []
    lines.append("PASS" if report["pass"] else "FAIL")
    lines.append("failures: %d" % len(failures))
    for name in failures:
        lines.append("  - " + name)
    lines.append("effective_life = 96 x 2.5 = 240")
    for fr in FRAMES:
        s = frame_stats[str(fr)]
        lines.append("frame %3d count=%3d visible=%3d z_mean=%s outside=%d ground_jump=%d" % (
            fr, s.get("count", 0), s.get("visible_count", 0), s.get("z_mean", "-"),
            s.get("outside_range_count", -1), s.get("near_floor_full_scale_count", -1)))
    lines.append("speed test frame20 mul2.5=%d mul1=%d restored=%s" % (
        len(slow_rows), len(fast_rows), old_mul))
    lines.append("kill test kill0.35=%d kill0=%d" % (len(kill_rows), len(no_kill_rows)))
    with open(TXT, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    print("BUBBLE_SPEED_MULTIPLIER_VERIFY_OK")


try:
    main()
except Exception as e:
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump({"error": repr(e), "pass": False}, fp, ensure_ascii=False, indent=2)
    with open(TXT, "w", encoding="utf-8") as fp:
        fp.write("ERROR\n" + repr(e) + "\n")
    print("BUBBLE_SPEED_MULTIPLIER_VERIFY_ERROR")
