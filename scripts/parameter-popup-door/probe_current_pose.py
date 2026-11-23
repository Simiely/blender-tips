import bpy
from collections import Counter

print("dirty=%s objects=%d frame=%d range=%d-%d" % (
    bpy.data.is_dirty, len(bpy.data.objects), bpy.context.scene.frame_current,
    bpy.context.scene.frame_start, bpy.context.scene.frame_end))

TARGET = ["右侧门", "左侧门", "角色伸出", "3点钟方向"]
for nm in TARGET:
    o = bpy.data.objects.get(nm)
    if o is None:
        print("MISSING", nm)
        continue
    ad = o.animation_data
    print("OBJ %-12s type=%-7s loc=%s rotE=%s scale=%s parent=%s" % (
        nm, o.type, [round(float(x), 6) for x in o.location],
        [round(float(x), 6) for x in o.rotation_euler],
        [round(float(x), 6) for x in o.scale],
        o.parent.name if o.parent else "-"))
    if ad is None:
        print("   animation_data=None")
    else:
        print("   action=%s drivers=%d nla=%d" % (
            ad.action.name if ad.action else "-", len(ad.drivers), len(ad.nla_tracks)))
        for d in ad.drivers:
            print("     DRIVER %s[%d] expr=%s valid=%s" % (
                d.data_path, d.array_index, d.driver.expression, d.is_valid))

ctrl = bpy.data.objects.get("3点钟_弹出控制")
print("CONTROLLER_EXISTS=%s" % (ctrl is not None))
if ctrl is not None:
    print("   type=%s custom=%s" % (ctrl.type, list(ctrl.keys())))

# 检查这些属性键是否已被占用
for nm in TARGET:
    o = bpy.data.objects.get(nm)
    if o is not None:
        print("KEYS %-12s %s" % (nm, [k for k in o.keys() if not k.startswith("_")]))

# 10点钟对照（角色缩回基准）
for nm in ("角色弹出02", "右侧门.001", "左侧门.001"):
    o = bpy.data.objects.get(nm)
    if o is not None:
        print("REF %-14s loc=%s rotE=%s parent=%s" % (
            nm, [round(float(x), 6) for x in o.location],
            [round(float(x), 6) for x in o.rotation_euler],
            o.parent.name if o.parent else "-"))
print("=== RECON DONE ===")
