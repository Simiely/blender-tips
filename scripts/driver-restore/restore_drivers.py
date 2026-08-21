import bpy

# =============================================================================
# restore_drivers.py —— 重开 .blend 后,一键恢复驱动依赖的命名空间函数
#
# 问题: Blender 5.2 重开文件时,文本块**不会**自动执行(use_register 已移除),
#       依赖 bob() / spin_speed() 的驱动会报红 / 失效(函数只活在进程内存)。
#
# 解决: 运行本脚本,把列出的文本块重新 exec 一遍,重新注册到 driver_namespace。
#
# 用法:
#   python send.py restore_drivers.py
#   或直接 Blender → Scripting → 文本编辑器 Run Script
#
# 自定义: 改下面的 TEXT_BLOCKS 列表,增删要恢复的文本块名(默认含 bob + spin)
# =============================================================================

TEXT_BLOCKS = ['bob_driver.py', 'spin_driver.py']


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


def main():
    ok = []
    for nm in TEXT_BLOCKS:
        if restore(nm):
            ok.append(nm)

    # 校验命名空间里是否真的有对应函数
    checks = {
        'bob_driver.py': 'bob',
        'spin_driver.py': 'spin_speed',
    }
    missing = []
    for nm in TEXT_BLOCKS:
        fn = checks.get(nm)
        if fn and fn not in bpy.app.driver_namespace:
            missing.append(f'{nm}→{fn}')

    print('NAMESPACE', {k: k in bpy.app.driver_namespace
                        for k in ('bob', 'spin_speed')})
    print('RESTORE_DONE' if not missing else f'RESTORE_INCOMPLETE 缺失={missing}')


if __name__ == '__main__':
    main()
