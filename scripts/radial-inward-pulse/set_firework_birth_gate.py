# -*- coding: utf-8 -*-
"""set_firework_birth_gate.py —— 给已建好的「径向内收多脉冲」材质加【出场】：
黑场起步 → 第一圈从圆心诞生往外扩 → 第二/三圈依次跟上 → 之后永久循环。

────────────────────────────────────────────────────────────────
为什么不能靠裁切/缩放做
────────────────────────────────────────────────────────────────
`FRACT(r/间距 + 相位)` 是**无限周期**图案 ⇒ 它**没有"开始"**：
任意相位下视野里恒有 N 条带（N 由 build 脚本的窗口公式定死，见 skill §2）。
把「亮面半径」从小长到大 = **整体缩放**（实测被当场否掉）。

量化（同一工程实测）：
    环往外走的真实速度 = 间距 ÷ |循环周期| = 0.3995 / 50 = 0.0080 /帧
    裁切边缘张开速度 = 亮面半径 ÷ 淡入帧数 = 0.8378 / 25 = 0.0335 /帧  → 快 4.2 倍
⇒ 看到的是"光圈张开"，不是"环一圈圈出来"。

────────────────────────────────────────────────────────────────
正解：在【脉冲掩码之后】串一道闸门，逐环放行（3 个 Math 节点）
────────────────────────────────────────────────────────────────
    x = 相位叠加 = r/间距 + 相位           ← 袋里现成
    t = 周期取模 = FRACT(x)                ← 袋里现成
    k = x − t = floor(x)                   ← 新增 1× SUBTRACT（环序号）
    放行 ⟺ k ≤ 0                           ← 新增 1× LESS_THAN（阈值 0.5）
    掩码裁切 × 放行 → 自发光 / 底色亮度      ← 新增 1× MULTIPLY，串进去

方向为什么是 `k ≤ 0`（外扩时）：
    外扩 = 循环周期取负 ⇒ 相位**递减**。
    第 k 圈的亮带是  r/间距 ∈ [k − 相位, k − 相位 + 占空比)
    ⇒ 左边缘 = (k − 相位) × 间距 随帧**增大** = 往外走；
    **左边缘 = 0 的那一刻就是"这圈在圆心诞生"**，此刻带宽度恰好为 0
    ⇒ 硬开也不跳变（天然连续）。
    k = 0 诞生于 相位 0；k = −1 于 −1；k = −2 于 −2 …
    ⇒ 每 |循环周期| 帧，从圆心**多放出**一条。
    门只放行 k ≤ 0 ⇒ 启动瞬间**只有 k = 0 这一条**，
    k = 1 / 2 … 那些"早就走到外面"的带被挡在门后，不会提前站在场上。

相位偏移取多少（决定第 1 帧是不是全黑）：
    全黑 ⟺ 相位 ≥ 占空比          （k = 0 的右边缘 ≤ 0）
    相位 = 帧号 ÷ 循环周期 + 相位偏移
    ⇒ 相位偏移 = 占空比 + 1 / |循环周期|      （本脚本自动算）
    实测：循环周期 −50、占空比 0.94 ⇒ 相位偏移 0.96
          f=1 纯黑 → f=48 第一圈铺满 → f=98 第二圈从圆心冒出 → f=148 三圈齐 → 永久循环

三条硬约束：
  1) 阈值用 **0.5** 不用 0 —— k 由 `x − FRACT(x)` 得来，k=0 时可能有 ±1e-7 浮点毛刺，
     `k < 0` 会漏判/误挡边界那一帧。
  2) 门**只乘在掩码上**，绝不碰 `亮面半径` / 色相 / 发光强度 ⇒ 才没有任何缩放。
  3) 核验读 **Value 节点**（帧号/循环周期/相位偏移）自己算相位；
     `相位叠加` / `相位` 是**已连线的 Math 输出**，Python 读回恒 0（skill §6 同一个坑）。

幂等：重跑会先拆掉旧闸门并恢复「掩码裁切 → 自发光/底色亮度」的直连，再重建。

用法（经桥）：
    python send.py set_firework_birth_gate.py

⚠ 桥 exec 环境没有 `__file__`：本脚本不读任何外部文件。
⚠ 送桥前确认文件**无 BOM**（否则 SyntaxError: invalid non-printable character U+FEFF）。
"""
import bpy

