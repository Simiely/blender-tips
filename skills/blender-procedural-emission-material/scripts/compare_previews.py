# compare_previews.py — 客观比对预览图（读像素求平均绝对差）
import bpy, os, json
from array import array

# 路径模板：使用前把 WORKDIR 改成你的「脚本/输出目录」（桥执行环境里 __file__ 不可靠）
WORKDIR = r"C:/Users/wandou/WorkBuddy/<项目>/blender_control"
D = WORKDIR + "/render"
REF = "nz_01_f001_zoom.png"
names = ["nz_01_f001_zoom.png", "nz_02_f121_zoom.png", "nz_03_seed1_zoom.png",
         "nz_04_seed50_zoom.png", "nz_05_density6.png", "nz_06_contrast03.png",
         "nz_07_detail2.png", "nz_08_detail6.png"]

def load_px(fn):
    p = os.path.join(D, fn)
    img = bpy.data.images.load(p, check_existing=False)
    w, h = img.size
    buf = array('f', [0.0]) * (w * h * 4)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    return w, h, buf

out = {}
data = {}
for n in names:
    w, h, buf = load_px(n)
    data[n] = (w, h, buf)
    out.setdefault("size", {})[n] = [w, h]

ref = data[REF][2]
rows = []
for n in names:
    if n == REF:
        continue
    b = data[n][2]
    if len(b) != len(ref):
        rows.append({"name": n, "error": "size mismatch"}); continue
    tot = 0.0; mx = 0.0; nz = 0
    for i in range(0, len(ref), 4):          # 只比 RGB，跳 alpha
        for k in range(3):
            d = abs(ref[i + k] - b[i + k])
            tot += d
            if d > mx: mx = d
            if d > 0.02: nz += 1
    cnt = (len(ref) // 4) * 3
    rows.append({"name": n,
                 "mean_abs_diff": round(tot / cnt, 6),
                 "mean_abs_diff_pct": round(tot / cnt * 100, 4),
                 "max_diff": round(mx, 4),
                 "pixels_changed_gt2pct": nz,
                 "pixels_changed_pct": round(nz / cnt * 100, 3)})
out["vs_ref"] = {"ref": REF, "rows": rows}
out["image_mean_luma"] = {n: round(sum(data[n][2][i] for i in range(0, len(data[n][2]), 4)) / (len(data[n][2]) // 4), 5) for n in names}
print(json.dumps(out, ensure_ascii=False, indent=1))
