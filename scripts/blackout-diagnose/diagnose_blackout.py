# -*- coding: utf-8 -*-
"""渲染发黑 / 材质不发光 —— 一次打全的诊断脚本

用法（通过 9877 桥发送）：
    python bl.py diagnose_blackout.py
结果直接 print 回传。

可选：把 TARGET 改成对象名，额外对该对象做逐项体检（可见性/Holdout/材质树）。
     留空则只做全场景扫描。
"""
import bpy
import traceback

TARGET = ""          # 例: "图形1371.001"
MAX_LIST = 40        # 每个清单最多打印多少条，避免刷屏

out_lines = []


def p(*a):
    s = " ".join(str(x) for x in a)
    out_lines.append(s)
    print(s)


def sock(node, *names):
    """按候选名取输入 socket（跨 Blender 版本兼容）"""
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    return None


def val(s, default=None):
    if s is None:
        return default
    v = getattr(s, "default_value", None)
    if v is None:
        return default
    try:
        return tuple(round(float(x), 4) for x in v)
    except TypeError:
        return round(float(v), 4)


def node_brief(n):
    """给节点打一句特征描述（只取关键输入）"""
    if n.type == "BSDF_PRINCIPLED":
        ec = sock(n, "Emission Color", "Emission")
        es = sock(n, "Emission Strength")
        return "base=%s emis_c=%s emis_s=%s alpha=%s" % (
            val(sock(n, "Base Color")), val(ec), val(es), val(sock(n, "Alpha")))
    if n.type == "EMISSION":
        return "color=%s strength=%s" % (
            val(sock(n, "Color")), val(sock(n, "Strength")))
    if n.type == "BSDF_TRANSPARENT":
        return "color=%s" % val(sock(n, "Color"))
    return ""


def emit_like_strength(n):
    """返回该节点的"发光强度"；不发光返回 None"""
    if n.type == "EMISSION":
        s = sock(n, "Strength")
        return float(s.default_value) if s else None
    if n.type == "BSDF_PRINCIPLED":
        es = sock(n, "Emission Strength")
        ec = sock(n, "Emission Color", "Emission")
        if es is None:
            return None
        strength = float(es.default_value)
        color_max = max(val(ec, (0, 0, 0))[:3]) if ec else 0
        # 强度非 0 且颜色非全黑，才算"真发光的意图"
        if strength > 0 and (color_max > 0 or not ec.is_linked):
            return strength
        return None
    return None


