# -*- coding: utf-8 -*-
# P60 —— 活体端到端核验：看门狗在【当前 Blender 会话】里到底有没有在跑？
#   判据：控制器上的 5 个属性值 与 材质驱动求值后的真值 是否一致。
#   若一致 ⇒ 用户改过属性后驱动确实被重算了（看门狗活着）
#   若不一致 ⇒ 驱动停在旧值（看门狗没跑）
import bpy, json, time

rep = {"t0": time.time()}
MATNAME = "竖向灯001_噪波滚动发光"
CTRLNAME = "竖向灯001_噪波控制"
TEXTNAME = "噪波滚动控制.py"

mat = bpy.data.materials.get(MATNAME)
ctl = bpy.data.objects.get(CTRLNAME)
nt = mat.node_tree

# ---- 1. 看门狗函数是否还在定时器里 ----
watch_info = {"module_has_watch": None, "is_registered": None, "api_available": None, "err": None}
try:
    txt = bpy.data.texts.get(TEXTNAME)
    watch_info["text_exists"] = txt is not None
    if txt is not None:
        mod = txt.as_module()
        fn = getattr(mod, "_watch", None)
        watch_info["module_has_watch"] = fn is not None
        api = getattr(bpy.app.timers, "is_registered", None)
        watch_info["api_available"] = api is not None
        if fn is not None and api is not None:
            watch_info["is_registered"] = bool(api(fn))
except Exception as e:
    watch_info["err"] = repr(e)
rep["watchdog"] = watch_info

# ---- 2. 属性值 vs 驱动求值真值 ----
props = {k: ctl[k] for k in ("噪波密度", "噪波种子", "Z向速度", "噪波对比度", "发光强度")}
dg = bpy.context.evaluated_depsgraph_get()
ent = mat.evaluated_get(dg).node_tree
mp = ent.nodes["滚动映射"]; nz = ent.nodes["噪波纹理"]; rp = ent.nodes["对比度"]; ml = ent.nodes["发光强度"]
ev = {
    "mapZ": float(mp.inputs["Location"].default_value[2]),
    "scale": float(nz.inputs["Scale"].default_value),
    "W": float(nz.inputs["W"].default_value),
    "ramp": [float(rp.color_ramp.elements[0].position), float(rp.color_ramp.elements[1].position)],
    "mult": float(ml.inputs[1].default_value),
}
fr = bpy.context.scene.frame_current
ct = float(props["噪波对比度"])
expect = {
    "mapZ": fr * float(props["Z向速度"]),
    "scale": float(props["噪波密度"]),
    "W": float(props["噪波种子"]) * 10.0,
    "ramp": [max(0.0, 0.5 - 0.5 / ct), min(1.0, 0.5 + 0.5 / ct)],
    "mult": float(props["发光强度"]),
}
rep["frame"] = fr
rep["ctrl_props"] = props
rep["driver_evaluated"] = ev
rep["driver_expected"] = {k: (round(v, 4) if isinstance(v, float) else [round(x, 4) for x in v])
                          for k, v in expect.items()}
RE = [("mapZ", "mapZ", 1e-4), ("scale", "scale", 1e-4), ("W", "W", 1e-3), ("mult", "mult", 1e-4)]
checks = {}
for a, b, tol in RE:
    checks[a] = abs(ev[a] - expect[b]) <= tol
checks["ramp"] = all(abs(ev["ramp"][i] - expect["ramp"][i]) <= 1e-3 for i in range(2))
rep["checks"] = checks
rep["all_track"] = all(checks.values())
rep["verdict"] = ("看门狗在跑：控件真值 == 驱动真值" if rep["all_track"]
                  else "驱动停在旧值：看门狗可能没在跑（需要重新 register）")

rep["object_count"] = len(bpy.data.objects)
rep["scene_now"] = bpy.context.scene.name
rep["total_sec"] = round(time.time() - rep["t0"], 2)
print("P60_BEGIN")
print(json.dumps(rep, ensure_ascii=False, indent=1))
print("P60_END")
