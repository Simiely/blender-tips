# verify_noise_scroll.py —— 独立核验「噪波滚动发光」标准链（另起一次请求 / 全新取引用）
#
# 注意：驱动真值必须从【求值后的依赖图】读，直接读原 datablock 会看到未求值的旧值
#       （5.2 实测：只读原值会一直显示工厂默认，误判成"驱动没生效"）。
import bpy, json

WORKDIR = r"<WORKDIR>"  # <<< 改成你的 blender_control 目录

TARGET_OBJ = "水晶走廊_竖向灯.001"
NEW_MAT = "竖向灯001_噪波滚动发光"
OLD_MAT = "灯光光.004"
CTRL_NAME = "竖向灯001_噪波控制"
PANEL_TEXT = "噪波滚动控制.py"
SIBLINGS = ("水晶走廊_竖向灯.002", "水晶走廊_竖向灯.003")

CHECKS = []


def ck(name, ok, detail=None):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})


obj = bpy.data.objects.get(TARGET_OBJ)
mat = bpy.data.materials.get(NEW_MAT)
old = bpy.data.materials.get(OLD_MAT)
ctrl = bpy.data.objects.get(CTRL_NAME)

ck("对象存在 " + TARGET_OBJ, obj is not None)
ck("材质存在 " + NEW_MAT, mat is not None)
ck("控制器存在 " + CTRL_NAME, ctrl is not None)
ck("原材质仍存在 " + OLD_MAT, old is not None)
if obj is None or mat is None or ctrl is None:
    print("VERIFY_BEGIN")
    print(json.dumps({"checks": CHECKS, "abort": True}, ensure_ascii=False, indent=1))
    print("VERIFY_END")
    raise SystemExit

nt = mat.node_tree
nodes = {n.name: n for n in nt.nodes}
has = lambda nm: nm in nodes

# ---------------- 1) 结构 ----------------
ck("slot0 == 新材质", bool(obj.material_slots) and obj.material_slots[0].material is mat)
ck("节点: 纹理坐标", has("纹理坐标"))
ck("节点: 滚动映射", has("滚动映射"))
ck("节点: 噪波纹理", has("噪波纹理"))
ck("节点: 对比度(ColorRamp)", has("对比度") and nodes["对比度"].bl_idname == 'ShaderNodeValToRGB')
ck("节点: 反色(MapRange)", has("反色") and nodes["反色"].bl_idname == 'ShaderNodeMapRange')
ck("节点: 发光强度(Math)", has("发光强度") and nodes["发光强度"].bl_idname == 'ShaderNodeMath')
ck("节点: 原理化 BSDF", any(n.bl_idname == 'ShaderNodeBsdfPrincipled' for n in nt.nodes))
# ★ v3：MapRange 只允许有 1 个，且用途是「反色」（不是 v1 那种拿它当对比度窗口的错误用法）
_mrs = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeMapRange']
ck("MapRange 有且仅有 1 个", len(_mrs) == 1, [n.name for n in _mrs])
ck("该 MapRange 命名为 反色", bool(_mrs) and _mrs[0].name == "反色")
ck("该 MapRange 是 FLOAT / LINEAR / clamp",
   bool(_mrs) and _mrs[0].data_type == 'FLOAT' and _mrs[0].interpolation_type == 'LINEAR'
   and bool(_mrs[0].clamp))
ck("无 Separate/Combine 残留",
   not any(n.bl_idname in ('ShaderNodeSeparateXYZ', 'ShaderNodeCombineXYZ') for n in nt.nodes))
ck("无 Z滚动 Math 残留", "Z滚动" not in nodes)


def _vin(node, name):
    for s in node.inputs:
        if s.name == name and s.type == 'VALUE':
            return s
    return None


ck("反色 From Min/Max 固定 0 / 1",
   bool(_mrs) and round(_vin(_mrs[0], 'From Min').default_value, 6) == 0.0
   and round(_vin(_mrs[0], 'From Max').default_value, 6) == 1.0)

tc = nodes.get("纹理坐标")
mp = nodes.get("滚动映射")
noise = nodes.get("噪波纹理")
ramp = nodes.get("对比度")
inv = nodes.get("反色")
mul = nodes.get("发光强度")

