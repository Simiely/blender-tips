# -*- coding: utf-8 -*-
# 合成器后期辉光(Glare)—— 幂等构建(经 9877 桥执行)
# ===========================================================================
# 结构:  渲染层(RLayers) ──Image──> 眩光(Glare) ──Image──> 合成输出(NodeGroupOutput)
# 参数:  空对象「辉光控制」上的 6 个中文滑块,经 5 条驱动器写进眩光节点的插座。
#
# 幂等:再次运行只会打印「跳过重接(幂等)」+「N 条驱动未改动」。
# 非破坏:不碰渲染设置(临时改动的在 finally 之外,见 [5]/[6]);不删用户节点(只清旧配方的遗留节点)。
#
# ★★ 5.2 事实(全部实测,别再猜):
#   - 场景合成器树挂在 scene.compositing_node_group(type='CompositorNodeTree'),
#     scene.node_tree 在 5.0 已**移除**,scene.use_nodes 恒 True 且设了没用。
#   - **终结节点必须是 NodeGroupOutput,而且必须先用
#     tree.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
#     声明组输出插座。** 少了这一步整条合成会被**静默旁路**(不报错、图完全不变,
#     连 PNG 文件字节数都一模一样)。—— 仓库旧配方漏了这步,已在 5.x 失效。
#   - **不要用 CompositorNodeConvertToDisplay 当终结节点**:它会把色彩管理再套一遍
#     (实测旁路档 max=0.4039、90944/129600 分量被改动)。正解是直接接 GroupOutput,
#     此时「眩光强度=0」的结果与"完全不加合成器"**逐位相同**(max=0.00000000, 0 个分量不同)。
#   - render.use_compositing 是总闸(关掉后极端眩光也 0 差异)。
#   - Glare 的 Type / Quality / Kernel Data Type 是 MENU 插座,取值是**标题式字符串**
#     ('Fog Glow' / 'Bloom' / 'Streaks' / 'Ghosts' / 'Simple Star' / 'Kernel'),
#     写成全大写标识符会 TypeError;NodeSocketMenu 没有 .enum_items,只能试。
#   - Size / Strength / Saturation / Smoothness 的 subtype 是 Factor ⇒ 量程 0-1。
#     (仓库里旧配方的 Size=12 是 2.x-3.x 的整数 API,在 5.x 已失效。)
#   - Glare 有三个输出:Image(原图+眩光) / Glare(只有眩光) / Highlights(只有高光)。
#
# ★ 本脚本只改内存,收尾必须提醒用户 Ctrl+S。

import bpy

# ================= 配置(换工程改这里) =================
GROUP_NAME   = "后期辉光"
CTRL_NAME    = "辉光控制"
NODE_RL      = "渲染层"
NODE_GLARE   = "眩光"
NODE_OUT     = "合成输出"
IFACE_SOCKET = "Image"
LEGACY_NODE  = "转显示"        # 旧配方遗留的错误终结节点,见到就删

GLARE_TYPE    = "Fog Glow"     # 可换:Bloom / Streaks / Ghosts / Simple Star / Kernel
GLARE_QUALITY = "High"         # Low / Medium / High

CTRL_LOC      = (0.0, 0.0, 0.0)
FORCE_REBUILD = False          # True = 无视现状强制重接链条

# (属性名, 目标插座, 默认值, soft_min, soft_max, 变量名, 角色, 说明)
KNOBS = [
    ("辉光开关",   None,         1.0,  0.0,   1.0,  "sw", "toggle", "1=开 / 0=关(强度乘 0,实测与不加合成器逐位相同)"),
    ("辉光强度",   "Strength",   1.0,  0.0,   2.0,  "st", "mul",    "眩光强度(会乘辉光开关)"),
    ("辉光阈值",   "Threshold",  1.0,  0.0,  20.0,  "th", "direct", "进入辉光的亮度阈值(线性,越高越挑剔)"),
    ("辉光尺寸",   "Size",       0.5,  0.0,   1.0,  "sz", "direct", "辉光扩散尺寸(0-1 比例,5.x 是 Factor)"),
    ("辉光饱和度", "Saturation", 1.0,  0.0,   2.0,  "sa", "direct", "饱和度(1=原色,>1 更艳)"),
    ("辉光最大亮度", "Maximum",   10.0, 0.0, 100.0,  "mx", "direct", "单像素最大贡献(压过曝)"),
]

