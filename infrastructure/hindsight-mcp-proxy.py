#!/usr/bin/env python3
"""Hindsight MCP SSE-to-StreamableHTTP proxy.

Hindsight MCP uses SSE transport (initialize returns mcp-session-id,
responses are event: message\ndata: {...}). Kilo CLI uses Streamable HTTP
(plain JSON POST, expects JSON response). This proxy bridges the two.

Usage: python3 hindsight-mcp-proxy.py [--port PORT] [--target URL]
Defaults: port 9090, target http://hindsight:8888/mcp/
"""
import json
import sys
import argparse
import urllib.request
import urllib.error
import http.server

MCP_TARGET = ["http://hindsight:8888/mcp/"]
SESSION_ID = [None]

def mcp_sse_request(body):
    url = MCP_TARGET[0]
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if SESSION_ID[0]:
        headers["Mcp-Session-Id"] = SESSION_ID[0]
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        return {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": e.code, "message": str(e.reason)}}

    if not SESSION_ID[0]:
        sid = resp.headers.get("mcp-session-id")
        if sid:
            SESSION_ID[0] = sid

    raw = resp.read().decode()
    for line in raw.split("\n"):
        if line.startswith("data: "):
            try:
                return json.loads(line[6:])
            except json.JSONDecodeError:
                pass
    return {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32700, "message": "Parse error"}}

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        result = mcp_sse_request(req)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[mcp-proxy] {args[0]} {args[1]} {args[2]}\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9090)
    parser.add_argument("--target", default=None)
    args = parser.parse_args()
    if args.target:
        MCP_TARGET[0] = args.target
    server = http.server.HTTPServer(("0.0.0.0", args.port), ProxyHandler)
    sys.stderr.write(f"[mcp-proxy] Listening on {args.port}, forwarding to {MCP_TARGET[0]}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

if __name__ == "__main__":
    main()
