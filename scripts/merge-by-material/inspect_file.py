# -*- coding: utf-8 -*-
"""
工程结构扫描 —— 只读,不改工程

打开一个巨型 .blend 前先看清里面长什么样:顶层集合树、每个集合的对象数、
总数统计。用于决定「删哪个集合 / 能不能合并 / 怎么合」。

运行位置(系统命令行,只读):
    blender.exe --background --factory-startup "<源.blend>" --python inspect_file.py
"""

import bpy

print("==BLENDER==", bpy.app.version_string)
print("==FILE==", bpy.data.filepath)


def walk(coll, depth=0):
    objs = list(coll.objects)
    sub = list(coll.children)
    print("==" + "  " * depth + "COLL==", coll.name,
          "| 直接对象:", len(objs), "| 子集合:", len(sub))
    for o in objs[:8]:
        print("==" + "  " * depth + "   OBJ==", o.name, "|", o.type)
    if len(objs) > 8:
        print("==" + "  " * depth + "   ... 还有", len(objs) - 8, "个对象")
    for c in sub:
        walk(c, depth + 1)


print("==SCENE_COLLECTION_CHILDREN==", len(bpy.context.scene.collection.children))
for c in bpy.context.scene.collection.children:
    walk(c, 0)

print("==ALL_COLLECTIONS_IN_DATA==", len(bpy.data.collections))
for c in bpy.data.collections:
    print("==DC==", c.name, "| users:", c.users, "| 对象:", len(c.objects),
          "| 父集合:", [p.name for p in bpy.data.collections
                   if c.name in [x.name for x in p.children]])

print("==TOTALS==")
print("==TOTAL_OBJECTS==", len(bpy.data.objects))
print("==TOTAL_MESHES==", len(bpy.data.meshes))
print("==TOTAL_MATERIALS==", len(bpy.data.materials))
print("==TOTAL_IMAGES==", len(bpy.data.images))
print("==TOTAL_SCENES==", len(bpy.data.scenes), [s.name for s in bpy.data.scenes])
print("==DONE==")
