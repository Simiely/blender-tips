# -*- coding: utf-8 -*-
"""
分体翻页牌 —— 批量挂中缝轴 + 斜向波浪相位(主脚本)

在 Blender 内运行(Scripting 工作区 Run Script,或经 9877 桥 send.py 发送)。

做的事:
  1. 按尺寸识别卡片 → 每张卡建一个根级 Empty 当中缝轴(放在卡的几何中心)
  2. 单重补偿挂接(世界位置严格不变)+ 改前快照 / 改后核验
  3. 按「列 + 行」写斜向波浪相位到轴的自定义属性
  4. 装 SCRIPTED 驱动(受信任重开时自动接管)+ 注册 frame_change 处理器(免信任实时生效)
  5. 结束时核验:卡片姿态是否仍竖直轴对齐

可调参数见下方 CONFIG。
"""
import bpy
import math
from mathutils import Vector, Matrix

# ---------------- CONFIG ----------------
CARD_DIMS = (0.01, 0.08, 0.12)   # 卡片尺寸(排序后的 厚/宽/高),用于识别
DIM_TOL = (0.006, 0.012, 0.012)  # 各维容差
TURNS = 3          # 转几圈(整数圈才会回到初始朝向;1 圈=停在背面,字看不见)
DUR = 16           # 单次翻页时长(帧)
PERIOD = 60        # 每张卡多久翻一次(帧)
STEP = 2           # 波浪步长(帧/列)
WRAP = 8           # 相位取模周期(列);同一对角线的卡同时翻
AXIS = 1           # 旋转轴索引: 根级无旋转 ⇒ 1 == 世界 Y(沿牌宽)
PIVOT_COLL = "FLIP_pivots"
# ----------------------------------------

scene = bpy.context.scene
vl = bpy.context.view_layer


def is_card(o):
    d = sorted(round(v, 3) for v in o.dimensions)
    return all(abs(d[i] - CARD_DIMS[i]) < DIM_TOL[i] for i in range(3))


