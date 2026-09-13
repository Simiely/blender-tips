# purge_empties.py — Blender EMPTY 收敛清理（不动点版 · 通用可复用）
#
# 用法：把本文件内容经 9877 桥发进 Blender，或直接 Run Script。
#       改 OUT_DIR 即可。
#
# 判定规则（不动点）：一个 EMPTY 需要保留 <=> 它「支撑」某个非 EMPTY 对象
#   支撑 = a) 直接挂非 EMPTY 子级 / b) 子级里有需保留的 EMPTY
#          / c) 被需保留的对象引用 / d) 被外部数据块引用
#
# 三重安全闸：① 只删 type=='EMPTY' ② 删后无非 EMPTY 对象失去父级
#             ③ 删后无保留对象产生悬空引用（由引用图保证）
#
# !! 关键实现约束：所有要用的字段（name / 集合 / 父级）必须在
#    bpy.data.objects.remove() 之前取完 —— 删除后连 o.name 都会抛
#    ReferenceError: StructRNA of type Object has been removed
import bpy, os, time
from collections import defaultdict, Counter

T0 = time.time()
# !! 必须改：报告与名单都写到这个目录（建议 = 本次会话的 blender_control 工作目录）
OUT_DIR = r"C:\path\to\workdir"
REPORT = os.path.join(OUT_DIR, "purge_final_report.txt")
NAMES = os.path.join(OUT_DIR, "purge_final_names.txt")

R = []
def p(*a):
    R.append(" ".join(str(x) for x in a))
def mark(tag):
    p("[stage %-14s %6.1fs]" % (tag, time.time() - T0))

objs = list(bpy.data.objects)
p("=" * 72)
p("空物体收敛清理  |  " + bpy.data.filepath)
p("=" * 72)
p("清理前: 总对象 %d   EMPTY %d" % (len(objs), sum(1 for o in objs if o.type == 'EMPTY')))
mark("init")

# ---------- 1. 继承关系 ----------
children = defaultdict(list)
for o in objs:
    if o.parent is not None:
        children[o.parent.name].append(o)
mark("children")

# ---------- 2. 引用图 ----------
incoming = defaultdict(set)   # target name -> set(source key)
SKIP_PROP = {('Scene', 'objects'), ('Collection', 'objects'), ('ViewLayer', 'objects'),
             ('Object', 'original'), ('Collection', 'all_objects')}

def add(target, src_key):
    if isinstance(target, bpy.types.Object):
        incoming[target.name].add(src_key)

def scan_ptr(owner, src_key):
    """只对少量对象（修改器）用 bl_rna 细扫；不要对全场景对象用"""
    try:
        props = owner.bl_rna.properties
    except Exception:
        return
    tn = type(owner).__name__
    for pr in props:
        try:
            if (tn, pr.identifier) in SKIP_PROP:
                continue
            if pr.type == 'POINTER':
                v = getattr(owner, pr.identifier, None)
                if isinstance(v, bpy.types.Object):
                    add(v, src_key)
            elif pr.type == 'COLLECTION':
                v = getattr(owner, pr.identifier, None)
                if v is not None:
                    for x in v:
                        if isinstance(x, bpy.types.Object):
                            add(x, src_key)
        except Exception:
            continue

n_con = n_mod = 0
for ob in objs:
    key = "OBJ:" + ob.name
    for c in ob.constraints:
        n_con += 1
        add(getattr(c, "target", None), key)
    pz = ob.pose
    if pz is not None:
        for pb in pz.bones:
            for c in pb.constraints:
                n_con += 1
                add(getattr(c, "target", None), key)
            add(getattr(pb, "custom_shape", None), key)
        for m in ob.modifiers:
            n_mod += 1
            scan_ptr(m, key)
    else:
        for m in ob.modifiers:
            n_mod += 1
            scan_ptr(m, key)
    ad = ob.animation_data
    if ad is not None:
        for d in ad.drivers:
            for v in d.variables:
                for t in v.targets:
                    try:
                        add(t.id, key)
                    except Exception:
                        pass
mark("obj_refs")

for arm in bpy.data.armatures:
    for b in arm.bones:
        for c in b.constraints:
            add(getattr(c, "target", None), "EXT:armature")
for cam in bpy.data.cameras:
    try:
        add(cam.dof.focus_object, "EXT:camera")
    except Exception:
        pass
for ps in bpy.data.particles:
    for an in ("dupli_object", "instance_object", "object", "render_object"):
        add(getattr(ps, an, None), "EXT:particles")
for sc in bpy.data.scenes:
    add(getattr(sc, "camera", None), "EXT:scene")

