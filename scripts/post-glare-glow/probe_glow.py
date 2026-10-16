# -*- coding: utf-8 -*-
# 合成器后期辉光(Glare)—— 只读侦察(经 9877 桥执行)
# ===========================================================================
# 不改任何数据。先跑这个,再决定要不要 build / verify / maintain。
#
# 它会回答 4 个问题:
#   Q1 合成器现在是什么状态?(有没有节点组、终结节点是什么、组输出插座声明了没)
#   Q2 是不是「旧配方」(终结节点 = CompositorNodeConvertToDisplay,或还挂着「转显示」节点)?
#   Q3 空对象「辉光控制」在不在、6 个旋钮键值多少?
#   Q4 驱动器有几条、指向谁、是不是已经被"改变量/改名"弄成 is_valid=False 的僵死状态?
#
# ★ 本场景对象数上万(实测 10630)⇒ 只打印**计数**,绝不 dump 全量对象列表
#   (全量列表会把桥的返回撑爆到几百 KB)。
import bpy

# ═══ 配置(换工程改这里) ═══
GROUP_NAME = "后期辉光"
CTRL_NAME  = "辉光控制"
KNOB_NAMES = ("辉光开关", "辉光强度", "辉光阈值", "辉光尺寸", "辉光饱和度", "辉光最大亮度")
LEGACY_NODE_NAMES = ("转显示",)   # 旧配方遗留的错误终结节点名
LEGACY_TERMINAL_TYPES = ("CompositorNodeConvertToDisplay",)
GLARE_TYPE_CANDIDATES = ("Fog Glow", "Bloom", "Streaks", "Ghosts", "Simple Star", "Kernel")
GLARE_QUALITY_CANDIDATES = ("Low", "Medium", "High")
# ═════════════════════════

C, D = bpy.context, bpy.data
sc = C.scene
r = sc.render

print("=== [Q0] 场景与渲染设置 ===")
print("文件=%r" % D.filepath)
print("引擎=%r  Cycles.device=%r  分辨率=%dx%d@%d%%  帧=%d  fps=%s  色彩变换=%r"
      % (r.engine, getattr(sc.cycles, "device", None),
         r.resolution_x, r.resolution_y, r.resolution_percentage,
         sc.frame_current, r.fps, sc.view_settings.view_transform))
print("Cycles: samples=%s denoise=%s adaptive=%s | persistent_data=%s"
      % (sc.cycles.samples, sc.cycles.use_denoising, sc.cycles.use_adaptive_sampling,
         r.use_persistent_data))
print("★ 大尺寸眩光 + 低采样 = 噪点放大器:先把渲染弄干净再调大「辉光尺寸」")

print("=== [Q0b] 规模(只报计数) ===")
print("objects=%d  materials=%d  images=%d  node_groups=%d  collections=%d  scenes=%d"
      % (len(D.objects), len(D.materials), len(D.images), len(D.node_groups),
         len(D.collections), len(D.scenes)))
try:
    print("合成器类可用性: Glare=%s RLayers=%s NodeGroupOutput=%s ConvertToDisplay=%s"
          % (hasattr(bpy.types, "CompositorNodeGlare"),
             hasattr(bpy.types, "CompositorNodeRLayers"),
             hasattr(bpy.types, "NodeGroupOutput"),
             hasattr(bpy.types, "CompositorNodeConvertToDisplay")))
except Exception as e:
    print("  探测合成器类失败: %r" % (e,))

print("=== [Q1] 合成器状态 ===")
print("render.use_compositing = %s  (★ 总闸,关掉后极端眩光也 0 差异)" % r.use_compositing)
ng = getattr(sc, "compositing_node_group", None)
print("scene.compositing_node_group = %r" % (ng.name if ng else None))
print("  注:scene.node_tree 在 5.0 已移除;scene.use_nodes 恒 True 且设了没用")
print("D.node_groups(CompositorNodeTree)=%r"
      % [(g.name, len(g.nodes), len(g.links)) for g in D.node_groups
         if g.bl_idname == 'CompositorNodeTree'])

terminal_types, iface = [], []
if ng is None:
    print("!! 场景没挂合成器节点组 ⇒ 合成器整条不生效")
else:
    print("  节点 %d 个:" % len(ng.nodes))
    for i, nd in enumerate(ng.nodes):
        print("    [%d] %-14s type=%-28s label=%r muted=%s"
              % (i, nd.name, nd.bl_idname, getattr(nd, "label", ""), nd.mute))
    print("  连线 %d 条:" % len(ng.links))
    for l in ng.links:
        print("        %s.%s -> %s.%s"
              % (l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name))
    iface = [(it.name, it.in_out) for it in ng.interface.items_tree
             if it.item_type == 'SOCKET']
    print("  interface 插座 = %r   (★ 缺 OUTPUT 插座 ⇒ 整条合成被静默旁路)" % iface)
    terminal_types = [nd.bl_idname for nd in ng.nodes
                      if nd.bl_idname in ("NodeGroupOutput",) + LEGACY_TERMINAL_TYPES]
    print("  终结类节点 = %r" % terminal_types)

print("=== [Q2] 是不是旧配方?(决定要不要重建) ===")
legacy_hits = []
if ng is not None:
    legacy_hits += [nd.name for nd in ng.nodes if nd.name in LEGACY_NODE_NAMES]
    legacy_hits += [nd.name for nd in ng.nodes if nd.bl_idname in LEGACY_TERMINAL_TYPES]
