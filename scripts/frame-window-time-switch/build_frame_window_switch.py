"""
帧窗口驱动: 给目标 Value 节点挂按帧区间开关的 SCRIPTED 驱动 (可复用)
==================================================================
场景: 让材质某个节点参数(如渐变开关)在特定帧区间=1、其余帧=0。
用法:
    python send.py build_frame_window_switch.py      # 经 socket 桥远程执行
    (或在 Blender Scripting 工作区 Run Script)

功能:
1. 注册命名空间函数 grad_window(fr) 并按档位参数生成源码, 写入 Register 文本块
   grad_window_driver.py(use_module=True -> 重启自动注册, 驱动不报红);
2. 清掉该节点无效的 Slotted-Action 关键帧, 改挂 SCRIPTED 驱动 grad_window(fr),
   fr 读 scene.frame_current; 强制重编译驱动;
3. 用 depsgraph 评估值逐帧验证(不读原始 socket)。

注意: 本脚本按仓库规范不写 __main__ 守卫(桥 exec 时 __name__ 是 builtins)。
"""
import bpy

# ===== 可复用配置 =====
MAT_NAMES = [
    "发光材质_005_需要做圆形扩展灯效果",
    "发光灯_需要做圆形扩展灯效果",
]
NODE_NAME = "主装置_渐变开关"   # 要驱动的 Value 节点名
FUNC_NAME = "grad_window"       # 命名空间函数名
FN_TEXT   = "grad_window_driver.py"   # 持久化 Register 文本块名
WINDOW    = (517, 657)          # 开(=1)的帧区间, 闭区间; 区间外=0

FCN = 'default_value'


def make_src(lo, hi):
    return (
        "import bpy\n"
        "def %s(fr):\n"
        "    return 1.0 if %r <= fr <= %r else 0.0\n"
        "bpy.app.driver_namespace['%s'] = %s\n"
    ) % (FUNC_NAME, float(lo), float(hi), FUNC_NAME, FUNC_NAME)


def register_func():
    src = make_src(*WINDOW)
    if FN_TEXT in bpy.data.texts:
        bpy.data.texts.remove(bpy.data.texts[FN_TEXT])
    tb = bpy.data.texts.new(FN_TEXT)
    tb.write(src)
    tb.use_module = True
    exec(src, {'__name__': FN_TEXT[:-3]})
    print('已注册并持久化 %s()' % FUNC_NAME)
    return tb


def drive_node(mat):
    m = bpy.data.materials.get(mat)
    if m is None or m.node_tree is None:
        print('  跳过(无材质/节点树):', mat); return
    n = m.node_tree.nodes.get(NODE_NAME)
    if n is None or n.type != 'VALUE':
        print('  跳过(找不到 Value 节点 %s):' % NODE_NAME, mat); return
    sock = n.outputs[0]
    # 清掉无效的 Slotted-Action 关键帧(action.fcurves 在 5.2 已移除)
    try:
        if m.node_tree.animation_data and m.node_tree.animation_data.action:
            m.node_tree.animation_data.action = None
    except Exception:
        pass
    try:
        sock.driver_remove(FCN)
    except Exception:
        pass
    fc = sock.driver_add(FCN)
    d = fc.driver
    d.type = 'SCRIPTED'
    for v in list(d.variables):
        d.variables.remove(v)
    v = d.variables.new(); v.name = 'fr'; v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'SCENE'
    v.targets[0].id = bpy.context.scene
    v.targets[0].data_path = 'frame_current'
    d.expression = '%s(fr)' % FUNC_NAME
    d.expression = d.expression  # 强制重编译(避免 depsgraph 缓存旧闭包)
    print('已挂驱动:', mat, '->', d.expression)


def verify(mat):
    m = bpy.data.materials.get(mat)
    if m is None or getattr(m, 'node_tree', None) is None:
        return
    deps = bpy.context.evaluated_depsgraph_get()
    lo, hi = WINDOW
    markers = [0, lo - 1, lo, lo + 1, hi - 1, hi, hi + 1]
    row = []
    for fr in sorted(set(max(0, x) for x in markers)):
        bpy.context.scene.frame_set(fr)
        deps.update()
        emat = deps.id_eval_get(m)
        val = emat.node_tree.nodes[NODE_NAME].outputs[0].default_value
        row.append('@%d=%.1f' % (fr, val))
    print('%-28s %s' % (mat, ' | '.join(row)))


def main():
    register_func()
    for mn in MAT_NAMES:
        drive_node(mn)
    bpy.context.view_layer.update()
    print('== 验证(评估值): 区间 [%d, %d] 内=1, 外=0 ==' % WINDOW)
    for mn in MAT_NAMES:
        verify(mn)


main()