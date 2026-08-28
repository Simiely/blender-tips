# ============================================================
# 金纸礼花系统 - 一键创建
# 用法: python send.py build_firework.py
# 依赖: 场景中需有 "发射点，方向Z向_01" 等空对象
# ============================================================
import bpy
from mathutils import Vector

# ===== 可调参数 =====
START_FRAME = 601
END_FRAME = 826
PARTICLE_COUNT = 4000
LIFETIME = 120
LIFETIME_RANDOM = 0.3
NORMAL_FACTOR = 24.0
FACTOR_RANDOM = 0.8
TANGENT_FACTOR = 1.0
GRAVITY = 0.8
BROWNIAN_FACTOR = 6.0
DRAG_FACTOR = 0.3
ANGULAR_VELOCITY = 6.0
PARTICLE_SIZE = 1.5
SIZE_RANDOM = 1.2

TURB_STRENGTH = 15.0
TURB_SIZE = 3.0

KILL_PLANE_SIZE = 6.0
EMITTER_PLANE_SIZE = 0.5

# ===== 纸片形状定义 =====
# (name, primitive, scale_xyz, bend_angle)
SHAPES = [
    ("sq_flat", 'cube', (0.15, 0.12, 0.02), 0.0),
    ("sq_bend", 'cube', (0.15, 0.12, 0.02), 0.4),
    ("sq_bend2", 'cube', (0.15, 0.12, 0.02), -0.3),
    ("rect_flat", 'cube', (0.25, 0.06, 0.02), 0.0),
    ("rect_bend", 'cube', (0.25, 0.06, 0.02), 0.6),
    ("rect_bend2", 'cube', (0.25, 0.06, 0.02), -0.5),
    ("circle", 'cylinder', (0.08, 0.08, 0.015), 0.3),
    ("circle2", 'cylinder', (0.08, 0.08, 0.015), -0.25),
    ("wide_flat", 'cube', (0.12, 0.18, 0.02), 0.0),
    ("wide_bend", 'cube', (0.12, 0.18, 0.02), 0.35),
    ("thin_bend", 'cube', (0.3, 0.04, 0.015), 0.7),
    ("thin_bend2", 'cube', (0.3, 0.04, 0.015), -0.6),
    ("tri", 'cylinder3', (0.08, 0.08, 0.015), 0.2),
    ("tri2", 'cylinder3', (0.08, 0.08, 0.015), -0.3),
]

# ===== 工具函数 =====

def make_bent_shape(name, primitive, scale_xyz, bend_angle):
    bpy.ops.object.select_all(action='DESELECT')
    if primitive == 'cube':
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0,0,0))
    elif primitive == 'cylinder':
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.5, depth=1.0, location=(0,0,0))
    elif primitive == 'cylinder3':
        bpy.ops.mesh.primitive_cylinder_add(vertices=3, radius=0.5, depth=1.0, location=(0,0,0))
    obj = bpy.context.object
    obj.scale = scale_xyz
    bpy.ops.object.transform_apply(scale=True)
    obj.name = name
    obj.hide_viewport = False
    obj.hide_render = False
    if abs(bend_angle) > 0.01:
        mod = obj.modifiers.new(name="Bend", type='SIMPLE_DEFORM')
        mod.deform_method = 'BEND'
        mod.deform_axis = 'X'
        mod.angle = bend_angle
    return obj


def clean_objects(prefix):
    for o in list(bpy.data.objects):
        if o.name.startswith(prefix):
            bpy.data.objects.remove(o, do_unlink=True)


def clean_materials(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)


def clean_collections(name):
    c = bpy.data.collections.get(name)
    if c:
        bpy.data.collections.remove(c)


# ===== 主函数 =====

