# -*- coding: utf-8 -*-
"""把 B 追加进 A（A 为底），做全套对账。
   ★ 对账口径：B 侧用「多重集」比对，完全不依赖对象名 ——
     因为 append 会让 Blender 按数字后缀给重名对象续号（实测 B 有 2,894 个父级名被位移），
     名字不可靠，但「世界矩阵 / 几何 / 数据块 / 资源引用」的多重集必须逐一相等。
   环境变量：
     MERGE_OUT    输出 .blend 路径；留空 = dry run（只对账，不落盘）
     MERGE_STRAYS 1|0  是否一并追加 B 的 3 个游离对象（默认 1）
     MERGE_UPDATE 1|0  是否额外测量 view_layer.update() 耗时（默认 0，实测为 0s）
     MERGE_NOREPORT 1|0 跳过写报告文件（内部调用用）
"""
import bpy, os, io, json, time, collections

WORK = os.environ.get("AMB_WORK", os.getcwd())   # 报告/基线/日志都写这里
SRC_A = os.environ.get("AMB_SRC_A", "")          # 底文件（对象少的那一边）
SRC_B = os.environ.get("AMB_SRC_B", "")          # 追加来源（对象多的那一边）
for _k in ("AMB_SRC_A", "AMB_SRC_B"):
    if not os.environ.get(_k):
        raise SystemExit("请先设环境变量 %s（传两个 .blend 的绝对路径）" % _k)
APPEND_COLL = "SKP Imported Data"
STRAYS = ["G-3d66-Edi961475.001", "Mesh1", "Mesh2"]
DO_STRAYS = os.environ.get("MERGE_STRAYS", "1") == "1"
OUT = os.environ.get("MERGE_OUT", "").strip()
DO_UPDATE = os.environ.get("MERGE_UPDATE", "0") == "1"
ROW = 6          # 世界矩阵取整位数（与 baseline_*.json 一致，便于位级比对）
BASELINE = os.path.join(WORK, "baseline_B.json")
LOGP = os.path.join(WORK, "merge_append_report.txt")

T = {}
def mark(k, t0):
    T[k] = round(time.time() - t0, 3)
    print("[T] %-24s %9.3f s" % (k, T[k]), flush=True)

L = []
def w(s=""):
    L.append(s)
    print(s, flush=True)

PASS, FAIL = [], []
def chk(ok, label, detail=""):
    (PASS if ok else FAIL).append(label)
    w("  [%s] %-46s %s" % ("OK " if ok else "!! ", label, detail))


D = bpy.data
t = time.time()
assert os.path.normcase(os.path.abspath(D.filepath)) == os.path.normcase(SRC_A), \
    "底文件不对: %s" % D.filepath
assert os.path.exists(SRC_B) and os.path.exists(BASELINE)
sc = bpy.context.scene
mark("载入底文件", t)

with io.open(BASELINE, encoding="utf-8") as f:
    BL = json.load(f)


# ---------------- 快照 ----------------
def obj_rec(o):
    return {
        "t": o.type, "d": (o.data.name if o.data else None),
        "du": (o.data.users if o.data else None),
        "p": (o.parent.name if o.parent else None),
        "c": sorted(c.name for c in o.users_collection),
        "m": [s.material.name if s.material else None for s in o.material_slots],
        "mo": [(m.name, m.type, getattr(getattr(m, "node_group", None), "name", None))
               for m in o.modifiers],
        "mw": tuple(round(v, ROW) for row in o.matrix_world for v in row),
        "hv": o.hide_viewport, "hr": o.hide_render,
        "v": (len(o.data.vertices) if o.type == "MESH" else None),
        "f": (len(o.data.polygons) if o.type == "MESH" else None),
    }


def snap_objects():
    return {o.name: obj_rec(o) for o in D.objects}


def snap_misc():
    return {
        "materials": {m.name: m.users for m in D.materials},
        "meshes": {m.name: (m.users, len(m.vertices), len(m.polygons)) for m in D.meshes},
        "images": {i.name: (i.users, i.packed_file is not None, i.source) for i in D.images},
        "node_groups": {g.name: g.users for g in D.node_groups},
        "cameras": {c.name: c.users for c in D.cameras},
        "worlds": {x.name: x.users for x in D.worlds},
        "collections": {c.name: (sorted(o.name for o in c.objects),
                                 sorted(x.name for x in c.children))
                        for c in D.collections},
        "scene": {"camera": (sc.camera.name if sc.camera else None),
                  "engine": sc.render.engine,
                  "res": (sc.render.resolution_x, sc.render.resolution_y,
                          sc.render.resolution_percentage),
                  "fps": (sc.render.fps, sc.render.fps_base),
                  "frames": (sc.frame_start, sc.frame_end),
                  "output": sc.render.filepath,
                  "world": (sc.world.name if sc.world else None),
                  "unit": sc.unit_settings.scale_length,
                  "top_children": sorted(c.name for c in sc.collection.children)},
    }


