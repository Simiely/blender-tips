# -*- coding: utf-8 -*-
# 【两段式·第 1 步】UI tag 观察器：装 depsgraph 监听 + 记基线
#
# 要回答的问题（仓库长期空白）：
#   在「物体属性 → 自定义属性」里拖动数值，Blender 会不会**自动**给物体打 depsgraph 标记，
#   从而让挂在材质节点上的 `SINGLE_PROP` 驱动重算？
#   —— 脚本侧 `ctrl[k] = v` 不 tag 是**已实测**的；但 **UI 编辑**这条路仓库从未隔离实测过
#      （emission skill §6 第 3 层唯一的证据脚本 probe_driver_autotrigger.py 用的是 Python 赋值）。
#
# 为什么不能从脚本侧旁证（2026-09-14 实测）：
#   ① 自定义属性**不出现在 `bl_rna`**（`prop_in_rna=False`）⇒ `setattr(ctrl, "键", v)` 直接
#      AttributeError，走不到 RNA 那条路；
#   ② `bpy.ops.wm.properties_edit` 是 **INVOKE-only** 的元数据弹窗（脚本调用报"不支持直接执行"），
#      不是数值框。
#   ⇒ 想判这条**只能在 UI 里真拖一次**。
#
# 用法：
#   1) 桥执行本脚本 → 观察器就位、日志清零、记基线
#   2) **人去 UI 里把 PROP 拖成另一个值**（只做这一步：不要换帧、不要播放 ——
#      换帧会强制全量重算，是**假阳性**来源）
#   3) 桥执行 probe_ui_tag_read.py → 只读回采
#
# ★ 用前改下面 5 个模板占位
import bpy, json, time, os

CTRL = "FB_ctrl"                    # 控制空物体名
MAT = "FB_Firework_View"            # 材质名（被驱动的材质）
PROP = "变亮前等待"                  # 被观察的自定义属性（中文键）
NODE = "T_BLACK"                    # 该属性驱动到的节点名（取 outputs[0]）
OUT = r"<改成你的输出目录>"           # 结果 json 落盘目录
KEY = "__uitag_json"                # 日志存在 scene 的字符串属性上

os.makedirs(OUT, exist_ok=True)
scn = bpy.context.scene
rep = {}


def snap():
    c = bpy.data.objects.get(CTRL)
    m = bpy.data.materials.get(MAT)
    if c is None or m is None:
        return {"prop": None, "node": None, "err": "missing ctrl/mat"}
    pv = float(c.get(PROP, -999.0))
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        nv = float(m.evaluated_get(dg).node_tree.nodes[NODE].outputs[0].default_value)
    except Exception as e:
        nv = "ERR:" + repr(e)[:60]
    return {"prop": pv, "node": nv}


def _handler(scene, depsgraph=None):
    try:
        s = snap()
        s["t"] = round(time.time(), 3)
        ev = json.loads(scene.get(KEY) or "[]")
        ev.append(s)
        if len(ev) > 200:
            ev = ev[-200:]
        scene[KEY] = json.dumps(ev)
    except Exception:
        pass


# 去重安装（每次 exec 定义的函数同名，先把旧的摘掉）
for f in list(bpy.app.handlers.depsgraph_update_post):
    if getattr(f, "__name__", "") == "_handler":
        try:
            bpy.app.handlers.depsgraph_update_post.remove(f)
        except Exception:
            pass
bpy.app.handlers.depsgraph_update_post.append(_handler)

scn[KEY] = "[]"                      # 清空日志
rep["t_installed"] = round(time.time(), 3)
rep["frame"] = scn.frame_current
rep["base"] = snap()
rep["node_raw_default"] = float(bpy.data.materials[MAT].node_tree.nodes[NODE].outputs[0].default_value)
try:
    ui = bpy.data.objects[CTRL].id_properties_ui(PROP).as_dict()
    rep["ui_range"] = {k: ui.get(k) for k in ("min", "max", "soft_min", "soft_max")}
except Exception as e:
    rep["ui_range"] = repr(e)[:80]
rep["handler_live"] = sum(1 for f in bpy.app.handlers.depsgraph_update_post
                          if getattr(f, "__name__", "") == "_handler")
rep["ctrl_props"] = [k for k in bpy.data.objects[CTRL].keys() if k != "_RNA_UI"]
rep["blender"] = bpy.app.version_string

with open(os.path.join(OUT, "ui_tag_step1.json"), "w", encoding="utf-8") as f:
    json.dump(rep, f, ensure_ascii=False, indent=1)
print(json.dumps(rep, ensure_ascii=False, indent=1))
print(">>> 观察器就位。现在去 UI 里把 %s 拖成另一个值，然后跑 probe_ui_tag_read.py" % PROP)
