# verify_purge.py — 清理后独立核验（必须另起脚本跑，不要复用执行脚本的内存状态）
#
# 用法：与 purge_empties.py 同目录，改 OUT_DIR / BASELINE 即可。
# 若存在 BASELINE json（由 purge 前的体检脚本写出）则做前后对比，否则只做绝对值检查。
import bpy, os, json
from collections import defaultdict, Counter
from mathutils import Vector

# !! 必须改：与 purge_empties.py / snapshot_baseline.py 保持一致
OUT_DIR = r"C:\path\to\workdir"
REPORT = os.path.join(OUT_DIR, "verify_final.txt")
BASELINE = os.path.join(OUT_DIR, "cleanup_baseline.json")
NAME_FILES = ("deleted_empty_names.txt", "purge_final_names.txt")

R = []
def p(*a):
    R.append(" ".join(str(x) for x in a))

base = None
if os.path.exists(BASELINE):
    try:
        with open(BASELINE, "r", encoding="utf-8") as f:
            base = json.load(f)
    except Exception:
        base = None

names = set()
for fn in NAME_FILES:
    fp = os.path.join(OUT_DIR, fn)
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if not ln or ln.startswith("#") or ln.startswith("NAME\t"):
                continue
            if ln.strip():
                names.add(ln.split("\t")[0])

objs = list(bpy.data.objects)
children = defaultdict(list)
for o in objs:
    if o.parent is not None:
        children[o.parent.name].append(o)

emp = [o for o in objs if o.type == 'EMPTY']
emp_noch = [o for o in emp if len(children.get(o.name, [])) == 0]

cur = {
    "total": len(objs),
    "empty": len(emp),
    "non_empty": len(objs) - len(emp),
    "mesh": sum(1 for o in objs if o.type == 'MESH'),
    "camera": sum(1 for o in objs if o.type == 'CAMERA'),
    "light": sum(1 for o in objs if o.type == 'LIGHT'),
    "parented_to_empty": sum(1 for o in objs if o.parent is not None and o.parent.type == 'EMPTY'),
    "empties_with_nonempty_child": sum(1 for o in emp
        if any(c.type != 'EMPTY' for c in children.get(o.name, []))),
    "materials": len(bpy.data.materials),
    "collections": len(bpy.data.collections),
    "scenes": len(bpy.data.scenes),
}

p("=" * 72)
p("清理后独立核验  |  " + bpy.data.filepath)
p("=" * 72)
p("累计被删名单: %d 个" % len(names))
p("")

if base:
    p("%-26s %10s %10s %s" % ("项目", "基线", "现在", "结论"))
    for k in ("total", "empty", "non_empty", "mesh", "camera", "light",
              "parented_to_empty", "empties_with_nonempty_child",
              "materials", "collections", "scenes"):
        if k not in base:
            continue
        b, c = base[k], cur[k]
        # 这几个必须完全不变
        strict = k in ("non_empty", "mesh", "camera", "light", "empties_with_nonempty_child",
                       "materials", "collections", "scenes")
        concl = ("OK" if b == c else "*** 变化 ***") if strict else \
                ("减少 %d" % (b - c) if c <= b else "*** 增加了 ***")
        p("%-26s %10s %10s %s" % (k, b, c, concl))
    p("")
    if "parented_to_empty" in base:
        p("  * parented_to_empty 减少 %d 属正常：被删的 EMPTY 自身也可能挂在 EMPTY 下"
          % (base["parented_to_empty"] - cur["parented_to_empty"]))
        p("")
else:
    p("(无基线文件，只做绝对值检查)")
    for k, v in cur.items():
        p("%-26s %10s" % (k, v))
    p("")

p("%-26s %10s %10s %s" % ("EMPTY 无子级", "-", len(emp_noch),
                          "OK 已收敛" if len(emp_noch) == 0 else "*** 仍有残留 ***"))
p("")

p("[1] 被删名单里仍存在的对象: %d (应 0)" % len([n for n in names if n in bpy.data.objects]))

dangle = []
for ob in objs:
    for c in ob.constraints:
        try:
            if c.type in ('TRACK_TO', 'COPY_LOCATION', 'COPY_ROTATION', 'COPY_SCALE',
                          'COPY_TRANSFORMS', 'DAMPED_TRACK', 'IK', 'FOLLOW_PATH',
                          'CHILD_OF', 'LOCKED_TRACK', 'STRETCH_TO', 'CLAMP_TO', 'SHRINKWRAP') \
               and c.target is None:
                dangle.append((ob.name, c.type))
        except Exception:
            pass
p("[2] 悬空约束: %d" % len(dangle))
for d in dangle[:10]:
    p("    - %s" % str(d))

p("[3] 父级丢失的对象: %d"
  % len([o for o in objs if o.parent is not None and o.parent.name not in bpy.data.objects]))

roots = [o for o in objs if o.parent is None]
p("[4] 层级根对象: %d  类型: %s" % (len(roots), dict(Counter(o.type for o in roots))))

pts = []
for o in objs:
    if o.type == 'EMPTY' or o.data is None:
        continue
    try:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            pts.append((w.x, w.y, w.z))
    except Exception:
        pass
if pts:
    p("[5] 可见几何包围盒: min=(%.2f, %.2f, %.2f)  max=(%.2f, %.2f, %.2f)" % (
        min(t[0] for t in pts), min(t[1] for t in pts), min(t[2] for t in pts),
        max(t[0] for t in pts), max(t[1] for t in pts), max(t[2] for t in pts)))

miss = []
for img in bpy.data.images:
    if img.source == 'FILE' and img.filepath and img.packed_file is None:
        if not os.path.exists(bpy.path.abspath(img.filepath)):
            miss.append(img.name)
p("[6] 真缺失贴图 %d / 链接库 %d / 字体 %d / 声音 %d" % (
    len(miss),
    len([l for l in bpy.data.libraries if l.filepath
         and not os.path.exists(bpy.path.abspath(l.filepath))]),
    len([f for f in bpy.data.fonts if f.filepath
         and not os.path.exists(bpy.path.abspath(f.filepath))]),
    len([s for s in bpy.data.sounds if s.filepath
         and not os.path.exists(bpy.path.abspath(s.filepath))])))
p("    孤儿材质 %d / 孤儿图像 %d / 孤儿动作 %d" % (
    sum(1 for m in bpy.data.materials if m.users == 0),
    sum(1 for i in bpy.data.images if i.users == 0),
    sum(1 for a in bpy.data.actions if a.users == 0)))

def fam(nm):
    s = nm
    for sep in ('-', '_', '.', ' '):
        s = s.split(sep)[0]
    return s[:18]
p("")
p("[7] 最终保留的 EMPTY %d 个" % len(emp))
p("    按集合:", dict(Counter(c.name for o in emp for c in o.users_collection).most_common(12)))
p("    按命名族:", dict(Counter(fam(o.name) for o in emp).most_common(12)))
p("    空集合(无对象的集合):", [c.name for c in bpy.data.collections if len(c.all_objects) == 0])
p("")
p("is_dirty=%s" % bpy.data.is_dirty)

txt = "\n".join(R)
with open(REPORT, "w", encoding="utf-8") as f:
    f.write(txt)
print(txt)
print("=== VERIFY_PURGE DONE ===")