t = time.time()
A_objs = snap_objects()
A_misc = snap_misc()
mark("快照 A（前）", t)
A_VERTS = sum(v["v"] or 0 for v in A_objs.values())
A_POLYS = sum(v["f"] or 0 for v in A_objs.values())

w("=" * 80)
w("底文件 A : %s" % SRC_A)
w("追加来源 : %s" % SRC_B)
w("追加对象 : 集合「%s」%s" % (APPEND_COLL, "  + 3 个游离对象" if DO_STRAYS else ""))
w("输出     : %s" % (OUT if OUT else "（dry run —— 只对账，不落盘）"))
w("=" * 80)
w("")
w("【A 侧基线】objects=%-6d verts=%-10d polys=%-10d colls=%d mats=%d imgs=%d cams=%d"
  % (len(A_objs), A_VERTS, A_POLYS, len(D.collections),
     len(D.materials), len(D.images), len(D.cameras)))
w("【B 侧基线】objects=%-6d verts=%-10d polys=%-10d colls=%d mats=%d imgs=%d cams=%d ngroup=%d"
  % (BL["sum"]["objects"], BL["sum"]["verts"], BL["sum"]["polys"],
     BL["sum"]["collections"], BL["sum"]["materials"], BL["sum"]["images"],
     BL["sum"]["cameras"], BL["sum"]["node_groups"]))
w("")

# ---------------- 追加 ----------------
t = time.time()
r1 = bpy.ops.wm.append(filepath=os.path.join(SRC_B, "Collection", APPEND_COLL),
                       directory=SRC_B + os.sep + "Collection" + os.sep,
                       filename=APPEND_COLL, instance_collections=False,
                       set_fake=False, use_recursive=False)
mark("① append 集合", t)
w("  append(Collection %s) -> %s" % (APPEND_COLL, list(r1)))

if DO_STRAYS:
    t = time.time()
    for n in STRAYS:
        rr = bpy.ops.wm.append(filepath=os.path.join(SRC_B, "Object", n),
                               directory=SRC_B + os.sep + "Object" + os.sep,
                               filename=n, instance_collections=False,
                               set_fake=False, use_recursive=False)
        w("  append(Object %s) -> %s" % (n, list(rr)))
    mark("② append 游离对象", t)

if DO_UPDATE:
    t = time.time()
    bpy.context.view_layer.update()
    mark("③ view_layer.update()", t)

t = time.time()
AB_objs = snap_objects()
AB_misc = snap_misc()
mark("④ 快照 A+B（后）", t)

# ---------------- 落盘（放在对账之前：对账再出错也不丢产物） ----------------
OUTP = None
if OUT:
    t = time.time()
    assert os.path.normcase(os.path.abspath(OUT)) != os.path.normcase(SRC_A)
    assert os.path.normcase(os.path.abspath(OUT)) != os.path.normcase(SRC_B)
    d = os.path.dirname(OUT)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT)
    mark("⑤ 存盘", t)
    OUTP = (OUT, os.path.getsize(OUT))
    w("  >> 已存盘: %s  (%d bytes / %.1f MiB)"
      % (OUT, OUTP[1], OUTP[1] / 1048576.0))

# ---------------- 对账 ----------------
t = time.time()
new = sorted(set(AB_objs) - set(A_objs))

w("")
w("【一】A 侧不变性 —— 追加不许动到底文件")
miss = sorted(set(A_objs) - set(AB_objs))
chk(not miss, "A.1 A 原对象一个不少", "缺 %d 个" % len(miss))
diff = []
for n, a in A_objs.items():
    b = AB_objs.get(n)
    if b is None:
        continue
    for k in ("t", "d", "du", "p", "c", "m", "mo", "mw", "hv", "hr", "v", "f"):
        if a[k] != b[k]:
            diff.append((n, k))
chk(not diff, "A.2 A 逐对象属性/世界矩阵未变", "差异 %d 处 %s" % (len(diff), diff[:5]))
for k in ("materials", "images", "meshes", "node_groups", "cameras", "worlds", "collections"):
    bad = [(n, v) for n, v in A_misc[k].items() if AB_misc[k].get(n) != v]
    chk(not bad, "A.3 A 原有的 %s 条目仍在且值不变" % k,
        "变了 %d 个 %s" % (len(bad), bad[:3]))