def center_of(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector((sum(c.x for c in cs) / 8, sum(c.y for c in cs) / 8, sum(c.z for c in cs) / 8))


def bbox_min(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (round(min(c.x for c in cs), 4), round(min(c.y for c in cs), 4), round(min(c.z for c in cs), 4))


# ---- 1. 收集卡片 + 改前快照 ----
cards = [o for o in bpy.data.objects if o.type == 'MESH' and is_card(o)]
print("[1] 识别卡片:", len(cards))
snap = {o.name: bbox_min(o) for o in cards}

# ---- 2. 行/列 → 相位 ----
info = [(o, center_of(o)) for o in cards]
rows = sorted(set(round(c.z, 2) for _, c in info))
row_idx = {r: i for i, r in enumerate(rows)}
cols_by_row = {}
for i, r in enumerate(rows):
    ys = sorted(set(round(c.y, 3) for o, c in info if round(c.z, 2) == r))
    cols_by_row[i] = {y: j for j, y in enumerate(ys)}
print("[2] 行数:", len(rows), "| 各排列数:", [len(v) for v in cols_by_row.values()])

# ---- 3. 专用集合 ----
coll = bpy.data.collections.get(PIVOT_COLL) or bpy.data.collections.new(PIVOT_COLL)
if coll.name not in [c.name for c in scene.collection.children]:
    scene.collection.children.link(coll)

# ---- 4. 批量挂轴(单重补偿) ----
made = 0
for o, c in info:
    r = row_idx[round(c.z, 2)]
    col = cols_by_row[r].get(round(c.y, 3), 0)
    delay = ((col + r) % WRAP) * STEP

    pv = o.parent if (o.parent and o.parent.name.startswith("FLIP_pivot")) else None
    if pv is None:
        mw = o.matrix_world.copy()          # 未动过的对象,matrix_world 可信
        name = "FLIP_pivot_" + o.name.split('.')[-1]
        pv = bpy.data.objects.get(name)
        if pv is None:
            pv = bpy.data.objects.new(name, None)
            coll.objects.link(pv)
            pv.empty_display_type = 'ARROWS'
            pv.empty_display_size = 0.05
            made += 1
        pv.location = c                      # 根级: 世界变换 == T(center),不回读
        o.parent = pv
        o.matrix_parent_inverse = Matrix.Translation(-c)   # 唯一的一次补偿
        o.matrix_basis = mw                                # 原世界矩阵,原样
    pv["flip_delay"] = delay
    pv["flip_period"] = PERIOD
    pv["flip_dur"] = DUR
    pv["flip_turns"] = TURNS
    pv["flip_axis"] = AXIS
    pv["flip_card"] = o.name

print("[4] 新建轴:", made, "| 总轴数:", len([o for o in bpy.data.objects if 'flip_delay' in o]))
vl.update()

# ---- 5. 核验:位置不能跑 ----
bad = [(o.name, snap[o.name], bbox_min(o)) for o in cards if bbox_min(o) != snap[o.name]]
print("[5] 位置核验:", "全部 PASS (%d 张)" % len(cards) if not bad else "FAIL %d 张 → %s" % (len(bad), bad[:3]))
if bad:
    raise SystemExit("位置偏移,已中止后续步骤")

# ---- 6. 驱动(受信任重开时接管;表达式必须返回弧度!) ----
TOTAL_DEG = 360.0 * TURNS
EXPR = ("(radians({t}) * (3*(((fc - dl) % {p}) / {d}) ** 2 - 2*(((fc - dl) % {p}) / {d}) ** 3)) "
        "if (((fc - dl) % {p}) < {d}) else radians({t})").format(t=TOTAL_DEG, p=PERIOD, d=DUR)
if 'radians' not in bpy.app.driver_namespace:
    bpy.app.driver_namespace['radians'] = math.radians
for pv in [o for o in bpy.data.objects if 'flip_delay' in o]:
    if pv.animation_data:
        for d_ in list(pv.animation_data.drivers):
            pv.animation_data.driver_remove(d_.data_path, d_.array_index)   # data_path 在 FCurve 上
    drv = pv.driver_add("rotation_euler", AXIS)
    d = drv.driver
    d.type = 'SCRIPTED'
    d.expression = EXPR
    d.use_self = False
    v1 = d.variables.new(); v1.name = "fc"; v1.type = 'SINGLE_PROP'
    v1.targets[0].id_type = 'SCENE'; v1.targets[0].id = scene; v1.targets[0].data_path = "frame_current"
    v2 = d.variables.new(); v2.name = "dl"; v2.type = 'SINGLE_PROP'
    v2.targets[0].id_type = 'OBJECT'; v2.targets[0].id = pv; v2.targets[0].data_path = '["flip_delay"]'
    d.is_valid = False
print("[6] 驱动已装:", EXPR)

# ---- 7. frame_change 处理器(免信任实时生效) ----
MARK = "flip_all_cards"
for h in list(bpy.app.handlers.frame_change_post):
    if getattr(h, "__name__", "") == MARK:
        bpy.app.handlers.frame_change_post.remove(h)
ns = {"bpy": bpy, "math": math}
exec(compile("""
def {m}(scene, depsgraph):
    import math
    f = scene.frame_current
    for ob in bpy.data.objects:
        if 'flip_delay' in ob:
            per = int(ob.get('flip_period', 60))
            dur = float(ob.get('flip_dur', 16))
            turns = int(ob.get('flip_turns', 3))
            total = math.radians(360.0 * turns)          # 弧度!写度数会让卡片全歪
            t = (f - int(ob['flip_delay'])) % per
            u = t / dur
            v = total * (3.0*u*u - 2.0*u*u*u) if u < 1.0 else total   # smoothstep
            ob.rotation_euler[ob.get('flip_axis', 1)] = v
""".format(m=MARK), "<flip>", "exec"), ns)
bpy.app.handlers.frame_change_post.append(ns[MARK])
print("[7] 处理器已注册:", MARK)

# ---- 8. 抽样:静止帧应回到初始朝向 ----
def dims(c):
    cs = [c.matrix_world @ Vector(v) for v in c.bound_box]
    return tuple(round(max(v[i] for v in cs) - min(v[i] for v in cs), 4) for i in range(3))

rest_frame = DUR + (WRAP - 1) * STEP + 2      # 所有卡都翻完的帧
scene.frame_set(rest_frame)
ok = 0
for pv in [o for o in bpy.data.objects if 'flip_delay' in o][:6]:
    c = bpy.data.objects.get(pv.get("flip_card", ""))
    if c:
        good = dims(c) == tuple(round(v, 4) for v in CARD_DIMS[::1]) or abs(dims(c)[0] - CARD_DIMS[0]) < 0.004
        ok += 1 if good else 0
print("[8] frame %d 静止核验: %d/6 张回到竖直姿态" % (rest_frame, ok))
scene.frame_set(1)
print("[DONE] 轴集合:", PIVOT_COLL, "| 保存前请先跑 reset_flip_rest.py")
