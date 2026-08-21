import bpy

# =============================================================================
# make_independent.py —— 把集合内对象的「共享数据块」转成每个对象独立
#
# 场景: 从外部导入/复制出来的对象, 往往是链接复制(linked duplicate):
#       多个对象共用同一个网格数据块 → 复制出去后改一个, 其它全跟着变。
#       本脚本把集合内每个对象的网格数据(可选: 材质)复制成独立副本,
#       让每个对象都持有自己的数据块, 复制/导出/编辑不再互相影响。
#
# 用法:
#   1) 改 COLLECTION 为目标集合名
#   2) 在桥里运行:  python send.py make_independent.py
#      (或直接在 Scripting 工作区 Run Script)
#
# 幂等: 已独立的数据块 users==1 会跳过, 可反复运行
# 注意: 桥接环境 exec 时 __name__ 为 'builtins', 不要用 __main__ 守卫
# =============================================================================

COLLECTION = '补充'                 # 目标集合名
MAKE_MATERIAL_UNIQUE = False        # 是否也把材质复制成独立副本(默认只处理网格)
VERBOSE = True


def main():
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        print(f'ERR 集合不存在: {COLLECTION}')
        return

    meshes = [o for o in col.objects if o.type == 'MESH']
    mesh_before = len(set(id(o.data) for o in meshes))
    mat_before = len(set(id(m) for o in meshes for m in o.data.materials if m))

    mesh_copied = 0
    mat_copied = 0
    for o in meshes:
        # 网格数据独立化: 只处理被多个对象共享的数据块
        if o.data.users > 1:
            old_name = o.data.name
            o.data = o.data.copy()
            if VERBOSE:
                print(f'  MESH 独立: {o.name}  {old_name} -> {o.data.name}')
            mesh_copied += 1

        # 材质独立化(可选)
        if MAKE_MATERIAL_UNIQUE:
            for i, m in enumerate(o.data.materials):
                if m and m.users > 1:
                    old = m.name
                    o.data.materials[i] = m.copy()
                    if VERBOSE:
                        print(f'    MAT 独立: {o.name}[{i}] {old} -> {o.data.materials[i].name}')
                    mat_copied += 1

    mesh_after = len(set(id(o.data) for o in meshes))
    mat_after = len(set(id(m) for o in meshes for m in o.data.materials if m))

    print(f'ALL_DONE 集合={COLLECTION} 网格对象={len(meshes)}')
    print(f'  网格数据块: {mesh_before} -> {mesh_after}  (独立化 {mesh_copied} 个)')
    print(f'  材质数据块: {mat_before} -> {mat_after}  (独立化 {mat_copied} 个)')
    if mesh_before == mesh_after and mesh_copied == 0 and mat_copied == 0:
        print('提示: 集合内对象的数据块本来就全部独立, 无需处理')
    print('DONE_OK')


main()
