import bpy

# =============================================================================
# 通用构建器: 给指定空物体挂「Z 轴匀速旋转」驱动
# 一个控制面板(旋转控制)承载 旋转速度 滑块,所有目标共用;每个目标可独立设定方向
#
# 用法:
#   1) 先在 Blender 里运行 spin_driver.py(注册 spin_speed 函数,可勾 Register 持久化)
#   2) 改下面的 TARGETS 成你的目标对象名 + 方向(+1 正向 / -1 反向)
#   3) 在桥里运行本脚本:  python send.py build_spin_drivers.py
#      (也可直接在 Scripting 工作区 Run Script)
#
# 可重复运行(幂等): 已有 Z 旋转驱动的目标先移除再重建;基准角(0°)只在首次复位
# =============================================================================

DEG2RAD = 0.017453292519943295
CTRL_NAME = '旋转控制'
COL_NAME = '新对象'                # 控制面板挂载到的集合名(找不到则回退场景集合)
SPEED_DEFAULT = 1.0               # 默认 1 度/帧(30fps ≈ 30°/秒)
SPEED_MIN, SPEED_MAX = 0.0, 20.0

# ---------- 目标对象: (对象名, 方向)  +1=正向(逆时针) / -1=反向(顺时针) ----------
# 默认即本仓库实战场景(空物体.006_需要旋转 正向, 空物体.007_需要旋转 反向)
# 换成你自己的对象只需改这里;要更多目标直接加元组
TARGETS = [
    ('空物体.006_需要旋转', +1),
    ('空物体.007_需要旋转', -1),
]


def ensure_spin():
    """确保 spin_speed() 已注册进驱动命名空间;没有则尝试加载文本块 spin_driver.py"""
    if 'spin_speed' in bpy.app.driver_namespace:
        return True
    txt = bpy.data.texts.get('spin_driver.py')
    if txt:
        exec(txt.as_string())
        return 'spin_speed' in bpy.app.driver_namespace
    raise RuntimeError("spin_speed() 未注册: 请先运行 spin_driver.py")


def make_ctrl(name, link_col=None):
    """新建旋转控制面板空物体并写入 旋转速度 滑块"""
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, None)
        (link_col or bpy.context.scene.collection).objects.link(obj)
    obj['旋转速度'] = SPEED_DEFAULT
    try:
        ui = obj.id_properties_ui('旋转速度')
        ui.update(
            description='Z 轴匀速旋转速度(度/帧):所有目标共用,可在时间轴 scrub 实时看效果',
            min=SPEED_MIN, max=SPEED_MAX, soft_min=0.0, soft_max=10.0,
            step=10, precision=2,
        )
    except Exception as e:
        print('UI_WARN', repr(e))
    return obj


def has_zrot_driver(o):
    ad = o.animation_data
    if not ad or not ad.drivers:
        return False
    return any(d.data_path == 'rotation_euler' and d.array_index == 2 for d in ad.drivers)


def add_driver(o, sign):
    """给物体 Z 轴(rotation_euler[2])挂匀速旋转驱动;幂等(先移除旧 Z 驱动)"""
    o.rotation_mode = 'XYZ'
    # 先清掉已存在的 Z 旋转驱动,保证幂等重建
    if o.animation_data and o.animation_data.drivers:
        for d in list(o.animation_data.drivers):
            if d.data_path == 'rotation_euler' and d.array_index == 2:
                o.animation_data.drivers.remove(d)
    # 复位基准角为 0(该属性曾被驱动污染,显式重置;原始 Z 即 0°)
    o.rotation_euler.z = 0.0
    base_z = 0.0

    fcu = o.driver_add('rotation_euler', 2)
    d = fcu.driver
    d.type = 'SCRIPTED'
    # 角度 = 基准 + 帧 × 速度(度/帧) × 度转弧度 × 方向
    d.expression = f"{base_z:.6f} + fr * spin_speed() * {DEG2RAD!r} * {sign:+d}"

    # 变量 fr -> 当前帧(每帧变化,强制驱动重算)
    vf = d.variables.new()
    vf.name = 'fr'
    vf.type = 'SINGLE_PROP'
    vf.targets[0].id_type = 'SCENE'
    vf.targets[0].id = bpy.context.scene
    vf.targets[0].data_path = 'frame_current'
    print(f'DRIVER {o.name} dir={sign:+d} base_z={base_z:.4f} expr="{d.expression}"')


def main():
    ensure_spin()
    col = bpy.data.collections.get(COL_NAME)
    ctrl = make_ctrl(CTRL_NAME, link_col=col)
    n = 0
    for name, sign in TARGETS:
        o = bpy.data.objects.get(name)
        if o is None:
            print('SKIP_NOT_FOUND', name)
            continue
        add_driver(o, sign)
        n += 1
    print(f'ALL_DONE 已挂 Z 旋转驱动目标数={n}  控制面板={ctrl.name} 旋转速度={ctrl["旋转速度"]}')
    if n == 0:
        print('提示: TARGETS 里的对象名均未找到,请核对名称(可在 Outline 复制精确名)')


# 直接调用 main()(注意: 桥接环境 exec 时 __name__ 为 'builtins', 不能用 __main__ 守卫)
main()
