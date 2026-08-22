# build_speed_light_drivers.py —— 给「速度驱动亮度」挂驱动(可幂等重跑)
#
# 用法(Blender Scripting 工作区 Run Script, 或远程桥 python send.py 本文件):
#   1. 先保证 speed_light_driver.py 的函数已注册(文本块勾 Register, 或先 run 一次)。
#   2. 配置下面 TARGETS:「灯轴心空物体名 -> 灯要跟踪的柱(目标)物体名」。
#      每盏灯会在灯数据上写 energy_panel 自定义属性(记录目标柱名), 供驱动变量读取。
#   3. 给灯的 energy 挂 SCRIPTED 驱动: speed_energy(pname, fr)。
#      pname 变量 -> 灯数据 ["energy_panel"];  fr 变量 -> scene.frame_current。
#
# 幂等: 已有 energy 驱动会先清除再重建, 重跑不叠加、不重复建灯。
import bpy

# ===== 配置 =====
# 灯轴心空对象名(灯打组在其下) -> 列表, 每项是该组内跟踪的柱目标名列表。
# 简化: 直接列出「灯 -> 目标」映射; 若灯已带 energy_panel 属性则保留其值。
# 更通用做法: 下方 AXES 指定轴心名, 灯的目标由灯数据 energy_panel 记录;
# 若灯尚无 energy_panel, 则从面板映射 PANEL_BY_AXIS 推断。
AXES = [
    "主装置01_灯向上_轴心",
    "主装置01_灯向下_轴心",
    "主装置02_灯向上_轴心",
    "主装置02_灯向下_轴心",
    "主装置03_灯向上_轴心",
    "主装置03_灯向下_轴心",
    "主装置04_灯向上_轴心",
    "主装置04_灯向下_轴心",
    "主装置05_灯向上_轴心",
    "主装置05_灯向下_轴心",
]
# 轴心名 -> 该轴心下所有灯默认跟踪的柱目标名(只用于灯尚缺 energy_panel 时补写)。
# 空则跳过; 若省略某轴心, 该轴心的灯若无 energy_panel 则维持现状。
PANEL_BY_AXIS = {}


def panel_of_light(light_data):
    """返回灯数据上记录的跟踪目标名(无则 None)。"""
    return light_data.get("energy_panel", None) or None


def main():
    scene = bpy.context.scene
    count = 0
    for ax_name in AXES:
        ax = bpy.data.objects.get(ax_name)
        if not ax:
            print("[skip] 轴心不存在:", ax_name)
            continue
        default_panel = PANEL_BY_AXIS.get(ax_name)
        for c in ax.children_recursive:
            if c.type != "LIGHT":
                continue
            ld = c.data
            panel = panel_of_light(ld) or default_panel
            if panel is None:
                print("[skip] 灯无目标:", c.name)
                continue
            # 记录目标(幂等)
            ld["energy_panel"] = panel

            # 清旧 energy 驱动
            if ld.animation_data:
                for d in list(ld.animation_data.drivers):
                    if d.data_path == "energy":
                        ld.animation_data.drivers.remove(d)

            # 挂新驱动
            drv = ld.driver_add("energy").driver
            drv.type = "SCRIPTED"
            drv.expression = "speed_energy(pname, fr)"

            v1 = drv.variables.new()
            v1.name = "pname"
            v1.type = "SINGLE_PROP"
            v1.targets[0].id_type = "LIGHT"
            v1.targets[0].id = ld
            v1.targets[0].data_path = '["energy_panel"]'

            v2 = drv.variables.new()
            v2.name = "fr"
            v2.type = "SINGLE_PROP"
            v2.targets[0].id_type = "SCENE"
            v2.targets[0].id = scene
            v2.targets[0].data_path = "frame_current"

            count += 1

    bpy.context.view_layer.update()
    print("DONE lights=", count)


if __name__ == "__main__":
    main()