import bpy

# =============================================================================
# spin_speed() —— 驱动命名空间函数,被每个目标的 Z 轴旋转驱动调用
# 实时读『旋转控制』空物体上的 旋转速度 自定义属性(单位:度/帧)
#
# 重开 .blend 后,本函数会丢失(它只活在进程内存,不随文件保存)→
# 把本文件作为文本块 spin_driver.py 在 Blender 里 Run Script 并勾 Register,
# 下次打开 .blend 即可自动重新注册(见 scripts/driver-spin/README.md)
# =============================================================================

def spin_speed():
    ctrl = bpy.data.objects.get('旋转控制')
    if ctrl is None:
        return 1.0
    return float(ctrl.get('旋转速度', 1.0))

# 注册进驱动命名空间(驱动表达式 spin_speed() 才能找到它)
bpy.app.driver_namespace['spin_speed'] = spin_speed
