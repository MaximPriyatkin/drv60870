"""Simple event bus client — receives JSON-lines over TCP or UDP.

Usage:
    python bus_client.py tcp 127.0.0.1 9000
    python bus_client.py udp 127.0.0.1 9001
"""

import sys
import json
import socket


def listen_tcp(host, port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)
    print(f"TCP listening on {host}:{port} ...")
    conn, addr = srv.accept()
    print(f"Connected: {addr}")
    buf = ''
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buf += data.decode()
            while '\n' in buf:
                line, buf = buf.split('\n', 1)
                obj = json.loads(line)
                print(obj)
    except KeyboardInterrupt:
        pass
    finally:
        conn.close()
        srv.close()


def listen_udp(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"UDP listening on {host}:{port} ...")
    try:
        while True:
            data, addr = sock.recvfrom(4096)
            obj = json.loads(data.decode())
            print(obj)
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: python bus_client.py <tcp|udp> <host> <port>")
        sys.exit(1)
    proto, host, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
    if proto == 'tcp':
        listen_tcp(host, port)
    elif proto == 'udp':
        listen_udp(host, port)
    else:
        print(f"Unknown protocol: {proto}")
