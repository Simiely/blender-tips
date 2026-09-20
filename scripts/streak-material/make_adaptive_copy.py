# make_adaptive_copy.py —— 让「滚筒斜纹」材质在小对象上也能看出条纹与动态
#
# 问题：原材质的柱面坐标用【世界空间】(纹理坐标.Object → 锚点空物体)。
#      贴到尺寸远小于条纹周期的对象上（如 scale=0.01 的小球）时，
#      整个对象落在同一个条纹里 ⇒ 纯色、看不出动。
# 正解：复制一份材质，把「纹理坐标.Object」【清空】——
#      此时 Object 输出 = 对象【自身】的局部坐标 ⇒ 条纹尺度自动适配每个对象，
#      且每个对象各自有一套完整的柱面坐标（各自成"一根小柱子"）。
#      驱动仍共享锚点，所以参数（速度/形状/强度）统一可控。
#
# 用法：跑本脚本 → 把那些小对象的材质槽换成生成的 `..._自适应` 版本。
import bpy

SRC = '滚动效果网格体_滚筒斜纹_按条数'
DST = SRC + '_自适应'

src = bpy.data.materials.get(SRC)
if src is None:
    print('✗ 找不到源材质', SRC); raise SystemExit(1)

dst = bpy.data.materials.get(DST)
if dst is None:
    dst = src.copy()
    dst.name = DST
    print('✔ 已复制材质 →', DST)
else:
    print('· 材质已存在，复用', DST)

nt = dst.node_tree
t = next((n for n in nt.nodes if n.type == 'TEX_COORD'), None)
if t is None:
    print('✗ 副本缺「纹理坐标」节点'); raise SystemExit(1)
t.object = None                      # ★ 关键：清空 ⇒ 用对象自身坐标
print('✔ tex.object 已清空 ⇒ 使用对象自身坐标（尺度自适应）')

# 统计：哪些对象在用源材质
users = [ob for ob in bpy.data.objects
         if ob.type == 'MESH' and ob.material_slots
         and any(s.material and s.material.name == SRC for s in ob.material_slots)]
print()
print('当前用源材质的对象：%d 个' % len(users))
print('  想把它们切成自适应版？跑下一行（按需取消注释）：')
print('    # for ob in users: 把槽里的 SRC 换成 DST')
print()
print('  ⚠️ 但那根真正的柱子（滚动效果网格体）应【保持原样】—— 它就该用世界坐标锚点。')
print('     建议只对"小尺寸 / 远离锚点"的对象换。')
print()
print('提示：换槽可以用——')
print('  for ob in [选择的对象]:')
print('      for s in ob.material_slots:')
print('          if s.material and s.material.name == %r: s.material = bpy.data.materials[%r]' % (SRC, DST))
print('ADAPT_OK')
