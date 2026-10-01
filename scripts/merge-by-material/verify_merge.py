# -*- coding: utf-8 -*-
"""
按材质合并 —— 复核脚本(**必须另开一次 Blender 进程**)

在合并进程里跑的 CHECK_VERTS / CHECK_POLYS 只能证明「内存里的数据对得上」,
**不能证明存出去的文件还能打开**。所以必须重开一次 Blender 加载产物做复核。

用法:跑完 merge_by_material.py 后,用产物数据填写下面的配置,再跑本脚本。

运行位置(系统命令行,只读):
    blender.exe --background --factory-startup "<合并后.blend>" --python verify_merge.py

判据(全部 OK 才算通过):
    顶点数一致 / 面数一致 / 排除对象仍原样保留 / 顶层集合完整 / 材质与图片未丢
"""

import bpy

# ==================== 配置项(改成你这次的实测值) ====================
# 取自合并源工程(analyze_materials.py 的 TOTAL_VERTS / TOTAL_POLYS)
EXPECT_VERTS = 0          # 例:10197620
EXPECT_POLYS = 0          # 例:7957765
# 期望保留的排除对象名(没有就留空表)
EXPECT_KEPT = []          # 例:["G-物体.24146"]
# 期望的顶层集合名(没有就留空表,留空则不校验)
EXPECT_TOP_COLLECTIONS = []
# ====================================================================

meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.data]
v = sum(len(o.data.vertices) for o in meshes)
p = sum(len(o.data.polygons) for o in meshes)

print("==FILE==", bpy.data.filepath)
print("==BLENDER==", bpy.app.version_string)
print("==MESH_OBJECTS==", len(meshes))
print("==VERTS==", v)
print("==POLYS==", p)
print("==MATERIALS==", len(bpy.data.materials))
print("==IMAGES==", len(bpy.data.images))
print("==EMPTY==", len([o for o in bpy.data.objects if o.type == "EMPTY"]))
print("==SCENES==", [s.name for s in bpy.data.scenes])
print("==TOP_COLLECTIONS==", [c.name for c in bpy.data.scenes[0].collection.children])

ok = True


def check(label, cond, detail=""):
    global ok
    print("==CHECK_%s==" % label, "OK" if cond else "FAIL " + detail)
    ok = ok and cond


if EXPECT_VERTS:
    check("VERTS", v == EXPECT_VERTS, "%d -> %d" % (EXPECT_VERTS, v))
if EXPECT_POLYS:
    check("POLYS", p == EXPECT_POLYS, "%d -> %d" % (EXPECT_POLYS, p))

for name in EXPECT_KEPT:
    hit = [o for o in meshes if o.name == name]
    check("KEPT_" + name, bool(hit), "排除对象丢失")
    if hit:
        o = hit[0]
        print("   ->", name, "| 顶点", len(o.data.vertices), "| 面", len(o.data.polygons),
              "| 材质", [m.name if m else None for m in o.data.materials])

if EXPECT_TOP_COLLECTIONS:
    got = [c.name for c in bpy.data.scenes[0].collection.children]
    check("TOP_COLLECTIONS", got == EXPECT_TOP_COLLECTIONS,
          "期望 %s 实际 %s" % (EXPECT_TOP_COLLECTIONS, got))

print("==NAMES==")
for o in sorted(meshes, key=lambda x: -len(x.data.vertices))[:20]:
    print("   ", o.name, "| 顶点", len(o.data.vertices), "| 面", len(o.data.polygons),
          "| 材质", len([m for m in o.data.materials if m]))

print("==VERIFY_RESULT==", "PASS" if ok else "FAIL")
print("==DONE==")
