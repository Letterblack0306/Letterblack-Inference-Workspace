"""
Fallback Proxy - Provides automatic failover between multiple API endpoints.

This proxy listens on a local port and forwards requests to multiple APIs
in priority order. If the primary API fails (timeout, error, rate limit),
it automatically tries the next API in the chain.

Usage:
    python -m backend.fallback_proxy --port 8090

Configuration:
    The fallback chain is configured via environment variables:
    - FALLBACK_APIS: JSON array of API configurations
    - FALLBACK_PORT: Port to listen on (default: 8090)

Example:
    FALLBACK_APIS='[
        {"name": "openrouter", "baseUrl": "https://openrouter.ai/api/v1", "apiKey": "sk-..."},
        {"name": "api2", "baseUrl": "https://api2.example.com/v1", "apiKey": "key2"},
        {"name": "api3", "baseUrl": "https://api3.example.com/v1", "apiKey": "key3"}
    ]' python -m backend.fallback_proxy --port 8090
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class FallbackProxy:
    """Manages a chain of API endpoints with automatic failover."""

    def __init__(self, apis: list[dict[str, Any]], timeout: float = 30.0):
        self._apis = apis
        self._timeout = timeout
        self._lock = threading.Lock()
        self._stats = {api["name"]: {"requests": 0, "failures": 0, "lastUsed": None} for api in apis}

    def forward(self, method: str, path: str, headers: dict[str, str], body: bytes | None) -> tuple[int, dict[str, str], bytes]:
        """Forward a request to the first available API in the chain."""
        errors = []

        for api in self._apis:
            api_name = api["name"]
            base_url = api["baseUrl"].rstrip("/")
            api_key = api.get("apiKey", "")

            url = f"{base_url}{path}"

            # Clean headers for upstream
            clean_headers = {k: v for k, v in headers.items() if k.lower() not in {"host", "content-length", "connection"}}
            if api_key:
                clean_headers["Authorization"] = f"Bearer {api_key}"
            clean_headers.setdefault("Accept", "application/json")

            req = urllib.request.Request(url, data=body, method=method, headers=clean_headers)

            try:
                with self._lock:
                    self._stats[api_name]["requests"] += 1
                    self._stats[api_name]["lastUsed"] = time.time()

                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    status = resp.status
                    resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in {"transfer-encoding", "connection"}}
                    resp_body = resp.read()

                    # Check if the response indicates a failure
                    if status >= 500:
                        errors.append(f"{api_name}: HTTP {status}")
                        with self._lock:
                            self._stats[api_name]["failures"] += 1
                        continue

                    if status == 429:  # Rate limited
                        errors.append(f"{api_name}: Rate limited (429)")
                        with self._lock:
                            self._stats[api_name]["failures"] += 1
                        continue

                    if status == 401:  # Unauthorized
                        errors.append(f"{api_name}: Unauthorized (401)")
                        with self._lock:
                            self._stats[api_name]["failures"] += 1
                        continue

                    # Success - return the response
                    return status, resp_headers, resp_body

            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    errors.append(f"{api_name}: Rate limited (429)")
                elif exc.code == 401:
                    errors.append(f"{api_name}: Unauthorized (401)")
                elif exc.code >= 500:
                    errors.append(f"{api_name}: HTTP {exc.code}")
                else:
                    errors.append(f"{api_name}: HTTP {exc.code}")

                with self._lock:
                    self._stats[api_name]["failures"] += 1
                continue

            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                errors.append(f"{api_name}: {exc}")
                with self._lock:
                    self._stats[api_name]["failures"] += 1
                continue

        # All APIs failed
        error_msg = json.dumps({"error": {"message": "All APIs failed", "type": "fallback_exhausted", "details": errors}})
        return 502, {"Content-Type": "application/json"}, error_msg.encode("utf-8")

    def get_stats(self) -> dict[str, Any]:
        """Return statistics about API usage."""
        with self._lock:
            return {"stats": self._stats.copy(), "apiCount": len(self._apis), "apis": [api["name"] for api in self._apis]}


class FallbackProxyHandler(BaseHTTPRequestHandler):
    """HTTP request handler that forwards to the fallback proxy."""

    proxy: FallbackProxy | None = None

    def do_GET(self) -> None:
        self._handle_request("GET")

    def do_POST(self) -> None:
        self._handle_request("POST")

    def do_PUT(self) -> None:
        self._handle_request("PUT")

    def do_DELETE(self) -> None:
        self._handle_request("DELETE")

    def do_PATCH(self) -> None:
        self._handle_request("PATCH")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Allow", "GET,POST,PUT,DELETE,PATCH,OPTIONS")
        self.end_headers()

    def _handle_request(self, method: str) -> None:
        if self.proxy is None:
            self.send_error(500, "Fallback proxy not configured")
            return

        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # Forward to fallback proxy
        headers = {k: v for k, v in self.headers.items()}
        status, resp_headers, resp_body = self.proxy.forward(method, self.path, headers, body)

        # Send response
        self.send_response(status)
        for key, value in resp_headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(resp_body)))
        self.send_header("X-Fallback-Proxy", "Letterblack-Control/6")
        self.end_headers()
        self.wfile.write(resp_body)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging."""
        pass


def load_apis_from_env() -> list[dict[str, Any]]:
    """Load API configurations from environment variable."""
    raw = os.environ.get("FALLBACK_APIS", "[]")
    try:
        apis = json.loads(raw)
        if not isinstance(apis, list):
            raise ValueError("FALLBACK_APIS must be a JSON array")
        return apis
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Error loading FALLBACK_APIS: {exc}")
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Fallback proxy with automatic failover")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8090, help="Port to listen on")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds")
    args = parser.parse_args()

    apis = load_apis_from_env()
    if not apis:
        print("No APIs configured. Set FALLBACK_APIS environment variable.")
        print("Example:")
        print('FALLBACK_APIS=\'[{"name":"openrouter","baseUrl":"https://openrouter.ai/api/v1","apiKey":"sk-..."}]\'')
        return

    proxy = FallbackProxy(apis, timeout=args.timeout)
    FallbackProxyHandler.proxy = proxy

    server = ThreadingHTTPServer((args.host, args.port), FallbackProxyHandler)
    print(f"Fallback proxy serving http://{args.host}:{args.port}")
    print(f"Configured APIs: {[api['name'] for api in apis]}")
    print(f"Stats endpoint: http://{args.host}:{args.port}/stats")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()