n_sock = 0
nts = [ng for ng in bpy.data.node_groups]
nts += [m.node_tree for m in bpy.data.materials if m.node_tree]
nts += [w.node_tree for w in bpy.data.worlds if w.node_tree]
for nt in nts:
    try:
        nodes = nt.nodes
    except Exception:
        continue
    for n in nodes:
        for inp in getattr(n, "inputs", []):
            try:
                if inp.type == 'OBJECT':
                    v = inp.default_value
                    if isinstance(v, bpy.types.Object):
                        n_sock += 1
                        add(v, "EXT:nodesocket")
                elif inp.type == 'COLLECTION':
                    v = inp.default_value
                    if v is not None:
                        for x in v.objects:
                            n_sock += 1
                            add(x, "EXT:nodesocket")
            except Exception:
                pass
mark("ext_refs")
p("扫描量: 约束 %d / 修改器 %d / 节点socket %d" % (n_con, n_mod, n_sock))
p("")

# ---------- 3. 不动点求解 ----------
empties = [o for o in objs if o.type == 'EMPTY']
survive = set(o.name for o in objs if o.type != 'EMPTY')
survive |= set(nm for nm, s in incoming.items() if any(x.startswith("EXT:") for x in s))
base = len(survive)

rounds = 0
while True:
    rounds += 1
    added = 0
    for o in empties:
        nm = o.name
        if nm in survive:
            continue
        ok = any(c.name in survive for c in children.get(nm, []))
        if not ok:
            ok = any(s.startswith("OBJ:") and s[4:] in survive for s in incoming.get(nm, ()))
        if ok:
            survive.add(nm)
            added += 1
    if added == 0 or rounds > 50:
        break
mark("fixpoint")
if rounds > 50:
    p("!! 不动点未收敛，已中止，请检查引用图构建")
    raise SystemExit(1)
p("不动点 %d 轮；保留 %d 个（非 EMPTY %d + EMPTY %d）"
  % (rounds, len(survive), base, len(survive) - base))
p("")

deletable = [o for o in empties if o.name not in survive]
p("可删 EMPTY: %d" % len(deletable))
p("  带 animation_data: %d   有父级: %d   有子级(级联): %d" % (
    sum(1 for o in deletable if o.animation_data is not None),
    sum(1 for o in deletable if o.parent is not None),
    sum(1 for o in deletable if len(children.get(o.name, [])) > 0)))
p("  按集合:", dict(Counter(c.name for o in deletable for c in o.users_collection).most_common(12)))
def fam(nm):
    s = nm
    for sep in ('-', '_', '.', ' '):
        s = s.split(sep)[0]
    return s[:18]
p("  按命名族:", dict(Counter(fam(o.name) for o in deletable).most_common(12)))
p("")

# ---------- 3b. 【关键】先把要用的字段全部冻结成纯 Python 值 ----------
frozen = []
for o in deletable:
    try:
        chain = []
        x = o.parent
        n = 0
        while x is not None and n < 12:
            chain.append(x.name)
            x = x.parent
            n += 1
        frozen.append((
            o.name,
            ";".join(c.name for c in o.users_collection),
            o.parent.name if o.parent else "-",
            " < ".join(chain),
            len(children.get(o.name, [])),
            int(o.animation_data is not None),
        ))
    except Exception as e:
        frozen.append(("<ERR>", str(e), "", "", 0, 0))

# 保留对象的变换快照（供删后比对是否漂移）
keep_snapshot = {}
for o in objs:
    if o.name in survive:
        try:
            t = o.matrix_world.translation
            keep_snapshot[o.name] = (t.x, t.y, t.z)
        except Exception:
            pass

mesh_before = sum(1 for o in objs if o.type == 'MESH')
cam_before = sum(1 for o in objs if o.type == 'CAMERA')
light_before = sum(1 for o in objs if o.type == 'LIGHT')
nonempty_before = len(objs) - len(empties)

# ---------- 4. 执行删除 ----------
removed = 0
failed = []
with open(NAMES, "w", encoding="utf-8") as f:
    f.write("# 收敛清理删除的 EMPTY（共 %d）\n" % len(frozen))
    f.write("NAME\tCOLLECTIONS\tPARENT\tANCESTOR_CHAIN\tCHILDREN\tHAS_ANIM\n")
    for nm, colls, parent, chain, nch, hanim in frozen:
        f.write("%s\t%s\t%s\t%s\t%d\t%d\n" % (nm, colls, parent, chain, nch, hanim))
