import bpy, random

# =============================================================================
# 通用构建器: 给指定集合里的网格物体挂「Z 轴平滑上下浮动」驱动
# 每个集合配一个独立控制面板(空物体),滑块实时调参;不动区(不修改*)自动排除
#
# 用法:
#   1) 先在 Blender 里运行 bob_driver.py(注册 bob 函数,可勾 Register 持久化)
#   2) 改下面的 TARGETS 成你的集合/控制面板名(或直接用默认的 主装置01~05)
#   3) 在桥里运行本脚本:  python send.py build_bob_drivers.py
#
# 可重复运行(幂等): 已有驱动的物体跳过,不会重置基准 Z 或种子
# =============================================================================

# ---------- 用户满意的默认参数(可在控制面板随时改) ----------
DEFAULTS = {
    '最大上移': 1.0, '最大下移': 1.0, '移动速度': 1.0, '速度随机范围': 0.2,
    '种子偏移': 0.5, '全局大波权重': 0.5, '局部错动权重': 0.2,
    '全局频率': 0.03, '局部频率': 0.02,
}
RANGES = {
    '最大上移': (0.0, 10.0, '最大上移距离'),
    '最大下移': (0.0, 10.0, '最大下移距离'),
    '移动速度': (0.0, 5.0, '整体移动快慢'),
    '速度随机范围': (0.0, 1.0, '每个物体速度随机增减范围(±)'),
    '种子偏移': (0.0, 1000.0, '主种子偏移,换整套错动花样'),
    '全局大波权重': (0.0, 1.0, '全局整体趋势占比'),
    '局部错动权重': (0.0, 1.0, '各自错动占比'),
    '全局频率': (0.0, 1.0, '全局大波频率(低=慢而整)'),
    '局部频率': (0.0, 1.0, '局部错动频率(高=更碎)'),
}

# ---------- 目标集合: (集合名, 控制面板名, 排除名包含) ----------
# 默认即本仓库实战场景(主装置01~05);换成你自己的集合只需改这里
TARGETS = [
    ('主装置01', '运动控制01', '不修改'),
    ('主装置02', '运动控制02', '不修改'),
    ('主装置03', '运动控制03', '不修改'),
    ('主装置04', '运动控制04', '不修改'),
    ('主装置05', '运动控制05', '不修改'),
]

SEED_BASE = 20260821   # 固定随机种子 → 每次重建花样一致(可改不同值换花样)


# ---------------------------------------------------------------------------
def ensure_bob():
    """确保 bob() 已注册进驱动命名空间;没有则尝试加载文本块 bob_driver.py"""
    if 'bob' in bpy.app.driver_namespace:
        return True
    txt = bpy.data.texts.get('bob_driver.py')
    if txt:
        exec(txt.as_string())
        return 'bob' in bpy.app.driver_namespace
    raise RuntimeError("bob() 未注册: 请先运行 bob_driver.py")


def make_ctrl(name, link_col=None):
    """新建一个控制面板空物体并写入默认参数 + 滑块范围"""
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, None)
        (link_col or bpy.context.scene.collection).objects.link(obj)
    for k, v in DEFAULTS.items():
        mn, mx, desc = RANGES[k]
        obj[k] = v
        try:
            ui = obj.id_properties_ui(k)
            ui.update(min=mn, max=mx, description=desc)
        except Exception as e:
            print('UI_WARN', k, repr(e))
    return obj


def descendants(o, acc):
    for c in o.children:
        acc.append(c)
        descendants(c, acc)


def skip_set_for(col, token='不修改'):
    """收集所有名字含 token 的 EMPTY 的子树 → 这些是不动区,不挂驱动"""
    s = set()
    for e in col.all_objects:
        if token in e.name and e.type == 'EMPTY':
            acc = []
            descendants(e, acc)
            for a in acc:
                s.add(a.name)
    return s


def has_z_driver(o):
    ad = o.animation_data
    if not ad or not ad.drivers:
        return False
    return any(d.data_path == 'location' and d.array_index == 2 for d in ad.drivers)


def add_driver(o, ctrl_name):
    """给物体 Z 轴挂 bob 驱动;幂等(已有则跳过,并保留已记录的基准 Z)"""
    o['bob_ctrl'] = ctrl_name
    if 'bob_base_z' not in o:
        o['bob_base_z'] = o.location.z          # 只在首次记录静止位置
    if has_z_driver(o):
        return
    if o.animation_data is None:
        o.animation_data_create()
    fcu = o.driver_add('location', 2)
    d = fcu.driver
    d.type = 'SCRIPTED'
    d.expression = 'bob(fr, self)'
    d.use_self = True                           # Blender 5.x: 用 use_self 让 self 可用
    vf = d.variables.new()
    vf.name = 'fr'
    vf.type = 'SINGLE_PROP'
    vf.targets[0].id_type = 'SCENE'
    vf.targets[0].id = bpy.context.scene
    vf.targets[0].data_path = 'frame_current'


def build_for_collection(col_name, ctrl_name, token='不修改', seed_base=SEED_BASE):
    """给单个集合构建: 建控制面板 + 给运动网格挂驱动(排除不动区)"""
    ensure_bob()
    col = bpy.data.collections.get(col_name)
    if col is None:
        print('SKIP_COLLECTION_NOT_FOUND', col_name)
        return 0
    ctrl = make_ctrl(ctrl_name, link_col=col)
    skip = skip_set_for(col, token)
    rng = random.Random(seed_base + hash(col_name) % 100000)
    n = 0
    for o in col.all_objects:
        if o.type == 'MESH' and o.name not in skip:
            if 'bob_seed' not in o:
                o['bob_seed'] = round(rng.uniform(0, 10000), 3)
            if 'bob_rand' not in o:
                o['bob_rand'] = round(rng.uniform(-1, 1), 3)
            add_driver(o, ctrl_name)
            n += 1
    print('BUILT', col_name, 'ctrl=', ctrl.name, '运动网格=', n, '排除不动区=', len(skip))
    return n


def main():
    total = 0
    for idx, (col_name, ctrl_name, token) in enumerate(TARGETS):
        # 按索引确定性偏移 → 各集合花样不同但每次重建一致(不用 hash,避免随机化)
        total += build_for_collection(col_name, ctrl_name, token,
                                      seed_base=SEED_BASE + idx * 7919)
    print('ALL_DONE 总运动网格=', total)


if __name__ == '__main__':
    main()
