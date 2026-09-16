"""给一批自定义属性批量写「周期三角波 + CYCLES 循环修饰器」关键帧动画。

供 9877 桥经 send.py 送进运行中的 Blender 执行。用法:

    python send.py skills/blender-loop-keyframe-anim/scripts/write_loop_anim.py

按场景改下面的 TARGET_OBJ / ANIMS 即可。写入前按需备份（见顶层注释与 AGENTS.md 纪律）。"""
import bpy

# ===== 配置 =====
TARGET_OBJ = "竖向灯001_噪波控制"   # 要打动画的对象
FRAME_START_GLOBAL = 1
FRAME_END_GLOBAL = 450              # CYCLES 循环铺满的末帧
# ANIMS: 属性名 -> [(帧,值), ...] 一个完整周期（末帧值=首帧值做无缝循环）
ANIMS = {
    "面光统一强度": [(1, 8.0), (16, 13.0), (31, 8.0)],   # 30 帧周期 8->13->8
    "发光强度":     [(1, 5.0), (11, 50.0), (21, 5.0)],   # 20 帧周期 5->50->5
}

# ===== 实现 =====
def write_loop_anim(obj, datapath, pts, frame_start, frame_end):
    ad = obj.animation_data
    a = ad.action
    cb = a.layers[0].strips[0].channelbags[0]
    fcurves = cb.fcurves
    # 幂等：移除同路径旧 fcurve
    for fc in list(fcurves):
        if fc.data_path == datapath:
            fcurves.remove(fc)
    fc = fcurves.new(datapath, index=0)
    kps = fc.keyframe_points
    kps.add(len(pts))
    for i, (fr, val) in enumerate(pts):
        kp = kps[i]
        kp.co = (float(fr), float(val))
        kp.interpolation = 'BEZIER'   # 贝塞尔 = 缓入缓出（平滑三角波）
    m = fc.modifiers.new('CYCLES')
    # 5.x FModifierCycles 无 mode 属性，默认正向循环
    m.frame_start = float(frame_start)
    m.frame_end = float(frame_end)
    fc.update()
    return fc

def main():
    obj = bpy.data.objects.get(TARGET_OBJ)
    if not obj:
        raise SystemExit(f"找不到对象: {TARGET_OBJ}")
    ad = obj.animation_data
    if not (ad and ad.action):
        raise SystemExit(f"{TARGET_OBJ} 无 animation_data/action，先确认对象是否有动画")
    for prop, pts in ANIMS.items():
        path = f'["{prop}"]'
        fc = write_loop_anim(obj, path, pts, FRAME_START_GLOBAL, FRAME_END_GLOBAL)
        print(f"{prop}: keys={[(int(k.co[0]), k.co[1]) for k in fc.keyframe_points]} "
              f"mods={[m.type for m in fc.modifiers]}")
    scn = bpy.context.scene
    scn.frame_start = FRAME_START_GLOBAL
    scn.frame_end = FRAME_END_GLOBAL
    print(f"帧范围: {scn.frame_start}-{scn.frame_end}")

main()  # 桥 exec 命名空间无 __name__，必须无条件调用