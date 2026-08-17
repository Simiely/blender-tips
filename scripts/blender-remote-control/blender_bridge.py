# ============================================================
#  WorkBuddy <-> Blender 控制桥 v2 (主线程执行版)
#
#  v2 改进:所有远程代码通过 bpy.app.timers 调度到主线程执行,
#  可安全地读写 bpy.context / 修改场景、自定义属性、驱动等。
#  监听端口改为 9877,避免与旧版(9876)冲突。
#
#  使用方法:
#   1. Blender -> Scripting 工作区 -> 文本编辑器
#   2. Open 打开本文件(或全选替换旧文本)
#   3. 点 Run Script(或 Alt+P)
#   4. 控制台输出 "[Bridge v2] BRIDGE READY" 即成功
#
#  重复运行安全:会自动关闭旧监听、不会重复注册任务。
# ============================================================

import bpy
import socket
import threading
import io
import contextlib
import traceback
import time

HOST = "127.0.0.1"
PORT = 9877

_srv = None
_queue = []


def _env():
    return {
        "bpy": bpy,
        "C": bpy.context,
        "D": bpy.data,
        "scene": bpy.context.scene,
        "mathutils": __import__("mathutils"),
        "__builtins__": __builtins__,
    }


def _run_timer():
    """主线程执行队列中的远程代码(每 0.05s 检查一次)。"""
    if _queue:
        code, res = _queue.pop(0)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(compile(code, "<remote>", "exec"), _env())
            res["out"] = "OK\n" + buf.getvalue()
        except Exception:
            res["out"] = "ERR\n" + traceback.format_exc()
    return 0.05


def _handle(conn):
    try:
        raw = b""
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                break
            raw += chunk
            if raw.endswith(b"<END>"):
                break
        code = raw[:-5].decode("utf-8", errors="replace")

        res = {}
        _queue.append((code, res))
        deadline = time.time() + 120
        while not res and time.time() < deadline:
            time.sleep(0.02)
        out = res.get("out", "ERR\ntimeout after 120s")
        conn.sendall(out.encode("utf-8") + b"<END>")
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _serve():
    global _srv
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(8)
    _srv = srv
    print(f"[Bridge v2] listening on {HOST}:{PORT}")
    while True:
        try:
            conn, _ = srv.accept()
            threading.Thread(target=_handle, args=(conn,), daemon=True).start()
        except Exception:
            break


def start_bridge():
    global _srv
    if _srv is not None:
        try:
            _srv.close()
            print("[Bridge v2] old server closed")
        except Exception:
            pass
        _srv = None
    if not bpy.app.timers.is_registered(_run_timer):
        bpy.app.timers.register(_run_timer)
    threading.Thread(target=_serve, name="wb_bridge_v2", daemon=True).start()
    print("[Bridge v2] BRIDGE READY - WorkBuddy control channel active on port 9877")


if __name__ == "__main__":
    start_bridge()
