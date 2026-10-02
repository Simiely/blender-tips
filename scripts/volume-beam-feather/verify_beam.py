"""独立核验:锥-灯轴对齐 / apex 落点 / 材质共享 / 可见性标志 / 驱动器。末尾给 PASS-FAIL。

**必须另跑一次**(跟构建分开),否则只是复述构建脚本的自检。

    python verify_beam.py
    python bl.py verify_beam.py <port>
"""
import bpy
import math
import mathutils
import traceback

# ============================ CONFIG ============================
MAT_NAME = "光锥_羽化材质"
CONE_SUFFIX = "_光锥"
EXPECT_CONE_COUNT = None      # None = 不检查数量;填数字则必须相符
PROP_KEY = "光锥羽化"          # 抽查的驱动属性
# ================================================================

TOL_AXIS = 1e-5
TOL_APEX = 1e-4


def main():
    fails = []
    cones = [o for o in bpy.data.objects if o.name.endswith(CONE_SUFFIX)]
    cones.sort(key=lambda o: o.name)
    print("=" * 72)
    print("锥体总数 %d" % len(cones))
    if EXPECT_CONE_COUNT is not None and len(cones) != EXPECT_CONE_COUNT:
        fails.append("锥体数量 %d ≠ 期望 %d" % (len(cones), EXPECT_CONE_COUNT))

    print("-" * 72)
    print("【1】轴对齐 / apex 落点 / 材质")
    for c in cones:
        lo = c.parent
        if lo is None:
            fails.append("%s 没有父级" % c.name)
            print("   BAD %-24s 无父级" % c.name)
            continue
        if lo.type != 'LIGHT':
            fails.append("%s 的父级不是灯" % c.name)
        wl = (lo.matrix_world.to_3x3() @ mathutils.Vector((0, 0, -1))).normalized()
        wc = (c.matrix_world.to_3x3() @ mathutils.Vector((0, 0, -1))).normalized()
        dot = wl.dot(wc)
        zmax = max(v.co.z for v in c.data.vertices)
        apex = c.matrix_world @ mathutils.Vector((0, 0, zmax))
        off = (apex - lo.matrix_world.translation).length
        m = c.data.materials[0].name if c.data.materials else None

        ok = abs(dot - 1.0) < TOL_AXIS and off < TOL_APEX
        if not ok:
            fails.append("%s 轴对齐/落点异常 dot=%.6f off=%.6f" % (c.name, dot, off))
        if m != MAT_NAME:
            fails.append("%s 材质是 %s(期望 %s)" % (c.name, m, MAT_NAME))
        print("   %s %-24s axis_dot=%.6f apex_off=%.6f mat=%s" % (
            "OK " if ok and m == MAT_NAME else "BAD", c.name, dot, off, m))

    print("-" * 72)
    print("【2】可见性标志(应只对相机可见)")
    for c in cones:
        flags = {a: getattr(c, a) for a in
                 ("visible_camera", "visible_shadow", "visible_diffuse",
                  "visible_glossy", "visible_transmission",
                  "visible_volume_scatter", "visible_volume") if hasattr(c, a)}
        bad = [k for k, v in flags.items() if k != "visible_camera" and v]
        if flags.get("visible_camera") is not True or bad:
            fails.append("%s 可见性标志异常 camera=%s 未关=%s" % (
                c.name, flags.get("visible_camera"), bad))
        print("   %s %-24s camera=%s 其他关闭=%d/%d" % (
            "OK " if not bad and flags.get("visible_camera") else "BAD",
            c.name, flags.get("visible_camera"),
            sum(1 for k, v in flags.items() if k != "visible_camera" and not v),
            len(flags) - 1))

    print("-" * 72)
    print("【3】材质共享")
    mat = bpy.data.materials.get(MAT_NAME)
    if mat is None:
        fails.append("材质 %s 不存在" % MAT_NAME)
    else:
        print("   %s users=%d nodes=%d" % (mat.name, mat.users, len(mat.node_tree.nodes)))
        if mat.users != len(cones):
            fails.append("材质使用者 %d ≠ 锥体数 %d ⇒ 不是全部共享" % (mat.users, len(cones)))
        nt = mat.node_tree
        pv = next((n for n in nt.nodes if n.type == 'PRINCIPLED_VOLUME'), None)
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if pv is None or out is None:
            fails.append("材质缺少 体积 或 输出 节点")
        else:
            for sock_name, sock in (("Density", pv.inputs["Density"]),
                                    ("Emission Strength", pv.inputs["Emission Strength"]),
                                    ("Volume", out.inputs["Volume"])):
                n_in = len([lk for lk in nt.links if lk.to_socket == sock])
                mark = "OK " if n_in == 1 else "BAD"
                if n_in != 1:
                    fails.append("%s 的 %s 没有连线(羽化必然失效)" % (mat.name, sock_name))
                print("   %s 连线 %-20s → %d" % (mark, sock_name, n_in))

    print("-" * 72)
    print("【4】驱动器")
    if mat is not None and mat.use_nodes:
        nt = mat.node_tree
        drvs = list(nt.animation_data.drivers) if nt.animation_data else []
        print("   驱动器 %d 条" % len(drvs))
        for fc in drvs:
            d = fc.driver
            tgt = d.variables[0].targets[0] if d.variables else None
            print("      %-46s type=%-8s target=%s" % (
                fc.data_path, d.type,
                (tgt.id_type, tgt.id.name if tgt.id else None, tgt.data_path) if tgt else None))
            if d.type == 'SCRIPTED':
                print("      ⚠️ SCRIPTED 型在非受信任 .blend 里会静默不求值,建议改 AVERAGE")

    print("-" * 72)
    print("【5】场景属性")
    sc = bpy.context.scene
    print("   %s = %s" % (PROP_KEY, sc.get(PROP_KEY, "(不存在)")))

    print("=" * 72)
    if fails:
        print("VERIFY_RESULT  FAIL  (%d 项)" % len(fails))
        for f in fails:
            print("   ✗ %s" % f)
    else:
        print("VERIFY_RESULT  PASS")
    print("VERIFY_BEAM_DONE")


try:
    main()
except Exception:
    print("EXCEPTION")
    print(traceback.format_exc())
