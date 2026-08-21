import bpy

# =============================================================================
# restore_drivers.py —— 重开 .blend 后,一键恢复驱动依赖的命名空间函数
#
# 问题: Blender 5.2 重开文件时,文本块**不会**自动执行(use_register 已移除),
#       依赖 bob() / spin_speed() 的驱动会报红 / 失效(函数只活在进程内存),
#       求值失败 → Blender 返回 0 → 物体掉到 Z=0(错位)。
#
# 解决(两步,缺一不可):
#   1) 把列出的文本块重新 exec 一遍,重新注册到 driver_namespace;
#   2) **重新赋值驱动表达式(同值),强制驱动重新编译** —— 只恢复函数不够,
#      depsgraph 仍缓存旧失败状态(driver.is_valid=False, 物体停在 0),
#      必须重赋值表达式触发重算。
#
# 用法:
#   python send.py restore_drivers.py
#   或直接 Blender → Scripting → 文本编辑器 Run Script
#
# 自定义: 改下面的 TEXT_BLOCKS 列表,增删要恢复的文本块名(默认含 bob + spin)
# =============================================================================

TEXT_BLOCKS = ['bob_driver.py', 'spin_driver.py']

# 命名空间函数名 → 驱动表达式要重新赋值的映射
# 键是文本块名, 值是该文本块注册的函数名(表达式里调用它)
EXPR_MAP = {
    'bob_driver.py': 'bob',
    'spin_driver.py': 'spin_speed',
}


def restore(nm):
    t = bpy.data.texts.get(nm)
    if t is None:
        print('SKIP 文本块缺失:', nm)
        return False
    try:
        exec(t.as_string())
        print('OK 已恢复:', nm)
        return True
    except Exception as e:
        print('ERR', nm, repr(e))
        return False


def force_recompile():
    """对调用已恢复函数的所有驱动,重新赋值表达式(同值)强制重新编译。
    不做这一步,driver.is_valid 仍为 False,物体停在 0 位。"""
    n = 0
    for o in bpy.data.objects:
        if not o.animation_data or not o.animation_data.drivers:
            continue
        for fc in o.animation_data.drivers:
            d = fc.driver
            if d.type != 'SCRIPTED':
                continue
            for fn in EXPR_MAP.values():
                # 表达式里引用了该函数 → 重赋值同值表达式强制重算
                if fn in d.expression:
                    d.expression = d.expression
                    n += 1
                    break
    bpy.context.view_layer.update()
    print(f'OK 强制重编译驱动表达式 {n} 条')
    return n


def main():
    ok = []
    for nm in TEXT_BLOCKS:
        if restore(nm):
            ok.append(nm)

    # 校验命名空间里是否真的有对应函数
    missing = []
    for nm in TEXT_BLOCKS:
        fn = EXPR_MAP.get(nm)
        if fn and fn not in bpy.app.driver_namespace:
            missing.append(f'{nm}→{fn}')

    # 函数都齐了 → 强制驱动重新编译
    if not missing:
        force_recompile()

    print('NAMESPACE', {k: k in bpy.app.driver_namespace
                        for k in EXPR_MAP.values()})
    print('RESTORE_DONE' if not missing else f'RESTORE_INCOMPLETE 缺失={missing}')


if __name__ == '__main__':
    main()
