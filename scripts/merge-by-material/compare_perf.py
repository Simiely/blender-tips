# -*- coding: utf-8 -*-
"""
对多个 .blend 做「加载 + 体检」同口径计时并输出对照（回答「合并后会更流畅吗」）。

用法：
    python compare_perf.py <源.blend> <产物.blend> [...]
    # Blender 可执行文件：--blender <exe>，或环境变量 BLENDER_EXE，
    # 否则在常见安装路径里自动找。

它测的是**冷读 + 全量遍历**的总耗时，包含 Blender 加载工程的时间 ——
这是「打开这个工程要等多久」的直接答案。
（注意：第二次跑同一文件会走系统页缓存，明显更快，**别用第二轮估第一轮**。）

输出：stdout 对照 + 落盘 perf_compare.txt
"""

import argparse
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "perf_probe.py")
DEFAULTS = [r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"]

ap = argparse.ArgumentParser()
ap.add_argument("--blender", default=os.environ.get("BLENDER_EXE", ""))
ap.add_argument("--out", default=os.path.join(os.getcwd(), "perf_compare.txt"))
ap.add_argument("files", nargs="+", help="要体检的 .blend（按顺序对照）")
a = ap.parse_args()

bl = a.blender
if not bl or not os.path.isfile(bl):
    for c in DEFAULTS + sorted(glob.glob(
            r"C:\Program Files\Blender Foundation\Blender*\blender.exe")):
        if os.path.isfile(c):
            bl = c
            break
if not bl or not os.path.isfile(bl):
    raise SystemExit("找不到 blender.exe，用 --blender <exe> 或环境变量 BLENDER_EXE 指定")

LOG = []


def W(s=""):
    LOG.append(str(s))
    print(s)


W("Blender: %s" % bl)
W("Probe  : %s" % PROBE)
W("=" * 72)

for fp in a.files:
    if not os.path.isfile(fp):
        W("!! 文件不存在: %s" % fp)
        continue
    sz = os.path.getsize(fp)
    szmb = sz / 1024 / 1024
    t0 = time.time()
    r = subprocess.run([bl, "--background", "--factory-startup", fp,
                        "--python", PROBE],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=os.getcwd())
    dt = time.time() - t0
    W("-" * 72)
    W("%s" % fp)
    W("  %d 字节 (%.1f MB)   加载+体检总耗时 %.1f 秒   (exit=%d)"
      % (sz, szmb, dt, r.returncode))
    W("-" * 72)
    W((r.stdout or "").strip())
    if r.returncode != 0:
        W("STDERR: %s" % (r.stderr or "")[-800:])

W("=" * 72)
with open(a.out, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(LOG) + "\n")
W("[saved] %s" % a.out)
