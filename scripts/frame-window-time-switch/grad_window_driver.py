"""
帧窗口时间开关函数(Register 文本块载荷, 由 build 脚本生成并写入 .blend)
===================================================================
作为文本块存进 .blend 并勾选 Register(use_module=True) + 偏好设置开
Auto Run Python Scripts -> 重启打开文件自动注册, 驱动不报红。

build_frame_window_switch.py 会根据 WINDOW 常量重新生成此函数源码再写入。
"""
import bpy

def grad_window(fr):
    """帧 517~657(闭区间)内返回 1, 其余返回 0 —— 渐变时间开关。"""
    return 1.0 if 517.0 <= fr <= 657.0 else 0.0

bpy.app.driver_namespace['grad_window'] = grad_window