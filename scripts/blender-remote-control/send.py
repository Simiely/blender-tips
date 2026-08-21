# 通用客户端:把指定文件中的代码发送给 Blender bridge 执行
# 用法:
#   python send.py <code_file.py>            # 发送文件内容(默认 9877)
#   python send.py -p 9897 <code_file.py>    # 指定端口(多 Blender 并存)
import socket
import sys

PORT = 9877

def main():
    args = sys.argv[1:]
    port = PORT
    # 解析 -p/--port <port>
    if len(args) >= 2 and args[0] in ('-p', '--port'):
        port = int(args[1])
        args = args[2:]
    if len(args) < 1:
        print(f'用法: python send.py [-p PORT] <code_file.py>  (默认端口 {port})')
        return
    path = args[0]
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()
    s = socket.socket()
    s.settimeout(300)
    s.connect(('127.0.0.1', port))
    s.sendall(code.encode('utf-8') + b'<END>')
    data = b''
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        data += chunk
        if data.endswith(b'<END>'):
            break
    s.close()
    print(data[:-5].decode('utf-8', errors='replace'))

main()
