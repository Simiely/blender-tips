"""为所有射灯(SPOT)批量建体积光锥,并**共享同一份材质** = 同一组驱动器

前提:所有射灯的 spot_size / cutoff_distance 完全一致(材质里烘焙了 R / L 常量)。
不一致会在开头拦下来,不会给你做出一份错误的材质。

    python add_cones_all_lights.py
    python bl.py add_cones_all_lights.py <port>
"""
import bpy
import math
import mathutils
import traceback

# ============================ CONFIG ============================
MAT_NAME = "光锥_羽化材质"        # 必须先用 build_feather_material.py 建好
COLL_NAME = None                 # 建好后的锥体放进哪个集合;None = 跟灯同集合
CONE_SUFFIX = "_光锥"
HIDE_OLD_CONES = True            # 把不匹配当前命名规则的旧锥体隐藏(不删除)
OLD_CONE_KEYWORDS = ("锥",)      # 旧锥体名称关键字(宽松匹配,别用 endswith 拼中文)
# ================================================================


def sig_of(lo):
    return (round(math.degrees(lo.data.spot_size), 4),
            round(float(lo.data.cutoff_distance or 10.0), 3))


def main():
    mat = bpy.data.materials.get(MAT_NAME)
    if mat is None:
        raise RuntimeError("材质 %s 不存在,先跑 build_feather_material.py" % MAT_NAME)

    sc = bpy.context.scene
    coll = bpy.data.collections.get(COLL_NAME) if COLL_NAME else None

    spots = [o for o in bpy.data.objects if o.type == 'LIGHT' and o.data.type == 'SPOT']
    spots.sort(key=lambda o: o.name)
    print("SPOT_LIGHTS %d" % len(spots))

    sigs = {}
    for lo in spots:
        sigs.setdefault(sig_of(lo), []).append(lo.name)
    if len(sigs) > 1:
        print("=" * 72)
        print("⚠️ 射灯几何不一致,不能共用一份材质(材质里烘焙了 R / L):")
        for s, names in sigs.items():
            print("     %s  ×%d  %s" % (s, len(names), names))
        print("   → 请按组分别改名 MAT_NAME 后重跑本脚本,先做出的锥体不会被动。")
        print("   → 本次已中止,未做任何修改。")
        print("ABORT_SIG_MISMATCH")
        return

    created, skipped = [], []
    for lo in spots:
        cname = lo.name + CONE_SUFFIX
        if bpy.data.objects.get(cname) is not None:
            skipped.append(cname)
            continue

        L = float(lo.data.cutoff_distance or 10.0)
        R = L * math.tan(lo.data.spot_size / 2.0)

        # 必须闭合(体积域要求),apex 在局部 +Z
        bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=R, radius2=0.0, depth=L,
                                        end_fill_type='TRIFAN', location=(0.0, 0.0, 0.0))
        c = bpy.context.object
        c.name = cname
        c.data.name = cname
        c.parent = lo
        c.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        c.location = (0.0, 0.0, -L / 2.0)     # apex 落在灯位
        c.rotation_euler = (0.0, 0.0, 0.0)    # 轴向随灯
        c.scale = (1.0, 1.0, 1.0)

        if coll:
            for cc in list(c.users_collection):
                cc.objects.unlink(c)
            coll.objects.link(c)

        # 只对相机可见:不投影、不影响场景光照
        for a in ("visible_shadow", "visible_diffuse", "visible_glossy",
                  "visible_transmission", "visible_volume_scatter",
                  "visible_volume"):
            if hasattr(c, a):
                setattr(c, a, False)

        c.data.materials.clear()
        c.data.materials.append(mat)          # ★ 共享 = 同一组驱动器
        created.append((cname, lo.name, R, L))

    print("CREATED %d" % len(created))
    for n, pn, R, L in created:
        print("   + %-24s parent=%-18s R=%.4f L=%.2f" % (n, pn, R, L))
    print("SKIPPED(已存在) %s" % (skipped or "[]"))

    if HIDE_OLD_CONES:
        keep = set(o.name for o in bpy.data.objects if o.name.endswith(CONE_SUFFIX))
        hidden = []
        for o in bpy.data.objects:
            if o.name in keep or o.type != 'MESH':
                continue
            if any(k in o.name for k in OLD_CONE_KEYWORDS):
                o.hide_render = True
                o.hide_viewport = True
                hidden.append(o.name)
        print("OLD_CONES_HIDDEN(未删除,可逆) %s" % (hidden or "[]"))

    bpy.context.view_layer.update()
    print("MAT %s users=%d (应等于锥体总数)" % (mat.name, mat.users))
    sc.update_tag()
    print("ADD_CONES_DONE")


try:
    main()
except Exception:
    print("EXCEPTION")
    print(traceback.format_exc())