for k in ("camera", "engine", "res", "fps", "frames", "output", "world", "unit"):
    a, b = A_misc["scene"][k], AB_misc["scene"][k]
    chk(a == b, "A.4 场景.%s 未变" % k,
        "一致 %r" % (a,) if a == b else "%r -> %r" % (a, b))

w("")
w("【二】B 侧完整性 —— 用多重集口径（不依赖对象名）")
chk(len(new) == BL["sum"]["objects"], "B.1 新增对象数 == B",
    "%d vs %d" % (len(new), BL["sum"]["objects"]))

def mset(seq):
    return collections.Counter(seq)

# 2.1 类型
cB = mset(v["t"] for v in BL["objects"].values())
cA = mset(AB_objs[n]["t"] for n in new)
chk(cB == cA, "B.2 对象类型多重集 == B", "%s" % (dict(cA) if cB != cA else ""))

# 2.2 世界矩阵（层级 + 变换的总账）
def mw_gate(listB, listA):
    """返回 (ok, detail)。
       ① 位级：raw 16-float 元组的多重集是否逐一相等（最强判据）
       ② 容差：逐列排序后逐点比 —— 免疫 float32 末位抖动（|v|≈5000 时 ULP≈6e-4）
    """
    cB = mset(tuple(v) for v in listB)
    cA = mset(tuple(v) for v in listA)
    exact = cB == cA
    cols = len(listB[0]) if listB else 0
    worst = 0.0
    bad = 0
    for j in range(cols):
        sb = sorted(v[j] for v in listB)
        sa = sorted(v[j] for v in listA)
        for x, y in zip(sb, sa):
            d = abs(x - y)
            if d > worst:
                worst = d
            if d > 2e-3 + 1e-6 * abs(x):
                bad += 1
    ok = bad == 0 and len(listB) == len(listA)
    tag = "位级完全一致" if exact else "位级有 %d 组差异(ULP级)" % (
        sum((cB - cA).values()) + sum((cA - cB).values()))
    return ok, "最大元素偏差 %.3e / 超差 %d 个 / %s" % (worst, bad, tag)


_ok, _det = mw_gate([tuple(v["mw"]) for v in BL["objects"].values()],
                    [AB_objs[n]["mw"] for n in new])
chk(_ok, "★B.3 世界矩阵多重集 == B（层级+变换总账）", _det)

# 2.3 每对象的 (类型, 顶点, 面, 材质槽数, 修改器节点组)
sigB = mset((v["t"], v["nv"], v["np"], len(v["m"]),
             tuple(sorted(x[2] or "" for x in v["mo"]))) for v in BL["objects"].values())
sigA = mset((AB_objs[n]["t"], AB_objs[n]["v"], AB_objs[n]["f"],
             len(AB_objs[n]["m"]),
             tuple(sorted(x[2] or "" for x in AB_objs[n]["mo"]))) for n in new)
chk(sigB == sigA, "B.4 逐对象几何+材质槽数+修改器签名 == B",
    "差 %d 种 %s" % (len(sigB - sigA) + len(sigA - sigB),
                     (list((sigB - sigA).elements())[:1] if sigB - sigA else
                      list((sigA - sigB).elements())[:1])))

# 2.4 几何总量
nV = sum(AB_objs[n]["v"] or 0 for n in new)
nF = sum(AB_objs[n]["f"] or 0 for n in new)
chk(nV == BL["sum"]["verts"], "B.5 新增顶点总量 == B", "%d vs %d" % (nV, BL["sum"]["verts"]))
chk(nF == BL["sum"]["polys"], "B.6 新增面总量 == B", "%d vs %d" % (nF, BL["sum"]["polys"]))

# 2.5 数据块与资源（多重集）
newMesh = [v for k, v in AB_misc["meshes"].items() if k not in A_misc["meshes"]]
mBm = mset((v["u"], v["nv"], v["np"]) for v in BL["meshes"].values())
mAm = mset(tuple(v) for v in newMesh)
chk(mBm == mAm, "B.7 新增网格数据块 (users,顶点,面) 多重集 == B",
    "%d vs %d 差 %s" % (sum(mAm.values()), sum(mBm.values()), (mBm - mAm) or (mAm - mBm)))

newMat = [v for k, v in AB_misc["materials"].items() if k not in A_misc["materials"]]
chk(mset(newMat) == mset(BL["materials"].values()), "B.8 新增材质 users 多重集 == B",
    "%d vs %d" % (len(newMat), len(BL["materials"])))

newImg = [v for k, v in AB_misc["images"].items() if k not in A_misc["images"]]
genB = mset((v["u"], v["p"], v["s"]) for v in BL["images"].values() if v["s"] != "VIEWER")
chk(mset(tuple(v) for v in newImg) == genB, "B.9 新增图像 (users,打包,来源) 多重集 == B−2 生成型",
    "%d vs %d  %s" % (len(newImg), sum(genB.values()), (genB - mset(tuple(v) for v in newImg))))