# ============================ 配置区 ============================
MAT    = "烟花灯01_内收脉冲"     # 已建成的「径向内收多脉冲」材质
CTRL   = "烟花灯01_内收控制"     # 它的控制器空物体（自定义属性的家）
PREFIX = "内收"                 # 与 build_inward_pulse.py 的前缀一致
PERIOD = -50.0                  # 循环周期（帧/圈）。★ 负 = 向外扩（出场用外扩）
SRC_NODE = PREFIX + "_掩码裁切"
TGT_NODES = (PREFIX + "_自发光", PREFIX + "_底色亮度")
# ==============================================================

K_THRESHOLD = 0.5        # k < 0.5 ⇔ k ≤ 0（别写 0，见 docstring 硬约束 1）
MIN_W = 1e-4             # 最小可见宽度（世界单位）：窄于它的"刀尖"不算一条亮带
D, C = bpy.data, bpy.context
scn = C.scene

log, fails = [], []
def chk(cond, msg):
    (log if cond else fails).append(("  ok " if cond else "  xx ") + msg)


# ---------------------------------------------------- 0. 前置
mat = D.materials.get(MAT)
ctrl = D.objects.get(CTRL)
if mat is None:
    raise RuntimeError("材质 %s 不存在（先跑 build_inward_pulse.py 建基线）" % MAT)
if ctrl is None:
    raise RuntimeError("控制器 %s 不存在" % CTRL)
nt = mat.node_tree
nodes, links = nt.nodes, nt.links
for nm in (SRC_NODE,) + TGT_NODES:
    if nodes.get(nm) is None:
        raise RuntimeError("基线里没有节点 %s —— 本脚本只给「内收多脉冲」基线加闸门" % nm)
DUTY0 = ctrl["脉冲宽度"] / ctrl["脉冲间距"]
log.append("基线：%s 节点=%d 连线=%d" % (MAT, len(nodes), len(links)))
log.append("基线：占空比 = %.4f（脉冲宽度 %.4f ÷ 间距 %.4f）"
           % (DUTY0, ctrl["脉冲宽度"], ctrl["脉冲间距"]))

# ---------------------------------------------------- 1. 幂等：拆旧闸门 + 恢复直连
for nm in (PREFIX + "_门控", PREFIX + "_环序号", PREFIX + "_出生门"):
    n = nodes.get(nm)
    if n is not None:
        nodes.remove(n)
        log.append("清理旧节点 %s" % nm)
for tn in TGT_NODES:
    t = nodes[tn]
    for l in list(links):
        if l.to_node == t and l.to_socket == t.inputs[0]:
            links.remove(l)
    links.new(nodes[SRC_NODE].outputs[0], t.inputs[0])
log.append("已恢复直连：%s → %s" % (SRC_NODE, " / ".join(TGT_NODES)))

# ---------------------------------------------------- 2. 建闸门（3 个 Math）
def MATH(name, label, op, x, y):
    n = nodes.new('ShaderNodeMath')
    n.name, n.label, n.operation = name, label, op
    n.location = (x, y)
    for i in range(3):
        n.inputs[i].default_value = 0.0      # ★ 未连线输入会用 default_value，默认 0.5 会污染
    return n

bx, by = nodes[SRC_NODE].location
kk = MATH(PREFIX + "_环序号", "环序号 k = floor(x)", 'SUBTRACT', bx + 260, by - 420)
links.new(nodes[PREFIX + "_相位叠加"].outputs[0], kk.inputs[0])
links.new(nodes[PREFIX + "_周期取模"].outputs[0], kk.inputs[1])

gt = MATH(PREFIX + "_出生门", "出生门：k ≤ 0 放行", 'LESS_THAN', bx + 460, by - 420)
gt.inputs[1].default_value = K_THRESHOLD     # ★ 0.5 而不是 0
links.new(kk.outputs[0], gt.inputs[0])

mu = MATH(PREFIX + "_门控", "出生门控（只乘掩码）", 'MULTIPLY', bx + 700, by - 420)
links.new(nodes[SRC_NODE].outputs[0], mu.inputs[0])
links.new(gt.outputs[0], mu.inputs[1])
chk(True, "闸门节点已建：%s → %s → %s" % (PREFIX + "_环序号", PREFIX + "_出生门", PREFIX + "_门控"))

# ---------------------------------------------------- 3. 串进自发光 / 底色亮度
for tn in TGT_NODES:
    t = nodes[tn]
    for l in list(links):
        if l.to_node == t and l.to_socket == t.inputs[0]:
            links.remove(l)
    links.new(mu.outputs[0], t.inputs[0])
chk(True, "已串入链：%s → %s → %s" % (SRC_NODE, PREFIX + "_门控", " / ".join(TGT_NODES)))