# ★ 硬 min/max:只写 soft_min/soft_max 时,Blender 里控件仍是个普通数值框(±3.4e38),
#   看起来不像滑块。要让它在属性面板里当成真滑块用,必须连硬 min/max 一起写。
#   硬范围给得比 soft 宽,留出"拖过头"的探索空间。
HARD = {
    "辉光开关":     (0.0,   1.0),
    "辉光强度":     (0.0,   4.0),
    "辉光阈值":     (0.0,  50.0),
    "辉光尺寸":     (0.0,   1.0),
    "辉光饱和度":   (0.0,   4.0),
    "辉光最大亮度": (0.0, 500.0),
}
STEP = 0.01          # 默认 1.0 太粗,拖一格跳 1
PRECISION = 3

# 眩光节点上"没做驱动、可直接手改"的插座 —— 与"色标归用户自己调"同一约定
DIRECT_SOCK = [
    ("Type",       "可直接改:类型 6 选 1"),
    ("Quality",    "可直接改:Low/Med/High"),
    ("Tint",       "可直接改:辉光染色"),
    ("Smoothness", "可直接改:阈值过渡柔度"),
]
SOCK_DESC_LIMIT = 63   # 实测硬上限:中文 3 字节/字 ⇒ 约 21 字,超了静默截断

REPORT = []
def R(msg):
    REPORT.append(msg)
    print(msg)

def force_refresh():
    ctrl.update_tag()
    ng.update_tag()
    sc.update_tag()
    bpy.context.evaluated_depsgraph_get().update()

# ================= 0. 环境断言 =================
for cls in ("CompositorNodeGlare", "CompositorNodeRLayers", "NodeGroupOutput"):
    assert hasattr(bpy.types, cls), "本版本没有 %s,先人工确认合成器 API" % cls

C  = bpy.context
sc = C.scene
vl = C.view_layer

# ================= 1. 只读侦察 =================
R("=" * 70)
R("[1] 改前状态")
R("  文件: %s" % bpy.data.filepath)
R("  引擎: %s   分辨率: %dx%d @%d%%" % (
    sc.render.engine, sc.render.resolution_x, sc.render.resolution_y,
    sc.render.resolution_percentage))
R("  render.use_compositing = %s" % sc.render.use_compositing)

ng = sc.compositing_node_group
R("  scene.compositing_node_group = %s" % (None if ng is None else ng.name))
if ng is not None:
    R("  现有合成器 NODES=%d LINKS=%d" % (len(ng.nodes), len(ng.links)))
    for n in ng.nodes:
        R("      - %-20s %s" % (n.name, n.bl_idname))
    R("  组 interface 插座: %s" % (
        [(it.name, getattr(it, 'in_out', None)) for it in ng.interface.items_tree
         if it.item_type == 'SOCKET'],))

ctrl = bpy.data.objects.get(CTRL_NAME)
R("  空对象「%s」= %s" % (CTRL_NAME, "已存在" if ctrl else "不存在"))

def one_incoming(node, sock_name):
    if node is None or ng is None:
        return []
    s = node.inputs.get(sock_name)
    if s is None:
        return []
    return [l for l in ng.links if l.to_socket == s]

def iface_has_output():
    if ng is None:
        return False
    for it in ng.interface.items_tree:
        if it.item_type == 'SOCKET' and getattr(it, 'in_out', None) == 'OUTPUT':
            return True
    return False