newNG = [k for k in AB_misc["node_groups"] if k not in A_misc["node_groups"]]
chk(len(newNG) == BL["sum"]["node_groups"]
    and sorted(AB_misc["node_groups"][k] for k in newNG) == sorted(BL["node_groups"].values()),
    "B.10 新增节点组(名+引用数) == B", "%s" % [(k, AB_misc["node_groups"][k]) for k in newNG])

newCam = [v for k, v in AB_misc["cameras"].items() if k not in A_misc["cameras"]]
chk(mset(newCam) == mset(BL["cameras"].values()), "B.11 新增相机 users 多重集 == B",
    "%d vs %d" % (len(newCam), len(BL["cameras"])))

newColl = [k for k in AB_misc["collections"] if k not in A_misc["collections"]]
chk(len(newColl) == 3, "B.12 新增集合 == 3（.001 子树）", "%s" % sorted(newColl))

mu = sum(1 for n in new if (AB_objs[n]["du"] or 0) > 1)
chk(mu == BL["sum"]["multi_user_objs"], "B.13 多实例被保留（未展开成实体）",
    "%d vs %d" % (mu, BL["sum"]["multi_user_objs"]))
mods = sum(1 for n in new if AB_objs[n]["mo"])
chk(mods == BL["sum"]["objs_with_mod"], "B.14 带修改器对象数 == B",
    "%d vs %d" % (mods, BL["sum"]["objs_with_mod"]))

# 2.6 名字位移（信息性，不算失败）
bm = set(BL["objects"])
nm = set(new)
shifted = sorted(nm - bm)
lost = sorted(bm - nm)
w("")
w("  ── 名字位移（Blender 按数字后缀续号所致，非数据问题） ──")
w("     产物里出现、但 B 里没这个名字的对象: %d 个" % len(shifted))
for x in shifted[:12]:
    w("        + %s" % x)
w("     B 有、但产物里没这个名的对象          : %d 个" % len(lost))
for x in lost[:12]:
    w("        - %s" % x)

w("")
w("【三】产物总览")
tv = sum(v["v"] or 0 for v in AB_objs.values())
tf = sum(v["f"] or 0 for v in AB_objs.values())
w("  对象总数 %d -> %d   MESH %d / EMPTY %d / CAMERA %d"
  % (len(A_objs), len(AB_objs),
     sum(1 for v in AB_objs.values() if v["t"] == "MESH"),
     sum(1 for v in AB_objs.values() if v["t"] == "EMPTY"),
     sum(1 for v in AB_objs.values() if v["t"] == "CAMERA")))
w("  顶点 %d -> %d  (A %d + B %d = %d)" % (A_VERTS, tv, A_VERTS, BL["sum"]["verts"],
                                          A_VERTS + BL["sum"]["verts"]))
w("  面   %d -> %d  (A %d + B %d = %d)" % (A_POLYS, tf, A_POLYS, BL["sum"]["polys"],
                                          A_POLYS + BL["sum"]["polys"]))
chk(tv == A_VERTS + BL["sum"]["verts"], "C.1 总顶点 = A + B", "%d" % tv)
chk(tf == A_POLYS + BL["sum"]["polys"], "C.2 总面数 = A + B", "%d" % tf)
w("  材质 %d -> %d   图像 %d -> %d   网格块 %d -> %d   节点组 %d -> %d   相机 %d -> %d   集合 %d -> %d"
  % (len(A_misc["materials"]), len(AB_misc["materials"]),
     len(A_misc["images"]), len(AB_misc["images"]),
     len(A_misc["meshes"]), len(AB_misc["meshes"]),
     len(A_misc["node_groups"]), len(AB_misc["node_groups"]),
     len(A_misc["cameras"]), len(AB_misc["cameras"]),
     len(A_misc["collections"]), len(AB_misc["collections"])))
w("  场景顶层集合: %s" % AB_misc["scene"]["top_children"])
w("  视图层对象数: %d / %d" % (len(bpy.context.view_layer.objects), len(AB_objs)))
if OUTP:
    w("  产物文件    : %s  (%.1f MiB)" % (OUTP[0], OUTP[1] / 1048576.0))
mark("⑥ 全套对账", t)

w("")
w("=" * 80)
w("PASS %d 项    FAIL %d 项" % (len(PASS), len(FAIL)))
for f in FAIL:
    w("  FAIL: %s" % f)
w("耗时: %s" % json.dumps(T, ensure_ascii=False))
w("=" * 80)

with io.open(LOGP, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("REPORT -> %s" % LOGP)
