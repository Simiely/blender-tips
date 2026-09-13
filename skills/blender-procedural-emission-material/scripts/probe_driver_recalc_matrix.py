# NOTE: 路径为模板占位 --- 使用前把 WORKDIR/OUTDIR 改成本机实际的「脚本/输出目录」。
#       （桥执行环境里 __file__ 不可靠，因此显式定义。）
# probe_36.py — 【干跑实验】驱动重算到底要 tag 谁？区分两种驱动写法
#   驱动 A：表达式直接调 driver_namespace 函数（无变量）→ 依赖图不知道它读了控制物体
#   驱动 B：表达式用 SINGLE_PROP 变量指向控制物体 .["p"] → 依赖图有一条到 ctrl 的边
# 全部在临时对象/材质上做，用完删除并校验无残留。
import bpy, json

CT = "__DRVPROBE_CTRL__"
MT = "__DRVPROBE_MAT__"
CTX = "p"

# ---------- 清理可能的残留 ----------
for n in (CT,):
    o = bpy.data.objects.get(n)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
m = bpy.data.materials.get(MT)
if m:
    bpy.data.materials.remove(m, do_unlink=True)

sc = bpy.context.scene
ctrl = bpy.data.objects.new(CT, None)
sc.collection.objects.link(ctrl)
ctrl[CTX] = 0.0


def probe_val():
    c = bpy.data.objects.get(CT)
    return float(c.get(CTX, 0.0)) if c else 0.0


bpy.app.driver_namespace["__drvprobe_val"] = probe_val

mat = bpy.data.materials.new(MT)
mat.use_nodes = True
# 必须把材质挂到一个真实物体上，否则它不在依赖图里，驱动根本不会被求值
me = bpy.data.meshes.new("__DRVPROBE_MESH__")
ob = bpy.data.objects.new("__DRVPROBE_OBJ__", me)
sc.collection.objects.link(ob)
ob.data.materials.append(mat)
nt = mat.node_tree
va = nt.nodes.new('ShaderNodeValue')
va.name = va.label = "A"
va.location = (-200, 0)
vb = nt.nodes.new('ShaderNodeValue')
vb.name = vb.label = "B"
vb.location = (-200, -150)

# 驱动 A：无变量，纯命名空间函数
fa = va.outputs[0].driver_add('default_value')
da = fa.driver
da.type = 'SCRIPTED'
da.expression = "__drvprobe_val()"

# 驱动 B：SINGLE_PROP 变量指向控制物体的自定义属性
fb = vb.outputs[0].driver_add('default_value')
db = fb.driver
db.type = 'SCRIPTED'
db.expression = "v"
v = db.variables.new()
v.name = 'v'
v.type = 'SINGLE_PROP'
v.targets[0].id = ctrl
v.targets[0].data_path = '["%s"]' % CTX

fa.update(); fb.update()
bpy.context.view_layer.update()


def read():
    return (round(va.outputs[0].default_value, 4), round(vb.outputs[0].default_value, 4))


def strat_none():
    pass


def strat_ctl():
    ctrl.update_tag()


def strat_mat():
    mat.update_tag()


def strat_nt():
    nt.update_tag()


def strat_mat_nt():
    mat.update_tag(); nt.update_tag()


def strat_all():
    ctrl.update_tag(); mat.update_tag(); nt.update_tag()


def strat_dg():
    bpy.context.evaluated_depsgraph_get().update()


def strat_frame():
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)


STRATS = [
    ("(不 tag)", strat_none),
    ("ctl.update_tag()", strat_ctl),
    ("mat.update_tag()", strat_mat),
    ("nt.update_tag()", strat_nt),
    ("mat+nt.update_tag()", strat_mat_nt),
    ("ctl+mat+nt.update_tag()", strat_all),
    ("depsgraph.update()", strat_dg),
    ("frame_set(当前帧)", strat_frame),
]

rows = []
for label, fn in STRATS:
    ctrl[CTX] = 0.0
    fn(); bpy.context.view_layer.update()
    a0, b0 = read()
    ctrl[CTX] = 7.0
    fn(); bpy.context.view_layer.update()
    a1, b1 = read()
    rows.append({
        "tag": label,
        "A_无变量命名空间驱动": ("✅ %s→%s" % (a0, a1)) if (a0 == 0.0 and a1 == 7.0) else ("❌ %s→%s" % (a0, a1)),
        "B_SINGLE_PROP变量驱动": ("✅ %s→%s" % (b0, b1)) if (b0 == 0.0 and b1 == 7.0) else ("❌ %s→%s" % (b0, b1)),
    })

# ---------- 清理 ----------
ctrl[CTX] = 0.0
bpy.data.materials.remove(mat, do_unlink=True)
bpy.data.objects.remove(ctrl, do_unlink=True)
bpy.data.objects.remove(ob, do_unlink=True)
if me.users == 0:
    bpy.data.meshes.remove(me)
del bpy.app.driver_namespace["__drvprobe_val"]

print("P36_BEGIN")
print(json.dumps({
    "结论表": rows,
    "残留对象": [o.name for o in bpy.data.objects if o.name.startswith("__DRVPROBE")],
    "残留网格": [x.name for x in bpy.data.meshes if x.name.startswith("__DRVPROBE")],
    "残留材质": [x.name for x in bpy.data.materials if x.name.startswith("__DRVPROBE")],
    "残留命名空间": [k for k in bpy.app.driver_namespace if k.startswith("__drvprobe")],
    "对象总数": len(bpy.data.objects),
}, ensure_ascii=False, indent=1))
print("P36_END")