already_ok = False
if (not FORCE_REBUILD) and ng is not None:
    a = ng.nodes.get(NODE_RL); b = ng.nodes.get(NODE_GLARE); o = ng.nodes.get(NODE_OUT)
    if a and b and o and a.bl_idname == 'CompositorNodeRLayers' \
       and b.bl_idname == 'CompositorNodeGlare' and o.bl_idname == 'NodeGroupOutput':
        ia = one_incoming(b, "Image"); io = one_incoming(o, IFACE_SOCKET)
        ok_ia = len(ia) == 1 and ia[0].from_node == a and ia[0].from_socket.name == "Image"
        ok_io = len(io) == 1 and io[0].from_node == b and io[0].from_socket.name == "Image"
        already_ok = ok_ia and ok_io and iface_has_output()
        R("  目标状态判定: %s (眩光.Image 入线=%d, 合成输出.%s 入线=%d, 输出插座=%s)" % (
            "已是目标状态" if already_ok else "需要重接",
            len(ia), IFACE_SOCKET, len(io), iface_has_output()))

will_rebuild = FORCE_REBUILD or (not already_ok)
R("  => 本次 %s" % ("会重接链条" if will_rebuild else "跳过重接(幂等)"))

# ================= 2. 建/取节点组 =================
R("-" * 70)
R("[2] 节点组")
if ng is None or ng.bl_idname != 'CompositorNodeTree':
    existing = bpy.data.node_groups.get(GROUP_NAME)
    if existing is not None and existing.bl_idname == 'CompositorNodeTree':
        ng = existing
        R("  复用已有同名节点组: %s" % ng.name)
    else:
        ng = bpy.data.node_groups.new(GROUP_NAME, type='CompositorNodeTree')
        R("  新建节点组: %s" % ng.name)
    sc.compositing_node_group = ng
else:
    R("  已有合成器节点组: %s" % ng.name)

if ng.name != GROUP_NAME and bpy.data.node_groups.get(GROUP_NAME) is None:
    ng.name = GROUP_NAME
    R("  节点组改名为 %s" % GROUP_NAME)

nodes = ng.nodes
links = ng.links

def ensure_iface_socket():
    for it in ng.interface.items_tree:
        if it.item_type == 'SOCKET' and getattr(it, 'in_out', None) == 'OUTPUT':
            R("  组输出插座已存在: %r" % it.name)
            return False
    ng.interface.new_socket(name=IFACE_SOCKET, in_out='OUTPUT', socket_type='NodeSocketColor')
    R("  + 声明组输出插座 %r (NodeSocketColor) —— ★ 少了这步整条合成会被静默旁路" % IFACE_SOCKET)
    return True

def ensure_node(name, idname):
    n = nodes.get(name)
    if n is None or n.bl_idname != idname:
        if n is not None:
            R("  ! 节点「%s」类型是 %s,期望 %s —— 删除重建" % (name, n.bl_idname, idname))
            nodes.remove(n)
        n = nodes.new(idname)
        n.name = name
        n.label = name
        R("  + 新建节点 %s (%s)" % (name, idname))
    return n

def ensure_link(from_node, from_sock, to_node, to_sock):
    dst = to_node.inputs[to_sock]
    cur = [l for l in links if l.to_socket == dst]
    if len(cur) == 1 and cur[0].from_node == from_node and cur[0].from_socket.name == from_sock:
        return False
    if len(cur) > 1:
        R("  ! %s.%s 原有 %d 条入线,清理为 1 条" % (to_node.name, to_sock, len(cur)))
    for l in cur:
        links.remove(l)
    links.new(from_node.outputs[from_sock], dst)
    R("  + 接线 %s.%s -> %s.%s" % (from_node.name, from_sock, to_node.name, to_sock))
    return True

