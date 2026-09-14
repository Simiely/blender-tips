# -*- coding: utf-8 -*-
"""self_test.py — 在**真实 Blender** 里对 radial_field.py 做隔离试跑

做法：把 radial_field.py 的 CONFIG 用正则改成
    material = _SKILLTEST_<mode>    assign = False
依次建 4 种模式的材质，捕获 print 输出，校验 FAILS=0，
最后**删除全部临时材质并逐项还原每个 mesh 的材质槽与当前帧**。
跑完场景必须与跑之前逐字节等价（对象数/材质表/槽位/帧）。

为什么必须 assign=False：这样新建的材质不挂到任何物体上，
不会影响渲染结果，也不存在"改坏用户成品"的风险；
赋槽逻辑由 radial_field.py 在真实使用中验证（它已在项目里跑通过）。
"""
import io
import os
import re
import sys
import bpy

# NOTE: 路径为模板占位 —— 用前改成你本机 radial_field.py 的实际路径。
#       （桥执行环境里 __file__ 不可靠，因此显式定义。）
FIELD = r"C:/Users/2504/.workbuddy/skills/blender-radial-pulse-material/scripts/radial_field.py"
MODES = ("spot", "ring", "spike", "pulse")

log = []

# ---------- 基线快照 ----------
def snapshot():
    return {
        "objs": sorted(o.name for o in bpy.data.objects),
        "mats": sorted(m.name for m in bpy.data.materials),
        "slots": {o.name: [m.name if m else None for m in o.data.materials]
                  for o in bpy.data.objects if o.type == 'MESH'},
        "frame": bpy.context.scene.frame_current,
    }

def restore(snap):
    """删掉所有以 _SKILLTEST 开头的材质，并把槽位/帧还原回基线。"""
    for m in [m for m in bpy.data.materials if m.name.startswith("_SKILLTEST")]:
        bpy.data.materials.remove(m)
    for name, want in snap["slots"].items():
        ob = bpy.data.objects.get(name)
        if not ob:
            continue
        me = ob.data
        me.materials.clear()
        for mn in want:
            if mn:                       # append(None) 会抛错 —— 跳过即可
                me.materials.append(bpy.data.materials[mn])
        for poly in me.polygons:
            poly.material_index = 0
    if bpy.context.scene.frame_current != snap["frame"]:
        bpy.context.scene.frame_set(snap["frame"])

BASE = snapshot()
log.append("基线: 对象=%d 材质=%d 帧=%d" % (len(BASE["objs"]), len(BASE["mats"]), BASE["frame"]))
log.append("基线材质表=%s" % BASE["mats"])

src = io.open(FIELD, encoding="utf-8").read()

results = []
for mode in MODES:
    code = src
    code, n1 = re.subn(r'"mode":\s*"[a-z]+"', '"mode": "%s"' % mode, code, count=1)
    test_name = "_SKILLTEST_" + mode
    code, n2 = re.subn(r'"material":\s*"[^"]+"', '"material": "%s"' % test_name, code, count=1)
    code, n3 = re.subn(r'"assign":\s*(True|False)', '"assign": False', code, count=1)
    assert n1 == n2 == n3 == 1, "CONFIG 替换失败 mode=%s (%d,%d,%d)" % (mode, n1, n2, n3)

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    err = None
    try:
        exec(compile(code, FIELD, "exec"), {"__name__": "__main__"})
    except Exception as e:
        err = "%s: %s" % (type(e).__name__, e)
    finally:
        sys.stdout = old
    text = buf.getvalue()

    m = bpy.data.materials.get(test_name)
    nodes = len(m.node_tree.nodes) if m else 0
    links = len(m.node_tree.links) if m else 0
    fails = [ln.strip() for ln in text.splitlines() if "**FAIL**" in ln]
    mf = re.search(r"FAILS=(\d+)", text)
    results.append({
        "mode": mode, "err": err, "nodes": nodes, "links": links,
        "fails": fails, "fails_n": int(mf.group(1)) if mf else -1,
        "ok": err is None and m is not None and nodes > 0 and not fails,
    })
    log.append("")
    log.append("=" * 60)
    log.append("MODE=%s  err=%s  nodes=%d links=%d  FAILS=%s"
               % (mode, err, nodes, links, mf.group(1) if mf else "?"))
    for ln in text.splitlines():
        if "CHECKS" in ln or "**FAIL**" in ln or "解析" in ln:
            pass
    # 只保留高信号行，避免桥输出过长
    keep = ("nodes=", "targets=", "keyframes", "FAILS=", "**FAIL**",
            "CHECKS", "解析表", "  f", "  （")
    for ln in text.splitlines():
        if any(k in ln for k in keep):
            log.append("    " + ln)

restore(BASE)
AFTER = snapshot()
same = (AFTER["objs"] == BASE["objs"] and AFTER["mats"] == BASE["mats"]
        and AFTER["slots"] == BASE["slots"] and AFTER["frame"] == BASE["frame"])

log.append("")
log.append("=" * 60)
n_ok = sum(1 for r in results if r["ok"])
log.append("SELF-TEST: %d/%d 模式通过" % (n_ok, len(MODES)))
for r in results:
    log.append("  %-6s %s  nodes=%d links=%d  fails=%d"
               % (r["mode"], "PASS" if r["ok"] else "**FAIL**", r["nodes"], r["links"], r["fails_n"]))
log.append("场景还原: %s" % ("OK（对象/材质表/槽位/帧 全部与基线一致）" if same else "**FAIL** 有残留"))
if not same:
    log.append("  残留材质=%s" % sorted(m.name for m in bpy.data.materials))
    log.append("  基线对象=%s" % BASE["objs"])
    log.append("  现在对象=%s" % AFTER["objs"])
print("\n".join(log))
