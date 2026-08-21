# sky_driver.py —— 天空控制 自定义属性 驱动 天空纹理 太阳(命名空间函数版)
# 用途: 天空控制 的 太阳角度(sun_rotation) / 太阳高度(sun_elevation) 由命名空间函数
#       实时读取(度 -> rad), 避免 SINGLE_PROP 读自定义属性"脚本内改值不重算"的缓存坑
# 持久化: 文本块勾 Register(use_module=True) + 偏好设置开 Auto Run Python Scripts
#          -> 重开 .blend 自动执行注册, 驱动不报红
# 驱动挂法: 见 docs/天空太阳高度驱动.md(挂 node_tree.animation_data,
#           路径 nodes["天空纹理"].sun_rotation / sun_elevation)
import bpy, math


def _ctrl():
    return bpy.data.objects.get('天空控制')


def sky_sun_angle():
    ob = _ctrl()
    return math.radians(float(ob.get('太阳角度', 0.0))) if ob else 0.0


def sky_sun_elev():
    ob = _ctrl()
    return math.radians(float(ob.get('太阳高度', 0.0))) if ob else 0.0


bpy.app.driver_namespace['sky_sun_angle'] = sky_sun_angle
bpy.app.driver_namespace['sky_sun_elev'] = sky_sun_elev
print('[sky_driver] sky_sun_angle / sky_sun_elev 已注册')