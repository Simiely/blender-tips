# speed_light_driver.py —— 运动速度驱动灯光亮度(命名空间函数版)
# 用途: 灯的 energy 由「跟踪目标的 Z 轴运动速度」驱动 —— 上移(向 +Z 运动)增强、
#       下移(向 -Z 运动)衰减, 最后 clamp 到 [E_MIN, E_MAX]。
#       速度用前向差分: v = pos(frame+1) - pos(frame), 单位 = 长度/帧。
#       目标位置来源是命名空间位置函数(POS_FN, 默认 bob), 不是目标当前 location ——
#       避免驱动求值顺序读到未刷新旧值。
#
# 按目标特征分档(TIERS): 不同尺寸/高度的目标, 速度放大系数与亮度上限可以不同。
#       例如短柱速度小、视觉上不需要太亮 → 小系数 + 低上限; 长柱反之。
#       分档依据默认取目标 Z 轴高度(dimensions.z), 也可改成任意特征。
#
# 持久化: 文本块勾 Register(use_module=True) + 偏好设置开 Auto Run Python Scripts
#         -> 重开 .blend 自动执行注册, 驱动不报红(见仓库 AGENTS.md 通用坑)。
#
# 挂驱动: 灯的 energy 挂 SCRIPTED 驱动, 表达式 speed_energy(pname, fr);
#         pname/ fr 用 SINGLE_PROP 变量分别指向 灯自定义属性(目标名) / scene.frame_current。
#         详见 scripts/speed-light/build_speed_light_drivers.py。
import bpy

# ===== 基础参数(所有目标共用) =====
BASE = 6.0           # 基础亮度: 速度≈0 时的 energy(通常取灯的原始静态亮度)
K_DOWN_RATIO = 2.0   # 下移衰减 = K_UP * K_DOWN_RATIO; 上下对称渐变用 1.0
E_MIN = 0.0          # 亮度下限
POS_FN = 'bob'       # 目标 Z 位置函数名(须已注册到 bpy.app.driver_namespace)

# ===== 分档表 TIERS(按需修改) =====
# 每档 = (特征函数, 上移放大系数 K_UP, 亮度上限 E_MAX)
# 依次匹配, 命中即生效; 最后一条应为「永远命中」的兜底档。
# 特征函数入参是目标 Z 轴高度(obj.dimensions.z), 单位米。
TIERS = [
    (lambda z: z < 2.0,  1700.0, 20.0),    # 短柱: 小系数 + 低上限
    (lambda z: True,     3400.0, 100.0),   # 长柱(兜底): 大系数 + 高上限
]


def _tier(z):
    """按 Z 高度返回该目标对应档的 (K_UP, E_MAX)。"""
    for cond, k_up, e_max in TIERS:
        if cond(z):
            return k_up, e_max
    return TIERS[-1][1], TIERS[-1][2]


def speed_energy(target_name, frame):
    """返回目标物体以当前帧运动速度对应的灯光亮度。

    target_name: 目标物体名(见灯的 energy 驱动变量 pname)
    frame:       当前帧号(见灯的 energy 驱动变量 fr)
    """
    t = bpy.data.objects.get(target_name)
    if t is None:
        return BASE
    pos = bpy.app.driver_namespace.get(POS_FN)
    if pos is None:
        return BASE

    v = pos(frame + 1, t) - pos(frame, t)   # 前向差分速度(上移为正)

    k_up, e_max = _tier(t.dimensions.z)

    if v >= 0.0:
        e = BASE + k_up * v                        # 上移 -> 增强
    else:
        e = BASE - K_DOWN_RATIO * k_up * (-v)      # 下移 -> 衰减(K_DOWN_RATIO 倍)

    if e < E_MIN:
        e = E_MIN
    if e > e_max:
        e = e_max
    return e


bpy.app.driver_namespace['speed_energy'] = speed_energy
print('[speed_light_driver] speed_energy 已注册(速度->亮度, 前向差分, 按高度分档)')