ck("纹理坐标.Object == 控制器", tc is not None and tc.object is ctrl)
ck("噪波为 4D", noise is not None and noise.noise_dimensions == '4D')
ck("滚动映射 = POINT 类型", mp is not None and mp.vector_type == 'POINT')
ck("ColorRamp 插值 LINEAR", ramp is not None and ramp.color_ramp.interpolation == 'LINEAR')
ck("发光强度 = MULTIPLY", mul is not None and mul.operation == 'MULTIPLY')


def linked(a, an, b, bn):
    A, B = nodes.get(a), nodes.get(b)
    if A is None or B is None:
        return False
    return any(l.from_node.name == a and l.from_socket.name == an and
               l.to_node.name == b and l.to_socket.name == bn for l in nt.links)


ck("连线 纹理坐标.Object → 滚动映射.Vector", linked("纹理坐标", "Object", "滚动映射", "Vector"))
ck("连线 滚动映射.Vector → 噪波纹理.Vector", linked("滚动映射", "Vector", "噪波纹理", "Vector"))
ck("连线 噪波纹理.Fac → 对比度.Fac", linked("噪波纹理", "Factor", "对比度", "Factor"))
ck("连线 对比度.Color → 反色.Value", linked("对比度", "Color", "反色", "Value"))
ck("连线 反色.Result → 发光强度.Value", linked("反色", "Result", "发光强度", "Value"))
ck("反色夹在 对比度 与 发光强度 之间（无旁路）",
   not any(l.from_node.name == "对比度" and l.to_node.name == "发光强度" for l in nt.links))
ck("连线 发光强度 → BSDF.Emission Strength",
   any(l.from_node.name == "发光强度" and l.to_node.bl_idname == 'ShaderNodeBsdfPrincipled'
       and l.to_socket.name == 'Emission Strength' for l in nt.links))
ck("连线 BSDF → 材质输出",
   any(l.from_node.bl_idname == 'ShaderNodeBsdfPrincipled' and
       l.to_node.bl_idname == 'ShaderNodeOutputMaterial' for l in nt.links))
ck("连线总数 == 7", len(nt.links) == 7, len(nt.links))

# ---------------- 2) 驱动 ----------------
drv_paths = {(d.data_path, d.array_index) for d in (nt.animation_data.drivers if nt.animation_data else [])}
want = {
    ('nodes["滚动映射"].inputs[1].default_value', 2),
    ('nodes["噪波纹理"].inputs[2].default_value', 0),
    ('nodes["噪波纹理"].inputs[1].default_value', 0),
    ('nodes["对比度"].color_ramp.elements[0].position', 0),
    ('nodes["对比度"].color_ramp.elements[1].position', 0),
    ('nodes["发光强度"].inputs[1].default_value', 0),
    ('nodes["反色"].inputs[3].default_value', 0),          # To Min (标量第 4 个插槽)
    ('nodes["反色"].inputs[4].default_value', 0),          # To Max
}
ck("驱动路径齐全 (8 条)", want <= drv_paths, sorted("%s[%d]" % p for p in drv_paths))
ck("驱动数 == 8", len(drv_paths) == 8, len(drv_paths))
ck("反色 To Min 驱动表达式 == iv",
   any(d.data_path == 'nodes["反色"].inputs[3].default_value' and d.driver.expression == 'iv'
       for d in nt.animation_data.drivers),
   [d.driver.expression for d in nt.animation_data.drivers
    if d.data_path.startswith('nodes["反色"]')])
ck("反色 To Max 驱动表达式 == 1.0 - iv",
   any(d.data_path == 'nodes["反色"].inputs[4].default_value' and d.driver.expression == '1.0 - iv'
       for d in nt.animation_data.drivers))
ck("滚动驱动绑定 fr=SINGLE_PROP(scene.frame_current)",
   any(v.name == 'fr' and v.type == 'SINGLE_PROP' and v.targets[0].data_path == 'frame_current'
       and v.targets[0].id is bpy.context.scene
       for d in nt.animation_data.drivers for v in d.driver.variables))
ck("无残留指向已删节点的驱动",
   not any(("分离XYZ" in p[0] or "合并XYZ" in p[0] or "Z滚动" in p[0] or "MapRange" in p[0])
           for p in drv_paths))

# ---------------- 2b) 自动刷新机制（用户实际报的坑）----------------
# 改自定义属性【本身】不会让驱动重算（AR-1 实测：改完立刻读仍是旧值）。
# 所以每个控件都必须有一条【已声明的依赖边】(SINGLE_PROP 变量指向 ctrl 的 ID 属性)，
# 外加一个不依赖 UI 的看门狗定时器兜底。
VAR_OF = {"噪波密度": "dn", "噪波种子": "sd", "Z向速度": "sp", "噪波对比度": "ct",
          "亮区阈值": "tt", "发光强度": "st", "反色": "iv"}
