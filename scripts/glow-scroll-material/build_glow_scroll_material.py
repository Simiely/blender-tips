import bpy

# =============================================================================
# build_glow_scroll_material.py —— 渐变发光滚动材质
#
# 场景: 一张竖图(上亮下暗渐变), 贴在物体上做发光 + 竖直匀速滚动:
#   - 贴图颜色 -> Base Color + Emission Color(自发光)
#   - Mapping Scale Y=0.5 -> 竖直放大 2 倍, 只显示渐变上半部分
#   - Mapping Location Y 挂驱动 fr * scroll_speed() -> 竖直匀速滚动
#   - 滚动速度可驱动: 控制空物体「贴图滚动控制」的「滚动速度」滑块(可打关键帧)
#
# 用法:
#   1) 改 MAT_NAME / IMG_PATH 为目标材质和贴图
#   2) 在桥里运行:  python send.py build_glow_scroll_material.py
#      (或直接在 Scripting 工作区 Run Script)
#
# 注意: 桥接 exec 时 __name__ 为 'builtins', 不用 __main__ 守卫
# =============================================================================

MAT_NAME = '06 - Default.003'
IMG_PATH = r'E:\desktop\260815\活力之丘点位模型\001.png'
CTRL_NAME = '贴图滚动控制'
SPEED_PROP = '滚动速度'
SPEED_DEFAULT = 0.05            # 每帧滚动 0.05 V 单位
SPEED_MIN, SPEED_MAX = 0.0, 1.0
COL_NAME = '新对象'
IMG_NODE_NAME = '渐变贴图'
MAPPING_NAME = '滚动映射'
TEXCOORD_NAME = '纹理坐标'


def scroll_speed():
    ctrl = bpy.data.objects.get(CTRL_NAME)
    if ctrl is None:
        return SPEED_DEFAULT
    return float(ctrl.get(SPEED_PROP, SPEED_DEFAULT))


def ensure_ctrl(link_col=None):
    obj = bpy.data.objects.get(CTRL_NAME)
    if obj is None:
        obj = bpy.data.objects.new(CTRL_NAME, None)
        (link_col or bpy.context.scene.collection).objects.link(obj)
    obj[SPEED_PROP] = SPEED_DEFAULT
    try:
        ui = obj.id_properties_ui(SPEED_PROP)
        ui.update(description='渐变贴图竖直滚动速度(V单位/帧): 可打关键帧调速',
                  min=SPEED_MIN, max=SPEED_MAX, soft_min=0.0, soft_max=0.2,
                  step=1, precision=3)
    except Exception as e:
        print('UI_WARN', repr(e))
    return obj


def rebuild_nodes(mat):
    """重建材质节点树: 纹理坐标 -> 映射(缩放/滚动) -> 图像 -> 发光"""
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)

    out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if out is None:
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        out.location = (500, 0)

    img = bpy.data.images.get('001.png')
    if img is None:
        img = bpy.data.images.load(IMG_PATH)
    img_node = nt.nodes.new('ShaderNodeTexImage')
    img_node.name = img_node.label = IMG_NODE_NAME
    img_node.image = img
    img_node.location = (100, 0)

    mp = nt.nodes.new('ShaderNodeMapping')
    mp.name = mp.label = MAPPING_NAME
    mp.location = (-150, 0)
    # Scale Y = 0.5 -> V 放大 2 倍, 只显示上半(渐变条顶亮区)
    mp.inputs['Scale'].default_value = (1.0, 0.5, 1.0)

    tc = nt.nodes.new('ShaderNodeTexCoord')
    tc.name = tc.label = TEXCOORD_NAME
    tc.location = (-400, 0)

    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (300, 0)
    bsdf.inputs['Emission Strength'].default_value = 1.0

    links = nt.links
    links.new(tc.outputs['UV'], mp.inputs['Vector'])
    links.new(mp.outputs['Vector'], img_node.inputs['Vector'])
    links.new(img_node.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(img_node.outputs['Color'], bsdf.inputs['Emission Color'])
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    return mp


def add_scroll_driver(nt, mp):
    """给 Mapping Location Y(V 分量) 挂驱动: fr * scroll_speed()
    节点驱动挂在 node_tree.animation_data 上, 路径 nodes['滚动映射'].inputs[1].default_value"""
    path = f'nodes["{MAPPING_NAME}"].inputs[1].default_value'
    if nt.animation_data and nt.animation_data.drivers:
        for d in list(nt.animation_data.drivers):
            if d.data_path == path and d.array_index == 1:
                nt.animation_data.drivers.remove(d)
    fcu = mp.inputs[1].driver_add('default_value', 1)
    drv = fcu.driver
    drv.type = 'SCRIPTED'
    drv.expression = 'fr * scroll_speed()'
    vf = drv.variables.new()
    vf.name = 'fr'
    vf.type = 'SINGLE_PROP'
    vf.targets[0].id_type = 'SCENE'
    vf.targets[0].id = bpy.context.scene
    vf.targets[0].data_path = 'frame_current'
    fcu.update()
    bpy.context.view_layer.update()
    print('SCROLL_DRIVER', path, '->', drv.expression)
    return fcu


def main():
    mat = bpy.data.materials.get(MAT_NAME)
    if mat is None:
        print('ERR 材质不存在:', MAT_NAME)
        return
    bpy.app.driver_namespace['scroll_speed'] = scroll_speed
    col = bpy.data.collections.get(COL_NAME)
    ctrl = ensure_ctrl(link_col=col)
    mp = rebuild_nodes(mat)
    add_scroll_driver(mat.node_tree, mp)
    print('DONE_OK 材质=%s 控制=%s.%s=%s' % (MAT_NAME, CTRL_NAME, SPEED_PROP, ctrl[SPEED_PROP]))


main()
