# streak_panel.py —— 「滚筒斜纹」材质 · 参数面板 + 看门狗（自包含，供 Register 文本块使用）
#
# 部署：作为文本块放进 .blend，勾 Register(use_module=True)，并开启
#       偏好设置 → Save & Load → Auto Run Python Scripts，然后 Ctrl+S。
#       重开后本模块自动 register()，面板与看门狗一起恢复。
#
# 说明：本文件不 import 任何外部脚本 —— 文本块里必须自包含。
#       与 spiral_rise_panel 的类名、定时器键互不干扰，可同时在线。
import bpy
import math

CTRL_NAME = '竖条旋转控制'
MAT_NAMES = ['滚动效果网格体_滚筒斜纹_按角度']
PROPS = ['条纹数量', '斜角', '前缘宽度', '拖尾起点',
         '上升速度', '旋转速度', '发光强度']

CYL_RADIUS = 3.7789          # 本柱实测半径
CYL_HEIGHT = 13.6764         # 本柱实测高
# 与建脚本保持一致：N = K × (H/P) ÷ tan(θ)
H_OVER_P = CYL_HEIGHT / (2.0 * math.pi * CYL_RADIUS)

_TICK = 0.25
_WATCH_LAST = {}
_WATCH_KEY = '_streak_angle_watch'


def _touch():
    """强制重算挂在材质/节点树上的驱动（ctrl + mat + node_tree 三处都 tag）。"""
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


class VIEW3D_PT_streak_angle(bpy.types.Panel):
    bl_label = '滚筒斜纹 · 按角度'
    bl_idname = 'VIEW3D_PT_streak_angle'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '滚筒斜纹·角度'

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

        a, b = c.get('前缘宽度'), c.get('拖尾起点')
        kk, ang = c.get('条纹数量') or 0.0, c.get('斜角') or 0.0
        lay.separator()
        if a is not None and b is not None:
            if b <= a:
                lay.label(text='拖尾起点 应 > 前缘宽度', icon='ERROR')
            else:
                lay.label(text='亮区 %.0f%% → %.0f%%（拖尾 %.0f%%）'
                          % (a * 100, b * 100, (1 - b) * 100), icon='INFO')
        # 斜角是主控，高度周期数 N 由它实时反算 —— 两个信息都露在面板上
        if kk and ang:
            try:
                n_calc = kk * H_OVER_P / math.tan(math.radians(ang))
                lay.label(text='高度周期数 N ≈ %.2f   (K=%d × %.3f ÷ tan%.0f°)'
                          % (n_calc, round(kk), H_OVER_P, ang), icon='DRIVER')
            except Exception:
                pass
        lay.label(text='条纹数量 必须是整数', icon='INFO')
        lay.label(text='上升速度 > 0 = 右下→左上', icon='INFO')
        lay.label(text='颜色改「发光配色」节点色标', icon='COLOR')


def register():
    try:
        bpy.utils.unregister_class(VIEW3D_PT_streak_angle)
    except Exception:
        pass
    bpy.utils.register_class(VIEW3D_PT_streak_angle)

    # 去重：模块被重新加载时 _watch 会是【新的函数对象】，
    # 直接 unregister(_watch) 摘不掉上一代那个 ⇒ 必须把上一代存起来再摘。
    old = bpy.app.driver_namespace.get(_WATCH_KEY)
    if old is not None:
        try:
            bpy.app.timers.unregister(old)
        except Exception:
            pass
    bpy.app.driver_namespace[_WATCH_KEY] = _watch
    bpy.app.timers.register(_watch, first_interval=0.5, persistent=True)
    print('[streak_panel] 面板 + 看门狗已注册')


def unregister():
    try:
        bpy.app.timers.unregister(_watch)
    except Exception:
        pass
    bpy.app.driver_namespace.pop(_WATCH_KEY, None)
    try:
        bpy.utils.unregister_class(VIEW3D_PT_streak_angle)
    except Exception:
        pass