# ---------------------------------------------------- 4. 控制器参数（外扩 + 黑场起步）
P0 = (DUTY0 + 1.0 / abs(PERIOD)) % 1.0
ctrl["循环周期"] = PERIOD
ctrl["相位偏移"] = P0
ctrl.update_tag()
C.view_layer.update()
chk(abs(ctrl["循环周期"] - PERIOD) < 1e-9, "循环周期 = %s（负 = 向外扩）" % PERIOD)
chk(abs(ctrl["相位偏移"] - P0) < 1e-9,
    "相位偏移 = %.4f（= 占空比 %.4f + 1/|%g|，第 1 帧恰好全黑）" % (P0, DUTY0, PERIOD))

# ---------------------------------------------------- 5. 逐帧解析自检（读 Value 节点真值）
DIV = ctrl["脉冲间距"]
DUTY = ctrl["脉冲宽度"] / DIV
R_SHOW = ctrl["亮面半径"]
FADE = ctrl["淡出宽度"]
print("=== 逐帧自检（间距 %.4f / 占空比 %.4f / 亮面半径 %.4f）===" % (DIV, DUTY, R_SHOW))
FR = [1, 25, 48, 73, 98, 148, 198]
seen = []
for f in FR:
    scn.frame_set(f)
    C.view_layer.update()
    rt = mat.evaluated_get(C.evaluated_depsgraph_get()).node_tree
    fr = rt.nodes[PREFIX + "_帧号"].outputs[0].default_value
    pd = rt.nodes[PREFIX + "_循环周期"].outputs[0].default_value
    p0 = rt.nodes[PREFIX + "_相位偏移"].outputs[0].default_value
    ph = fr / pd + p0
    chk(abs(fr - f) < 1e-4, "f=%3d 帧号节点 = %.3f" % (f, fr))
    chk(abs(ph - (f / PERIOD + P0)) < 1e-5,
        "f=%3d 相位 = %+.4f（期望 %+.4f）" % (f, ph, f / PERIOD + P0))
    bands = []
    for k in range(2, -8, -1):
        lo, hi = (k - ph) * DIV, (k - ph + DUTY) * DIV
        if hi <= 0 or lo >= R_SHOW:
            continue                       # 完全在圆心内 / 亮面外
        if k > 0:
            continue                       # 门只放行 k ≤ 0
        lo_c, hi_c = max(lo, 0.0), min(hi, R_SHOW)
        if hi_c - lo_c <= MIN_W:
            continue                       # ★ 小于最小可见宽度不算一条
        bands.append("k=%d r∈[%.3f,%.3f]" % (k, lo_c, hi_c))
    seen.append(len(bands))
    print("  f=%3d 相位=%+.3f | 放行 %s" % (f, ph, " / ".join(bands) if bands else "无 → 全黑"))
scn.frame_set(1)
C.view_layer.update()

# ---------------------------------------------------- 6. 判据
chk(seen[0] == 0, "第 1 帧没有任何亮带（全黑起步）")
chk(max(seen) <= 3, "任一时点放行 ≤ 3 条（与窗口公式的 N 一致）")
chk(seen[-1] == seen[-2] == 3, "稳态恒为 3 条（f=%d / f=%d 都是 3）" % (FR[-2], FR[-1]))
chk(sum(seen) > 0, "出场段确实从 0 条逐步涨到 3 条：%s" % seen)


# 亮面半径必须逐帧恒定（= 没有任何缩放）
rs = []
for f in FR:
    scn.frame_set(f)
    C.view_layer.update()
    rt = mat.evaluated_get(C.evaluated_depsgraph_get()).node_tree
    rs.append(rt.nodes[PREFIX + "_亮面半径"].outputs[0].default_value)
scn.frame_set(1)
C.view_layer.update()
chk(len(set(round(x, 6) for x in rs)) == 1,
    "亮面半径逐帧恒定 = %.4f（%d 帧无变化 ⇒ 无整体缩放）" % (rs[0], len(FR)))

# 驱动守卫：全部挂在 Value 节点输出上
if nt.animation_data:
    bad = []
    for d in nt.animation_data.drivers:
        p = d.data_path
        nm = p.split('"')[1] if '"' in p else None
        n = nt.nodes.get(nm) if nm else None
        if n is None or n.type != 'VALUE':
            bad.append((p, n.type if n else None))
    chk(not bad, "驱动全部挂在 Value 节点上（违规 %s）" % bad)

print("\n".join(log))
print("节点=%d 连线=%d（基线 %d/%d + 闸门 3 节点 / 4 连线）"
      % (len(nodes), len(links), len(nodes) - 3, len(links) - 4))
print("FAILS=%d" % len(fails))
for x in fails:
    print(x)
