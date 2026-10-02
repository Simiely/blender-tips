# -*- coding: utf-8 -*-
"""比对 A/B 同名材质与世界的指纹：同一份 => append 会复用引用；不同 => 会生成 .001 副本。"""
import json, os, io, sys

WORK = os.environ.get("AMB_WORK", os.getcwd())   # 报告/基线/日志都写这里
A = json.load(open(os.path.join(WORK, "matfp_A.json"), encoding="utf-8"))
B = json.load(open(os.path.join(WORK, "matfp_B.json"), encoding="utf-8"))

out = []
w = out.append

ma, mb = A["materials"], B["materials"]
w("== 材质 ==")
w("A: %d 个   B: %d 个" % (len(ma), len(mb)))
common = sorted(set(ma) & set(mb))
w("同名材质共 %d 个：" % len(common))
same, diff = [], []
for n in common:
    fa, ia = ma[n]["fp"], ma[n]["info"]
    fb, ib = mb[n]["fp"], mb[n]["info"]
    if fa == fb:
        same.append(n)
        w("  [同一份] %-32s fp=%s  nodes=%s/%s  users A=%s B=%s"
          % (n, fa, ia.get("nodes"), ib.get("nodes"), ma[n]["users"], mb[n]["users"]))
    else:
        diff.append(n)
        w("  [不同!!] %-32s fpA=%s fpB=%s" % (n, fa, fb))
        w("           A nodes=%s links=%s types=%s" % (ia.get("nodes"), ia.get("links"), ia.get("node_types")))
        w("           B nodes=%s links=%s types=%s" % (ib.get("nodes"), ib.get("links"), ib.get("node_types")))
        ia_img, ib_img = ia.get("images") or [], ib.get("images") or []
        if ia_img != ib_img:
            w("           A images=%s" % (ia_img[:6],))
            w("           B images=%s" % (ib_img[:6],))

w("")
w("== 世界 ==")
for n in sorted(set(A["worlds"]) & set(B["worlds"])):
    wa, wb = A["worlds"][n], B["worlds"][n]
    w("  %s  A(fp=%s nodes=%s)  B(fp=%s nodes=%s)  => %s"
      % (n, wa["fp"], wa["nodes"], wb["fp"], wb["nodes"],
         "同一份" if wa["fp"] == wb["fp"] else "不同!!"))

w("")
w("== 只在一侧存在的材质（不会冲突）==")
onlyA = sorted(set(ma) - set(mb))
onlyB = sorted(set(mb) - set(ma))
w("仅 A: %d 个  %s" % (len(onlyA), onlyA[:20]))
w("仅 B: %d 个（前20）%s" % (len(onlyB), onlyB[:20]))

with io.open(os.path.join(WORK, "cmp_matfp.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("same=%d diff=%d  -> cmp_matfp.txt" % (len(same), len(diff)))
