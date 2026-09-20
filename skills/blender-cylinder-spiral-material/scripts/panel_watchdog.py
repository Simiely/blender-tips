# spiral_rise_panel.py —— 螺旋上升材质 · 参数面板 + 看门狗（自包含，供 Register 文本块使用）
#
# 部署：作为文本块放进 .blend，勾 Register(use_module=True)，并开启
#       偏好设置 → Save & Load → Auto Run Python Scripts，然后 Ctrl+S。
#       重开后本模块自动 register()，面板与看门狗一起恢复。
#
# 说明：本文件不 import 任何外部脚本 —— 文本块里必须自包含。
import bpy

CTRL_NAME = '螺旋上升控制'
MAT_NAMES = ['滚动效果网格体_螺旋上升']
PROPS = ['环绕圈数', '高度条纹', '条纹宽度', '上升速度', '发光强度']

_TICK = 0.25
_WATCH_LAST = {}


def _touch():
    """强制重算挂在材质/节点树上的驱动（ctl + mat + node_tree 三处都 tag）。"""
    c = bpy.data.objects.get(CTRL_NAME)
    if c:
        c.update_tag()
    for mn in MAT_NAMES:
        m = bpy.data.materials.get(mn)
        if m is None:
            continue
        m.update_tag()
        if m.use_nodes and m.node_tree:
            m.node_tree.update_tag()
    bpy.context.view_layer.update()


def _watch():
    """定时看门狗：只在该值真的变了才 tag ⇒ 无空转、无递归。"""
    try:
        c = bpy.data.objects.get(CTRL_NAME)
        if c is not None:
            dirty = False
            for k in PROPS:
                v = c.get(k)
                if _WATCH_LAST.get(k) != v:
                    _WATCH_LAST[k] = v
                    dirty = True
            if dirty:
                _touch()
    except Exception:
        pass
    return _TICK


class VIEW3D_PT_spiral_rise(bpy.types.Panel):
    bl_label = '螺旋上升材质'
    bl_idname = 'VIEW3D_PT_spiral_rise'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '螺旋上升'

    def draw(self, context):
        lay = self.layout
        c = bpy.data.objects.get(CTRL_NAME)
        if c is None:
            lay.label(text='未找到控制空物体:', icon='ERROR')
            lay.label(text=CTRL_NAME)
            return
        col = lay.column(align=True)
        for k in PROPS:
            col.prop(c, '["%s"]' % k, text=k)
        lay.separator()
        lay.label(text='环绕圈数/高度条纹 决定螺旋角度', icon='INFO')
        lay.label(text='上升速度 > 0 = 向上流动', icon='INFO')


def register():
    try:
        bpy.utils.unregister_class(VIEW3D_PT_spiral_rise)
    except Exception:
        pass
    bpy.utils.register_class(VIEW3D_PT_spiral_rise)

    # 去重：模块被重新加载时 _watch 会是【新的函数对象】，
    # 直接 unregister(_watch) 摘不掉上一代那个 ⇒ 必须把上一代存起来再摘。
    old = bpy.app.driver_namespace.get('_spiral_rise_watch')
    if old is not None:
        try:
            bpy.app.timers.unregister(old)
        except Exception:
            pass
    bpy.app.driver_namespace['_spiral_rise_watch'] = _watch
    bpy.app.timers.register(_watch, first_interval=0.5, persistent=True)
    print('[spiral_rise_panel] 面板 + 看门狗已注册')


def unregister():
    try:
        bpy.app.timers.unregister(_watch)
    except Exception:
        pass
    bpy.app.driver_namespace.pop('_spiral_rise_watch', None)
    try:
        bpy.utils.unregister_class(VIEW3D_PT_spiral_rise)
    except Exception:
        pass