verdict = []
if ng is None:
    verdict.append("没挂节点组 ⇒ 需要 build")
else:
    if legacy_hits:
        verdict.append("发现旧配方遗留节点 %r ⇒ 需要 build(会删掉)" % legacy_hits)
    if 'NodeGroupOutput' not in terminal_types:
        verdict.append("终结节点不是 NodeGroupOutput(%r)⇒ 5.x 下会被静默旁路,需要 build"
                       % terminal_types)
    if not any(io == 'OUTPUT' for _, io in iface):
        verdict.append("组没有声明 OUTPUT 插座 ⇒ 合成被静默旁路,需要 build")
    if len(ng.links) != 2:
        verdict.append("连线数 %d != 2 ⇒ 结构不完整,需要 build" % len(ng.links))
if not verdict:
    verdict.append("结构已是目标状态 ⇒ build 会走「跳过重接(幂等)」")
for v in verdict:
    print("  - %s" % v)

print("=== [Q3] 空对象「%s」与旋钮 ===" % CTRL_NAME)
ctrl = D.objects.get(CTRL_NAME)
if ctrl is None:
    print("!! 找不到 %r ⇒ build 会新建(位置 %r)" % (CTRL_NAME, (0.0, 0.0, 0.0)))
else:
    print("type=%s  users=%d  hide_viewport=%s hide_render=%s  animation_data=%r"
          % (ctrl.type, ctrl.users, ctrl.hide_viewport, ctrl.hide_render, ctrl.animation_data))
    for k in sorted(ctrl.keys()):
        if k.startswith("_"):
            continue
        try:
            d = ctrl.id_properties_ui(k).as_dict()
        except Exception:
            d = {}
        print("  %-14s = %-10s  min=%-9s max=%-9s soft=[%s~%s] step=%s"
              % (k, ctrl[k], d.get("min"), d.get("max"),
                 d.get("soft_min"), d.get("soft_max"), d.get("step")))
    missing = [k for k in KNOB_NAMES if k not in ctrl.keys()]
    if missing:
        print("  !! 缺旋钮: %r ⇒ build 会补齐" % missing)
    print("  ★ 交付铁律:必须把该对象设为 view_layer.objects.active —— "
          "Blender 物体属性面板**只显示活动对象**")
    print("  当前活动对象 = %r" % (C.view_layer.objects.active.name
                                  if C.view_layer.objects.active else None))

print("=== [Q4] 驱动器 ===")
if ng is None:
    print("  (没有节点组)")
else:
    ad = ng.animation_data
    if ad is None or not ad.drivers:
        print("  !! 节点组上没有驱动器 ⇒ 旋钮不会生效,需要 build")
    else:
        print("  节点组 %r 上有 %d 条驱动器:" % (ng.name, len(ad.drivers)))
        for d in ad.drivers:
            vs = []
            for v in d.driver.variables:
                tg = v.targets[0] if len(v.targets) else None
                vs.append("%s=(%s: %s%s)" % (
                    v.name, v.type,
                    tg.id.name if (tg is not None and tg.id) else None,
                    tg.data_path if tg is not None else None))
            print("    %-58s type=%-9s expr=%-12r is_valid=%s"
                  % (d.data_path, d.driver.type, d.driver.expression, d.driver.is_valid))
            for s in vs:
                print("        %s" % s)
        bad = [d.data_path for d in ad.drivers if not d.driver.is_valid]
        print("  ★ is_valid=False 的条数 = %d %s"
              % (len(bad), ("-> %r" % bad) if bad else "(健康)"))
        print("  注:驱动挂在**合成器节点树**上时,脚本里读插座值必须手工 "
              "ng.update_tag() + 依赖图更新,否则读到**陈旧值**;"
              "但**渲染路径会自己求值**。")

print("=== [Q5] 眩光节点插座(现状 + 候选) ===")
glare = None
if ng is not None:
    for nd in ng.nodes:
        if nd.bl_idname == 'CompositorNodeGlare':
            glare = nd
            break
if glare is None:
    print("  (还没有眩光节点)")
else:
    _skip = ("NodeSocketVirtual",)
    print("  输入 %d 个:" % len(glare.inputs))
    for s in glare.inputs:
        if s.bl_idname in _skip:
            continue
        print("    %-20s type=%-22s value=%-22r driven=%s"
              % (s.name, s.bl_idname, s.default_value,
                 "是(紫色)" if glare.id_data and glare.id_data.animation_data and
                 any(d.data_path.endswith('["%s"].default_value' % s.name)
                     for d in glare.id_data.animation_data.drivers) else "否"))
    print("  输出 %d 个: %r" % (len(glare.outputs), [s.name for s in glare.outputs]))
    print("  ★ Type 候选(标题式字符串,写全大写会 TypeError): %r" % (GLARE_TYPE_CANDIDATES,))
    print("  ★ Quality 候选: %r" % (GLARE_QUALITY_CANDIDATES,))
    print("  ★ Size/Strength/Saturation/Smoothness 的 subtype=Factor ⇒ 量程 0-1"
          "(旧配方的 Size=12 已失效)")
    print("  ★ NodeSocketMenu 没有 .enum_items,枚举只能试写")
    print("  ★ NodeSocket.description 硬上限 63 字节;NodeSocket.label 只读")

print("PROBE_GLOW_OK")
