# -*- coding: utf-8 -*-
"""长任务实时进度看板（零依赖本地服务）。

读后台无头任务的日志与 state.json，解析成 JSON 给 progress.html 轮询。

    python serve_progress.py [端口]            # 默认 8765
    PROGRESS_JOB_DIR=<任务输出目录> python serve_progress.py

`<任务输出目录>` 形如 `C:\\Temp\\trae-agent-toolhost\\jobs\\job-xxxx\\`，
必须含 `output.log`（任务 stdout）与 `state.json`（可选，含 status/exit_code）。

只认脚本打点的固定前缀 —— `delete_region.py` 用的是 `[DEL]`，换个前缀本看板即可复用到别的长任务。
"""
import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(BASE, "progress.html")

CONFIG = dict(
    JOB_DIR=r"C:\Temp\trae-agent-toolhost\jobs\job-XXXXXXXX",
    PREFIX="[DEL]",
)
JOB_DIR = os.environ.get("PROGRESS_JOB_DIR", CONFIG["JOB_DIR"])
LOG_PATH = os.path.join(JOB_DIR, "output.log")
STATE_PATH = os.path.join(JOB_DIR, "state.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

RE_LOADED = re.compile(r"loaded\s+(\d+)\s+objects")
RE_VICTIMS = re.compile(r"victims:\s*(\d+)")
RE_FROZEN = re.compile(r"frozen[^:]*:\s*(\d+)\s+([\d.]+)\s*s")
RE_REMOVED = re.compile(r"removed\s+(\d+)\s*/\s*(\d+)\s+elapsed\s+([\d.]+)s", re.I)
RE_REMAIN = re.compile(r"objects remaining:\s*(\d+)")
RE_PURGE = re.compile(r"orphans_purge pass\s+(\d+)\s*->\s*(\d+)")
RE_AFTER = re.compile(r"after purge -> objects:\s*(\d+)\s+meshes:\s*(\d+)\s+materials:\s*(\d+)\s+images:\s*(\d+)")
RE_SAVED = re.compile(r"saved\s*->\s*(.+?)\s+([\d.]+)\s*MB\s+([\d.]+)\s*s", re.I)
RE_SRC = re.compile(r"src=(.+?)\s*$")
RE_NEW = re.compile(r"target new=(.+?)\s*$")

STAGE_LABELS = {
    "loading": "读取工程", "scanning": "扫描并判定覆盖区对象", "freezing": "冻结父级对象（保持世界坐标）",
    "deleting": "删除覆盖区内对象", "purging": "清理孤立无用数据", "saving": "另存为新文件",
    "done": "已完成", "error": "出错中断",
}


def read_text(path):
    """容错读取：多编码回退 + 短重试（日志可能正被别的进程追加）。"""
    data = None
    mtime = None
    for _ in range(3):
        try:
            with open(path, "rb") as f:
                data = f.read()
            mtime = os.path.getmtime(path)
            break
        except OSError:
            time.sleep(0.05)
    if data is None:
        return "", None
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return data.decode(enc), mtime
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), mtime


