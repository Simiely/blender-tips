# restore_legacy_angle.py —— 补回旧版材质 `滚动效果网格体_竖条旋转` 需要的「斜角」属性
#
# 背景：新版（按条数）建脚本会把「斜角」当废弃键清掉，但**旧版材质仍在 146 个对象上使用**，
#      它的 `斜角_弧度` 节点靠 ctrl["斜角"] 驱动 ⇒ 属性没了 ⇒ 该驱动失效
#      （表现：条纹疏密退回默认；上升动态仍在）。
# 用法：跑过任何新版建脚本之后，若要继续用旧版材质，跑一次本脚本。
import bpy

CTRL = '竖条旋转控制'
LEGACY = '滚动效果网格体_竖条旋转'
DEFAULT_ANGLE = 41.0

ctrl = bpy.data.objects.get(CTRL)
if ctrl is None:
    print('✗ 找不到锚点', CTRL); raise SystemExit(1)

need = False
m = bpy.data.materials.get(LEGACY)
if m and m.use_nodes and m.node_tree.animation_data:
    for d in m.node_tree.animation_data.drivers:
        if '斜角' in d.data_path:
            if not d.driver.is_valid:
                need = True
if need and '斜角' not in ctrl:
    ctrl['斜角'] = DEFAULT_ANGLE
    print('✔ 已补回 ctrl["斜角"] = %s' % DEFAULT_ANGLE)
elif '斜角' in ctrl:
    print('· ctrl["斜角"] 已存在 =', round(ctrl['斜角'], 3))
else:
    print('· 旧版材质的斜角驱动没有失效，无需补')

ctrl.update_tag()
for mm in bpy.data.materials:
    if mm.name.startswith('滚动效果网格体') and mm.use_nodes:
        mm.update_tag(); mm.node_tree.update_tag()
bpy.context.view_layer.update()

if m and m.use_nodes and m.node_tree.animation_data:
    drs = m.node_tree.animation_data.drivers
    print('  旧版材质驱动: %d 条，有效 %d 条'
          % (len(drs), sum(1 for d in drs if d.driver.is_valid)))
print('RESTORE_OK')
