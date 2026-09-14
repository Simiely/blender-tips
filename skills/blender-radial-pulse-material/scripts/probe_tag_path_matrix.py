# -*- coding: utf-8 -*-
# 【单段式】写入路径 → 是否自动触发驱动重算 的对照矩阵
#
# 为什么需要它：仓库里「改自定义属性驱动不重算」这条一直只被 **Python 下标赋值**验证过，
# 而用户在 UI 里拖数值走的是**另一条路**。本脚本把能测的路径逐条分开测，把不能测的
# 也钉死"为什么不能测"，避免再拿一条路径的结果去推断另一条。
#
# 判据：写入后【不 tag、不换帧】，直接读**求值依赖图**里的节点值。
#       跟着变 = 该路径会自动触发重算；停在旧值 = 需要外部 tag。
#
# 2026-09-14 实测结果（Blender 5.2.0 LTS，节点插槽驱动 + SINGLE_PROP）：
#   prop_in_rna = False                      ← 自定义属性不在 bl_rna 里
#   A 下标 IDProperty  ctrl[k]=30   → 节点停在 20.0  ✘  → 脚本侧必须 update_tag()
#   B RNA 赋值 setattr(ctrl, k, 40) → AttributeError ✘  → 走不到 RNA（键不在 bl_rna）
#   C wm.properties_edit            → "不支持直接执行" ✘ → INVOKE-only 弹窗，非数值框
#   D 下标赋值 + update_tag()       → 节点读 60.0    ✔  → 脚本侧正解
#   ⇒ 「UI 里拖数值会不会自动 tag」**无法从脚本侧旁证**，只能真去 UI 里拖
#      （配方见同目录 probe_ui_tag_arm.py + probe_ui_tag_read.py）
#
# 全程 try/finally 还原：属性值 / 活动物体 / 选择集。
# ★ 用前改下面 5 个模板占位
import bpy, json, os

CTRL = "FB_ctrl"
MAT = "FB_Firework_View"
PROP = "变亮前等待"
NODE = "T_BLACK"
BASE = 20.0                     # 属性的基线值（实验起点，也是还原值）
OUT = r"<改成你的输出目录>"
KEY = "__uitag_json"

os.makedirs(OUT, exist_ok=True)
scn = bpy.context.scene
ctrl = bpy.data.objects[CTRL]
mat = bpy.data.materials[MAT]
L = []
A = L.append
rep = {"blender": bpy.app.version_string}


def node_eval():
    dg = bpy.context.evaluated_depsgraph_get()
    return round(float(mat.evaluated_get(dg).node_tree.nodes[NODE].outputs[0].default_value), 3)


def node_raw():
    return round(float(mat.node_tree.nodes[NODE].outputs[0].default_value), 3)


def events():
    try:
        return len(json.loads(scn.get(KEY) or "[]"))
    except Exception:
        return -1


# ---------- 0. 该自定义属性在 RNA 层是否可见 ----------
rna_names = [p.identifier for p in ctrl.bl_rna.properties]
rep["prop_in_rna"] = PROP in rna_names
rep["rna_prop_count"] = len(rna_names)
rep["prop_type_in_rna"] = (ctrl.bl_rna.properties[PROP].type if PROP in rna_names else None)

prev_active = bpy.context.view_layer.objects.active
prev_active_name = prev_active.name if prev_active else None
prev_sel = [o.name for o in bpy.context.selected_objects]
prev_prop = float(ctrl[PROP])


def hard_reset():
    """把属性硬设回基线并强制重算，作为每次实验的干净起点"""
    ctrl[PROP] = BASE
    ctrl.update_tag()
    bpy.context.view_layer.update()
    bpy.context.evaluated_depsgraph_get()


def step(tag, write):
    hard_reset()
    before = node_eval()
    e0 = events()
    try:
        write()
        err = ""
    except Exception as ex:
        err = type(ex).__name__ + ": " + str(ex)[:70]
    after = node_eval()          # 只读
    e1 = events()
    A("%-34s 属性=%6.1f  节点 %s -> %s  事件+%d  %s" % (
        tag, float(ctrl[PROP]), before, after, e1 - e0,
        err or ("跟着变 ✔" if abs(after - before) > 1e-6 else "停在旧值 ✘")))


A("基线：属性=%.1f  节点求值=%.3f  节点原始=%.3f  events=%d" % (
    prev_prop, node_eval(), node_raw(), events()))
A("自定义属性是否出现在 RNA（决定 setattr 走哪条路）: %s  类型=%s  RNA 属性数=%d" % (
    rep["prop_in_rna"], rep["prop_type_in_rna"], rep["rna_prop_count"]))
A("")

step("A. 下标 IDProperty  ctrl[k]=30", lambda: ctrl.__setitem__(PROP, 30.0))
step("B. RNA 赋值  setattr(ctrl, k, 40)", lambda: setattr(ctrl, PROP, 40.0))

# C 属性编辑器操作符（预期失败：INVOKE-only，是元数据弹窗不是数值框）
bpy.context.view_layer.objects.active = ctrl
ctrl.select_set(True)
step("C. wm.properties_edit()", lambda: bpy.ops.wm.properties_edit(
    data_path="", property_name=PROP))


# D 对照：下标赋值 + 显式 tag（已知会生效）
def d_write():
    ctrl[PROP] = 60.0
    ctrl.update_tag()
    bpy.context.view_layer.update()


step("D. 下标赋值 + update_tag(60)", d_write)

# ---------- 还原 ----------
ctrl[PROP] = prev_prop
ctrl.update_tag()
bpy.context.view_layer.update()
if prev_active_name:
    try:
        bpy.context.view_layer.objects.active = bpy.data.objects[prev_active_name]
    except Exception:
        pass
for o in bpy.context.selected_objects:
    o.select_set(False)
for n in prev_sel:
    try:
        bpy.data.objects[n].select_set(True)
    except Exception:
        pass

rep["lines"] = L
rep["restored_prop"] = float(ctrl[PROP])
rep["node_after_restore"] = node_eval()

with open(os.path.join(OUT, "tag_path_matrix.json"), "w", encoding="utf-8") as f:
    json.dump(rep, f, ensure_ascii=False, indent=1)
print("\n".join(L))
print("还原: prop=%.1f  node=%.3f" % (rep["restored_prop"], rep["node_after_restore"]))
