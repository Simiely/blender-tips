import bpy

# =============================================================================
# build_sky_sun_driver.py —— 天空太阳高度数字驱动
#
# 场景: 想让天空纹理的太阳高度(sun_elevation)可调、可打关键帧做太阳升降动画。
#       直接给 sun_elevation 打关键帧也行, 但用「数字驱动」更灵活:
#       一个控制面板空物体上的 太阳高度(度) 滑块, 实时驱动天空;
#       对滑块打关键帧 = 对太阳高度打关键帧(单位友好, 且集中控制)。
#
# 用法:
#   1) 改顶部 CTRL_NAME / PROP_NAME / COL_NAME(控制面板挂载集合)
#   2) 在桥里运行:  python send.py build_sky_sun_driver.py
#      (或直接在 Scripting 工作区 Run Script)
#
# 幂等: 已有 sun_elevation 驱动先移除再重建; 控制面板已存在则复用
# 注意: 桥接环境 exec 时 __name__ 为 'builtins', 不能用 __main__ 守卫
# =============================================================================

DEG2RAD = 0.017453292519943295
CTRL_NAME = '天空控制'            # 控制面板空物体名
PROP_NAME = '太阳高度'            # 滑块属性(单位: 度)
COL_NAME = '新对象'               # 控制面板挂载到的集合(找不到回退场景集合)
DEFAULT_DEG = 3.0                 # 默认太阳高度(度)
MIN_DEG, MAX_DEG = -90.0, 90.0    # 滑块范围


def find_sky():
    """找世界节点树里的天空纹理节点(TEX_SKY)"""
    for w in bpy.data.worlds:
        if w.node_tree:
            for n in w.node_tree.nodes:
                if n.type == 'TEX_SKY':
                    return n
    return None


def ensure_ctrl(link_col=None):
    """新建天空控制空物体并写入 太阳高度 滑块(单位度)"""
    obj = bpy.data.objects.get(CTRL_NAME)
    if obj is None:
        obj = bpy.data.objects.new(CTRL_NAME, None)
        (link_col or bpy.context.scene.collection).objects.link(obj)
    obj[PROP_NAME] = DEFAULT_DEG
    try:
        ui = obj.id_properties_ui(PROP_NAME)
        ui.update(description='太阳高度(度): 可打关键帧控制太阳升降',
                  min=MIN_DEG, max=MAX_DEG, soft_min=-30.0, soft_max=60.0,
                  step=10, precision=1)
    except Exception as e:
        print('UI_WARN', repr(e))
    return obj


def add_sky_driver(sky, ctrl):
    """sun_elevation 挂 SCRIPTED 驱动, 读 ctrl['太阳高度'](度->弧度)
    注意: 节点驱动存在 node_tree.animation_data 上(不是节点上),
          路径形如 nodes["天空纹理"].sun_elevation"""
    nt = sky.id_data
    path = f'nodes["{sky.name}"].sun_elevation'
    # 幂等: 先移除旧 sun_elevation 驱动(在节点树的 animation_data 上)
    if nt.animation_data and nt.animation_data.drivers:
        for d in list(nt.animation_data.drivers):
            if d.data_path == path:
                nt.animation_data.drivers.remove(d)

    fcu = sky.driver_add('sun_elevation')
    drv = fcu.driver
    drv.type = 'SCRIPTED'
    # 弧度 = 度 * DEG2RAD
    drv.expression = f'elev * {DEG2RAD!r}'

    v = drv.variables.new()
    v.name = 'elev'
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'OBJECT'
    v.targets[0].id = ctrl
    v.targets[0].data_path = f'["{PROP_NAME}"]'

    # 立即重算
    fcu.update()
    bpy.context.view_layer.update()
    print(f'SKY_DRIVER_OK expr={drv.expression}')
    print(f'  {CTRL_NAME}.{PROP_NAME}={ctrl[PROP_NAME]}° -> sun_elevation={sky.sun_elevation * 57.29578:.2f}°')
    return fcu


def main():
    sky = find_sky()
    if sky is None:
        print('ERR 找不到天空纹理节点(TEX_SKY)')
        return
    col = bpy.data.collections.get(COL_NAME)
    ctrl = ensure_ctrl(link_col=col)
    add_sky_driver(sky, ctrl)
    print('DONE_OK')


main()
