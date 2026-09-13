# NOTE: 路径为模板占位 --- 使用前把 WORKDIR/OUTDIR 改成本机实际的「脚本/输出目录」。
#       （桥执行环境里 __file__ 不可靠，因此显式定义。）
# compose_sheet_v2.py —— 把预览图拼成对照表（用 Blender 图像 API，不走外部库）
import bpy, os, json

D = r"C:\path\to\blender_control\render"   # <<< 改这里
TW = TH = 460
GAP = 10
COLS, ROWS = 3, 2

# 自上而下、自左而右
TILES = [
    "p53_平面_c2.png", "p53_平面_c5.png", "p53_平面_c10.png",
    "nz2_01_base_f1.png", "nz2_02_f121.png", "nz2_06_density6.png",
]

W = COLS * TW + (COLS + 1) * GAP
H = ROWS * TH + (ROWS + 1) * GAP
buf = [0.0] * (W * H * 4)
# 背景：深灰（浅色端不至于刺眼）
BG = 0.06
for i in range(W * H):
    buf[i * 4] = BG; buf[i * 4 + 1] = BG; buf[i * 4 + 2] = BG; buf[i * 4 + 3] = 1.0

log = []
for idx, fn in enumerate(TILES):
    p = os.path.join(D, fn)
    if not os.path.exists(p):
        log.append({"file": fn, "ok": False, "err": "missing"})
        continue
    img = bpy.data.images.load(p, check_existing=False)
    img.scale(TW, TH)
    px = [0.0] * (TW * TH * 4)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)

    c = idx % COLS
    r = idx // COLS
    # Blender 像素缓冲自下而上：把第 r 行（自上而下）折算成从底部数的行号
    x0 = GAP + c * (TW + GAP)
    y0 = H - GAP - TH - r * (TH + GAP)
    for y in range(TH):
        src = y * TW * 4
        dst = ((y0 + y) * W + x0) * 4
        buf[dst:dst + TW * 4] = px[src:src + TW * 4]
    log.append({"file": fn, "ok": True, "slot": [r, c]})

out = bpy.data.images.new("SHEET_nz2", width=W, height=H, alpha=True)
out.pixels.foreach_set(buf)
op = os.path.join(D, "SHEET_nz2_params.png")
out.filepath_raw = op
out.file_format = 'PNG'
out.save()
bpy.data.images.remove(out)

print("SHEET2_BEGIN")
print(json.dumps({"sheet": op, "size": [W, H], "tile": [TW, TH], "order": TILES, "log": log},
                 ensure_ascii=False, indent=1))
print("SHEET2_END")
