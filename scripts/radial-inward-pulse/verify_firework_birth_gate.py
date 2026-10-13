# -*- coding: utf-8 -*-
"""verify_firework_birth_gate.py —— 【独立核验】出场闸门（另起一次请求跑）

铁律：核验要**全新取引用**、**只读不改**，且判据取「结构 + 真值 + 解析复算」三层。

▶ 能读什么、读不到什么（skill §6，本轮又踩了一次）
    已连线的「计算输出」插槽（`相位叠加` / `相位` / `周期取模`… 都是 Math 节点）
    Python 读 `default_value` **恒为 0** —— 因为它们由节点自身运算决定。
    ⇒ 相位只能靠 **Value 节点**（`帧号` / `循环周期` / `相位偏移`，被驱动器写入）自己算。

▶ 判据
    结构：闸门 3 节点 + 4 条关键连线；`掩码裁切` 不再直连 自发光/底色亮度
    参数：循环周期 < 0（外扩）；相位偏移 = 占空比 + 1/|周期|
    行为：逐帧相位真值、第 1 帧 0 条亮带、出场段单调涨到 3、稳态恒 3 条
    红线：`亮面半径` 逐帧恒定（有任何"长大"就是整体缩放）；驱动全挂 Value 节点

用法（经桥）：
    python send.py verify_firework_birth_gate.py
"""
import bpy

# ============================ 配置区（与 set_firework_birth_gate.py 一致）============
MAT    = "烟花灯01_内收脉冲"
CTRL   = "烟花灯01_内收控制"
PREFIX = "内收"
EXPECT_BANDS_STEADY = 3      # 稳态应有几条（= build 时窗口公式解出的 N）
# ==================================================================================

D, C = bpy.data, bpy.context
scn = C.scene
N = PREFIX
ok, bad = [], []
def chk(c, m):
    (ok if c else bad).append(("  ok " if c else "  xx ") + m)

mat = D.materials.get(MAT)
ctrl = D.objects.get(CTRL)
chk(mat is not None, "材质 %s 存在" % MAT)
chk(ctrl is not None, "控制器 %s 存在" % CTRL)
nt = mat.node_tree
nodes, links = nt.nodes, nt.links

# ---------------- 1. 结构 ----------------
KN, GT, MU = N + "_环序号", N + "_出生门", N + "_门控"
SRC = N + "_掩码裁切"
TGT = (N + "_自发光", N + "_底色亮度")
for nm in (KN, GT, MU):
    chk(nodes.get(nm) is not None, "节点存在 %s" % nm)
chk(nodes[KN].operation == 'SUBTRACT', "环序号 = SUBTRACT（x − FRACT(x)）")
chk(nodes[GT].operation == 'LESS_THAN', "出生门 = LESS_THAN")
chk(abs(nodes[GT].inputs[1].default_value - 0.5) < 1e-9,
    "出生门阈值 = 0.5（不是 0；实际 %s）" % nodes[GT].inputs[1].default_value)
chk(nodes[MU].operation == 'MULTIPLY', "门控 = MULTIPLY")

ksrc = [l.from_node.name for l in links if l.to_node.name == KN]
chk(set(ksrc) == {N + "_相位叠加", N + "_周期取模"},
    "环序号 = 相位叠加 − 周期取模（实际 %s）" % sorted(ksrc))
gate_src = [l.from_node.name for l in links if l.to_node.name == MU]
chk(set(gate_src) == {SRC, GT}, "门控 两路 = 掩码裁切 × 出生门（实际 %s）" % sorted(gate_src))

up = {}
for l in links:
    up.setdefault((l.to_node.name, l.to_socket.name), []).append(l.from_node.name)
for tn in TGT:
    # ★ Math 节点的三个输入插槽 name 都叫 "Value"，按名字聚集会收到多个来源 ——
    #   所以判据是「门控在里面」（不是"恰等于"）。
    got = up.get((tn, "Value"), [])
    chk(MU in got, "%s 的一路来自门控（实际 %s）" % (tn, got))
stray = [l for l in links if l.from_node.name == SRC and l.to_node.name in TGT]
chk(not stray, "掩码裁切 不再直连 自发光/底色亮度（残留 %d 条）" % len(stray))