def build_firework(prefix, launch_empty_name, z_up=True, seed_offset=0):
    """为一个发射点创建礼花系统"""
    launch = bpy.data.objects.get(launch_empty_name)
    if not launch:
        print(f"未找到 {launch_empty_name}，跳过")
        return

    launch_pos = launch.location.copy()
    launch_rot = launch.rotation_euler.copy()
    kill_empty = bpy.data.objects.get("杀死粒子")

    # 清理旧对象
    clean_objects(prefix)
    clean_materials(f"{prefix}_gold_mat")
    clean_collections(f"{prefix}_col")

    # 1. 金色材质
    gold_mat = bpy.data.materials.new(f"{prefix}_gold_mat")
    gold_mat.use_nodes = True
    gold_mat.node_tree.nodes.clear()
    ge = gold_mat.node_tree.nodes.new('ShaderNodeEmission')
    ge.inputs['Strength'].default_value = 20.0
    ge.inputs['Color'].default_value = (1.0, 0.8, 0.1, 1.0)
    go = gold_mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    gold_mat.node_tree.links.new(ge.outputs['Emission'], go.inputs['Surface'])

    # 2. 纸片形状
    bpy.ops.collection.create(name=f"{prefix}_col")
    col = bpy.data.collections[f"{prefix}_col"]
    for name, prim, scale, bend in SHAPES:
        obj = make_bent_shape(f"{prefix}_{name}", prim, scale, bend)
        obj.data.materials.append(gold_mat)
        col.objects.link(obj)

    bpy.ops.object.select_all(action='DESELECT')

    # 3. 发射器
    bpy.ops.mesh.primitive_plane_add(size=EMITTER_PLANE_SIZE, location=launch_pos)
    emitter = bpy.context.object
    emitter.name = f"{prefix}_emitter"
    emitter.rotation_euler = (0, 0, 0) if z_up else launch_rot
    emitter.hide_viewport = False
    emitter.hide_render = False

    # 4. 粒子系统
    emitter.select_set(True)
    bpy.context.view_layer.objects.active = emitter
    bpy.ops.object.particle_system_add()
    ps = emitter.modifiers[-1].particle_system
    pset = ps.settings
    pset.name = f"{prefix}_settings"

    pset.type = 'EMITTER'
    pset.count = PARTICLE_COUNT
    pset.frame_start = START_FRAME
    pset.frame_end = END_FRAME
    pset.lifetime = LIFETIME
    pset.lifetime_random = LIFETIME_RANDOM
    pset.emit_from = 'FACE'
    pset.normal_factor = NORMAL_FACTOR
    pset.factor_random = FACTOR_RANDOM
    pset.tangent_factor = TANGENT_FACTOR
    pset.physics_type = 'NEWTON'
    pset.effector_weights.gravity = GRAVITY
    pset.brownian_factor = BROWNIAN_FACTOR
    pset.drag_factor = DRAG_FACTOR
    pset.rotation_mode = 'NOR'
    pset.angular_velocity_factor = ANGULAR_VELOCITY
    pset.render_type = 'COLLECTION'
    pset.instance_collection = col
    pset.particle_size = PARTICLE_SIZE
    pset.size_random = SIZE_RANDOM
    pset.display_percentage = 100
    pset.display_size = 1.0

    # 5. 湍流场
    bpy.ops.object.effector_add(type='TURBULENCE', location=launch_pos)
    turb = bpy.context.object
    turb.name = f"{prefix}_turbulence"
    turb.rotation_euler = (0, 0, 0)
    turb.field.strength = TURB_STRENGTH
    turb.field.size = TURB_SIZE
    turb.field.seed = 42 + seed_offset

    # 6. 杀死平面
    if kill_empty:
        bpy.ops.mesh.primitive_plane_add(size=KILL_PLANE_SIZE, location=kill_empty.location)
        kill = bpy.context.object
        kill.name = f"{prefix}_kill_plane"
        kill.rotation_euler = (0, 0, 0)
        kill.hide_viewport = False
        kill.hide_render = True
        mod = kill.modifiers.new(name="Collision", type='COLLISION')
        col_set = mod.settings
        col_set.use_particle_kill = True
        col_set.permeability = 0.0
        col_set.damping = 1.0
        col_set.stickiness = 0.0
        col_set.thickness_outer = 0.0

    bpy.ops.object.select_all(action='DESELECT')
    print(f"{prefix} 创建完成 @ ({launch_pos.x:.1f}, {launch_pos.y:.1f}, {launch_pos.z:.1f})")


# ===== 执行 =====

def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'

    # 合成器 Bloom
    if not scene.use_nodes or not scene.compositing_node_group:
        scene.use_nodes = True
        if scene.compositing_node_group is None:
            ng = bpy.data.node_groups.new("CompositingNodeTree", type='CompositorNodeTree')
            scene.compositing_node_group = ng
        tree = scene.compositing_node_group
        nodes = tree.nodes
        links = tree.links
        nodes.clear()
        rl = nodes.new('CompositorNodeRLayers')
        glare = nodes.new('CompositorNodeGlare')
        glare.location = (300, 0)
        glare.inputs['Type'].default_value = 'Bloom'
        glare.inputs['Quality'].default_value = 'High'
        glare.inputs['Threshold'].default_value = 0.15
        glare.inputs['Strength'].default_value = 4.0
        glare.inputs['Size'].default_value = 12
        display = nodes.new('CompositorNodeConvertToDisplay')
        display.location = (600, 0)
        links.new(rl.outputs['Image'], glare.inputs['Image'])
        links.new(glare.outputs['Image'], display.inputs['Image'])
    scene.render.use_compositing = True

    # 切换到 Rendered 视口
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'RENDERED'


# --- 入口 ---
setup_scene()

# 自动检测所有发射点
launch_points = []
for o in bpy.data.objects:
    if o.type == 'EMPTY' and "发射点，方向Z向" in o.name:
        launch_points.append(o)

if not launch_points:
    print("未找到任何发射点空对象！请先创建命名如 '发射点，方向Z向_01' 的空对象")
else:
    # 按名称排序
    launch_points.sort(key=lambda x: x.name)
    for i, lp in enumerate(launch_points):
        prefix = f"礼花_{i+1:02d}"
        build_firework(prefix, lp.name, z_up=True, seed_offset=i)

    print(f"\n完成！共创建 {len(launch_points)} 个礼花系统")
    print(f"帧范围: {START_FRAME} - {END_FRAME}")
    print(f"粒子数/个: {PARTICLE_COUNT}  法向速度: {NORMAL_FACTOR}")