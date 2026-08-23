"""
材质参数实时控制器面板(可复用)
================================
给「控制空物体 + 自定义属性 + 材质节点驱动」这套体系加一个 3D 视口侧边栏面板,
拖动滑块时实时重算材质驱动(自动 update_tag 刷新)。

持久化:把本文件作为一个文本块放进 .blend 并勾选 **Register**(= use_module=True),
并开启 偏好设置 → Save & Load → Auto Run Python Scripts,
保存文件后,重启打开此文件即自动注册此面板,无需手动操作。
```
依照仓库命名规范(AGENTS.md §44):本脚本直接注册,不写 __main__ 守卫。
"""
import bpy

# ===== 可复用配置 =====
CTRL_NAME = "主装置_圆环控制"   # 控制空物体名
PROPS = [                       # (属性键, 显示名) —— 会在面板里按顺序显示成滑块
    ("speed",       "扩散速度"),
    ("density",     "环密度"),
    ("gain",        "发光强度"),
    ("solid",       "纯色亮度"),
    ("gradient_on", "渐变开关"),
]
PANEL_CATEGORY = "圆环控制"     # N 面板里的分类名


class RING_CTRL_PT_controls(bpy.types.Panel):
    bl_label = "材质参数实时控制器"
    bl_idname = "RING_CTRL_PT_controls"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = PANEL_CATEGORY
    _last = {}

    def draw(self, context):
        layout = self.layout
        ctl = bpy.data.objects.get(CTRL_NAME)
        if ctl is None:
            layout.label(text="未找到控制器 %s" % CTRL_NAME)
            return
        box = layout.box()
        box.label(text=CTRL_NAME, icon='SHADING_RENDERED')
        for key, label in PROPS:
            box.prop(ctl, '["%s"]' % key, text=label)
        # 检测到任一属性变化 → 强制刷新依赖图,让材质驱动实时重算
        changed = False
        for key, _ in PROPS:
            cur = ctl.get(key)
            if RING_CTRL_PT_controls._last.get(key) != cur:
                RING_CTRL_PT_controls._last[key] = cur
                changed = True
        if changed:
            ctl.update_tag()
            bpy.context.view_layer.update()


def register():
    if hasattr(bpy.types, 'RING_CTRL_PT_controls'):
        try:
            bpy.utils.unregister_class(RING_CTRL_PT_controls)
        except Exception:
            pass
    bpy.utils.register_class(RING_CTRL_PT_controls)


register()