# ---------------- 2. 参数 ----------------
PERIOD = ctrl["循环周期"]
DIV = ctrl["脉冲间距"]
DUTY = ctrl["脉冲宽度"] / DIV
R_SHOW = ctrl["亮面半径"]
P0 = ctrl["相位偏移"]
EXP_P0 = (DUTY + 1.0 / abs(PERIOD)) % 1.0
chk(PERIOD < 0, "循环周期 = %s < 0（向外扩）" % PERIOD)
chk(abs(P0 - EXP_P0) < 1e-6,
    "相位偏移 = %.4f = 占空比 %.4f + 1/|%g|（期望 %.4f）" % (P0, DUTY, PERIOD, EXP_P0))

# ---------------- 3. 行为：逐帧真值 + 解析复算 ----------------
FR = [1, 25, 48, 73, 98, 148, 198]
print("=== 逐帧真值（读 Value 节点，非推算）===")
print("  间距 %.4f / 占空比 %.4f / 亮面半径 %.4f" % (DIV, DUTY, R_SHOW))
seen, rs = [], []
for f in FR:
    scn.frame_set(f)
    C.view_layer.update()
    rt = mat.evaluated_get(C.evaluated_depsgraph_get()).node_tree
    fr = rt.nodes[N + "_帧号"].outputs[0].default_value
    pd = rt.nodes[N + "_循环周期"].outputs[0].default_value
    p0 = rt.nodes[N + "_相位偏移"].outputs[0].default_value
    gr = rt.nodes[N + "_亮面半径"].outputs[0].default_value
    rs.append(gr)
    ph = fr / pd + p0
    chk(abs(fr - f) < 1e-4, "f=%3d 帧号节点 = %.3f" % (f, fr))
    chk(abs(ph - (f / PERIOD + P0)) < 1e-5, "f=%3d 相位 = %+.4f" % (f, ph))
    bands = []
    for k in range(2, -8, -1):
        lo, hi = (k - ph) * DIV, (k - ph + DUTY) * DIV
        lo_c, hi_c = max(lo, 0.0), min(hi, R_SHOW)
        if k > 0 or hi_c - lo_c <= 1e-4:
            continue
        bands.append("k=%d[%.3f,%.3f]" % (k, lo_c, hi_c))
    seen.append(len(bands))
    print("  f=%3d 相位=%+.3f | 放行 %s" % (f, ph, " / ".join(bands) if bands else "无 → 全黑"))
scn.frame_set(1)
C.view_layer.update()

chk(seen[0] == 0, "第 1 帧全黑（放行 0 条）")
chk(seen == sorted(seen), "出场段环数单调不减：%s" % seen)
chk(seen[-1] == EXPECT_BANDS_STEADY and seen[-2] == EXPECT_BANDS_STEADY,
    "稳态恒为 %d 条（结尾两帧 %s）" % (EXPECT_BANDS_STEADY, seen[-2:]))
chk(max(seen) <= EXPECT_BANDS_STEADY, "任一时点不超过 %d 条（没多露）" % EXPECT_BANDS_STEADY)

# ---------------- 4. 红线：不许有缩放 ----------------
chk(len(set(round(x, 6) for x in rs)) == 1,
    "亮面半径逐帧恒定 = %.4f ⇒ 无整体缩放" % rs[0])
chk(abs(rs[0] - ctrl["亮面半径"]) < 1e-5, "亮面半径 = 控制器属性（没被别处改）")

if nt.animation_data:
    wrong = []
    for d in nt.animation_data.drivers:
        p = d.data_path
        nm = p.split('"')[1] if '"' in p else None
        n = nt.nodes.get(nm) if nm else None
        if n is None or n.type != 'VALUE':
            wrong.append((p, n.type if n else None))
        if not d.driver.is_valid:
            wrong.append((p, 'INVALID'))
    chk(not wrong, "全部驱动 is_valid 且挂在 Value 节点上（违规 %s）" % wrong)
    chk(len(nt.animation_data.drivers) >= 11,
        "驱动条数 = %d（基线 11，闸门本身不引入驱动）" % len(nt.animation_data.drivers))

print("--- 通过 %d 项 / 失败 %d 项 ---" % (len(ok), len(bad)))
for x in ok:
    print(x)
for x in bad:
    print(x)
print("FAILS=%d" % len(bad))
