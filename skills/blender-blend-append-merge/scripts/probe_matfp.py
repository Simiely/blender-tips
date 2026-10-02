# -*- coding: utf-8 -*-
"""材质指纹：节点树结构 + 连线 + 全部输入默认值 + 关键属性。用于判断两文件同名材质是否同一份。"""
import bpy, os, json, hashlib

WORK = os.environ.get("AMB_WORK", os.getcwd())   # 报告/基线/日志都写这里
TAG = os.environ.get("MT_TAG", "?")
D = bpy.data


def val(v):
    try:
        if hasattr(v, "__len__") and not isinstance(v, str):
            return tuple(round(float(x), 5) for x in v)
        return round(float(v), 5)
    except Exception:
        return str(v)[:40]


def mat_fp(m):
    h = hashlib.sha1()
    h.update(("blend_method=%s|shadow=%s|use_backface=%s|"
              % (getattr(m, "blend_method", "?"), getattr(m, "shadow_method", "?"),
                 getattr(m, "use_backface_culling", "?"))).encode())
    nt = m.node_tree
    if nt is None:
        return "NO_NODETREE", {}
    nodes = sorted(nt.nodes, key=lambda n: n.name)
    for n in nodes:
        h.update(("N|%s|%s|%s|" % (n.name, n.type, n.bl_idname)).encode())
        for i in n.inputs:
            h.update(("I|%s|%s|%s|" % (i.name, i.type, val(getattr(i, "default_value", None)))).encode())
        for o in n.outputs:
            h.update(("O|%s|%s|" % (o.name, o.type)).encode())
        if hasattr(n, "blend_type"):
            h.update(("B|%s|" % n.blend_type).encode())
        # 节点内部数据（ColorRamp 色标 / Mapping 等）
        try:
            for e in n.color_ramp.elements:
                h.update(("CE|%.5f|%s|" % (e.position, val(e.color))).encode())
        except Exception:
            pass
        try:
            h.update(("SOCK|%s|" % str(n.mute)).encode())
        except Exception:
            pass
    for l in sorted(nt.links, key=lambda x: (x.from_node.name, x.from_socket.name,
                                             x.to_node.name, x.to_socket.name)):
        h.update(("L|%s.%s>%s.%s|" % (l.from_node.name, l.from_socket.name,
                                      l.to_node.name, l.to_socket.name)).encode())
    return h.hexdigest()[:16], {
        "nodes": len(nt.nodes), "links": len(nt.links),
        "node_types": sorted(set(n.type for n in nt.nodes)),
        "images": [n.image.name for n in nt.nodes
                   if n.type == 'TEX_IMAGE' and getattr(n, "image", None)],
    }


out = {}
for m in D.materials:
    fp, info = mat_fp(m)
    out[m.name] = {"fp": fp, "users": m.users, "info": info}

outw = {}
for w in D.worlds:
    nt = w.node_tree
    h = hashlib.sha1()
    if nt:
        for n in sorted(nt.nodes, key=lambda n: n.name):
            h.update(("N|%s|%s|" % (n.name, n.type)).encode())
            for i in n.inputs:
                h.update(("I|%s|%s|" % (i.name, val(getattr(i, "default_value", None)))).encode())
        for l in sorted(nt.links, key=lambda x: (x.from_node.name, x.to_node.name)):
            h.update(("L|%s>%s|" % (l.from_node.name, l.to_node.name)).encode())
    outw[w.name] = {"fp": h.hexdigest()[:16], "use_nodes": w.use_nodes,
                    "nodes": len(nt.nodes) if nt else 0}

res = {"tag": TAG, "filepath": D.filepath, "materials": out, "worlds": outw}
with open(os.path.join(WORK, "matfp_%s.json" % TAG), "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("ok", TAG, len(out), "materials,", len(outw), "worlds")
