# -*- coding: utf-8 -*-
"""
按材质合并网格体 —— 执行脚本

把工程里成千上万个零碎网格,按「材质列表 + UV 配置」相同的原则合并成极少数几个对象,
解决 *对象太多导致 GUI 卡顿* 的根因。典型场景:SketchUp / CAD 导入后的工程。

运行位置(**不是**桥 send.py,是系统命令行):
    blender.exe --background --factory-startup "<源.blend>" ^
                --python merge_by_material.py -- "<输出.blend>" [要排除的对象名...]

参数:
    <输出.blend>        必须有。一律另存,绝不覆盖源文件(脚本内有校验).
    [要排除的对象名...] 可选,多个用空格分隔。会与 <cwd>/exclude.txt 里的名单合并。

输出:
    日志同时写盘 + 打印 stdout。<cwd>/merge_run.log,长任务后台跑时可持续 tail 查看。
"""

import bpy, collections, time, os, sys

# ==================== 配置项 ====================
# 日志 / 报告落盘位置(默认当前工作目录)
HERE = os.getcwd()
LOG = os.environ.get("MBM_LOG", os.path.join(HERE, "merge_run.log"))
# 排除名单文件:一行一个对象名,# 开头为注释
EXCLUDE_FILE = os.path.join(HERE, "exclude.txt")
# 合并后对象名前缀(取该组第一个材质名)
NAME_PREFIX = "M_"
# 空物体是否清理:SKetchUp 组件层级在合并后就失去意义了,默认清掉
PURGE_EMPTY = True
# ================================================

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.splitext(bpy.data.filepath)[0] + "_合并.blend"

# ---- 安全闸:绝不覆盖源文件 ----
_src = os.path.normpath(os.path.abspath(bpy.data.filepath or ""))
_out = os.path.normpath(os.path.abspath(OUT))
if _src and _src == _out:
    raise SystemExit("[SAFETY] 输出路径等于源文件,拒绝覆盖。请换个文件名。")

t0 = time.time()


def P(*a):
    """同时写日志盘 + 打印 stdout,保证长任务后台跑也能看进度。"""
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("[%7.1fs] %s\n" % (time.time() - t0, s))
    try:
        print("==" + s, flush=True)
    except Exception:
        pass


P("SRC", bpy.data.filepath)
P("OUT", OUT)

# ---- 排除名单:文件 + 命令行附加 ----
EXCLUDE = set()
if os.path.isfile(EXCLUDE_FILE):
    with open(EXCLUDE_FILE, encoding="utf-8") as f:
        for line in f:
            n = line.strip()
            if n and not n.startswith("#"):
                EXCLUDE.add(n)
EXCLUDE.update(a for a in argv[1:] if a and not a.endswith(".blend"))
P("EXCLUDE_LIST", sorted(EXCLUDE) if EXCLUDE else "(空)")


def totals():
    v = p = 0
    for o in bpy.data.objects:
        if o.type == "MESH" and o.data:
            v += len(o.data.vertices)
            p += len(o.data.polygons)
    return v, p


all_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
meshes = [o for o in all_meshes if o.name not in EXCLUDE]
excluded = [o for o in all_meshes if o.name in EXCLUDE]

# 名单里的名字在工程中不存在 → 告警(多半是手抖写错,静默跳过会埋雷)
missing = sorted(EXCLUDE - {o.name for o in all_meshes})
if missing:
    P("!! 排除名单里有工程中不存在的对象:", missing)

for o in excluded:
    P("EXCLUDED", o.name, "| 顶点", len(o.data.vertices), "| 面", len(o.data.polygons),
      "| 材质", [m.name if m else None for m in o.data.materials])

v0, p0 = totals()
P("BEFORE | 网格对象", len(all_meshes), "→ 参与合并", len(meshes), "| 排除", len(excluded),
  "| 顶点", v0, "| 面", p0,
  "| 空物体", len([o for o in bpy.data.objects if o.type == "EMPTY"]))

# ---- 1. 解除父子关系但保留世界变换(否则 join 的坐标系会错,模型散架) ----
# 这是整个脚本最关键的一步:对象若有父级 / 旋转 / 缩放,直接 join 会丢失世界位姿。
if len(meshes) > 1:
    try:
        with bpy.context.temp_override(selected_editable_objects=meshes, active_object=meshes[0]):
            bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        P("PARENT_CLEARED_OK")
    except Exception as e:
        P("PARENT_CLEAR_ERR", repr(e))

# ---- 2. 按「材质列表 + UV 配置」分组 ----
# key 必须带上 UV 层配置:若把带 UV 的和不带 UV 的并进同一组,UV 会被拉平丢失。
groups = collections.defaultdict(list)
for o in meshes:
    key = (tuple((m.name if m else "<空>") for m in o.data.materials),
           tuple(l.name for l in o.data.uv_layers))
    groups[key].append(o)
P("GROUP_COUNT", len(groups))

# ---- 3. 逐组合并(对象多的组排在前面,先啃硬骨头) ----
ok = err = 0
ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))
for i, (key, g) in enumerate(ordered):
    mats = key[0]
    if len(g) == 1:
        result = g[0]
    else:
        try:
            with bpy.context.temp_override(selected_editable_objects=g, active_object=g[0]):
                bpy.ops.object.join()
            result = g[0]
        except Exception as e:
            P("JOIN_ERR", list(mats)[:3], repr(e))
            err += 1
            continue
    ok += 1
    base = mats[0] if mats else "无材质"
    nm = (NAME_PREFIX + base)[:55]
    n, k = nm, 1
    while n in bpy.data.objects:
        n = nm + ".%03d" % k
        k += 1
    result.name = n
    P("JOINED", "%3d/%3d" % (i + 1, len(ordered)), n,
      "| 并入对象", len(g), "| 顶点", len(result.data.vertices),
      "| 面", len(result.data.polygons))

P("MERGE_OK", ok, "| ERR", err)

# ---- 4. 清理空物体(迭代到稳定,而不是只删一轮「当前无子级」的) ----
# 删完一批会「长出」新的无子级 EMPTY,必须循环到不动点。
removed = 0
if PURGE_EMPTY:
    for _ in range(30):
        dead = [o for o in bpy.data.objects
                if o.type == "EMPTY" and not o.children and not o.children_recursive]
        if not dead:
            break
        for o in dead:
            bpy.data.objects.remove(o, do_unlink=True)
        removed += len(dead)
P("EMPTIES_REMOVED", removed)

# ---- 5. 几何守恒校验 ----
v1, p1 = totals()
P("AFTER | 网格对象", len([o for o in bpy.data.objects if o.type == "MESH"]),
  "| 顶点", v1, "| 面", p1,
  "| 空物体", len([o for o in bpy.data.objects if o.type == "EMPTY"]))
P("CHECK_VERTS", "一致" if v0 == v1 else "!! 不一致 %d -> %d" % (v0, v1))
P("CHECK_POLYS", "一致" if p0 == p1 else "!! 不一致 %d -> %d" % (p0, p1))

os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
P("SAVING...")
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=True,
                            check_existing=False, copy=False)
P("SAVED", OUT, "%.1f MB" % (os.path.getsize(OUT) / 1024 / 1024))
P("DONE")
