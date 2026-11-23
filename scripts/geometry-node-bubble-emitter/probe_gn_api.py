import bpy
import json

OUT = r"D:/workbuddy/2026-11-23-17-56-14/bubble_gn_api_report.json"
BACKUP = r"D:/workbuddy/2026-11-23-17-56-14/bubble_scene_backup_before.json"


def f(v):
    try:
        return round(float(v), 6)
    except Exception:
        return None


def vec(v):
    return [f(x) for x in v]


def sockets(items):
    out = []
    for s in items:
        out.append({
            "name": s.name,
            "identifier": s.identifier,
            "bl_idname": s.bl_idname,
            "enabled": bool(getattr(s, "enabled", True)),
        })
    return out


def backup_scene():
    objs = []
    for o in bpy.data.objects:
        d = {
            "name": o.name,
            "type": o.type,
            "parent": o.parent.name if o.parent else None,
            "location": vec(o.location),
            "rotation_euler": vec(o.rotation_euler),
            "scale": vec(o.scale),
            "world_translation": vec(o.matrix_world.translation),
            "hide_render": bool(o.hide_render),
            "hide_viewport": bool(o.hide_viewport),
            "collections": [c.name for c in o.users_collection],
            "custom_props": {k: str(o[k]) for k in o.keys() if not k.startswith("_")},
            "modifiers": [(m.name, m.type) for m in o.modifiers],
        }
        if o.type == "MESH":
            d["mesh"] = {
                "data": o.data.name,
                "vertices": len(o.data.vertices),
                "polygons": len(o.data.polygons),
            }
        objs.append(d)
    with open(BACKUP, "w", encoding="utf-8") as fp:
        json.dump({
            "file": bpy.data.filepath,
            "scene": bpy.context.scene.name,
            "frame_current": bpy.context.scene.frame_current,
            "objects": objs,
        }, fp, ensure_ascii=False, indent=2)


def main():
    backup_scene()
    ng = bpy.data.node_groups.new("__BUBBLE_GN_API_PROBE__", "GeometryNodeTree")
    report = {"file": bpy.data.filepath, "objects": len(bpy.data.objects), "nodes": {}}

    types = [
        "NodeGroupOutput",
        "GeometryNodeMeshLine",
        "GeometryNodeInputIndex",
        "FunctionNodeRandomValue",
        "GeometryNodeInputSceneTime",
        "ShaderNodeMath",
        "ShaderNodeVectorMath",
        "ShaderNodeCombineXYZ",
        "ShaderNodeSeparateXYZ",
        "ShaderNodeValue",
        "GeometryNodeObjectInfo",
        "GeometryNodeBoundBox",
        "GeometryNodeInstanceOnPoints",
        "GeometryNodeDeleteGeometry",
    ]

    try:
        if hasattr(ng, "interface"):
            out_socket = ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
            report["interface_output"] = {
                "name": out_socket.name,
                "identifier": out_socket.identifier,
                "socket_type": out_socket.bl_socket_idname,
            }

        for t in types:
            try:
                n = ng.nodes.new(t)
                d = {
                    "inputs": sockets(n.inputs),
                    "outputs": sockets(n.outputs),
                }
                if hasattr(n, "mode"):
                    d["mode"] = str(n.mode)
                    d["modes"] = [x.identifier for x in n.bl_rna.properties["mode"].enum_items]
                if hasattr(n, "data_type"):
                    d["data_type"] = str(n.data_type)
                    d["data_types"] = [x.identifier for x in n.bl_rna.properties["data_type"].enum_items]
                if t == "ShaderNodeMath":
                    d["operations"] = [x.identifier for x in n.bl_rna.properties["operation"].enum_items]
                if t == "ShaderNodeVectorMath":
                    d["operations"] = [x.identifier for x in n.bl_rna.properties["operation"].enum_items]
                if t == "FunctionNodeRandomValue":
                    try:
                        n.data_type = "FLOAT"
                        d["float_inputs"] = sockets(n.inputs)
                        d["float_outputs"] = sockets(n.outputs)
                    except Exception as e:
                        d["float_error"] = repr(e)
                    try:
                        n.data_type = "VECTOR"
                        d["vector_inputs"] = sockets(n.inputs)
                        d["vector_outputs"] = sockets(n.outputs)
                    except Exception as e:
                        d["vector_error"] = repr(e)
                report["nodes"][t] = d
                ng.nodes.remove(n)
            except Exception as e:
                report["nodes"][t] = {"error": repr(e)}
    finally:
        bpy.data.node_groups.remove(ng)

    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_GN_API_OK")


try:
    main()
except Exception as e:
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump({"error": repr(e)}, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_GN_API_ERROR")