bound = {}
for _d in nt.animation_data.drivers:
    for _v in _d.driver.variables:
        if _v.type == 'SINGLE_PROP' and _v.targets[0].id is ctrl:
            bound[_v.name] = _v.targets[0].data_path
for _prop, _vn in VAR_OF.items():
    ck("控件 %s 有声明依赖边 (%s -> ctrl[\"%s\"])" % (_prop, _vn, _prop),
       bound.get(_vn) == '["%s"]' % _prop, bound.get(_vn))
ck("驱动表达式已全部改用变量（不再调命名空间函数）",
   not any("nz_" in _d.driver.expression for _d in nt.animation_data.drivers),
   [_d.driver.expression for _d in nt.animation_data.drivers])
ck("对比度上下界由表达式 max()/min() 夹取",
   any(_d.driver.expression.startswith("max(") for _d in nt.animation_data.drivers) and
   any(_d.driver.expression.startswith("min(") for _d in nt.animation_data.drivers),
   [_d.driver.expression for _d in nt.animation_data.drivers])
try:
    _txt = bpy.data.texts.get(PANEL_TEXT)
    _ns = {"__name__": "builtins"}
    exec(compile(_txt.as_string(), PANEL_TEXT, 'exec'), _ns)      # register() 幂等
    ck("看门狗 _watch 已注册为定时器", bool(bpy.app.timers.is_registered(_ns["_watch"])))
    ck("看门狗周期为有限值 (秒)", isinstance(_ns.get("_TICK"), float) and 0 < _ns["_TICK"] <= 2.0,
       _ns.get("_TICK"))
except Exception as _e:
    ck("看门狗 _watch 已注册为定时器", False, repr(_e))

# ---------------- 3) 命名空间 / 面板 / 原材质 ----------------
for f in ("nz_density", "nz_seed", "nz_z_speed", "nz_contrast", "nz_strength",
          "nz_invert", "nz_c_lo", "nz_c_hi"):
    ck("命名空间函数 %s" % f, f in bpy.app.driver_namespace and callable(bpy.app.driver_namespace[f]))
ck("面板类已注册", hasattr(bpy.types, "NOISE_SCROLL_PT_controls"))
txt = bpy.data.texts.get(PANEL_TEXT)
ck("文本块 %s 存在" % PANEL_TEXT, txt is not None)
ck("文本块 use_module=True", txt is not None and txt.use_module)
ck("文本块 PROPS 含新控件 反色",
   txt is not None and '"反色"' in txt.as_string())
ck("文本块 PROPS 含新控件 亮区阈值",
   txt is not None and '"亮区阈值"' in txt.as_string())
ck("原材质 fake_user 已设", old is not None and old.use_fake_user)
ck("原材质节点树未被动过",
   old is not None and [n.name for n in old.node_tree.nodes] == ["原理化 BSDF", "材质输出"],
   [n.name for n in old.node_tree.nodes] if old else None)

# ---------------- 4) 驱动真值实测 ----------------
DEF = {"噪波密度": 2.0, "噪波种子": 0.0, "Z向速度": 0.02, "噪波对比度": 5.0,
       "亮区阈值": 0.5, "发光强度": 5.0, "反色": 0.0}
KEYS = tuple(DEF.keys())
ORIG_FRAME = bpy.context.scene.frame_current
# ★ 核验脚本会反复改控件，跑完必须【复原成跑之前的值】，不能硬写成默认值
#   （用户可能正在 UI 里调参，硬写默认会抹掉他的工作）。
ORIG = {}
for _k in KEYS:
    try:
        ORIG[_k] = float(ctrl[_k])
    except Exception:
        ORIG[_k] = float(DEF[_k])


def apply(**kw):
    for k, v in kw.items():
        ctrl[k] = float(v)
    ctrl.update_tag()
    mat.update_tag()
    nt.update_tag()
    bpy.context.view_layer.update()