def parse():
    text, mtime = read_text(LOG_PATH)
    lines = [ln.rstrip("\r") for ln in text.splitlines() if ln.strip()]
    body = [ln for ln in lines if ln.startswith(CONFIG["PREFIX"])]

    src = new_path = saved_path = None
    total_objects = None
    victims = None
    denom = None
    frozen = None
    removed = 0
    last_elapsed = 0.0
    samples = []
    purge_log = []
    after = None
    remaining = None
    stage = "loading"
    done = False

    for ln in body:
        low = ln.lower()
        m = RE_SRC.search(ln)
        if m:
            src = m.group(1).strip().strip('"')
            continue
        m = RE_NEW.search(ln)
        if m:
            new_path = m.group(1).strip().strip('"')
            continue
        m = RE_LOADED.search(ln)
        if m:
            total_objects = int(m.group(1))
            stage = "scanning"
            continue
        m = RE_VICTIMS.search(ln)
        if m:
            victims = int(m.group(1))
            denom = victims
            continue
        m = RE_FROZEN.search(ln)
        if m:
            frozen = int(m.group(1))
            stage = "freezing"
            continue
        m = RE_REMOVED.search(ln)
        if m:
            removed = int(m.group(1))
            denom = int(m.group(2))
            last_elapsed = float(m.group(3))
            samples.append({"removed": removed, "elapsed": last_elapsed})
            stage = "deleting"
            continue
        m = RE_REMAIN.search(ln)
        if m:
            remaining = int(m.group(1))
            stage = "purging"
            continue
        m = RE_PURGE.search(ln)
        if m:
            purge_log.append([int(m.group(1)), int(m.group(2))])
            stage = "purging"
            continue
        m = RE_AFTER.search(ln)
        if m:
            after = {"objects": int(m.group(1)), "meshes": int(m.group(2)),
                     "materials": int(m.group(3)), "images": int(m.group(4))}
            stage = "saving"
            continue
        m = RE_SAVED.search(ln)
        if m:
            saved_path, stage = m.group(1).strip().strip('"'), "saving"
            continue
        if "DONE" in ln or "完成" in ln:
            done, stage = True, "done"
            continue
        if "start" in low or "target new" in low:
            continue

    if not done and denom and removed >= denom:
        stage = "purging"

    job_status = exit_code = None
    try:
        with open(STATE_PATH, "r", encoding="utf-8", errors="replace") as f:
            st = json.load(f)
        job_status, exit_code = st.get("status"), st.get("exit_code")
    except Exception:
        pass

    error = None
    if job_status == "Exited" and exit_code not in (0, None):
        stage, error = "error", "进程退出，exit_code=%s" % exit_code
    if job_status == "Exited" and exit_code == 0 and not done:
        done, stage = True, "done"
    for ln in lines:
        if "Traceback (most recent call last)" in ln or ln.startswith("Error:") or "[FATAL]" in ln:
            error, stage = ln.strip()[:300], "error"
            break

    den = denom or victims or 0
    pct = (100.0 * removed / den) if den else 0.0
    rate = (removed / last_elapsed) if last_elapsed > 0 and removed else 0.0
    eta = ((den - removed) / rate) if rate > 0 and removed < den else 0.0

    return {
        "now": time.time(), "stage": stage, "stage_label": STAGE_LABELS.get(stage, stage),
        "done": done, "error": error,
        "src": src, "new_path": new_path, "saved_path": saved_path,
        "total_objects": total_objects, "victims": victims, "denom": den,
        "removed": removed, "frozen": frozen, "remaining": remaining,
        "percent": round(pct, 3), "rate": round(rate, 3), "eta_seconds": round(eta, 1),
        "last_elapsed": round(last_elapsed, 1), "samples": samples,
        "purge_log": purge_log, "after": after,
        "log_age": round(time.time() - mtime, 1) if mtime else None,
        "job_status": job_status, "exit_code": exit_code,
        "lines": body[-30:] if body else lines[-30:],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, ctype, payload):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/progress.html", "/index.html"):
            try:
                with open(HTML, "rb") as f:
                    self._send(200, "text/html; charset=utf-8", f.read())
            except OSError as e:
                self._send(500, "text/plain; charset=utf-8", ("缺少 progress.html: %s" % e).encode("utf-8"))
        elif path == "/api/progress":
            try:
                data = json.dumps(parse(), ensure_ascii=False).encode("utf-8")
            except Exception as e:
                data = json.dumps({"error": "解析失败: %s" % e, "stage": "error"},
                                  ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", data)
        else:
            self._send(404, "text/plain; charset=utf-8", b"404")


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("进度看板已启动:  http://127.0.0.1:%d/" % PORT)
    print("日志来源:        %s" % LOG_PATH)
    print("按 Ctrl+C 停止")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


main()
