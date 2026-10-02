# 射灯阵列「花开 / 花闭合」径向摆动系统 —— 主构建脚本
#
# 经 9877/9888 桥执行(不要写 if __name__=='__main__' 守卫, 桥端 __name__ 是 builtins)
#
# 几何约定:
#   起始线(0 度) = 灯 -> 中轴线对象 的连线 (可能是倾斜的, 取决于中轴对象高度)
#   旋转平面     = 灯与竖直中轴线确定的竖直径向平面
#   旋转轴       = 该平面内的水平切向轴
#   层级         = 射灯(位置) -> 铰链(rotation_euler=(alpha,0,rz)) -> 灯(pi/2+elev,0,0)
#
# 节奏(拍频):
#   alpha_i(t) = amin + (amax-amin)*(0.5 - 0.5*cos(2*pi*(t*f_i - sync*(f_i-1))/period))
#   f_i = 1 + spread*i/7
#   => t = sync 时括号内恒为 sync/period, 与 i 无关 => 8 盏精确同步
import bpy
import math
import re
from mathutils import Vector

# ============ 配置区(按工程改这里) ============
COLLECTION = "动态灯的坐标"        # 灯所在的集合
CENTER_OBJ = "绽放中轴线"          # 中轴线对象(摆动基准与"花心")
SPOT_PREFIX = "射灯"               # 定位空对象名前缀
LAMP_PREFIX = "射灯_光"            # 灯对象名前缀
HINGE_PREFIX = "射灯_铰链"         # 铰链对象名前缀

PERIOD = 240.0        # 一次完整开合的帧数
SYNC = 600.0          # 8 盏精确同步的帧
SPREAD = 0.10         # 速度差幅度: 最快比最慢快 10%
MIN_DEG = 0.0         # 起始角(0 = 起始线本身)
MAX_DEG = 125.0       # 完全展开角

PARAM_PREFIX = "bloom_"            # 场景自定义属性前缀
DEFAULTS = {
    PARAM_PREFIX + "period": PERIOD,
    PARAM_PREFIX + "sync_frame": SYNC,
    PARAM_PREFIX + "spread": SPREAD,
    PARAM_PREFIX + "min_deg": MIN_DEG,
    PARAM_PREFIX + "max_deg": MAX_DEG,
}
FORCE = (PARAM_PREFIX + "min_deg", PARAM_PREFIX + "max_deg")   # 摆幅参数强制覆盖
# =============================================

sc = bpy.context.scene
col = bpy.data.collections.get(COLLECTION)
assert col is not None, "集合不存在: " + COLLECTION

for k, v in DEFAULTS.items():
    if k in FORCE or k not in sc:
        sc[k] = v
    try:
        sc.id_properties_ui(k).update(description=k)
    except Exception:
        pass
print("PARAMS", {k: sc[k] for k in DEFAULTS})

ctr = bpy.data.objects.get(CENTER_OBJ)
assert ctr is not None, "中轴线对象不存在: " + CENTER_OBJ
C = Vector(ctr.location)
print("CENTER", tuple(round(v, 4) for v in C))

# ---- 取定位空对象: 严格匹配 "射灯" 或 "射灯.NNN", 避免误吞 射灯_光 / 射灯_铰链 ----
pat = re.compile(r"^%s(\.\d{3})?$" % re.escape(SPOT_PREFIX))
empties = [o for o in col.objects if o.type == 'EMPTY' and pat.match(o.name)]
assert len(empties) == 8, "期望 8 个定位空对象, 实得 %d" % len(empties)
empties = sorted(empties, key=lambda o: math.atan2(o.location.y - C.y, o.location.x - C.x))

created = []
for i, e in enumerate(empties):
    d = Vector(e.location) - C
    r_hat = Vector((d.x, d.y, 0.0)).normalized()               # 径向(轴 -> 灯)
    t_hat = Vector((0.0, 0.0, 1.0)).cross(r_hat).normalized()  # 切向 = 旋转轴
    rz = math.atan2(t_hat.y, t_hat.x)                          # 铰链绕 Z 的静态对齐角

    d_full = C - Vector(e.location)
    horiz = math.hypot(d_full.x, d_full.y)
    elev = math.atan2(d_full.z, horiz)                         # 起始线仰角(朝内上方为正)

    hinge_name = e.name.replace(SPOT_PREFIX, HINGE_PREFIX, 1)
    lamp_name = e.name.replace(SPOT_PREFIX, LAMP_PREFIX, 1)

    hinge = bpy.data.objects.get(hinge_name)
    if hinge is None:
        hinge = bpy.data.objects.new(hinge_name, None)
        hinge.empty_display_type = 'PLAIN_AXES'
        hinge.empty_display_size = 0.5
        col.objects.link(hinge)
    hinge.location = (0.0, 0.0, 0.0)
    hinge.parent = e
    hinge.rotation_euler = (0.0, 0.0, rz)

    lamp = bpy.data.objects.get(lamp_name)
    assert lamp is not None, "灯对象缺失: " + lamp_name
    lamp.parent = hinge
    lamp.location = (0.0, 0.0, 0.0)
    lamp.rotation_euler = (math.pi / 2.0 + elev, 0.0, 0.0)

    if not hinge.animation_data:
        hinge.animation_data_create()
    for dr in list(hinge.animation_data.drivers):
        if dr.data_path == "rotation_euler" and dr.array_index == 0:
            hinge.animation_data.drivers.remove(dr)

    dr = hinge.animation_data.drivers.new("rotation_euler", index=0)
    dr.driver.type = 'SCRIPTED'
    dr.driver.expression = (
        "amin*pi/180 + (amax-amin)*pi/180"
        "*(0.5 - 0.5*cos(2*pi*(fr*(1+spread*%d/7) - sync*spread*%d/7)/period))" % (i, i)
    )

    def add_var(name, data_path):
        v = dr.driver.variables.new()
        v.name = name
        v.type = 'SINGLE_PROP'
        tg = v.targets[0]
        tg.id_type = 'SCENE'      # ★ 5.2 必须先指定, 否则 id 只接受 Object
        tg.id = sc
        tg.data_path = data_path

    add_var("fr", "frame_current")
    add_var("period", '["%speriod"]' % PARAM_PREFIX)
    add_var("sync", '["%ssync_frame"]' % PARAM_PREFIX)
    add_var("spread", '["%sspread"]' % PARAM_PREFIX)
    add_var("amin", '["%smin_deg"]' % PARAM_PREFIX)
    add_var("amax", '["%smax_deg"]' % PARAM_PREFIX)

    created.append((e.name, hinge_name, lamp_name, i, elev))
    print("  SET", e.name, "-> i", i,
          "| 方位角", round(math.degrees(math.atan2(d.y, d.x)), 2),
          "| 起始线仰角", round(math.degrees(elev), 3))

bpy.context.view_layer.update()
print("BUILD_DONE", len(created))
