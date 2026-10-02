"""探查:射灯清单 / 已有锥体 / 材质与驱动器 / 场景自定义属性

跑之前先看它输出什么,别猜。
    python probe_beam.py                    # 独立后台跑
    python bl.py probe_beam.py <port>       # 经远程桥跑
"""
import bpy
import math

# None = 全场景;填集合名则只统计该集合
COLL_NAME = None
CONE_SUFFIX = "_光锥"


def _in_coll(o, coll):
    return coll is None or coll in [c.name for c in o.users_collection]


def main():
    coll = bpy.data.collections.get(COLL_NAME) if COLL_NAME else None
    sc = bpy.context.scene

    print("=" * 72)
    print("【1】场景自定义属性(带 min/max 的会显示成滑块)")
    for k in sc.keys():
        if k.startswith("_"):
            continue
        ui = sc.id_properties_ui(k)
        d = ui.as_dict() if hasattr(ui, "as_dict") else {}
        print("   %-16s = %-10s  min=%s max=%s soft=[%s, %s]" % (
            k, round(sc[k], 4) if isinstance(sc[k], float) else sc[k],
            d.get("min"), d.get("max"), d.get("soft_min"), d.get("soft_max")))

    print("=" * 72)
    print("【2】射灯(SPOT)清单 —— 锥体能否共用一份材质,取决于这里是否完全一致")
    spots = [o for o in bpy.data.objects
             if o.type == 'LIGHT' and o.data.type == 'SPOT' and _in_coll(o, coll)]
    spots.sort(key=lambda o: o.name)
    sigs = {}
    for lo in spots:
        try:
            ss = math.degrees(lo.data.spot_size)
        except Exception:
            ss = None
        try:
            cd = lo.data.cutoff_distance
        except Exception:
            cd = None
        kids = [c.name for c in lo.children]
        sig = (round(ss, 4) if ss else ss, round(cd, 3) if cd else cd)
        sigs.setdefault(sig, []).append(lo.name)
        print("   %-20s spot=%-8s cutoff=%-8s children=%s" % (
            lo.name, round(ss, 4) if ss else ss,
            round(cd, 3) if cd else cd, kids or "[]"))

    print("   —— 几何签名分组(同组才可共用材质):")
    for sig, names in sigs.items():
        print("      %s  ×%d  %s" % (sig, len(names), names))
    if len(sigs) > 1:
        print("   ⚠️ 签名不一致 ⇒ 必须按组各建一份材质(材质里烘焙了 R / L 常量)")

    print("=" * 72)
    print("【3】已有锥体对象")
    cones = [o for o in bpy.data.objects if o.name.endswith(CONE_SUFFIX)]
    cones.sort(key=lambda o: o.name)
    if not cones:
        print("   (无)")
    for c in cones:
        m = c.data.materials[0] if c.data.materials else None
        zmax = max(v.co.z for v in c.data.vertices)
        zmin = min(v.co.z for v in c.data.vertices)
        R = max(math.hypot(v.co.x, v.co.y) for v in c.data.vertices)
        print("   %-24s parent=%-18s verts=%-4d L=%.2f R=%.4f mat=%s" % (
            c.name, c.parent.name if c.parent else None,
            len(c.data.vertices), zmax - zmin, R, m.name if m else None))
        print("        隐藏状态 hide_render=%s hide_viewport=%s  可见性 camera=%s shadow=%s diffuse=%s" % (
            c.hide_render, c.hide_viewport,
            c.visible_camera, c.visible_shadow, c.visible_diffuse))

    print("=" * 72)
    print("【4】材质与驱动器")
    for m in bpy.data.materials:
        nt = m.node_tree if m.use_nodes else None
        if nt is None:
            continue
        if not any("光锥" in (n.name or "") or "光锥" in (n.label or "")
                   or n.type == 'PRINCIPLED_VOLUME' for n in nt.nodes):
            continue
        drvs = [fc.data_path for fc in nt.animation_data.drivers] if nt.animation_data else []
        print("   %-28s nodes=%-3d users=%-3d drivers=%d" % (
            m.name, len(nt.nodes), m.users, len(drvs)))
        for p in drvs:
            print("        DRV %s" % p)

    print("=" * 72)
    print("PROBE_BEAM_DONE")


try:
    main()
except Exception:
    import traceback
    print("EXCEPTION")
    print(traceback.format_exc())
