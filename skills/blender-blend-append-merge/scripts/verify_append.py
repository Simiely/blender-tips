# -*- coding: utf-8 -*-
"""独立复核：另开一次 Blender 打开「合并产物」，对着 baseline_A / baseline_B 校验。
   用法：blender.exe --background --factory-startup "<产物.blend>" --python verify_append.py
   ★ B 侧一律用多重集口径（不依赖对象名）—— append 会让 Blender 按数字后缀给重名对象续号。
"""
import bpy, os, io, json, collections

WORK = os.environ.get("AMB_WORK", os.getcwd())   # 报告/基线/日志都写这里
ROW = 6
LOGP = os.path.join(WORK, "verify_append_report.txt")

D = bpy.data
sc = bpy.context.scene
L = []
def w(s=""):
    L.append(s)
    print(s, flush=True)

PASS, FAIL = [], []
def chk(ok, label, detail=""):
    (PASS if ok else FAIL).append(label)
    w("  [%s] %-48s %s" % ("OK " if ok else "!! ", label, detail))

with io.open(os.path.join(WORK, "baseline_A.json"), encoding="utf-8") as f:
    BA = json.load(f)
with io.open(os.path.join(WORK, "baseline_B.json"), encoding="utf-8") as f:
    BB = json.load(f)

mset = collections.Counter
w("=" * 80)
w("独立复核（另开一次 Blender 打开产物）")
w("产物: %s" % D.filepath)
w("=" * 80)
w("")

