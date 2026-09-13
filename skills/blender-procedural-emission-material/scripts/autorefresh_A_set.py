# NOTE: 路径为模板占位 --- 使用前把 WORKDIR/OUTDIR 改成本机实际的「脚本/输出目录」。
#       （桥执行环境里 __file__ 不可靠，因此显式定义。）
# -*- coding: utf-8 -*-
# AR-1 设置：改 5 个控件属性，**不做任何 tag / update**
# 模拟用户直接在「物体属性 → 自定义属性」里改数字（那条路径不会触发我的面板 draw）
import bpy, json

MAT = "竖向灯001_噪波滚动发光"
CTRL = "竖向灯001_噪波控制"
NEW = {"噪波密度": 3.7, "噪波种子": 4.2, "Z向速度": 0.05, "噪波对比度": 7.5, "发光强度": 23.0}

ctrl = bpy.data.objects[CTRL]
mat = bpy.data.materials[MAT]
for k, v in NEW.items():
    ctrl[k] = float(v)                    # ★ 只赋值，不 tag、不 update
    assert ctrl[k] == float(v)


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


print("AR1_BEGIN")
print(json.dumps({"set": NEW, "ts": bpy.context.scene.frame_current,
                  "immediate_read": read_eval()}, ensure_ascii=False, indent=1))
print("AR1_END")