if will_rebuild:
    # 先清掉旧配方遗留的错误终结节点(否则它会跟 GroupOutput 抢输出)
    legacy = nodes.get(LEGACY_NODE)
    if legacy is not None and legacy.bl_idname == 'CompositorNodeConvertToDisplay':
        nodes.remove(legacy)
        R("  - 删除旧配方遗留的错误终结节点「%s」(ConvertToDisplay 会把色彩管理套两遍)" % LEGACY_NODE)
    for n in list(nodes):
        if n.bl_idname in ('CompositorNodeComposite',):
            nodes.remove(n)
            R("  - 删除过时节点 %s" % n.name)

    ensure_iface_socket()
    n_rl = ensure_node(NODE_RL, 'CompositorNodeRLayers')
    n_gl = ensure_node(NODE_GLARE, 'CompositorNodeGlare')
    n_ou = ensure_node(NODE_OUT, 'NodeGroupOutput')

    if n_gl.inputs["Type"].default_value != GLARE_TYPE:
        R("  眩光 Type: %r -> %r" % (n_gl.inputs["Type"].default_value, GLARE_TYPE))
        n_gl.inputs["Type"].default_value = GLARE_TYPE
    else:
        R("  眩光 Type 已是 %r(保留用户改过的值)" % GLARE_TYPE)
    if n_gl.inputs["Quality"].default_value != GLARE_QUALITY:
        R("  眩光 Quality: %r -> %r" % (n_gl.inputs["Quality"].default_value, GLARE_QUALITY))
        n_gl.inputs["Quality"].default_value = GLARE_QUALITY

    n_rl.location = (-420, 0)
    n_gl.location = (-140, 0)
    n_ou.location = (180, 0)
    ensure_link(n_rl, "Image", n_gl, "Image")
    # 组输出插座名可能被用户改过,按名字取不到就退回第一个
    okey = IFACE_SOCKET if IFACE_SOCKET in [s.name for s in n_ou.inputs] else None
    if okey is None:
        assert len(n_ou.inputs) >= 1, "NodeGroupOutput 没有任何输入插座"
        okey = n_ou.inputs[0].name
        R("  ! 组输出插座名不是 %r,退回用 %r" % (IFACE_SOCKET, okey))
    ensure_link(n_gl, "Image", n_ou, okey)
else:
    n_rl = nodes.get(NODE_RL); n_gl = nodes.get(NODE_GLARE); n_ou = nodes.get(NODE_OUT)
    R("  跳过重接(结构已正确)")

ng.use_fake_user = True
R("  节点组 NODES=%d LINKS=%d  终结节点=%s" % (len(nodes), len(links), n_ou.bl_idname))
R("  当前 Type=%r Quality=%r" % (n_gl.inputs["Type"].default_value,
                                n_gl.inputs["Quality"].default_value))

# ================= 3. 空对象 + 中文滑块 =================
R("-" * 70)
R("[3] 空对象与滑块")
if ctrl is None:
    ctrl = bpy.data.objects.new(CTRL_NAME, None)
    sc.collection.objects.link(ctrl)
    R("  + 新建空对象 %s" % CTRL_NAME)
else:
    R("  复用已有空对象 %s" % CTRL_NAME)
ctrl.empty_display_type = 'CUBE'
ctrl.empty_display_size = 2.0
ctrl.hide_viewport = False
ctrl.hide_render = False

changed_props = []
for prop, sock, dflt, smin, smax, var, role, desc in KNOBS:
    cur = ctrl.get(prop, None)
    if cur is None:
        ctrl[prop] = dflt
        changed_props.append("%s=%.3f(新建)" % (prop, dflt))
    else:
        changed_props.append("%s=%.3f(已有)" % (prop, float(cur)))
    try:
        hmn, hmx = HARD[prop]
        ctrl.id_properties_ui(prop).update(min=hmn, max=hmx,
                                           soft_min=smin, soft_max=smax,
                                           step=STEP, precision=PRECISION,
                                           description=desc)
    except Exception as e:
        R("  ! 设置 %s 的滑块范围失败: %r" % (prop, e))
R("  " + " | ".join(changed_props))

