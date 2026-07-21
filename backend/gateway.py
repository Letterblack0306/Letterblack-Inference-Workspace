from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable


class GatewayError(RuntimeError):
    def __init__(self, code: str, message: str, *, status: int = 502, details: Any = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details


@dataclass
class ActiveRequest:
    id: str
    route: str
    protocol: str
    started_at: int
    client: str | None = None
    model: str | None = None
    stream: bool = False
    state: str = "active"
    upstream_status: int | None = None
    bytes_sent: int = 0
    finished_at: int | None = None
    error: dict[str, Any] | None = None


class GatewayRequestManager:
    """Tracks in-flight gateway requests and provides a bounded drain gate.

    Cancellation is truthful: queued requests can be rejected while draining, but an
    already-dispatched urllib request cannot be interrupted safely by this stdlib-only
    implementation. The API therefore reports cancelUnsupported for active requests.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._active: dict[str, ActiveRequest] = {}
        self._history: list[dict[str, Any]] = []
        self._draining = False

    def begin(self, request: ActiveRequest) -> None:
        with self._condition:
            if self._draining:
                raise GatewayError("GATEWAY_DRAINING", "The gateway is draining and is not accepting new requests.", status=503)
            self._active[request.id] = request

    def finish(self, request_id: str, *, state: str = "completed", upstream_status: int | None = None,
               bytes_sent: int = 0, error: dict[str, Any] | None = None) -> None:
        with self._condition:
            req = self._active.pop(request_id, None)
            if req:
                req.state = state
                req.upstream_status = upstream_status
                req.bytes_sent = bytes_sent
                req.finished_at = int(time.time() * 1000)
                req.error = error
                self._history.insert(0, req.__dict__.copy())
                del self._history[500:]
            self._condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "draining": self._draining,
                "active": [x.__dict__.copy() for x in self._active.values()],
                "history": list(self._history[:200]),
                "activeCount": len(self._active),
            }

    def set_draining(self, enabled: bool) -> None:
        with self._condition:
            self._draining = enabled
            self._condition.notify_all()

    def drain(self, timeout_sec: float) -> dict[str, Any]:
        deadline = time.monotonic() + max(0.0, timeout_sec)
        self.set_draining(True)
        with self._condition:
            while self._active and time.monotonic() < deadline:
                self._condition.wait(timeout=min(0.25, max(0.0, deadline - time.monotonic())))
            remaining = [x.__dict__.copy() for x in self._active.values()]
            return {"drained": not remaining, "remaining": remaining, "activeCount": len(remaining)}

    def cancel(self, request_id: str) -> dict[str, Any]:
        with self._lock:
            req = self._active.get(request_id)
            if not req:
                return {"found": False, "cancelled": False}
            return {
                "found": True,
                "cancelled": False,
                "cancelUnsupported": True,
                "reason": "The request is already dispatched to the upstream runtime.",
                "request": req.__dict__.copy(),
            }


OPENAI_ROUTES = {
    "/v1/chat/completions": "/v1/chat/completions",
    "/v1/completions": "/v1/completions",
    "/v1/embeddings": "/v1/embeddings",
}
OLLAMA_ROUTES = {
    "/api/chat": "/api/chat",
    "/api/generate": "/api/generate",
    "/api/embeddings": "/api/embeddings",
}


def upstream_base(runtime: dict[str, Any]) -> str:
    if runtime.get("state") != "ready" and not runtime.get("port"):
        raise GatewayError("RUNTIME_NOT_READY", "No ready runtime is registered for gateway forwarding.", status=503)
    host = runtime.get("host") or "127.0.0.1"
    if host in {"0.0.0.0", "::"}: host = "127.0.0.1"
    port = int(runtime.get("port") or 1234)
    return f"http://{host}:{port}"


def model_list(runtime: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
    active_id = runtime.get("activeModelId")
    active = next((m for m in models if m.get("id") == active_id), None)
    if not active:
        return {"object": "list", "data": []}
    return {"object": "list", "data": [{"id": active.get("name") or active_id, "object": "model", "owned_by": "letterblack", "permission": []}]}


def ollama_tags(runtime: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
    active_id = runtime.get("activeModelId")
    active = next((m for m in models if m.get("id") == active_id), None)
    if not active:
        return {"models": []}
    return {"models": [{
        "name": active.get("name") or active_id,
        "model": active.get("name") or active_id,
        "modified_at": "1970-01-01T00:00:00Z",
        "size": active.get("sizeBytes", 0),
        "digest": active.get("fingerprint") or active_id,
        "details": {"format": "gguf", "family": active.get("metadata", {}).get("architecture", "unknown")},
    }]}


def proxy_request(*, url: str, method: str, headers: dict[str, str], body: bytes | None,
                  timeout_sec: float = 300.0):
    clean_headers = {k: v for k, v in headers.items() if k.lower() not in {"host", "content-length", "connection"}}
    clean_headers.setdefault("Accept", "application/json")
    req = urllib.request.Request(url, data=body, method=method, headers=clean_headers)
    try:
        return urllib.request.urlopen(req, timeout=timeout_sec)
    except urllib.error.HTTPError as exc:
        return exc
    except urllib.error.URLError as exc:
        raise GatewayError("UPSTREAM_UNREACHABLE", "The active llama-server endpoint is unreachable.", details=str(exc)) from exc
