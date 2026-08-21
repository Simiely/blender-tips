# light_driver.py —— 灯偏移函数(命名空间函数, 供驱动实时读取)
# 用途: 灯光方案的灯挂驱动 location = 网格位置 + light_off(self, 轴)
#       light_off 实时读灯自身的 偏移X/Y/Z 属性, 避免 SINGLE_PROP 缓存
# 持久化: 勾 Register(use_module=True) + Auto Run Python Scripts
#          -> 重开 .blend 自动执行, 驱动不报红(实测: 重启后驱动全部自动恢复)
# 部署: 把本文件内容作为文本块放进 .blend, 勾 Register(use_module=True), Ctrl+S
import bpy

OFFSET_PROPS = ['偏移X', '偏移Y', '偏移Z']


def light_off(obj, axis):
    """实时读灯的偏移属性(命名空间函数, 避免 SINGLE_PROP 缓存)"""
    if obj is None:
        return 0.0
    return float(obj.get(OFFSET_PROPS[axis], 0.0))


bpy.app.driver_namespace['light_off'] = light_off
print('[light_driver] light_off 已注册')
