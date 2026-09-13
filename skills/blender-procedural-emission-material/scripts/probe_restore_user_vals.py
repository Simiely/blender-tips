# -*- coding: utf-8 -*-
"""probe_62: 确认控制器当前值，并把用户调好的参数恢复回去。
背景：render_invert_check 第一轮带 bug 的运行在中途改了控制器值，
     第二轮的「还原」还原的是第一轮残留的测试值 ⇒ 用户调的值可能被顶掉。
只动 竖向灯001_噪波控制 这一个物体的自定义属性，其他一概不碰。
"""
import json

CTRL_NAME = "竖向灯001_噪波控制"
# 用户在 UI 里调出来的值（build v3 时 props_before 实测）
USER_VALS = {
    "噪波密度": 6.0,
    "噪波种子": 11.34,
    "Z向速度": -0.1,
    "噪波对比度": 10.0,
    "发光强度": 5.0,
    "反色": 0.0,
}

import bpy

rep = {"step": "probe_62_restore_user_vals"}
obj = bpy.data.objects.get(CTRL_NAME)
rep["ctrl_found"] = obj is not None

cur = {}
if obj:
    for k in ("噪波密度", "噪波种子", "Z向速度", "噪波对比度", "发光强度", "反色"):
        cur[k] = obj.get(k)
rep["values_before"] = cur

# 无论当前是什么，统一恢复成用户调的值（反色是新控件，保持 0 = 不反色）
changed = {}
if obj:
    for k, v in USER_VALS.items():
        old = obj.get(k)
        if old is None or abs(float(old) - v) > 1e-6:
            obj[k] = v
            changed[k] = [old, v]
rep["changed"] = changed

# tag 一下让驱动立即跟上（看门狗 0.25s 内也会兜底）
obj.update_tag()
mat = bpy.data.materials.get("竖向灯001_噪波滚动")
if mat:
    mat.update_tag()
    if mat.node_tree:
        mat.node_tree.update_tag()
bpy.context.view_layer.update()

after = {k: obj.get(k) for k in USER_VALS}
rep["values_after"] = after
rep["all_restored"] = all(abs(float(after[k]) - v) < 1e-6 for k, v in USER_VALS.items())

print("P62_BEGIN" + json.dumps(rep, ensure_ascii=False) + "P62_END")