# ================= 3b. 可发现性:插座提示 + 节点标题 =================
# 被驱动的插座在 UI 上是紫色的、拖不动。这不是坏了,是"改道去空对象改"。
# 所以给它写个悬停提示,顺手把眩光节点的标题也改成指路的。幂等、非破坏。
R("-" * 70)
R("[3b] 可发现性标注")
try:
    n_gl.label = "参数在空对象「%s」上" % CTRL_NAME   # 只改 label,node.name 不变 ⇒ 驱动地址不受影响
    R("  眩光节点 label = %r (name 仍是 %r)" % (n_gl.label, n_gl.name))

    wrote = 0
    for prop, sock, dflt, smin, smax, var, role, desc in KNOBS:
        if sock is None or sock not in n_gl.inputs:
            continue
        txt = "被驱动 →「%s」的%s" % (CTRL_NAME, prop)     # 紫色格的指路牌
        nb = len(txt.encode("utf-8"))
        if nb > SOCK_DESC_LIMIT:
            R("  ! %s 的提示 %d 字节超上限,跳过" % (sock, nb))
            continue
        n_gl.inputs[sock].description = txt
        if n_gl.inputs[sock].description != txt:
            R("  ! %s 提示写回不一致(%d 字节)" % (sock, nb))
        else:
            wrote += 1
    for sock, txt in DIRECT_SOCK:
        if sock not in n_gl.inputs:
            continue
        if len(txt.encode("utf-8")) > SOCK_DESC_LIMIT:
            R("  ! %s 的提示超上限,跳过" % sock)
            continue
        n_gl.inputs[sock].description = txt
        if n_gl.inputs[sock].description == txt:
            wrote += 1
    R("  插座提示已写 %d 条(上限 %d 字节)" % (wrote, SOCK_DESC_LIMIT))
except Exception as e:
    R("  ! 可发现性标注失败(不影响功能): %r" % (e,))


# ================= 4. 驱动器(原子重建) =================
R("-" * 70)
R("[4] 驱动器")
if ng.animation_data is None:
    ng.animation_data_create()
ad = ng.animation_data

spec_paths = {}
for prop, sock, dflt, smin, smax, var, role, desc in KNOBS:
    if sock is None:
        continue
    spec_paths['nodes["%s"].inputs["%s"].default_value' % (NODE_GLARE, sock)] = (prop, sock, var, role)

for d in [x for x in ad.drivers if x.data_path not in spec_paths]:
    R("  ! 保留一条非本脚本的驱动: %s" % d.data_path)

def describe(d):
    """★ DriverVariable 本身没有 data_path/id —— 都在 v.targets[0] 上,读错了就永远判"规格不符"、每跑必重建"""
    try:
        vs = []
        for v in d.driver.variables:
            tg = v.targets[0] if len(v.targets) else None
            vs.append((v.name, v.type,
                       (tg.id.name if tg is not None and tg.id else None),
                       (tg.data_path if tg is not None else None)))
    except Exception as e:
        vs = "读变量失败: %r" % (e,)
    return (d.driver.type, d.driver.expression, vs)

# ★ 组重建后旧驱动的 data_path 可能悬空,先清掉所有指向「眩光」的悬空驱动
alive_pre = 0
for d in list(ad.drivers):
    t, e, vs = describe(d)
    if isinstance(vs, str):
        continue
    if any(v[2] is None for v in vs):
        ad.drivers.remove(d)
        alive_pre += 1
if alive_pre:
    R("  - 清掉 %d 条悬空驱动(重建节点后 id 已失效)" % alive_pre)