def snap():
    dg = bpy.context.evaluated_depsgraph_get()
    et = mat.evaluated_get(dg).node_tree
    n = {x.name: x for x in et.nodes}
    pb = [n[k] for k in n if n[k].bl_idname == 'ShaderNodeBsdfPrincipled'][0]

    def ev(nm, sock):
        for s in n[nm].inputs:
            if s.name == sock and s.type == 'VALUE':
                return s
        return None

    return {
        "mapZ": round(n["滚动映射"].inputs[1].default_value[2], 4),
        "scale": round(n["噪波纹理"].inputs[2].default_value, 4),
        "w": round(n["噪波纹理"].inputs[1].default_value, 3),
        "ramp0": round(n["对比度"].color_ramp.elements[0].position, 4),
        "ramp1": round(n["对比度"].color_ramp.elements[1].position, 4),
        "strength": round(n["发光强度"].inputs[1].default_value, 3),
        "inv_min": round(ev("反色", 'To Min').default_value, 4),
        "inv_max": round(ev("反色", 'To Max').default_value, 4),
        "emission_linked": bool(pb.inputs['Emission Strength'].is_linked),
        "emission_raw": round(pb.inputs['Emission Strength'].default_value, 4),
    }


bpy.context.scene.frame_set(ORIG_FRAME)
apply(**ORIG)
SNAP_ORIG = snap()                       # ★ 核验前的快照，收尾要逐字段比回来

bpy.context.scene.frame_set(1)
apply(**DEF)
s = snap()
ck("默认: 密度2 → Scale 2.0", s["scale"] == 2.0, s["scale"])
ck("默认: 种子0 → W 0.0", s["w"] == 0.0, s["w"])
ck("默认: 对比度5 → 色标 0.4 / 0.6", (s["ramp0"], s["ramp1"]) == (0.4, 0.6), (s["ramp0"], s["ramp1"]))
ck("默认: 强度 → 5.0", s["strength"] == 5.0, s["strength"])
ck("默认: 反色0 → To Min/To Max = 0 / 1 (恒等映射)", (s["inv_min"], s["inv_max"]) == (0.0, 1.0),
   (s["inv_min"], s["inv_max"]))
ck("默认: f1 × 速度0.02 → Z滚动 0.02", s["mapZ"] == 0.02, s["mapZ"])
ck("BSDF.Emission Strength 由连线提供数值 (插槽 default_value 被忽略)",
   s["emission_linked"] is True, "linked=%s raw=%s" % (s["emission_linked"], s["emission_raw"]))

apply(噪波密度=3.0)
ck("密度 2→3 → Scale 3.0", snap()["scale"] == 3.0, snap()["scale"])
apply(噪波密度=2.0)

apply(噪波种子=7.0)
ck("种子 0→7 → W 70.0 (7×10)", snap()["w"] == 70.0, snap()["w"])
apply(噪波种子=0.0)

apply(噪波对比度=10.0)
s = snap()
ck("对比度 5→10 → 色标 0.45 / 0.55", (s["ramp0"], s["ramp1"]) == (0.45, 0.55), (s["ramp0"], s["ramp1"]))
apply(噪波对比度=2.0)
s = snap()
ck("对比度 5→2 → 色标 0.25 / 0.75", (s["ramp0"], s["ramp1"]) == (0.25, 0.75), (s["ramp0"], s["ramp1"]))
apply(噪波对比度=0.5)
s = snap()
ck("对比度 <1 被夹到 1.0 → 色标 0.0 / 1.0 (直通)", (s["ramp0"], s["ramp1"]) == (0.0, 1.0),
   (s["ramp0"], s["ramp1"]))
apply(噪波对比度=5.0)

# ---- 亮区阈值（v4 新控件）：窗口中心随 T 搬家，默认 0.5 = 与 v3 完全一致 ----
apply(亮区阈值=0.7, 噪波对比度=10.0)
s = snap()
ck("阈值 0.5→0.7 (c=10) → 色标 0.65 / 0.75 (窗口搬到分布顶部=黑底白点)",
   (s["ramp0"], s["ramp1"]) == (0.65, 0.75), (s["ramp0"], s["ramp1"]))
apply(亮区阈值=0.9, 噪波对比度=100.0)
s = snap()
ck("阈值 0.9 + 对比度 100 → 色标 0.895 / 0.905 (近似硬阈值，白点极稀疏)",
   (s["ramp0"], s["ramp1"]) == (0.895, 0.905), (s["ramp0"], s["ramp1"]))
apply(亮区阈值=0.2, 噪波对比度=5.0)
s = snap()
ck("阈值 0.2 (c=5) → 色标 0.1 / 0.3 (窗口下移=白多黑少)", (s["ramp0"], s["ramp1"]) == (0.1, 0.3),
   (s["ramp0"], s["ramp1"]))
