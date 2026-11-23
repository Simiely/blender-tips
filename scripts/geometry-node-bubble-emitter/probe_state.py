import bpy
import json

OUT = r"D:/workbuddy/2026-11-23-17-56-14/bubble_state_probe.json"

ctrl = bpy.data.objects.get("泡泡控制")
ng = bpy.data.node_groups.get("泡泡发射_GN")
scene = bpy.context.scene


def sname(socket):
    if socket is None:
        return None
    return "%s:%s" % (getattr(socket.node, "label", socket.node.name), socket.name)


report = {
    "file": bpy.data.filepath,
    "frame_current": scene.frame_current,
    "props": {},
    "nodes": [],
    "links": [],
}

if ctrl:
    for k in ctrl.keys():
        if not k.startswith("_"):
            report["props"][k] = ctrl[k]

if ng:
    for n in ng.nodes:
        report["nodes"].append({
            "name": n.name,
            "label": n.label,
            "type": n.bl_idname,
        })
    for l in ng.links:
        report["links"].append({
            "from": sname(l.from_socket),
            "to": sname(l.to_socket),
        })

with open(OUT, "w", encoding="utf-8") as fp:
    json.dump(report, fp, ensure_ascii=False, indent=2)
print("BUBBLE_STATE_PROBE_OK")
