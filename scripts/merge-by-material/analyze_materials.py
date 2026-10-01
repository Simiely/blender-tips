# -*- coding: utf-8 -*-
"""
按材质合并 —— 前置可行性分析(只读,不改工程)

**动手前必须跑这个**。它回答四个决定成败的问题:

1. 有多少对象共用同一个网格数据块(多实例)?——不为 0 就危险,合并会把一份几何复制 N 份
2. 有多少 UV / 顶点色 / 形态键 / 修改器?—— 这些决定分组键怎么定、会不会丢
3. 去重后的材质组合有多少种?—— 直接等于合并后的对象数
4. 有没有父级 / 旋转 / 缩放?—— 决定必须做世界变换烘焙

运行位置(系统命令行,只读):
    blender.exe --background --factory-startup "<源.blend>" --python analyze_materials.py

输出:<cwd>/material_report.json + stdout
"""

import bpy, collections, json, time, os

LOG = os.path.join(os.getcwd(), "material_report.json")
L = []
t0 = time.time()


def P(*a):
    s = " ".join(str(x) for x in a)
    L.append(s)
    try:
        print("==" + s, flush=True)
    except Exception:
        pass


P("FILE", bpy.data.filepath)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
P("MESH_OBJECTS", len(meshes))
P("TOTAL_MESH_DATABLOCKS", len(bpy.data.meshes))
P("TOTAL_VERTS", sum(len(m.data.vertices) for m in meshes))
P("TOTAL_POLYS", sum(len(m.data.polygons) for m in meshes))
P("MATERIALS_TOTAL", len(bpy.data.materials))

# 每个对象挂了几个材质槽
slot_hist = collections.Counter(len(o.data.materials) for o in meshes)
P("SLOTS_PER_OBJECT_HIST", dict(sorted(slot_hist.items())))

# 材质组合(按完整材质列表)去重后还剩多少组 = 合并后的理论对象数
sets = collections.Counter(
    tuple((m.name if m else "<空>") for m in o.data.materials) for o in meshes
)
P("DISTINCT_MATERIAL_SETS", len(sets))
P("TOP15_SETS", [(list(k)[:3], v) for k, v in sets.most_common(15)])

# ★ 关键红线:mesh 数据块被多少个对象共用(SKP 组件实例 / Alt+D 复制)
users_hist = collections.Counter(o.data.users for o in meshes)
P("MESH_USERS_HIST_对象数", dict(sorted(users_hist.items())[:15]))
shared = [o for o in meshes if o.data.users > 1]
P("对象共用同一网格的数量", len(shared))
P("涉及共享网格的数据块数", len({o.data for o in shared}))
if shared:
    P("共享最多的网格", collections.Counter(o.data.name for o in shared).most_common(5))
    P("!! 存在多实例:直接合并会把同一份几何复制 N 份,文件可能暴涨。先 Evaluate/独立化")
else:
    P("无多实例:可以安全按材质合并")

# UV / 顶点色 / 形态键盘点 —— 决定分组键与会不会丢数据
uv_hist = collections.Counter(len(o.data.uv_layers) for o in meshes)
P("UV_LAYER_COUNT_HIST", dict(sorted(uv_hist.items())))
uv_names = collections.Counter(l.name for o in meshes for l in o.data.uv_layers)
P("UV_LAYER_NAMES", dict(uv_names))
P("有顶点色的对象", sum(1 for o in meshes if o.data.color_attributes))
P("有形态键的对象", sum(1 for o in meshes if o.data.shape_keys))

single = [o for o in meshes if len(o.data.materials) == 1]
nomat = [o for o in meshes if len(o.data.materials) == 0]
multi = [o for o in meshes if len(o.data.materials) > 1]
P("单材质对象", len(single), "| 无材质对象", len(nomat), "| 多材质对象", len(multi))

# 合并会改变 / 丢失的东西
P("有父级的对象", sum(1 for o in meshes if o.parent is not None))
P("带修改器", sum(1 for o in meshes if o.modifiers))
P("带约束", sum(1 for o in meshes if o.constraints))
P("有自定义属性", sum(1 for o in meshes if len(o.keys()) > 1))
P("非单位缩放", sum(1 for o in meshes if any(abs(x - 1.0) > 1e-6 for x in o.scale)))
P("非 EMPTY 非 MESH 的对象", sum(1 for o in bpy.data.objects
                            if o.type not in ("MESH", "EMPTY")))

with open(LOG, "w", encoding="utf-8") as f:
    json.dump({"lines": L}, f, ensure_ascii=False, indent=1)
P("REPORT", LOG)
P("ELAPSED", "%.1f" % (time.time() - t0))
P("DONE")