n_drv_ok = 0
for path, (prop, sock, var, role) in spec_paths.items():
    want_expr = "(sw * st)" if role == "mul" else var
    if role == "mul":
        want_vars = [("sw", "辉光开关"), (var, prop)]
    else:
        want_vars = [(var, prop)]
    want_sig = sorted((vn, 'SINGLE_PROP', CTRL_NAME, '["%s"]' % vp) for vn, vp in want_vars)

    existing = [d for d in ad.drivers if d.data_path == path]
    if len(existing) == 1:
        # ★ 必须用 existing[0],不能直接用上一个循环残留的 d ——
        #   否则打印出来的"旧规格"其实是隔壁那条驱动(它自己是对的),看着像旋钮串了位。
        #   另注:AnimData.drivers.new() 是**追加到末尾**,remove() 会让后续元素前移 ⇒
        #   「第 i 条驱动」这个索引永远不稳定,一律按 data_path 匹配。
        t, e, vs = describe(existing[0])
        vs_sig = sorted((v[0], v[1], v[2], v[3]) for v in vs) if isinstance(vs, list) else vs
        if t == 'SCRIPTED' and e == want_expr and vs_sig == want_sig:
            n_drv_ok += 1
            R("  = %-14s 已符合规格(不重建)" % sock)
            continue
        R("  ~ %-14s 规格不符,原子重建 (旧: type=%s expr=%r vars=%s)" % (sock, t, e, vs))
        ad.drivers.remove(existing[0])
    elif len(existing) > 1:
        R("  ~ %-14s 有 %d 条重复驱动,全部删除后重建" % (sock, len(existing)))
        for d in existing:
            ad.drivers.remove(d)

    d = ad.drivers.new(path)
    d.driver.type = 'SCRIPTED'
    for vn, vp in want_vars:
        v = d.driver.variables.new()
        v.name = vn
        v.type = 'SINGLE_PROP'
        tgt = v.targets[0]
        tgt.id_type = 'OBJECT'      # ★ 必须先 id_type 再 id
        tgt.id = ctrl
        tgt.data_path = '["%s"]' % vp
    d.driver.expression = want_expr
    R("  + %-14s 新建驱动 expr=%r vars=%s" % (sock, want_expr, [v[0] for v in want_vars]))

R("  驱动总数 = %d (其中本规格 %d 条未改动)" % (len(ad.drivers), n_drv_ok))
for d in ad.drivers:
    R("      %-58s %s" % (d.data_path, d.driver.expression))

# ================= 5. 打开合成 + 视口合成器 =================
R("-" * 70)
R("[5] 开关")
if not sc.render.use_compositing:
    sc.render.use_compositing = True
    R("  render.use_compositing: False -> True (★ 这是总闸,关了合成器整条不生效)")
else:
    R("  render.use_compositing 已是 True(总闸开着)")

n_vp = 0
for area in C.screen.areas:
    if area.type != 'VIEW_3D':
        continue
    for sp in area.spaces:
        if sp.type == 'VIEW_3D' and getattr(sp.shading, 'use_compositor', None) != 'ALWAYS':
            sp.shading.use_compositor = 'ALWAYS'
            n_vp += 1
R("  视口合成器设为 ALWAYS 的 3D 视图: %d 个(默认 DISABLED ⇒ 视口里看不到辉光)" % n_vp)

# ================= 6. 活动对象(交付铁律) =================
R("-" * 70)
R("[6] 活动对象")
for o in bpy.data.objects:
    o.select_set(False)
ctrl.select_set(True)
vl.objects.active = ctrl
R("  view_layer.objects.active = %s (属性面板才看得到参数)" % vl.objects.active.name)

# ================= 7. 强刷新 + 行为级验收 =================
R("-" * 70)
R("[7] 强刷新与行为级验收")
force_refresh()

probe_sock, probe_prop = "Threshold", "辉光阈值"
sock = n_gl.inputs[probe_sock]
base = float(sock.default_value)
orig_prop = float(ctrl[probe_prop])
ctrl[probe_prop] = orig_prop + 3.0
force_refresh()
after = float(sock.default_value)
ctrl[probe_prop] = orig_prop
force_refresh()
back = float(sock.default_value)
R("  行为验收(%s): 属性 %.3f -> %.3f 时插座 %.4f -> %.4f ; 还原后 %.4f" % (
    probe_sock, orig_prop, orig_prop + 3.0, base, after, back))
assert abs(after - base) > 1e-6, "驱动没生效:改了属性而插座纹丝不动"
assert abs(back - base) < 1e-6, "还原失败"

