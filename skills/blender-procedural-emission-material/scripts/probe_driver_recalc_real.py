# NOTE: 路径为模板占位 --- 使用前把 WORKDIR/OUTDIR 改成本机实际的「脚本/输出目录」。
#       （桥执行环境里 __file__ 不可靠，因此显式定义。）
# probe_37.py — 在【真实材质】上逐条复测「改控件属性后如何触发驱动重算」
# 只读试探：每组策略前后都把控件还原，最后恢复默认值。
import bpy, json

CTRL = "竖向灯001_噪波控制"
MAT = "竖向灯001_噪波滚动发光"
KEY = "noise_density"
DEF = 2.0
PROBE = 5.0

ctrl = bpy.data.objects[CTRL]
mat = bpy.data.materials[MAT]
nt = mat.node_tree
noise = nt.nodes["噪波纹理"]


def scale():
    return round(noise.inputs[2].default_value, 4)


def s_none():
    pass


def s_ctl():
    ctrl.update_tag()


def s_mat():
    mat.update_tag()


def s_nt():
    nt.update_tag()


def s_mat_nt():
    mat.update_tag(); nt.update_tag()


def s_all():
    ctrl.update_tag(); mat.update_tag(); nt.update_tag()


def s_dg():
    bpy.context.evaluated_depsgraph_get().update()


def s_frame():
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)


STRATS = [("(不 tag)", s_none), ("ctl", s_ctl), ("mat", s_mat), ("nt", s_nt),
          ("mat+nt", s_mat_nt), ("ctl+mat+nt", s_all),
          ("depsgraph.update()", s_dg), ("frame_set(当前帧)", s_frame)]

rows = []
for label, fn in STRATS:
    ctrl[KEY] = DEF
    fn(); bpy.context.view_layer.update()
    lo = scale()
    ctrl[KEY] = PROBE
    fn(); bpy.context.view_layer.update()
    hi = scale()
    ok = (lo == DEF and hi == PROBE)
    rows.append({"tag": label, "读回": "%s -> %s" % (lo, hi),
                 "是否重算": "✅" if ok else "❌"})

# 还原
ctrl[KEY] = DEF
ctrl.update_tag(); mat.update_tag(); nt.update_tag()
bpy.context.view_layer.update()

print("P37_BEGIN")
print(json.dumps({
    "target": MAT, "probe_socket": "噪波纹理.inputs[2] (Scale)",
    "rows": rows,
    "restored": scale(),
}, ensure_ascii=False, indent=1))
print("P37_END")