try:
    sc = bpy.context.scene
    vl = bpy.context.view_layer

    # ============ A. 渲染设置 ============
    p("=" * 62)
    p("A. 渲染设置")
    p("=" * 62)
    p("filepath      :", bpy.data.filepath)
    p("engine        :", sc.render.engine)
    p("view_transform:", sc.view_settings.view_transform,
      "| look:", sc.view_settings.look,
      "| exposure:", round(sc.view_settings.exposure, 4),
      "| gamma:", round(sc.view_settings.gamma, 4))
    p("film_transparent:", sc.render.film_transparent)
    p("resolution    : %dx%d @%d%%" % (
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage))
    p("")
    if sc.render.engine == "BLENDER_WORKBENCH":
        p("  ⚠ 引擎是 Workbench —— 它【完全不读材质节点树】，发光永远不生效")
    if sc.view_settings.view_transform in ("AgX", "Filmic"):
        p("  ⚠ view_transform=%s —— 会对高亮强烈滚降，发光会被压暗（建议提高 Strength 验证）"
          % sc.view_settings.view_transform)
    p("")

    # ============ B. 材质覆盖（头号嫌疑） ============
    p("=" * 62)
    p("B. 材质覆盖 / 单色模式（头号嫌疑）")
    p("=" * 62)
    hit_override = False
    for v in sc.view_layers:
        mo = v.material_override
        p("- view_layer %r" % v.name)
        p("    material_override:", (repr(mo.name) if mo else None))
        if mo:
            hit_override = True
            p("    users=%d use_nodes=%s" % (mo.users, mo.use_nodes))
            if mo.use_nodes and mo.node_tree:
                for n in mo.node_tree.nodes:
                    p("      [%s] %r %s" % (n.type, n.name, node_brief(n)))
                for l in mo.node_tree.links:
                    p("      %r.%r -> %r.%r" % (
                        l.from_node.name, l.from_socket.name,
                        l.to_node.name, l.to_socket.name))
    try:
        sh = sc.display.shading
        p("- Workbench shading: color_type=%s light=%s single_color=%s"
          % (sh.color_type, sh.light,
             tuple(round(float(x), 4) for x in sh.single_color)))
        if sh.color_type == "SINGLE":
            p("  ⚠ color_type=SINGLE —— Workbench 下整场景单色，材质不生效")
    except Exception as e:
        p("- Workbench shading 读取失败:", e)
    p("")
    p("  >>> material_override 命中:", hit_override)
    p("")

    # ============ C. 材质健康度 ============
    p("=" * 62)
    p("C. 全场景材质健康度（%d 个材质）" % len(bpy.data.materials))
    p("=" * 62)

    no_nodes = []           # use_nodes == False
    no_output = []          # 没有 active output / Surface 未连线
    output_from_transparent = []   # 直连 Transparent BSDF
    fake_emissive = []      # 发光值 > 0 但【未接到输出】= 假发光 ★
    multi_bsdf = []         # 多个 BSDF 只接了其中一个
    orphan_output = []      # 存在多个 OUTPUT_MATERIAL，只一个 active

    for m in bpy.data.materials:
        if not m.use_nodes:
            no_nodes.append((m.name, m.users, "use_nodes=False"))
            continue
        nt = m.node_tree
        if nt is None:
            no_output.append((m.name, m.users, "node_tree is None"))
            continue

        outs = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"]
        actives = [n for n in outs if getattr(n, "is_active_output", False)]
        if not outs:
            no_output.append((m.name, m.users, "无 OUTPUT_MATERIAL 节点"))
            continue
        if len(outs) > 1:
            orphan_output.append((m.name, m.users, len(outs), len(actives)))
        out = actives[0] if actives else outs[0]

        surf = out.inputs.get("Surface")
        if surf is None or not surf.is_linked:
            no_output.append((m.name, m.users, "Surface 未连线"))
            continue

        from_node = surf.links[0].from_node
        if from_node.type == "BSDF_TRANSPARENT":
            output_from_transparent.append((m.name, m.users, from_node.name))

        # 图中所有 BSDF / 发光类节点
        bsdfs = [n for n in nt.nodes
                 if n.type in ("BSDF_PRINCIPLED", "EMISSION", "BSDF_GLASS",
                               "EMISSION_ALPHA", "BSDF_TRANSPARENT",
                               "BSDF_DIFFUSE", "BSDF_GLOSSY", "BSDF_METALLIC")]

        # 哪些 BSDF 真的在"通向输出"的链上（沿反向可达）
        reaching = set()
        stack = [out]
        seen = set()
        while stack:
            n = stack.pop()
            if n.name in seen:
                continue
            seen.add(n.name)
            for inp in n.inputs:
                for l in inp.links:
                    reaching.add(l.from_node.name)
                    stack.append(l.from_node)
        reaching.add(out.name)

        for b in bsdfs:
            st = emit_like_strength(b)
            if st is not None and b.name not in reaching:
                fake_emissive.append((m.name, m.users, b.name, b.type, st))

        connected_bsdfs = [b for b in bsdfs if b.name in reaching]
        if len(bsdfs) > 1 and len(connected_bsdfs) == 1:
            others = [b for b in bsdfs if b.name not in reaching]
            multi_bsdf.append((
                m.name, m.users,
                connected_bsdfs[0].type, connected_bsdfs[0].name,
                [(b.type, b.name, emit_like_strength(b)) for b in others[:4]]))

    p("① use_nodes=False 的材质: %d 个" % len(no_nodes))
    for n, u, _ in no_nodes[:MAX_LIST]:
        p("     - %r (users=%d)" % (n, u))
    p("")
    p("② 输出未连通 / 无输出节点的材质: %d 个" % len(no_output))
    for n, u, why in no_output[:MAX_LIST]:
        p("     - %r (users=%d)  %s" % (n, u, why))
    p("")
    p("③ 输出直连 Transparent BSDF 的材质: %d 个" % len(output_from_transparent))
    for n, u, nn in output_from_transparent[:MAX_LIST]:
        p("     - %r (users=%d)  <- %r" % (n, u, nn))
    p("")
    p("④ ★假发光：发光强度>0 但【未接到输出】的节点: %d 个" % len(fake_emissive))
    for n, u, nn, tp, st in fake_emissive[:MAX_LIST]:
        p("     - 材质 %r (users=%d)" % (n, u))
        p("         节点 [%s] %r  emission_strength=%s  ← 改了它没用" % (tp, nn, st))
    p("")
    p("⑤ 多个 BSDF 但只有 1 个接在输出上: %d 个材质" % len(multi_bsdf))
    for n, u, ct, cn, others in multi_bsdf[:MAX_LIST]:
        p("     - 材质 %r (users=%d)" % (n, u))
        p("         生效: [%s] %r" % (ct, cn))
        for tp, nn, st in others:
            p("         孤儿: [%s] %r  emit_s=%s" % (tp, nn, st))
    p("")
    p("⑥ 存在多个 OUTPUT_MATERIAL 的材质: %d 个" % len(orphan_output))
    for n, u, tot, act in orphan_output[:MAX_LIST]:
        p("     - %r (users=%d) outputs=%d active=%d" % (n, u, tot, act))
    p("")

    # ============ D. 对象级体检 ============
    p("=" * 62)
    p("D. 对象级体检")
    p("=" * 62)
    if not TARGET:
        p("(TARGET 为空，跳过。要查具体对象就把脚本顶部 TARGET 改成对象名)")
    else:
        tgts = [o for o in bpy.data.objects if TARGET in o.name]
        p("匹配 %r 的对象: %d 个" % (TARGET, len(tgts)))
        for o in tgts:
            p("- %r  type=%s" % (o.name, o.type))
            p("    parent=%s  data=%s  colls=%s" % (
                (o.parent.name if o.parent else None),
                (o.data.name if o.data else None),
                [c.name for c in o.users_collection]))
            p("    hide_render=%s hide_viewport=%s hide_get=%s visible_get=%s" % (
                o.hide_render, o.hide_viewport, o.hide_get(), o.visible_get()))
            p("    in_view_layer=%s  vl.hide_viewport=%s" % (
                (vl.objects.get(o.name) is not None),
                (vl.objects.get(o.name).hide_viewport
                 if vl.objects.get(o.name) else "n/a")))
            p("    【渲染可见性】is_holdout=%s indirect_only=%s is_shadow_catcher=%s" % (
                getattr(o, "is_holdout", "n/a"),
                getattr(o, "indirect_only", "n/a"),
                getattr(o, "is_shadow_catcher", "n/a")))
            p("    【光线可见性】camera=%s diffuse=%s glossy=%s transmission=%s shadow=%s" % (
                getattr(o, "visible_camera", "n/a"),
                getattr(o, "visible_diffuse", "n/a"),
                getattr(o, "visible_glossy", "n/a"),
                getattr(o, "visible_transmission", "n/a"),
                getattr(o, "visible_shadow", "n/a")))
            p("    dimensions=%s  display_type=%s" % (
                tuple(round(v, 4) for v in o.dimensions), o.display_type))
            p("    material_slots=%d" % len(o.material_slots))
            for i, ms in enumerate(o.material_slots):
                m = ms.material
                p("      slot%d link=%s: %r" % (i, ms.link, (m.name if m else None)))
                if not m:
                    continue
                p("         users=%d use_nodes=%s blend=%s backface_cull=%s" % (
                    m.users, m.use_nodes,
                    getattr(m, "blend_method", "n/a"),
                    getattr(m, "use_backface_culling", "n/a")))
                if m.use_nodes and m.node_tree:
                    nt = m.node_tree
                    for n in nt.nodes:
                        p("         [%s] %r %s" % (n.type, n.name, node_brief(n)))
                    for l in nt.links:
                        p("         %r.%r -> %r.%r" % (
                            l.from_node.name, l.from_socket.name,
                            l.to_node.name, l.to_socket.name))
    p("")

    # ============ E. 结论 ============
    p("=" * 62)
    p("E. 结论 / 建议动作（按命中率降序）")
    p("=" * 62)
    verdict = []
    if hit_override:
        verdict.append("★ 命中 View Layer 材质覆盖 material_override —— "
                       "该视图层下全部对象材质被替换，你改的任何材质都不生效。"
                       "清除：vl.material_override = None")
    if sc.render.engine == "BLENDER_WORKBENCH":
        verdict.append("★ 引擎是 WORKBENCH —— 不读材质节点。切 CYCLES 或 EEVEE_NEXT")
    if not verdict:
        if fake_emissive:
            verdict.append("★ 存在「假发光」节点 %d 个 —— 发光值是改在未接输出的节点上，"
                           "真正生效的是另一个 BSDF（见 C.④）" % len(fake_emissive))
        if no_output:
            verdict.append("★ 有 %d 个材质输出未连通，渲染为默认黑/灰（见 C.②）" % len(no_output))
        if sc.view_settings.view_transform in ("AgX", "Filmic"):
            verdict.append("· view_transform=%s 会压暗高亮 —— 发光强度需显著提高才亮"
                           % sc.view_settings.view_transform)
        if output_from_transparent:
            verdict.append("· 有 %d 个材质输出直连 Transparent（全透明）" % len(output_from_transparent))
        if not verdict:
            verdict.append("七条路径全未命中 —— 请填 TARGET 做对象级体检（D 区），"
                           "重点看 is_holdout / visible_camera / 是否被遮挡")
    for i, v in enumerate(verdict, 1):
        p("%d) %s" % (i, v))
    p("")
    p("统计: 材质 %d | 未连通 %d | 假发光 %d | 多BSDF只连一 %d | 覆盖材质 %s"
      % (len(bpy.data.materials), len(no_output), len(fake_emissive),
         len(multi_bsdf), hit_override))

except Exception:
    p("EXC:")
    p(traceback.format_exc())