sw_sock = n_gl.inputs["Strength"]
sw_orig = float(ctrl["辉光开关"]); st_orig = float(ctrl["辉光强度"])
ctrl["辉光开关"] = 0.0
force_refresh()
strength_off = float(sw_sock.default_value)
ctrl["辉光开关"] = sw_orig
force_refresh()
strength_on = float(sw_sock.default_value)
R("  开关验收: 辉光开关=0 -> Strength=%.4f ; =%.1f -> Strength=%.4f" % (
    strength_off, sw_orig, strength_on))
assert abs(strength_off) < 1e-6, "辉光开关=0 时强度没归零(旁路不成立)"
assert abs(strength_on - st_orig * sw_orig) < 1e-6, "辉光开关=1 时强度不等于乘子结果"

# ================= 8. 结构验收 =================
R("-" * 70)
R("[8] 结构验收")
assert sc.compositing_node_group is ng, "节点组没挂到场景上"
assert n_ou.bl_idname == 'NodeGroupOutput', "终结节点不是 NodeGroupOutput"
assert iface_has_output(), "组没有声明输出插座 ⇒ 合成会被静默旁路"
assert len(links) == 2, "连线数应为 2,实为 %d" % len(links)
for l in links:
    R("      %s.%s -> %s.%s" % (l.from_node.name, l.from_socket.name,
                                l.to_node.name, l.to_socket.name))
io = one_incoming(n_ou, IFACE_SOCKET)
assert len(io) == 1, "合成输出.%s 的入线不是 1 条" % IFACE_SOCKET
assert n_ou.bl_idname == 'NodeGroupOutput'
R("  终结节点 = %s ; 入线来自 %s.%s ; 组输出插座已声明" % (
    n_ou.bl_idname, io[0].from_node.name, io[0].from_socket.name))

R("=" * 70)
R("旋钮清单(空对象 %s,已设为活动对象):" % CTRL_NAME)
for prop, sockn, dflt, smin, smax, var, role, desc in KNOBS:
    hmn, hmx = HARD[prop]
    R("      %-14s = %-6.3f  硬[%g~%g] 软[%g~%g] step=%g  %s" % (
        prop, float(ctrl[prop]), hmn, hmx, smin, smax, STEP, desc))

# --- 可发现性回读:面板里必须真的像滑块,紫色格必须真的带指路牌 ---
bad_ui = []
for prop, sockn, dflt, smin, smax, var, role, desc in KNOBS:
    d = ctrl.id_properties_ui(prop).as_dict()
    hmn, hmx = HARD[prop]
    if abs(d.get("min", 0.0) - hmn) > 1e-9 or abs(d.get("max", 0.0) - hmx) > 1e-9:
        bad_ui.append("%s 硬范围 %s~%s != %g~%g"
                      % (prop, d.get("min"), d.get("max"), hmn, hmx))
    if abs(d.get("step", 1.0) - STEP) > 1e-9:
        bad_ui.append("%s step=%s" % (prop, d.get("step")))
R("  滑块回读: 6 个旋钮全部 min/max/step 就位" if not bad_ui
  else "  ! 滑块回读异常: %s" % bad_ui)

tip = 0
for prop, sockn, dflt, smin, smax, var, role, desc in KNOBS:
    if sockn and sockn in n_gl.inputs and n_gl.inputs[sockn].description:
        tip += 1
tip += sum(1 for s, _ in DIRECT_SOCK if s in n_gl.inputs and n_gl.inputs[s].description)
R("  插座提示: %d 条 ; 眩光节点 label = %r" % (tip, n_gl.label))
assert not bad_ui, "滑块 UI 回读不合格: %s" % bad_ui

R("眩光 Type = %r  (可手改:Bloom / Fog Glow / Streaks / Ghosts / Simple Star / Kernel)"
  % n_gl.inputs["Type"].default_value)
R("BUILD_GLOW_OK")
