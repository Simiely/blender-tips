import bpy
import json

OUT = r"D:/workbuddy/2026-11-23-17-56-14/bubble_slow_all_report.json"

ctrl = bpy.data.objects.get("泡泡控制")
ng = bpy.data.node_groups.get("泡泡发射_GN")
scene = bpy.context.scene

if ctrl is None or ng is None:
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump({"error": "missing controller or node group", "pass": False},
                  fp, ensure_ascii=False, indent=2)
    print("BUBBLE_SLOW_ALL_ERROR")
else:
    old_props = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")}
    old_frame = scene.frame_current

    ctrl["生命周期"] = 240.0
    ctrl["泡泡数量"] = 200
    ui = ctrl.id_properties_ui("生命周期")
    ui.update(min=24.0, max=600.0, default=240.0,
              description="单个泡泡完整生命周期帧数；越大整体越慢")
    ui = ctrl.id_properties_ui("泡泡数量")
    ui.update(min=60, max=1200, default=200, description="实例泡泡数量")

    ctrl.update_tag(refresh={"OBJECT"})
    ng.update_tag()
    bpy.context.view_layer.update()
    scene.frame_set(300)
    bpy.context.view_layer.update()

    new_props = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")}
    report = {
        "file": bpy.data.filepath,
        "old_frame": old_frame,
        "frame_current_set": scene.frame_current,
        "old_props": old_props,
        "new_props": new_props,
        "changes": {
            "生命周期": [old_props.get("生命周期"), ctrl["生命周期"]],
            "泡泡数量": [old_props.get("泡泡数量"), ctrl["泡泡数量"]],
        },
        "spawn_rate": {
            "old_per_frame": round(float(old_props.get("泡泡数量", 360)) / float(old_props.get("生命周期", 96)), 6),
            "new_per_frame": round(200.0 / 240.0, 6),
        },
        "preserved": ["起始帧", "泡泡半径", "扩散半径", "上升高度", "随机种子",
                      "边界余量", "范围匹配", "下落消散", "顶点比例"],
        "note": "桥只改内存，未保存 .blend",
    }
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print("BUBBLE_SLOW_ALL_OK")
