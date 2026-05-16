#!/usr/bin/env python3
import argparse
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


class OllamaProxyHandler(SimpleHTTPRequestHandler):
    ollama_base = "http://127.0.0.1:11434"
    proxy_prefix = "/ollama/"

    def do_OPTIONS(self):
        if self.path.startswith(self.proxy_prefix):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            return
        self.send_error(405, "Method Not Allowed")

    def do_GET(self):
        if self.path.startswith(self.proxy_prefix):
            self._proxy_request("GET")
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith(self.proxy_prefix):
            self._proxy_request("POST")
            return
        self.send_error(405, "Method Not Allowed")

    def _proxy_request(self, method: str):
        target = self.path.removeprefix(self.proxy_prefix)
        url = urljoin(self.ollama_base.rstrip("/") + "/", target)

        body = None
        if method in {"POST", "PUT", "PATCH"}:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else None

        request_headers = {}
        content_type = self.headers.get("Content-Type")
        if content_type:
            request_headers["Content-Type"] = content_type

        req = Request(url=url, data=body, headers=request_headers, method=method)

        try:
            with urlopen(req, timeout=300) as resp:
                payload = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)
        except HTTPError as exc:
            payload = exc.read() if hasattr(exc, "read") else b""
            self.send_response(exc.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if payload:
                self.wfile.write(payload)
            else:
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
        except URLError as exc:
            msg = {"error": f"Cannot reach Ollama at {self.ollama_base}", "detail": str(exc)}
            payload = json.dumps(msg).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)


def main():
    parser = argparse.ArgumentParser(description="Simple Web UI + Ollama proxy server")
    parser.add_argument("--port", type=int, default=8088, help="Port to listen on")
    parser.add_argument(
        "--ollama-base",
        default=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        help="Base URL for Ollama API",
    )
    args = parser.parse_args()

    web_root = Path(__file__).resolve().parent
    os.chdir(web_root)

    handler_cls = OllamaProxyHandler
    handler_cls.ollama_base = args.ollama_base

    with ThreadingHTTPServer(("127.0.0.1", args.port), handler_cls) as server:
        print(f"Simple Web UI running at http://127.0.0.1:{args.port}/index.html")
        print(f"Proxying /ollama/* -> {args.ollama_base}")
        server.serve_forever()


if __name__ == "__main__":
    main()
