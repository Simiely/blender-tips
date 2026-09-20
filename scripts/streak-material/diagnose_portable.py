# diagnose_portable.py —— 诊断「材质贴到别的对象/文件后不动」
#   用法：在【出问题的那个文件】里，把本脚本 send 进去或 Run Script
import bpy

KEY = '滚筒斜纹'          # 材质名关键字
print('=== ① 有哪些"滚筒斜纹"材质 ===')
mats = [m for m in bpy.data.materials if KEY in m.name]
if not mats:
    print('   一个都没有 —— 说明这个文件里根本没有这个材质')
for m in mats:
    print('   %s  (users=%d, use_nodes=%s)' % (m.name, m.users, m.use_nodes))

print()
print('=== ② 每个材质的「锚点」与「驱动」是否还有效 ===')
for m in mats:
    print('--- %s' % m.name)
    if not m.use_nodes:
        print('    ✗ use_nodes = False（节点被关掉了）'); continue
    nt = m.node_tree
    t = next((n for n in nt.nodes if n.type == 'TEX_COORD'), None)
    if t is None:
        print('    ✗ 没有「纹理坐标」节点')
    else:
        print('    %s 锚点 tex.object = %r'
              % ('✔' if t.object else '✗', t.object.name if t.object else None))
        if not t.object:
            print('       ⇒ 会退回【世界坐标】：条纹位置会变、且不跟随锚点')
    ad = nt.animation_data
    drs = ad.drivers if ad else []
    if not drs:
        print('    ✗ 一条驱动都没有 ⇒ 完全静态')
    bad = [d for d in drs if not d.driver.is_valid]
    print('    驱动 %d 条，其中无效 %d 条' % (len(drs), len(bad)))
    for d in drs:
        tag = '✔' if d.driver.is_valid else '✗'
        print('      %s %-46s = %s' % (tag, d.data_path[:46], d.driver.expression))
        if not d.driver.is_valid:
            for v in d.driver.variables:
                for tg in v.targets:
                    nm = getattr(tg.id, 'name', None)
                    print('           变量 %-5s → %s %r  %s'
                          % (v.name, tg.id_type, nm, '（ID 已丢失！）' if tg.id is None else ''))

print()
print('=== ③ 哪些对象在用这些材质 ===')
found = False
for ob in bpy.data.objects:
    if not hasattr(ob, 'material_slots'):
        continue
    hit = [s.material.name for s in ob.material_slots if s.material and KEY in s.material.name]
    if hit:
        found = True
        print('   %-30s 槽=%s 集合=%s 场景=%s'
              % (ob.name, hit, [c.name for c in ob.users_collection],
                 [s.name for s in bpy.data.scenes if ob.name in s.objects]))
if not found:
    print('   没有对象在用（材质只在数据块里挂着）')

print()
print('=== ④ 修复提示 ===')
print('   若 ② 里出现 ✗：')
print('     · 锚点丢了 ⇒ 需要在本文件里有一个空物体当锚点，并把 tex.object 指回去')
print('     · 驱动无效 ⇒ 驱动变量指向的 ID 不在了，需要重指向本文件的锚点/场景')
print('     · 最省事：把原文件里的「竖条旋转控制」空物体一起复制过来（一次），再跑修复')
print('DIAG_OK')
