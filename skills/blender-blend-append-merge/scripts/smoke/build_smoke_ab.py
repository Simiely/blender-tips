# -*- coding: utf-8 -*-
"""构建 A/B 两个合成场景，逐条覆盖 append 时可能出问题的语义：
   集合同名 / 对象同名 / 材质同名(内容相同) / 修改器依赖 NodeGroup /
   多实例 mesh / 父级链 / EMPTY / 打包贴图 / 世界同名(内容不同) / 相机同名。
   SMK_TAG=A|B
"""
import bpy, os

TAG = os.environ.get("SMK_TAG", "A")
WORK = os.environ.get("AMB_WORK", os.getcwd())   # 报告/基线/日志都写这里
os.makedirs(WORK, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ---------- 世界（A 3 节点 / B 2 节点，内容不同） ----------
world = bpy.data.worlds.new("World")
sc.world = world
world.use_nodes = True
nt = world.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
bg = nt.nodes.new("ShaderNodeBackground")
out = nt.nodes.new("ShaderNodeOutputWorld")
bg.inputs["Color"].default_value = (0.05, 0.05, 0.05, 1.0)
bg.inputs["Strength"].default_value = (1.0 if TAG == "A" else 2.5)
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
if TAG == "A":
    lp = nt.nodes.new("ShaderNodeLightPath")
    lp.location = (0, -300)
    nt.links.new(lp.outputs["Is Camera Ray"], bg.inputs["Strength"])

# ---------- 集合结构（刻意与真实文件对齐） ----------
root = bpy.data.collections.new("SKP Imported Data")
sc.collection.children.link(root)
mesh_c = bpy.data.collections.new("SKP Mesh Objects")
root.children.link(mesh_c)
cam_c = bpy.data.collections.new("SKP Scenes (as Cameras)")
root.children.link(cam_c)
exp = bpy.data.collections.new("Export")
sc.collection.children.link(exp)
if TAG == "A":
    jic = bpy.data.collections.new("相机")          # 只有 A 有
    sc.collection.children.link(jic)


def link(name, coll):
    o = bpy.data.objects.new(name, None)
    coll.objects.link(o)
    return o


def mk_mesh(name, coll, ngon=3, z=0.0):
    me = bpy.data.meshes.new(name)
    verts = [(0 + i, 0, z) for i in range(ngon)]
    me.from_pydata(verts, [], [tuple(range(ngon))])
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def mk_cam(name, coll):
    c = bpy.data.cameras.new(name)
    o = bpy.data.objects.new(name, c)
    coll.objects.link(o)
    return o


def attach_smooth(o, ng):
    m = o.modifiers.new("Smooth by Angle", "NODES")
    m.node_group = ng
    return m


# ---------- 材质 ----------
m_shared = bpy.data.materials.new("M_shared")          # 两边同名 + 内容完全一致
m_shared.use_nodes = True
bsdf = m_shared.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.2, 0.4, 0.6, 1.0)

if TAG == "A":
    m_onlya = bpy.data.materials.new("M_onlyA")
    m_onlya.use_nodes = True

    a1 = mk_mesh("G-物体", mesh_c, 3, 0.0)
    a1.data.materials.append(m_shared)
    a2 = mk_mesh("G-Obj3d66-257262", mesh_c, 4, 1.0)
    a2.data.materials.append(m_onlya)
    root_empty = link("G-空A", root)
    a3 = mk_mesh("Obj_A_only", mesh_c, 5, 2.0)
    a3.parent = root_empty
    a3.matrix_parent_inverse = root_empty.matrix_world.inverted()
    a3.matrix_world.translation = (3.0, 4.0, 5.0)
    a3.data.materials.append(m_shared)
    mk_cam("Cam: 场景号1", cam_c)
    mk_cam("Cam_A_only", jic)

else:
    # NodeGroup 依赖（模拟 Smooth by Angle）
    ng = bpy.data.node_groups.new("Smooth by Angle", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gin = ng.nodes.new("NodeGroupInput")
    gout = ng.nodes.new("NodeGroupOutput")
    ng.links.new(gin.outputs["Geometry"], gout.inputs["Geometry"])

    # 打包贴图 + 引用它的材质
    img = bpy.data.images.new("texB", 4, 4, alpha=False)
    img.pixels = [0.5, 0.2, 0.8, 1.0] * 16
    img.filepath_raw = os.path.join(WORK, "texB.png")
    img.file_format = "PNG"
    img.save()
    img.pack()
    m_texb = bpy.data.materials.new("M_texB")
    m_texb.use_nodes = True
    tn = m_texb.node_tree.nodes.new("ShaderNodeTexImage")
    tn.image = img
    m_texb.node_tree.links.new(tn.outputs["Color"],
                               m_texb.node_tree.nodes["Principled BSDF"].inputs["Base Color"])

    b1 = mk_mesh("G-物体", mesh_c, 3, 0.0)
    b1.data.materials.append(m_shared)
    attach_smooth(b1, ng)

    b2 = mk_mesh("G-Obj3d66-257262", mesh_c, 4, 1.0)
    b2.data.materials.append(m_texb)
    attach_smooth(b2, ng)

    # 三个对象共用一份 mesh（多实例）
    shared_me = bpy.data.meshes.new("G-共享源")
    shared_me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    shared_me.materials.append(m_texb)
    for i in range(3):
        o = bpy.data.objects.new("G-共享%02d" % (i + 1), shared_me)
        mesh_c.objects.link(o)
        o.location = (i * 2.0, 0, 0)
        attach_smooth(o, ng)

    be = link("G-空B", mesh_c)
    bc = mk_mesh("G-子01", mesh_c, 6, 3.0)
    bc.parent = be
    bc.matrix_parent_inverse = be.matrix_world.inverted()
    bc.matrix_world.translation = (-7.0, 8.0, 9.0)
    bc.data.materials.append(m_texb)
    attach_smooth(bc, ng)

    mk_cam("Cam: 场景号1", cam_c)

sc.render.fps = 30 if TAG == "A" else 24
sc.render.filepath = "//" + TAG + "_out/"
sc.frame_start, sc.frame_end = ((1, 3000) if TAG == "A" else (1, 250))

outp = os.path.join(WORK, "smoke_%s.blend" % TAG)
bpy.ops.wm.save_as_mainfile(filepath=outp)

D = bpy.data
print("=== SMOKE_%s 已建 ===" % TAG)
print("objects=%d meshes=%d mats=%d imgs=%d colls=%d worlds=%d ngroup=%d cams=%d"
      % (len(D.objects), len(D.meshes), len(D.materials), len(D.images),
         len(D.collections), len(D.worlds), len(D.node_groups), len(D.cameras)))
print("OBJ:", sorted(o.name for o in D.objects))
print("COL:", sorted(c.name for c in D.collections))
print("MAT:", sorted(m.name for m in D.materials))
print("NG:", sorted(g.name for g in D.node_groups))
print("IMG:", sorted((i.name, i.packed_file is not None) for i in D.images))
print("SAVED:", outp)
