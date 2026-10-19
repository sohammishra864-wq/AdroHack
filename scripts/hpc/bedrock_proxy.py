"""Tiny HTTPS (CONNECT) proxy that lets the offline GPU node reach Amazon Bedrock through the
laptop's internet (and Supabase for login). Only *.amazonaws.com and *.supabase.co :443; anything else gets 403. Traffic stays
TLS end to end (the proxy only pipes bytes), so it never sees the token or the text.

Laptop:   python scripts/hpc/bedrock_proxy.py            (listens on 127.0.0.1:3128)
          ssh -N -J <user>@<login> -R 3128:127.0.0.1:3128 <user>@<gpu-node>
GPU node: HTTPS_PROXY=http://127.0.0.1:3128   (scripts/hpc/demo.pbs sets it)
"""
import socket
import sys
import threading

ALLOWED = (".amazonaws.com", ".supabase.co")   # Bedrock + Supabase login


def pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while data := src.recv(65536):
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def handle(client: socket.socket) -> None:
    try:
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = client.recv(4096)
            if not chunk:
                return
            head += chunk
        method, target, _ = head.split(b"\r\n", 1)[0].decode("latin-1").split(" ", 2)
        host, _, port = target.rpartition(":")
        if method != "CONNECT" or port != "443" or not host.endswith(ALLOWED):
            client.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            print(f"blocked  {method} {target}", flush=True)
            return
        upstream = socket.create_connection((host, 443), timeout=10)
        upstream.settimeout(None)
        client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
        print(f"tunnel   {host}", flush=True)
        threading.Thread(target=pipe, args=(upstream, client), daemon=True).start()
        pipe(client, upstream)
    except Exception as e:  # one bad connection must not stop the proxy
        print(f"error    {type(e).__name__}: {e}", flush=True)
    finally:
        client.close()


def main(port: int = 3128) -> None:
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(64)
    print(f"Bedrock proxy on 127.0.0.1:{port} (allows only *.amazonaws.com / *.supabase.co :443)", flush=True)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3128)
