"""撤销:删锥体 / 删材质 / 删场景属性 / 可选恢复被隐藏的旧锥体

默认先打印「将要删除什么」,`DRY_RUN = True` 时只看不动。

    python undo_beam.py
    python bl.py undo_beam.py <port>
"""
import bpy
import traceback

# ============================ CONFIG ============================
DRY_RUN = False                 # True = 只列清单不动手
MAT_NAME = "光锥_羽化材质"
CONE_SUFFIX = "_光锥"
PROP_KEYS = ("光锥羽化", "光锥浓度", "光锥亮度")
MERGE_INTO_LIGHTS = True        # 删锥体前把它们的父级关系清掉(避免留下悬空引用)
UNHIDE_HIDDEN = False           # 是否把 hide_render/hide_viewport 的对象恢复显示
# ================================================================


def main():
    sc = bpy.context.scene
    removed = []

    cones = [o for o in bpy.data.objects if o.name.endswith(CONE_SUFFIX)]
    cones.sort(key=lambda o: o.name)
    print("将删除锥体 %d 个:" % len(cones))
    for c in cones:
        print("   - %-24s parent=%s materials=%s" % (
            c.name, c.parent.name if c.parent else None,
            [m.name for m in c.data.materials]))

    mat = bpy.data.materials.get(MAT_NAME)
    print("将删除材质: %s" % (mat.name if mat else "(无)"))

    print("将删除场景属性: %s" % [k for k in PROP_KEYS if k in sc])

    hidden = [o.name for o in bpy.data.objects if o.hide_render and o.hide_viewport]
    print("当前处于隐藏状态的对象 %d 个: %s" % (len(hidden), hidden[:20]))
    print("   (UNHIDE_HIDDEN=%s ⇒ %s)" % (UNHIDE_HIDDEN, "会恢复显示" if UNHIDE_HIDDEN else "保持隐藏"))

    if DRY_RUN:
        print("DRY_RUN=True,未做任何修改")
        print("UNDO_BEAM_DONE")
        return

    # ---- 1) 锥体 ----
    for c in cones:
        if MERGE_INTO_LIGHTS:
            try:
                mw = c.matrix_world.copy()
                c.parent = None
                c.matrix_world = mw
            except Exception:
                pass
        bpy.data.objects.remove(c, do_unlink=True)
        removed.append(c.name)

    # ---- 2) 材质(驱动器挂在它的节点树上,随之消失) ----
    if mat is not None:
        if mat.node_tree and mat.node_tree.animation_data:
            for fc in list(mat.node_tree.animation_data.drivers):
                try:
                    mat.node_tree.animation_data.drivers.remove(fc)
                except Exception:
                    pass
        gone_name = mat.name
        bpy.data.materials.remove(mat, do_unlink=True)
        removed.append(gone_name)

    # ---- 3) 场景属性 ----
    for k in PROP_KEYS:
        if k in sc:
            del sc[k]

    # ---- 4) 可选恢复隐藏 ----
    if UNHIDE_HIDDEN:
        for n in hidden:
            o = bpy.data.objects.get(n)
            if o:
                o.hide_render = False
                o.hide_viewport = False

    sc.update_tag()
    print("-" * 72)
    print("已删除: %s" % removed)
    print("剩余 %s 结尾的对象: %d" % (
        CONE_SUFFIX, len([o for o in bpy.data.objects if o.name.endswith(CONE_SUFFIX)])))
    print("UNDO_BEAM_DONE")


try:
    main()
except Exception:
    print("EXCEPTION")
    print(traceback.format_exc())
