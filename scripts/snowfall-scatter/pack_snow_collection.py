# -*- coding: utf-8 -*-
# 归拢下雪系统依赖对象到新集合 下雪_系统, 便于整体复制到别的工程
import bpy

NEW = '下雪_系统'
NEED = ['下雪_宿主', '花瓣雪花_低模', '平面.005']   # 宿主 / 雪花源 / 地面参考(落雪范围)

# 新建集合并挂到场景
coll = bpy.data.collections.get(NEW)
if coll is None:
    coll = bpy.data.collections.new(NEW)
if NEW not in [c.name for c in bpy.context.scene.collection.children]:
    bpy.context.scene.collection.children.link(coll)

print('=== 归拢对象到集合 [%s] ===' % NEW)
for name in NEED:
    o = bpy.data.objects.get(name)
    if o is None:
        print('[缺失] %s' % name)
        continue
    before = [c.name for c in o.users_collection]
    for c in list(o.users_collection):
        c.objects.unlink(o)
    coll.objects.link(o)
    print('[放入] %s  原集合=%s -> 现集合=[%s]' % (name, before, NEW))

# 依赖的数据块(none在集合内, 属于全局 data, 追加集合时会被自动带入)
print('=== 依赖数据块(跟随宿主/源自动带入, 无需手动装) ===')
print(' 节点组 :', '下雪_GN' if '下雪_GN' in bpy.data.node_groups else '缺失!')
print(' 网格   :', '花瓣雪花_低模' if '花瓣雪花_低模' in bpy.data.meshes else '缺失!')
print(' 材质   :', '花瓣雪花_低模_mat' if '花瓣雪花_低模_mat' in bpy.data.materials else '缺失!')