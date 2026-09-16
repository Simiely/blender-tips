# -*- coding: utf-8 -*-
"""
param_ref_scan.py —— 参数化驱动【引用体检】

用途(只读,不改场景):
  1) MODE='refs'   列出「谁在读指定 ID 的指定自定义属性」—— 跨全部 data-block(含最常漏的
                   物体数据 → node_tree 层)
  2) MODE='health' 全库体检:失效驱动(is_valid=False) + 悬空引用(变量 data_path 指向已不存在的属性)
                   ⇒ 改名/删键之后必须跑一次,判据是 0 条

经桥执行(无 __main__ 守卫,直接 main()):
  python send.py param_ref_scan.py            # 9877
"""

import bpy
import re

# ============================== CONFIG ==============================
MODE = 'refs'                      # 'refs' | 'health' | 'both'
TARGET_ID = ""                     # refs 模式:目标 ID 名(物体/材质名);空串 = 全库
PROPS = []                         # refs 模式:要查的自定义属性键;空列表 = 该 ID 的【全部】自定义属性
OUT_DIR = r""                      # 报告输出目录(留空 = 只打印,不落盘)
# ====================================================================

RE_IDPROP = re.compile(r'^\["(.+)"\]$')


def iter_animation_data():
    """遍历全库动画数据,返回 [(层标签, 所有者名, animation_data)]"""
    out = []
    for o in bpy.data.objects:
        out.append(("物体", o.name, getattr(o, "animation_data", None)))
        if o.data:
            out.append(("物体数据", o.name, getattr(o.data, "animation_data", None)))
            nt = getattr(o.data, "node_tree", None)
            if nt is not None:
                out.append(("★物体数据节点树", o.name, getattr(nt, "animation_data", None)))
        for md in o.modifiers:
            ng = getattr(md, "node_group", None)
            if ng is not None:
                out.append(("修改器节点组", o.name + "." + md.name, getattr(ng, "animation_data", None)))
    for m in bpy.data.materials:
        out.append(("材质", m.name, getattr(m, "animation_data", None)))
        if m.node_tree is not None:
            out.append(("材质节点树", m.name, getattr(m.node_tree, "animation_data", None)))
    for ng in bpy.data.node_groups:
        out.append(("节点组", ng.name, getattr(ng, "animation_data", None)))
    for s in bpy.data.scenes:
        out.append(("场景", s.name, getattr(s, "animation_data", None)))
    for w in bpy.data.worlds:
        out.append(("世界", w.name, getattr(w, "animation_data", None)))
        if w.node_tree is not None:
            out.append(("世界节点树", w.name, getattr(w.node_tree, "animation_data", None)))
    return out


def scan_refs(lines):
    lines.append("=== 引用体检:谁在读这些属性 ===")
    targets = []
    if TARGET_ID:
        for coll in (bpy.data.objects, bpy.data.materials):
            if TARGET_ID in coll:
                targets.append(coll[TARGET_ID])
        for o in bpy.data.objects:          # 材质节点树/灯光节点树也算目标宿主
            nt = getattr(o.data, "node_tree", None) if o.data else None
            if nt is not None and nt.name == TARGET_ID:
                targets.append(nt)
        if not targets:
            lines.append("  ⚠ 找不到目标 ID: %s" % TARGET_ID)
            return
    hit = 0
    for layer, owner, ad in iter_animation_data():
        if not ad or not ad.drivers:
            continue
        for dr in ad.drivers:
            for v in dr.driver.variables:
                t = v.targets[0] if v.targets else None
                if t is None or t.id is None:
                    continue
                if TARGET_ID and t.id not in targets:
                    continue
                dp = t.data_path or ""
                m = RE_IDPROP.match(dp)
                if m is None:
                    continue                     # 只看自定义属性引用
                key = m.group(1)
                if PROPS and key not in PROPS:
                    continue
                hit += 1
                lines.append("  [%s] %s :: %s  变量 %s -> %s%s  expr=%r  valid=%s" % (
                    layer, owner, dr.data_path, v.name, t.id.name, dp,
                    dr.driver.expression, dr.driver.is_valid))
    lines.append("  引用合计: %d" % hit)
    if hit == 0:
        lines.append("  ⚠ 零引用 —— 先怀疑扫描不全(尤其 data.node_tree 层),再下「假控件」结论")


def scan_health(lines):
    lines.append("=== 失效体检:is_valid / 悬空引用 ===")
    invalid, dangling = [], []
    total = 0
    for layer, owner, ad in iter_animation_data():
        if not ad or not ad.drivers:
            continue
        for dr in ad.drivers:
            total += 1
            if not dr.driver.is_valid:
                invalid.append("[%s] %s :: %s expr=%r" % (layer, owner, dr.data_path, dr.driver.expression))
            for v in dr.driver.variables:
                t = v.targets[0] if v.targets else None
                if t is None or t.id is None:
                    continue
                dp = t.data_path or ""
                m = RE_IDPROP.match(dp)
                if m and m.group(1) not in t.id.keys():
                    dangling.append("[%s] %s :: %s 变量 %s -> %s%s (键已不存在)" % (
                        layer, owner, dr.data_path, v.name, t.id.name, dp))
    lines.append("  驱动总数: %d" % total)
    lines.append("  失效驱动(is_valid=False): %d" % len(invalid))
    for x in invalid:
        lines.append("    ✗ " + x)
    lines.append("  悬空引用(指向已删属性): %d" % len(dangling))
    for x in dangling:
        lines.append("    ✗ " + x)
    lines.append("  判据: 两者都必须为 0 —— %s" % (
        "PASS" if (not invalid and not dangling) else "FAIL"))


def main():
    lines = []
    lines.append("场景: %s | 当前帧: %s" % (bpy.context.scene.name, bpy.context.scene.frame_current))
    if MODE in ('refs', 'both'):
        scan_refs(lines)
    if MODE in ('health', 'both'):
        scan_health(lines)
    text = "\n".join(lines)
    print(text)
    if OUT_DIR:
        import os
        os.makedirs(OUT_DIR, exist_ok=True)
        p = os.path.join(OUT_DIR, "param_ref_scan_%s.txt" % MODE)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        print("报告已写入: " + p)


main()
