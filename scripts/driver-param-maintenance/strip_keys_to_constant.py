# -*- coding: utf-8 -*-
"""
strip_keys_to_constant.py —— 把某个参数的【关键帧动画】收敛成【常量】

用途:
  MODE='report' 只读:打印该曲线的 (帧,值) 全表 / 插值 / 外插 / 当前帧求值 / 属性静态值
                —— 这份输出就是【回滚依据】,先留档再动手
  MODE='apply'  删除该路径的关键帧曲线,并把常量写回

要点:
  * 只删【目标 data_path + array_index】那一条 fcurve,同一 action 里的其它曲线原样保留
  * CONSTANT = None ⇒ 取「当前帧所见值」(画面不跳变);给了数值 ⇒ 用指定值
  * 自定义属性关键帧在分层 Action 里:action.layers[].strips[].channelbags[].fcurves
  * 写后必须 update_tag() + view_layer.update();验证要【另起一次请求】

经桥执行(无 __main__ 守卫,直接 main()):
  python send.py strip_keys_to_constant.py
"""

import bpy

# ============================== CONFIG ==============================
MODE = 'report'                      # 'report' | 'apply'
OWNER_KIND = 'OBJECT'                # 'OBJECT' | 'OBJECT_DATA_NT'(灯光/网格节点树) | 'MATERIAL_NT'
OWNER = "竖向灯001_噪波控制"          # 控制物体名 / 节点树宿主对象名 / 材质名
DATA_PATH = '["噪波种子"]'            # 自定义属性写 '["键"]';节点插槽写 'nodes["X"].inputs[1].default_value'
ARRAY_INDEX = 0                      # 向量插槽分量(标量恒 0)
NODE_NAME = ""                       # DATA_PATH 为节点插槽时,节点名(写回用)
SOCKET_INDEX = 1                     # 节点插槽序号(写回用)
CONSTANT = None                      # None = 当前帧求值;否则用该数值
WRITE_BACK = True                    # 删完是否写回常量
OUT_DIR = r""                        # 报告目录(留空 = 只打印)
# ====================================================================


def resolve_owner():
    if OWNER_KIND == 'OBJECT':
        return bpy.data.objects[OWNER]
    if OWNER_KIND == 'OBJECT_DATA_NT':
        return bpy.data.objects[OWNER].data.node_tree
    if OWNER_KIND == 'MATERIAL_NT':
        return bpy.data.materials[OWNER].node_tree
    raise ValueError("未知 OWNER_KIND: %s" % OWNER_KIND)


def iter_fcurves(owner):
    """产出 (channelbag, fcurve) —— 覆盖分层 Action 的全部 slot"""
    ad = getattr(owner, "animation_data", None)
    if not ad or not ad.action:
        return
    for lay in ad.action.layers:
        for st in lay.strips:
            for cb in st.channelbags:
                for fc in cb.fcurves:
                    yield cb, fc


def is_idprop_path():
    return DATA_PATH.startswith('[') and DATA_PATH.endswith(']')


def idprop_key():
    return DATA_PATH.strip('[]"').replace('\\"', '"')


def write_back(owner, value, lines):
    if is_idprop_path():
        key = idprop_key()
        owner[key] = value
        lines.append("已写自定义属性 [%s] = %r" % (key, owner[key]))
    else:
        node = owner.nodes.get(NODE_NAME) if hasattr(owner, "nodes") else None
        if node is None:
            lines.append("⚠ 找不到节点 %r,未写回插槽(手动确认 NODE_NAME/SOCKET_INDEX)" % NODE_NAME)
            return
        node.inputs[SOCKET_INDEX].default_value = value
        lines.append("已写节点插槽 nodes[%r].inputs[%d] = %r" % (
            NODE_NAME, SOCKET_INDEX, node.inputs[SOCKET_INDEX].default_value))


def main():
    owner = resolve_owner()
    lines = []
    lines.append("宿主: %s (%s) | 当前帧: %d" % (OWNER, OWNER_KIND, bpy.context.scene.frame_current))

    matched = [(cb, fc) for cb, fc in iter_fcurves(owner)
               if fc.data_path == DATA_PATH and fc.array_index == ARRAY_INDEX]
    if matched:
        fc0 = matched[0][1]
        kps = [(float(kp.co[0]), float(kp.co[1])) for kp in fc0.keyframe_points]
        lines.append("曲线: %s idx=%d | 关键帧 %d 个 | 插值 %s | 外插 %s" % (
            DATA_PATH, ARRAY_INDEX, len(kps),
            fc0.keyframe_points[0].interpolation, fc0.extrapolation))
        lines.append("(帧, 值) 全表 —— ★ 回滚依据,请先留档:")
        for f, v in kps:
            lines.append("    %10.3f  %12.4f" % (f, v))
        lines.append("当前帧求值: %.6f" % fc0.evaluate(bpy.context.scene.frame_current))
    else:
        lines.append("⚠ 未找到匹配曲线 —— 可能已收敛过(幂等)或 path/index 写错")

    lines.append("动作内 fcurve 总数: %d" % sum(1 for _ in iter_fcurves(owner)))
    if is_idprop_path():
        key = idprop_key()
        has = key in owner.keys()
        lines.append("属性静态值: %r (键存在=%s)" % (owner[key] if has else None, has))

    if MODE == 'apply':
        cur = None
        for cb, fc in matched:
            cur = fc.evaluate(bpy.context.scene.frame_current)
            cb.fcurves.remove(fc)
            lines.append("已删除曲线: %s idx=%d" % (DATA_PATH, ARRAY_INDEX))
        value = CONSTANT if CONSTANT is not None else cur
        lines.append("常量取值: %r (%s)" % (
            value, "用户指定" if CONSTANT is not None else "当前帧所见值"))
        if value is not None and WRITE_BACK:
            write_back(owner, value, lines)
        rest = [(fc.data_path, fc.array_index) for _, fc in iter_fcurves(owner)]
        lines.append("动作剩余 fcurves: %s" % (rest if rest else "[]"))
        owner.update_tag()
        bpy.context.view_layer.update()
        lines.append("已 update_tag + view_layer.update() —— 请【另起一次请求】复核")

    text = "\n".join(lines)
    print(text)
    if OUT_DIR:
        import os
        os.makedirs(OUT_DIR, exist_ok=True)
        p = os.path.join(OUT_DIR, "strip_keys_%s.txt" % MODE)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        print("报告已写入: " + p)


main()