apply(亮区阈值=0.5, 噪波对比度=5.0)

# ---- 反色（v3 新控件）：To Min/To Max 必须随 iv 对调 ----
apply(反色=1.0)
s = snap()
ck("反色 0→1 → To Min/To Max 对调为 1 / 0 (黑白互换)", (s["inv_min"], s["inv_max"]) == (1.0, 0.0),
   (s["inv_min"], s["inv_max"]))
apply(反色=0.5)
s = snap()
ck("反色 0.5 → To Min/To Max 均为 0.5 (对半混合)", (s["inv_min"], s["inv_max"]) == (0.5, 0.5),
   (s["inv_min"], s["inv_max"]))
apply(反色=0.0)
s = snap()
ck("反色 1→0 → To Min/To Max 复原为 0 / 1 (恒等)", (s["inv_min"], s["inv_max"]) == (0.0, 1.0),
   (s["inv_min"], s["inv_max"]))

apply(发光强度=12.0)
ck("强度 5→12 → 12.0", snap()["strength"] == 12.0, snap()["strength"])
apply(发光强度=5.0)

bpy.context.scene.frame_set(60)
apply()
ck("f60 × 0.02 → Z滚动 1.2 (滚动真的动)", snap()["mapZ"] == 1.2, snap()["mapZ"])
apply(Z向速度=-0.05)
bpy.context.scene.frame_set(60)
apply(Z向速度=-0.05)
ck("负速度 -0.05 @f60 → Z滚动 -3.0 (反向)", snap()["mapZ"] == -3.0, snap()["mapZ"])

bpy.context.scene.frame_set(ORIG_FRAME)
apply(**ORIG)
SNAP_BACK = snap()
ck("已逐字段复原成核验前的原始状态（不硬写默认值，别抹掉用户调好的参数）",
   SNAP_BACK == SNAP_ORIG, {"before": SNAP_ORIG, "after": SNAP_BACK})

# ---------------- 5) 未越界 ----------------
ck("目标面数仍 84208", len(obj.data.polygons) == 84208, len(obj.data.polygons))
for sb in SIBLINGS:
    o = bpy.data.objects.get(sb)
    cur = (o.material_slots[0].material.name
           if o and o.material_slots and o.material_slots[0].material else None)
    ck("兄弟对象 %s 未受影响 (材质=%s)" % (sb, cur), o is not None and cur != NEW_MAT)
bak = [o.name for o in bpy.data.objects if o.name.startswith("__BAK__")]
ck("无 __BAK__ 残留", not bak, bak)
ck("控制器仍在世界原点 / 无旋转 / scale=1",
   tuple(round(x, 6) for x in ctrl.location) == (0.0, 0.0, 0.0)
   and tuple(round(x, 6) for x in ctrl.rotation_euler) == (0.0, 0.0, 0.0)
   and tuple(round(x, 6) for x in ctrl.scale) == (1.0, 1.0, 1.0))
ck("控制器 7 个中文键齐全（含 反色 / 亮区阈值）",
   set(ctrl.keys()) >= {"噪波密度", "噪波种子", "Z向速度", "噪波对比度", "亮区阈值",
                        "发光强度", "反色"},
   [k for k in ctrl.keys() if not k.startswith("_")])
ck("无英文键残留", not any(k in ctrl.keys() for k in
                          ("noise_density", "noise_seed", "z_speed", "noise_contrast",
                           "glow_strength", "invert")))
ck("反色 属性带 UI 元数据 (min0/max1/step1/precision0)",
   (lambda u: u.get("min") == 0.0 and u.get("max") == 1.0 and u.get("step") == 1.0
    and u.get("precision") == 0)(ctrl.id_properties_ui("反色").as_dict()),
   ctrl.id_properties_ui("反色").as_dict())

npass = sum(1 for c in CHECKS if c["ok"])
out = {"checks": CHECKS, "passed": npass, "total": len(CHECKS),
       "failed": [c["name"] for c in CHECKS if not c["ok"]],
       "scene_frame_after": bpy.context.scene.frame_current,
       "object_count": len(bpy.data.objects), "material_count": len(bpy.data.materials)}
with open(WORKDIR + r"\verify_noise_scroll.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("VERIFY_BEGIN")
print(json.dumps(out, ensure_ascii=False, indent=1))
print("VERIFY_END")
