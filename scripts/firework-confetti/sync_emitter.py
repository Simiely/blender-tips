# ============================================================
# 同步发射器到发射点空对象位置
# 用法: python send.py sync_emitter.py
# 在 Blender 中移动发射点空对象后，运行此脚本同步
# ============================================================
import bpy

# 查找所有礼花前缀
for prefix in ["礼花_01", "礼花_02", "礼花_03", "礼花_04"]:
    emitter = bpy.data.objects.get(f"{prefix}_emitter")
    turb = bpy.data.objects.get(f"{prefix}_turbulence")

    # 找到对应的发射点空对象
    launch_empty = None
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and "发射点，方向Z向" in o.name:
            # 按序号匹配
            num = prefix.split("_")[1]
            if num in o.name:
                launch_empty = o
                break

    if launch_empty and emitter:
        emitter.location = launch_empty.location.copy()
        emitter.rotation_euler = launch_empty.rotation_euler.copy()
        if turb:
            turb.location = launch_empty.location.copy()
        print(f"{prefix} 同步到 ({launch_empty.location.x:.1f}, {launch_empty.location.y:.1f}, {launch_empty.location.z:.1f})")
    elif launch_empty:
        print(f"{prefix} 发射器不存在，跳过")
    else:
        print(f"{prefix} 未找到匹配的发射点空对象")