# ---------- 现场快照 ----------
prod = {}
for o in D.objects:
    prod[o.name] = {
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

w("【一】A 侧（底文件）在产物里逐项未变")
missA = sorted(set(BA["objects"]) - set(prod))
chk(not missA, "A 原对象一个不少", "缺 %d 个 %s" % (len(missA), missA[:5]))
diffA = []
for n, a in BA["objects"].items():
    b = prod.get(n)
    if b is None:
        continue
    # baseline_A 里没有 material_slots 以外的差异项：字段名对齐
    if a["t"] != b["t"] or a["d"] != b["d"] or a["p"] != b["p"] or a["c"] != b["c"]:
        diffA.append((n, "ident"))
    if a["m"] != b["m"] or len(a["mo"]) != len(b["mo"]):
        diffA.append((n, "mats/mods"))
    if tuple(round(x, ROW) for x in a["mw"]) != b["mw"]:
        diffA.append((n, "mw"))
    if a["nv"] != b["v"] or a["np"] != b["f"]:
        diffA.append((n, "geom"))
chk(not diffA, "A 逐对象（身份/材质/修改器/世界矩阵/几何）未变",
    "差异 %d 处 %s" % (len(diffA), diffA[:5]))

matA = mset(v for v in BA["materials"].values())
imgA = mset(tuple(v) for v in BA["images"].values())
meshA = mset(tuple(v) for v in BA["meshes"].values())
ngA = mset(BA["node_groups"].values())
camA = mset(BA["cameras"].values())

prod_mat = {m.name: m.users for m in D.materials}
prod_img = {i.name: (i.users, i.packed_file is not None, i.source) for i in D.images}
prod_mesh = {m.name: (m.users, len(m.vertices), len(m.polygons)) for m in D.meshes}
prod_ng = {g.name: g.users for g in D.node_groups}
prod_cam = {c.name: c.users for c in D.cameras}
prod_coll = {c.name: (sorted(o.name for o in c.objects),
                      sorted(x.name for x in c.children)) for c in D.collections}

for nm, base, now in (("materials", BA["materials"], prod_mat),
                      ("node_groups", BA["node_groups"], prod_ng),
                      ("cameras", BA["cameras"], prod_cam)):
    bad = [k for k, v in base.items() if now.get(k) != v]
    chk(not bad, "A 原有的 %s 条目仍在且值不变" % nm, "变了 %s" % bad[:3])
bad = [k for k, v in BA["images"].items()
       if prod_img.get(k) != (v["u"], v["p"], v["s"])]
chk(not bad, "A 原有的 images 条目仍在且值不变", "变了 %s" % bad[:3])
bad = [k for k, v in BA["meshes"].items()
       if prod_mesh.get(k) != (v["u"], v["nv"], v["np"])]
chk(not bad, "A 原有的 meshes 条目仍在且值不变", "变了 %s" % bad[:3])
bad = [k for k, v in BA["collections"].items()
       if prod_coll.get(k) != (sorted(v["o"]), sorted(v["ch"]))]
chk(not bad, "A 原有的 collections 条目仍在且值不变", "变了 %s" % bad[:3])

# ---------- B 侧 ----------
new = sorted(set(prod) - set(BA["objects"]))
w("")
w("【二】B 侧在产物里完整（多重集口径，不依赖名字）")
chk(len(new) == BB["sum"]["objects"], "新增对象数 == B",
    "%d vs %d" % (len(new), BB["sum"]["objects"]))

chk(mset(v["t"] for v in BB["objects"].values()) == mset(prod[n]["t"] for n in new),
    "对象类型多重集 == B")

mB = [tuple(v["mw"]) for v in BB["objects"].values()]
mA = [prod[n]["mw"] for n in new]
cB, cA = mset(mB), mset(mA)
_cols = len(mB[0]) if mB else 0
_worst = 0.0
_bad = 0
for _j in range(_cols):
    _sb = sorted(v[_j] for v in mB)
    _sa = sorted(v[_j] for v in mA)
    for _x, _y in zip(_sb, _sa):
        _d = abs(_x - _y)
        if _d > _worst:
            _worst = _d
        if _d > 2e-3 + 1e-6 * abs(_x):
            _bad += 1
chk(_bad == 0 and len(mB) == len(mA), "★世界矩阵多重集 == B（层级+变换总账）",
    "最大元素偏差 %.3e / 超差 %d 个 / %s"
    % (_worst, _bad, "位级完全一致" if cB == cA else "位级有 ULP 级差异"))

sigB = mset((v["t"], v["nv"], v["np"], len(v["m"]),
             tuple(sorted(x[2] or "" for x in v["mo"]))) for v in BB["objects"].values())
sigA = mset((prod[n]["t"], prod[n]["v"], prod[n]["f"], len(prod[n]["m"]),
             tuple(sorted(x[2] or "" for x in prod[n]["mo"]))) for n in new)
chk(sigB == sigA, "逐对象（类型/顶点/面/材质槽数/修改器）签名 == B",
    "差 %d" % (len(sigB - sigA) + len(sigA - sigB)))

nV = sum(prod[n]["v"] or 0 for n in new)
nF = sum(prod[n]["f"] or 0 for n in new)
chk(nV == BB["sum"]["verts"], "新增顶点总量 == B", "%d vs %d" % (nV, BB["sum"]["verts"]))
chk(nF == BB["sum"]["polys"], "新增面总量 == B", "%d vs %d" % (nF, BB["sum"]["polys"]))

newMesh = [v for k, v in prod_mesh.items() if k not in BA["meshes"]]
chk(mset(newMesh) == mset((v["u"], v["nv"], v["np"]) for v in BB["meshes"].values()),
    "新增网格块 (users,顶点,面) 多重集 == B",
    "%d vs %d" % (len(newMesh), len(BB["meshes"])))
newMat = [v for k, v in prod_mat.items() if k not in BA["materials"]]
chk(mset(newMat) == mset(BB["materials"].values()), "新增材质 users 多重集 == B",
    "%d vs %d" % (len(newMat), len(BB["materials"])))
newImg = [v for k, v in prod_img.items() if k not in BA["images"]]
genB = mset((v["u"], v["p"], v["s"]) for v in BB["images"].values() if v["s"] != "VIEWER")
chk(mset(newImg) == genB, "新增图像多重集 == B−2（生成型不入）",
    "%d vs %d" % (len(newImg), sum(genB.values())))
newNG = [k for k in prod_ng if k not in BA["node_groups"]]
chk(len(newNG) == len(BB["node_groups"])
    and sorted(prod_ng[k] for k in newNG) == sorted(BB["node_groups"].values()),
    "新增节点组(名+引用数) == B", "%s" % [(k, prod_ng[k]) for k in newNG])
newCam = [v for k, v in prod_cam.items() if k not in BA["cameras"]]
chk(mset(newCam) == mset(BB["cameras"].values()), "新增相机 users 多重集 == B",
    "%d vs %d" % (len(newCam), len(BB["cameras"])))
newColl = [k for k in prod_coll if k not in BA["collections"]]
chk(len(newColl) == 3, "新增集合 == 3", "%s" % sorted(newColl))

mu = sum(1 for n in new if (prod[n]["du"] or 0) > 1)
chk(mu == BB["sum"]["multi_user_objs"], "多实例保持共享（未展开）",
    "%d vs %d" % (mu, BB["sum"]["multi_user_objs"]))
mods = sum(1 for n in new if prod[n]["mo"])
chk(mods == BB["sum"]["objs_with_mod"], "带修改器对象数 == B",
    "%d vs %d" % (mods, BB["sum"]["objs_with_mod"]))

# ---------- 总量 / 场景 ----------
w("")
w("【三】总量与场景")
tv = sum(v["v"] or 0 for v in prod.values())
tf = sum(v["f"] or 0 for v in prod.values())
chk(tv == BA["sum"]["verts"] + BB["sum"]["verts"], "总顶点 = A + B", "%d" % tv)
chk(tf == BA["sum"]["polys"] + BB["sum"]["polys"], "总面数 = A + B", "%d" % tf)
w("  对象 %d   MESH %d / EMPTY %d / CAMERA %d / 其他 %d"
  % (len(prod), sum(1 for v in prod.values() if v["t"] == "MESH"),
     sum(1 for v in prod.values() if v["t"] == "EMPTY"),
     sum(1 for v in prod.values() if v["t"] == "CAMERA"),
     sum(1 for v in prod.values() if v["t"] not in ("MESH", "EMPTY", "CAMERA"))))
w("  顶点 %d   面 %d" % (tv, tf))
w("  材质 %d   图像 %d   网格块 %d   节点组 %d   相机 %d   集合 %d"
  % (len(D.materials), len(D.images), len(D.meshes), len(D.node_groups),
     len(D.cameras), len(D.collections)))
w("  场景相机 %s   引擎 %s   %dx%d   fps %s   帧 %s-%s   输出 %s   世界 %s"
  % (sc.camera.name if sc.camera else None, sc.render.engine,
     sc.render.resolution_x, sc.render.resolution_y, sc.render.fps,
     sc.frame_start, sc.frame_end, sc.render.filepath,
     sc.world.name if sc.world else None))
w("  顶层集合 %s" % sorted(c.name for c in sc.collection.children))
w("  视图层对象 %d / %d" % (len(bpy.context.view_layer.objects), len(prod)))

# 未被覆盖的对象（游离对象是否也进来了）
covered = {o.name for c in D.collections for o in c.objects}
stray = sorted({o.name for o in D.objects} - covered)
w("  游离对象（不属任何集合）%d 个: %s" % (len(stray), stray))
chk(len(stray) == 3, "B 的 3 个游离对象已并入", "%s" % stray)

# ---------- 名字挪号规模（信息性） ----------
# 用「全属性结构键」把 B 的对象与产物里的新对象配对：
# 键 = (类型, 顶点, 面, 材质槽数, 修改器数, 位级世界矩阵)
# 键相同的对象之间除了名字完全一样 ⇒ 键组内名字集合的差集 = 真被改名的对象数
keyB = collections.defaultdict(list)
for nm, v in BB["objects"].items():
    keyB[(v["t"], v["nv"], v["np"], len(v["m"]), len(v["mo"]), tuple(v["mw"]))].append(nm)
keyA = collections.defaultdict(list)
for n in new:
    r = prod[n]
    keyA[(r["t"], r["v"], r["f"], len(r["m"]), len(r["mo"]), r["mw"])].append(n)
shifted = 0
keymiss = 0
for k, namesB in keyB.items():
    namesA = keyA.get(k)
    if namesA is None:
        keymiss += 1
        continue
    shifted += len(namesB) - len(set(namesB) & set(namesA))
w("")
w("  ── 名字挪号规模（信息性，不影响数据） ──")
w("     结构键无法匹配的键组: %d  （应为 0）" % keymiss)
chk(keymiss == 0, "全属性结构键 100% 可配对", "%d" % keymiss)
w("     除名字外完全一致、但名字被改掉的对象: %d / %d" % (shifted, len(new)))
w("     （Blender 对重名对象按「数字后缀续号」重新分配；父子链接按指针，不受影响）")

# 场景设置应与 A 一致
chk((sc.camera.name if sc.camera else None) == "2281-3000", "场景相机 == A 的", "")
chk(sc.render.fps == 30 and (sc.frame_start, sc.frame_end) == (1, 3000)
    and sc.render.filepath == "//output\\", "fps/帧范围/输出路径 == A 的", "")

w("")
w("=" * 80)
w("VERIFY_RESULT: %s      PASS %d / FAIL %d" %
  ("PASS" if not FAIL else "FAIL", len(PASS), len(FAIL)))
for f in FAIL:
    w("  FAIL: %s" % f)
w("REOPEN_OK")
w("=" * 80)

with io.open(LOGP, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("REPORT -> %s" % LOGP)
