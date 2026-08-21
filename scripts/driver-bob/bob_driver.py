import bpy, mathutils

# =============================================================================
# bob() —— 驱动命名空间函数,被每个网格物体的 location.z 驱动调用
# 运动 = 平滑噪波(Perlin 类)随帧取样 → 连续无突变 → 天然的丝滑 / 阻尼感
# 两层结构: 全局大波(整体同频趋势) + 局部错动(各物体独立种子)
# =============================================================================

def bob(frame, self):
    # 每个网格物体通过 bob_ctrl 指向自己集合的控制面板(找不到回退到『运动控制』)
    ctrl_name = self.get('bob_ctrl')
    ctrl = bpy.data.objects.get(ctrl_name) if ctrl_name else None
    if ctrl is None:
        ctrl = bpy.data.objects.get('运动控制')
    if ctrl is None:
        # 没有控制面板 → 原地不动(返回基准 Z)
        return float(self.get('bob_base_z', 0.0))

    base = float(self.get('bob_base_z', 0.0))   # 物体原始静止位置
    seed = float(self.get('bob_seed', 0.0))     # 每个物体独立种子(相位错开)
    r = float(self.get('bob_rand', 0.0))        # 随机速度因子(-1~1)

    # 时间流速: 基准速度 × (1 + 随机因子 × 速度随机范围) → 每个物体速度不同
    sp = float(ctrl['移动速度'])
    sr = float(ctrl['速度随机范围'])
    sp_i = sp * (1.0 + r * sr)
    t = frame * sp_i

    # 全局大波: 所有物体同输入 → 整批被同一波牵着走(整体趋势)
    gseed = float(ctrl['种子偏移']) * 0.37
    gn = mathutils.noise.noise((t * float(ctrl['全局频率']) + gseed, 0.0, 0.0))

    # 局部错动: 各物体带独立 seed → 相位错开(层次不齐)
    ln = mathutils.noise.noise(
        (t * float(ctrl['局部频率']) + seed + float(ctrl['种子偏移']), 13.1, 7.7)
    )

    # 加权混合: 归一化加权平均,权重控制大波/错动占比
    tw = float(ctrl['全局大波权重'])
    lw = float(ctrl['局部错动权重'])
    s = tw + lw
    if s <= 0:
        s = 1.0
    c = (tw * gn + lw * ln) / s
    c = max(-1.0, min(1.0, c))          # clamp 到 [-1, 1]

    # 符号决定方向,上下限可不对称
    off = (c * float(ctrl['最大上移'])) if c >= 0.0 else (c * float(ctrl['最大下移']))
    return base + off

# 注册进驱动命名空间(驱动表达式 bob(fr, self) 才能找到它)
bpy.app.driver_namespace['bob'] = bob
