# scroll_driver.py —— 渐变贴图滚动速度函数(命名空间函数, 供驱动实时读取)
# 用途: 渐变发光滚动材质的 Mapping Location Y 驱动 = fr * scroll_speed()
#       scroll_speed 实时读「贴图滚动控制」空物体的 滚动速度 属性
# 持久化: 勾 Register(use_module=True) + Auto Run Python Scripts
#          -> 重开 .blend 自动执行, 驱动不报红(实测: 重启后驱动全部自动恢复)
# 部署: 把本文件内容作为文本块放进 .blend, 勾 Register(use_module=True), Ctrl+S
import bpy

CTRL_NAME = '贴图滚动控制'
SPEED_PROP = '滚动速度'
SPEED_DEFAULT = 0.05


def scroll_speed():
    ctrl = bpy.data.objects.get(CTRL_NAME)
    if ctrl is None:
        return SPEED_DEFAULT
    return float(ctrl.get(SPEED_PROP, SPEED_DEFAULT))


bpy.app.driver_namespace['scroll_speed'] = scroll_speed
print('[scroll_driver] scroll_speed 已注册')
