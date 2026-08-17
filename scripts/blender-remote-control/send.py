# 通用客户端:把指定文件中的代码发送给 Blender bridge(9877)执行
import socket
import sys

PORT = 9877

def main():
    if len(sys.argv) < 2:
        print('用法: python send.py <code_file.py>')
        return
    path = sys.argv[1]
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()
    s = socket.socket()
    s.settimeout(120)
    s.connect(('127.0.0.1', PORT))
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

if __name__ == '__main__':
    main()
