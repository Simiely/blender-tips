# -*- coding: utf-8 -*-
# 【两段式·第 2 步】UI tag 回采：**只读**，绝对不换帧、不打任何标记
#
# 只回答一个问题：用户在「物体属性 → 自定义属性」里拖过值之后，
#     属性值   -> 变了
#     驱动求值 -> 有没有跟着变？
#   两者都变   => UI 编辑**会**自动 tag（仓库的看门狗属于冗余保险）
#   只有属性变 => UI 编辑**不会**自动 tag（看门狗是必需的）
#
# 读两个来源：
#   ① `scene[KEY]` 上的观察器事件（由 probe_ui_tag_arm.py 挂的 handler 累积）
#   ② 当前值：属性值 vs 节点【求值后】的值 vs 原始 default_value
#   ③ 顺带核对所有驱动的 `is_valid`（变红 = 表达式里有东西解析不了）
#
# 采完收工：`del bpy.context.scene["__uitag_json"]`（那个键会随 .blend 一起存盘，别留着）
#
# ★ 用前改下面 5 个模板占位
import bpy, json, os

CTRL = "FB_ctrl"
MAT = "FB_Firework_View"
PROP = "变亮前等待"
NODE = "T_BLACK"
OUT = r"<改成你的输出目录>"
KEY = "__uitag_json"

os.makedirs(OUT, exist_ok=True)
scn = bpy.context.scene
rep = {"blender": bpy.app.version_string}

raw = scn.get(KEY)
ev = json.loads(raw) if raw else []
rep["event_count"] = len(ev)
rep["frame_now"] = scn.frame_current

c = bpy.data.objects.get(CTRL)
m = bpy.data.materials.get(MAT)
rep["prop_now"] = float(c.get(PROP, -999.0))
rep["node_raw"] = float(m.node_tree.nodes[NODE].outputs[0].default_value)
try:
    dg = bpy.context.evaluated_depsgraph_get()
    rep["node_eval"] = float(m.evaluated_get(dg).node_tree.nodes[NODE].outputs[0].default_value)
except Exception as e:
    rep["node_eval"] = "ERR " + repr(e)[:80]

# 驱动总览
nt = m.node_tree
allv = []
if nt.animation_data:
    for f in nt.animation_data.drivers:
        allv.append({
            "path": f.data_path,
            "valid": bool(f.driver.is_valid),
            "expr": f.driver.expression[:46],
            "vars": [(v.name, v.type, getattr(v, "data_path", "")) for v in f.driver.variables],
        })
rep["drivers_total"] = len(allv)
rep["drivers_invalid"] = [d["path"] for d in allv if not d["valid"]]
rep["drv_target_node"] = [d for d in allv if NODE in d["path"]]

# 只保留"值发生变化"的时刻
changes, last = [], None
for e in ev:
    cur = (e.get("prop"), e.get("node"))
    if cur != last:
        changes.append(e)
        last = cur
rep["change_points"] = changes[-40:]
rep["handlers_live"] = sum(1 for f in bpy.app.handlers.depsgraph_update_post
                           if getattr(f, "__name__", "") == "_handler")

# 判读
if rep["event_count"] == 0:
    rep["verdict"] = "没采到事件 —— 要么人还没拖，要么这次编辑根本没触发依赖图更新"
elif abs(float(rep["prop_now"]) - float(rep["node_eval"])) < 1e-4:
    rep["verdict"] = "属性值与驱动求值一致 ⇒ UI 编辑会自动 tag（看门狗属冗余保险）"
else:
    rep["verdict"] = "属性值变了但驱动求值仍是旧值 ⇒ UI 编辑不自动 tag（看门狗必需）"

with open(os.path.join(OUT, "ui_tag_step2.json"), "w", encoding="utf-8") as f:
    json.dump(rep, f, ensure_ascii=False, indent=1)
print(json.dumps(rep, ensure_ascii=False, indent=1))
print(">>> 判读：%s" % rep["verdict"])
print(">>> 收工清理：del bpy.context.scene['%s']" % KEY)
