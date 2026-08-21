import bpy
import math

# =============================================================================
# build_light_system.py —— 运动网格灯光方案(一键全套)
#
# 场景: 给"带驱动上下浮动"的网格对象, 在每个轴心加一对 AREA 灯:
#   - 向下组: 朝下照(rot_x=0),  亮度 1.5 倍
#   - 向上组: 朝上照(rot_x=pi), z+0.001, 亮度 2 倍
#   - 两组分别 parent 到组轴心空对象(集合运动中心)
#   - 灯位置驱动跟随网格(可加手动偏移 偏移X/Y/Z)
#   - 旋转绑定: 向上灯为主(自由转), 向下灯跟随(差 pi)
#
# 用法:
#   1) 改 TARGETS 为你的集合列表(只处理集合内"带 location.z 驱动"的 MESH)
#   2) 在桥里运行:  python send.py build_light_system.py
#      (或直接在 Scripting 工作区 Run Script)
#
# 幂等: 已有灯/驱动会复用, 可反复运行
# 注意: 桥接 exec 时 __name__ 为 'builtins', 不用 __main__ 守卫
# =============================================================================

TARGETS = ['主装置01', '主装置02', '主装置03', '主装置04', '主装置05']
# 灯参数
LIGHT_SIZE = 1.0
LIGHT_SCALE = 0.26
DOWN_ENERGY = 15.0
UP_ENERGY = 20.0
UP_OFFSET_Z = 0.001
# 命名
DOWN_PREFIX = '面光_'          # 向下灯名 = 面光_<网格名>(特殊: 网格 Rectangle066.001 用「面光」)
UP_SUFFIX = '_up'              # 向上灯名 = <向下灯名>_up
DOWN_AXIS_SUFFIX = '_灯向下_轴心'
UP_AXIS_SUFFIX = '_灯向上_轴心'
# 偏移属性(可调, 单位: 米)
OFFSET_PROPS = ['偏移X', '偏移Y', '偏移Z']
OFFSET_LIMIT = 5.0


def light_off(obj, axis):
    """实时读灯的偏移属性(命名空间函数, 避免 SINGLE_PROP 缓存)"""
    if obj is None:
        return 0.0
    return float(obj.get(OFFSET_PROPS[axis], 0.0))


def driven_meshes(cn):
    col = bpy.data.collections.get(cn)
    return [o for o in col.objects
            if o.type == 'MESH' and o.animation_data and o.animation_data.drivers
            and any(d.data_path == 'location' and d.array_index == 2 for d in o.animation_data.drivers)]


def center_of(movers):
    n = len(movers)
    return [sum(m.location[i] for m in movers) / n for i in range(3)]


def ensure_empty(name, loc, link_col):
    o = bpy.data.objects.get(name)
    if o is None:
        o = bpy.data.objects.new(name, None)
        (link_col or bpy.context.scene.collection).objects.link(o)
    o.location = loc
    return o


def make_light(name, loc, rot_x, energy, link_col):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = LIGHT_SIZE
    ld.size_y = LIGHT_SIZE
    obj = bpy.data.objects.new(name, ld)
    obj.location = loc
    obj.rotation_euler = (rot_x, 0.0, 0.0)
    obj.scale = (LIGHT_SCALE, LIGHT_SCALE, LIGHT_SCALE)
    (link_col or bpy.context.scene.collection).objects.link(obj)
    return obj


def remove_drivers(obj, path):
    if obj.animation_data and obj.animation_data.drivers:
        for d in list(obj.animation_data.drivers):
            if d.data_path == path:
                obj.animation_data.drivers.remove(d)


def add_var_driver(obj, path, index, master, master_path, offset):
    """obj.<path>[index] = master.<master_path>[index] + offset (SINGLE_PROP)
    5.2: DriverTarget 无 array_index, data_path 带下标"""
    remove_drivers(obj, path)
    fcu = obj.driver_add(path, index)
    drv = fcu.driver
    drv.type = 'SCRIPTED'
    drv.expression = f'v + {offset!r}'
    v = drv.variables.new()
    v.name = 'v'
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'OBJECT'
    v.targets[0].id = master
    v.targets[0].data_path = f'{master_path}[{index}]'
    fcu.update()
    return fcu


def add_offset_props(light):
    for i, pn in enumerate(OFFSET_PROPS):
        light[pn] = 0.0
        try:
            ui = light.id_properties_ui(pn)
            ui.update(description=f'灯手动偏移({pn[-1]}): 在网格跟随位置上的附加偏移',
                      min=-OFFSET_LIMIT, max=OFFSET_LIMIT, soft_min=-2.0, soft_max=2.0,
                      step=1, precision=3)
        except Exception as e:
            print('UI_WARN', repr(e))


def process_collection(cn):
    col = bpy.data.collections.get(cn)
    movers = driven_meshes(cn)
    if not movers:
        print(f'{cn}: 无运动网格, SKIP')
        return
    center = center_of(movers)
    # 注意: 组轴心空物体创建后必须 update 再读 matrix_world,
    #       否则 matrix_parent_inverse 会设成单位矩阵导致灯偏移(实战坑)
    down_axis = ensure_empty(cn + DOWN_AXIS_SUFFIX, center, col)
    up_axis = ensure_empty(cn + UP_AXIS_SUFFIX, center, col)
    bpy.context.view_layer.update()

    for m in movers:
        # 命名: 主装置01 的 Rectangle066.001 向下灯特例叫「面光」
        dn = '面光' if m.name == 'Rectangle066.001' else DOWN_PREFIX + m.name
        un = dn + UP_SUFFIX

        # 1) 创建/获取 两个灯
        d_light = bpy.data.objects.get(dn)
        if d_light is None:
            d_light = make_light(dn, m.location.copy(), 0.0, DOWN_ENERGY, col)
        u_light = bpy.data.objects.get(un)
        if u_light is None:
            up_loc = m.location.copy()
            up_loc.z += UP_OFFSET_Z
            u_light = make_light(un, up_loc, math.pi, UP_ENERGY, col)

        # 2) 打组 parent 到轴心
        d_light.parent = down_axis
        d_light.matrix_parent_inverse = down_axis.matrix_world.inverted()
        u_light.parent = up_axis
        u_light.matrix_parent_inverse = up_axis.matrix_world.inverted()

        # 3) 偏移属性
        add_offset_props(d_light)
        add_offset_props(u_light)

        # 4) 位置跟随驱动(两灯都跟网格; 向上灯 z 额外 +0.001)
        for axis in range(3):
            add_var_driver(d_light, 'location', axis, m, 'location', 0.0)
            add_var_driver(u_light, 'location', axis, m, 'location',
                           UP_OFFSET_Z if axis == 2 else 0.0)

        # 5) 旋转绑定: 向上灯为主(自由), 向下灯跟随(差 pi)
        #    先清掉向上灯可能残留的旋转驱动, 让向上灯自由
        remove_drivers(u_light, 'rotation_euler')
        for axis in range(3):
            add_var_driver(d_light, 'rotation_euler', axis, u_light, 'rotation_euler',
                           -math.pi if axis == 0 else 0.0)

    bpy.context.view_layer.update()
    print(f'{cn}: 运动网格={len(movers)} 灯已建(向下+向上) 轴心@({center[0]:.2f},{center[1]:.2f},{center[2]:.2f})')


def main():
    # 注册命名空间函数
    bpy.app.driver_namespace['light_off'] = light_off
    for cn in TARGETS:
        process_collection(cn)
    bpy.context.view_layer.update()
    print('ALL_DONE')


main()
