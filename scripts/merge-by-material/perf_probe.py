# -*- coding: utf-8 -*-
"""
【无头 · 性能体检】统计场景规模 + 测几项与「流畅度」相关的客观耗时。

用法：
    blender.exe --background --factory-startup "<x>.blend" --python perf_probe.py
    # 结果追加到 <cwd>/perf_out.txt（可用环境变量 MBM_PERF_OUT 指定别处）

它回答的是「合并后会更流畅吗」——四个指标各有分工，别混着看：
    · mesh_objects      draw call 的代理量  → 视口刷新 / Outliner / 选择的响应
    · objects_with_mod  依赖图求值负担      → 每个带修改器的对象每次重算都要过一遍
    · objsum_verts      **每帧真正提交的顶点量** → 这一个不变，就说明渲染帧率不变
    · uniq_verts        显存 / 内存占用      → 实例被展开后会变大，这是合并的固有取舍
"""

import bpy, time, os, sys

D = bpy.data
VL = bpy.context.view_layer
OUT = os.environ.get("MBM_PERF_OUT", os.path.join(os.getcwd(), "perf_out.txt"))
out = []


def p(s=""):
    out.append(str(s))
    try:
        print("==" + str(s), flush=True)
    except Exception:
        pass


objs = list(D.objects)
mesh_objs = [o for o in objs if o.type == "MESH"]

p("FILE %s" % bpy.data.filepath)
p("BYTES %d" % (os.path.getsize(bpy.data.filepath) if bpy.data.filepath
                and os.path.isfile(bpy.data.filepath) else 0))
p("objects            %8d" % len(objs))
p("mesh_objects       %8d   <= draw call 代理量" % len(mesh_objs))
p("empties            %8d" % sum(1 for o in objs if o.type == "EMPTY"))
p("mesh_blocks        %8d" % len(D.meshes))
p("collections        %8d" % len(D.collections))
p("materials          %8d" % len(D.materials))
p("images             %8d" % len(D.images))

# 唯一 mesh 数据块的几何量（显存 / 内存口径）
uv = uf = 0
for m in D.meshes:
    uv += len(m.vertices)
    uf += len(m.polygons)
p("uniq_verts         %8d   <= 显存 / 内存口径" % uv)
p("uniq_faces         %8d" % uf)

# 按对象累加（共享 mesh 也按使用次数各算一遍）= 渲染时 GPU 每帧真正要处理的几何量
v_obj = f_obj = 0
for o in mesh_objs:
    v_obj += len(o.data.vertices)
    f_obj += len(o.data.polygons)
p("objsum_verts       %8d   <= 视口每帧真正提交的顶点量" % v_obj)
p("objsum_faces       %8d" % f_obj)

# 修改器（『按角度平滑』是 NODES 型，每个对象一次求值）
n_mod_obj = sum(1 for o in objs if len(o.modifiers))
n_mod = sum(len(o.modifiers) for o in objs)
p("objects_with_mod   %8d   <= 依赖图求值负担" % n_mod_obj)
p("total_modifiers    %8d" % n_mod)


def t(label, fn):
    t0 = time.perf_counter()
    fn()
    dt = time.perf_counter() - t0
    p("TIME %-22s %7.3f s" % (label, dt))
    return dt


t("select_all(SELECT)", lambda: bpy.ops.object.select_all(action="SELECT"))
t("select_all(DESELECT)", lambda: bpy.ops.object.select_all(action="DESELECT"))


def walk():
    for o in objs:
        _ = o.matrix_world
        _ = o.name


t("walk_read_matrix", walk)


def dg_eval():
    dg = bpy.context.evaluated_depsgraph_get()
    for _ in dg.object_instances:
        pass


t("depsgraph_instances", dg_eval)
t("view_layer_update", lambda: VL.update())
t("view_layer_update#2", lambda: VL.update())

p("=" * 62)
p("py %s  blender %s" % (".".join(str(x) for x in sys.version_info[:3]),
                         bpy.app.version_string))

with open(OUT, "a", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out) + "\n\n")
