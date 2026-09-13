# NOTE: 路径为模板占位 --- 使用前把 WORKDIR/OUTDIR 改成本机实际的「脚本/输出目录」。
#       （桥执行环境里 __file__ 不可靠，因此显式定义。）
# -*- coding: utf-8 -*-
# AR-2 读取：看门狗应该已经把值刷进去了；读完顺手把参数还原成默认（同样不 tag）
import bpy, json

MAT = "竖向灯001_噪波滚动发光"
CTRL = "竖向灯001_噪波控制"
NEW = {"噪波密度": 3.7, "噪波种子": 4.2, "Z向速度": 0.05, "噪波对比度": 7.5, "发光强度": 23.0}
DEF = {"噪波密度": 2.0, "噪波种子": 0.0, "Z向速度": 0.02, "噪波对比度": 5.0, "发光强度": 5.0}

ctrl = bpy.data.objects[CTRL]
mat = bpy.data.materials[MAT]


def read_eval():
    dg = bpy.context.evaluated_depsgraph_get()
    nte = mat.evaluated_get(dg).node_tree
    out = {}
    for n in nte.nodes:
        if n.type == 'MAPPING':
            out["map_loc"] = [round(x, 4) for x in n.inputs[1].default_value]
        if n.type == 'TEX_NOISE':
            out["noise_scale"] = round(n.inputs[2].default_value, 4)
            out["noise_W"] = round(n.inputs[1].default_value, 4)
        if n.type == 'VALTORGB':
            out["ramp"] = [round(e.position, 4) for e in n.color_ramp.elements]
        if n.type == 'MATH' and n.operation == 'MULTIPLY':
            out["mult"] = round(n.inputs[1].default_value, 4)
    return out


# 期望值（按新参数手算）
c = NEW["噪波对比度"]
exp = {
    "map_loc": [0.0, 0.0, round(0.05 * bpy.context.scene.frame_current, 4)],
    "noise_scale": NEW["噪波密度"],
    "noise_W": round(NEW["噪波种子"] * 10.0, 4),
    "ramp": [round(max(0.0, 0.5 - 0.5 / c), 4), round(min(1.0, 0.5 + 0.5 / c), 4)],
    "mult": NEW["发光强度"],
}
got = read_eval()
checks = {k: (got.get(k) == exp[k]) for k in exp}
res = {"ctrl_still_holds": {k: ctrl.get(k) for k in NEW},
       "expected": exp, "read": got, "checks": checks,
       "all_ok": all(checks.values())}

# 还原默认（同样不 tag，交给看门狗）
for k, v in DEF.items():
    ctrl[k] = float(v)
res["restored_to"] = DEF
res["ctrl_after_restore"] = {k: ctrl.get(k) for k in DEF}
res["read_right_after_restore"] = read_eval()
print("AR2_BEGIN")
print(json.dumps(res, ensure_ascii=False, indent=1))
print("AR2_END")