for o in deletable:
    try:
        bpy.data.objects.remove(o, do_unlink=True)
        removed += 1
    except Exception as e:
        failed.append((o.name, str(e)))
p("实际删除 %d  失败 %d" % (removed, len(failed)))
for nm, err in failed[:20]:
    p("   ERR %s :: %s" % (nm, err))
mark("delete")
p("")

# ---------- 5. 删后核验（注意：全部重新取引用，绝不能碰 objs / deletable） ----------
objs2 = list(bpy.data.objects)
children2 = defaultdict(list)
for o in objs2:
    if o.parent is not None:
        children2[o.parent.name].append(o)
emp2 = [o for o in objs2 if o.type == 'EMPTY']
emp2_noch = [o for o in emp2 if len(children2.get(o.name, [])) == 0]

p("=" * 72)
p("[核验]")
p("=" * 72)
p("%-22s %10s %10s %s" % ("项目", "清理前", "现在", "结论"))
def row(label, before, now):
    p("%-22s %10s %10s %s" % (label, before, now, "OK" if before == now else "*** 变化 ***"))
row("总对象", len(objs), len(objs2))
row("EMPTY", len(empties), len(emp2))
row("非 EMPTY 对象", nonempty_before, len(objs2) - len(emp2))
row("MESH", mesh_before, sum(1 for o in objs2 if o.type == 'MESH'))
row("CAMERA", cam_before, sum(1 for o in objs2 if o.type == 'CAMERA'))
row("LIGHT", light_before, sum(1 for o in objs2 if o.type == 'LIGHT'))
p("%-22s %10s %10s %s" % ("EMPTY 无子级", len(emp2_noch) + len(frozen),
                          len(emp2_noch), "OK 已收敛" if len(emp2_noch) == 0 else "*** 残留 ***"))
p("")

names_frozen = [t[0] for t in frozen]
still = [n for n in names_frozen if n in bpy.data.objects]
p("[1] 名单里仍存在: %d (应 0)" % len(still))

dangle = 0
for ob in objs2:
    for c in ob.constraints:
        try:
            if c.type in ('TRACK_TO', 'COPY_LOCATION', 'COPY_ROTATION', 'COPY_SCALE',
                          'COPY_TRANSFORMS', 'DAMPED_TRACK', 'IK', 'FOLLOW_PATH',
                          'CHILD_OF', 'LOCKED_TRACK', 'STRETCH_TO', 'CLAMP_TO', 'SHRINKWRAP') \
               and c.target is None:
                dangle += 1
        except Exception:
            pass
p("[2] 无目标约束(悬空): %d" % dangle)

broken = sum(1 for o in objs2 if o.parent is not None and o.parent.name not in bpy.data.objects)
p("[3] 父级丢失: %d" % broken)

drift = 0
for nm, (x, y, z) in keep_snapshot.items():
    o = bpy.data.objects.get(nm)
    if o is None:
        continue
    try:
        t = o.matrix_world.translation
        if abs(t.x - x) > 1e-6 or abs(t.y - y) > 1e-6 or abs(t.z - z) > 1e-6:
            drift += 1
    except Exception:
        pass
p("[4] 保留对象位置漂移: %d" % drift)

miss = []
for img in bpy.data.images:
    if img.source == 'FILE' and img.filepath and img.packed_file is None:
        if not os.path.exists(bpy.path.abspath(img.filepath)):
            miss.append(img.name)
p("[5] 真缺失贴图: %d  链接库: %d  字体: %d" % (
    len(miss),
    len([l for l in bpy.data.libraries if l.filepath
         and not os.path.exists(bpy.path.abspath(l.filepath))]),
    len([f for f in bpy.data.fonts if f.filepath
         and not os.path.exists(bpy.path.abspath(f.filepath))])))
p("[6] 孤儿材质/图像/动作: %d / %d / %d" % (
    sum(1 for m in bpy.data.materials if m.users == 0),
    sum(1 for i in bpy.data.images if i.users == 0),
    sum(1 for a in bpy.data.actions if a.users == 0)))
p("[7] 最终保留的 EMPTY %d 个，其中直接挂非 EMPTY 子级 %d 个" % (
    len(emp2), sum(1 for o in emp2 if any(c.type != 'EMPTY' for c in children2.get(o.name, [])))))
p("")
p("is_dirty=%s  （桥只改内存，需用户 Ctrl+S）" % bpy.data.is_dirty)
mark("verify")

txt = "\n".join(R)
with open(REPORT, "w", encoding="utf-8") as f:
    f.write(txt)
print(txt)
print("=== PURGE DONE ===")
