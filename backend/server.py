from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import sys
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from collections.abc import Callable
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.contracts import create_job, envelope, error, new_id, now_ms, validate_machine, validate_profile, validate_workspace
    from backend.store import JsonStore
    from backend.runtime import ProcessManager, RuntimeFailure, build_llama_command, controller_rpc, controller_status, scan_gguf, tcp_probe
    from backend.gateway import ActiveRequest, GatewayError, GatewayRequestManager, OPENAI_ROUTES, OLLAMA_ROUTES, model_list, ollama_tags, proxy_request, upstream_base
    from backend.hardware import estimate_allocation, local_telemetry
    from backend.extensions import combined_actions, combined_endpoints, combined_widgets, execute_http_action, normalized_extension, test_endpoint, validate_action, validate_endpoint, validate_extension
else:
    from .contracts import create_job, envelope, error, new_id, now_ms, validate_machine, validate_profile, validate_workspace
    from .store import JsonStore
    from .runtime import ProcessManager, RuntimeFailure, build_llama_command, controller_rpc, controller_status, scan_gguf, tcp_probe
    from .gateway import ActiveRequest, GatewayError, GatewayRequestManager, OPENAI_ROUTES, OLLAMA_ROUTES, model_list, ollama_tags, proxy_request, upstream_base
    from .hardware import estimate_allocation, local_telemetry
    from .extensions import combined_actions, combined_endpoints, combined_widgets, execute_http_action, normalized_extension, test_endpoint, validate_action, validate_endpoint, validate_extension

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
CONTRACT_ROOT = ROOT / "contracts"
STORE = JsonStore(ROOT / "data" / "state.json")
PROCESS = ProcessManager(ROOT / "data" / "logs")
GATEWAY = GatewayRequestManager()

CONTROL_PLANE_HOST = "127.0.0.1"
CONTROL_PLANE_PORT = 8088


def control_plane_listener() -> dict[str, Any]:
    """Return the only supported control-plane listener."""
    return {
        "host": CONTROL_PLANE_HOST,
        "port": CONTROL_PLANE_PORT,
        "url": f"http://{CONTROL_PLANE_HOST}:{CONTROL_PLANE_PORT}",
        "remoteControlSupported": False,
    }


CONTROL_SERVER_SHUTDOWN_DELAY_SECONDS = 2.0
_control_server_shutdown: Callable[[], None] | None = None
_control_server_shutdown_lock = threading.Lock()


def configure_control_server_shutdown(callback: Callable[[], None] | None) -> None:
    """Register the active HTTP server's shutdown callback at process startup."""
    global _control_server_shutdown
    with _control_server_shutdown_lock:
        _control_server_shutdown = callback


def schedule_control_server_shutdown(delay_seconds: float = CONTROL_SERVER_SHUTDOWN_DELAY_SECONDS) -> dict[str, Any]:
    """Stop the control server from a separate thread after a completed stop job."""
    with _control_server_shutdown_lock:
        callback = _control_server_shutdown
    if callback is None:
        raise RuntimeFailure(
            "CONTROL_SERVER_SHUTDOWN_UNAVAILABLE",
            "The active control server cannot be shut down from this process.",
        )
    delay = max(0.0, float(delay_seconds))
    timer = threading.Timer(delay, callback)
    timer.daemon = True
    timer.start()
    return {"scheduled": True, "delaySeconds": delay}

CAPABILITIES = {
    "contractVersion": "6.0.0", "phase": 6, "runtimeMode": "declarative-extensibility",
    "features": {
        "workspaceRegistry": True, "workspacePersistence": True, "widgetRegistry": True,
        "layoutImportExport": True, "machineRegistry": True, "machineConnectionTest": True,
        "controllerStatus": True, "rpcLifecycle": "real-controller-http", "modelScanning": "real-recursive-gguf",
        "profileRegistry": True, "runtimeLifecycle": "real-local-process", "readinessVerification": True,
        "stopAllEvidence": True, "jobs": True, "logs": True, "telemetry": "live-local-nvidia-controller",
        "openAICompatibility": "subset-proxy", "ollamaCompatibility": "subset-proxy",
        "requestTracking": True, "requestDrain": True, "activeCancellation": False, "arbitraryShell": False,
        "ggufHeaderParsing": True, "allocationEstimator": True, "unsafeLaunchPrevention": True,
        "actionBuilder": True, "extensionManifests": "declarative-only", "customWidgets": True,
        "customEndpoints": True, "extensionExecutableCode": False,
    },
    "defaultPorts": {"dashboard":8088,"openai":1234,"ollama":11434,"rpc":50052,"controller":50053},
}


WIDGET_REGISTRY = [
    {"type": "active-model", "name": "Active model", "category": "runtime", "minSize": {"w": 4, "h": 2}, "defaultSize": {"w": 8, "h": 3}},
    {"type": "machine-topology", "name": "Machine topology", "category": "machines", "minSize": {"w": 4, "h": 2}, "defaultSize": {"w": 4, "h": 3}},
    {"type": "gpu-telemetry", "name": "GPU & VRAM telemetry", "category": "telemetry", "minSize": {"w": 4, "h": 2}, "defaultSize": {"w": 7, "h": 3}},
    {"type": "request-table", "name": "Request table", "category": "requests", "minSize": {"w": 4, "h": 2}, "defaultSize": {"w": 5, "h": 3}},
    {"type": "logs", "name": "Logs & evidence", "category": "developer", "minSize": {"w": 5, "h": 2}, "defaultSize": {"w": 7, "h": 3}},
    {"type": "quick-actions", "name": "Custom actions", "category": "runtime", "minSize": {"w": 3, "h": 2}, "defaultSize": {"w": 4, "h": 2}},
    {"type": "playground", "name": "Prompt playground", "category": "developer", "minSize": {"w": 5, "h": 3}, "defaultSize": {"w": 8, "h": 4}},
    {"type": "api-health", "name": "API health", "category": "api", "minSize": {"w": 3, "h": 2}, "defaultSize": {"w": 4, "h": 2}},
]

TELEMETRY_CONTROLLER_TIMEOUT_SECONDS = 0.75

def add_log(state: dict[str, Any], severity: str, source: str, message: str, **details: Any) -> dict[str, Any]:
    event = {
        "id": new_id("log"),
        "timestamp": now_ms(),
        "severity": severity,
        "source": source,
        "message": message,
        "details": details,
    }
    state["logs"].insert(0, event)
    del state["logs"][500:]
    return event


def update_job(job_id: str, **updates: Any) -> dict[str, Any] | None:
    def mutate(state):
        for job in state["jobs"]:
            if job["id"] == job_id:
                job.update(updates); job["updatedAt"] = now_ms(); return job
        return None
    return STORE.mutate(mutate)


def job_evidence(job_id: str, phase: str, status: str, **details: Any) -> None:
    def mutate(state):
        for job in state["jobs"]:
            if job["id"] == job_id:
                job["evidence"].append({"phase":phase,"status":status,"timestamp":now_ms(),**details}); job["updatedAt"]=now_ms(); return
    STORE.mutate(mutate)


def run_job(job: dict[str, Any], task) -> None:
    def worker():
        try:
            update_job(job["id"], state="running", progress=1)
            result=task(job)
            update_job(job["id"], state="succeeded", phase="complete", progress=100, result=result)
            def log(state): add_log(state,"info","jobs",f"Job {job['id']} completed.",jobType=job["type"])
            STORE.mutate(log)
        except RuntimeFailure as exc:
            update_job(job["id"],state="failed",phase="failed",error={"code":exc.code,"message":str(exc),"details":exc.details})
            STORE.mutate(lambda state:add_log(state,"error","jobs",str(exc),jobId=job["id"],code=exc.code,details=exc.details))
        except Exception as exc:
            update_job(job["id"],state="failed",phase="failed",error={"code":"UNEXPECTED_RUNTIME_ERROR","message":str(exc)})
            STORE.mutate(lambda state:add_log(state,"error","jobs","Unexpected runtime job failure.",jobId=job["id"],diagnostic=str(exc)))
    threading.Thread(target=worker,daemon=True).start()


def rpc_task(machine: dict[str,Any], action: str):
    def task(job):
        update_job(job["id"],phase="validate",progress=10)
        probe=tcp_probe(machine["addresses"][0],machine["controller"]["port"]); job_evidence(job["id"],"validate","pass" if probe["reachable"] else "fail",**probe)
        if not probe["reachable"]: raise RuntimeFailure("CONTROLLER_UNREACHABLE","Worker controller is unreachable.",probe)
        update_job(job["id"],phase="dispatch",progress=40)
        response=controller_rpc(machine,action); job_evidence(job["id"],"dispatch","pass",response=response)
        update_job(job["id"],phase="verify",progress=75)
        if action=="start":
            rpc=tcp_probe(machine["addresses"][0],machine.get("rpc",{}).get("port",50052),timeout=5)
            job_evidence(job["id"],"verify","pass" if rpc["reachable"] else "fail",**rpc)
            if not rpc["reachable"]: raise RuntimeFailure("RPC_NOT_READY","Controller accepted start but RPC port did not become ready.",rpc)
        else:
            deadline=time.monotonic()+8; rpc=None
            while time.monotonic()<deadline:
                rpc=tcp_probe(machine["addresses"][0],machine.get("rpc",{}).get("port",50052),timeout=.5)
                if not rpc["reachable"]: break
                time.sleep(.3)
            job_evidence(job["id"],"verify","pass" if rpc and not rpc["reachable"] else "fail",probe=rpc)
            if rpc and rpc["reachable"]: raise RuntimeFailure("RPC_STILL_RUNNING","RPC port remains reachable after stop.",rpc)
        return {"controllerResponse":response}
    return task


def scan_task(body: dict[str,Any]):
    def task(job):
        update_job(job["id"],phase="validate-sources",progress=10)
        state=STORE.snapshot(); sources=body.get("sources") or state.get("modelSources",[])
        sources=[x if isinstance(x,dict) else {"id":"source-manual","path":str(x)} for x in sources]
        job_evidence(job["id"],"validate-sources","pass",sourceCount=len(sources))
        update_job(job["id"],phase="enumerate",progress=35)
        models=scan_gguf([x for x in sources if x.get("enabled",True)])
        job_evidence(job["id"],"enumerate","pass",modelCount=len(models))
        update_job(job["id"],phase="register",progress=75)
        STORE.mutate(lambda st: st.update({"models":models}) or models)
        return {"modelCount":len(models),"models":models}
    return task


def action_task(action: dict[str, Any], inputs: dict[str, Any]):
    required = {
        "http-request": "network.http",
        "controller-status": "machine.status",
        "rpc-start": "machine.rpc.start",
        "rpc-stop": "machine.rpc.stop",
        "models-scan": "models.scan",
        "profile-select": "profile.read",
    }
    def task(job):
        action_type = action["type"]
        permission = required[action_type]
        update_job(job["id"], phase="validate-permissions", progress=15)
        if permission not in action.get("permissions", []):
            raise RuntimeFailure("ACTION_PERMISSION_MISSING", "Action does not declare the required permission.", {"required": permission})
        state = STORE.snapshot()
        job_evidence(job["id"], "validate-permissions", "pass", permission=permission)
        update_job(job["id"], phase="execute", progress=45)
        config = action.get("config", {})
        if action_type == "http-request":
            endpoints = combined_endpoints(state.get("customEndpoints", []), state.get("extensions", []))
            endpoint = next((item for item in endpoints if item["id"] == config.get("endpointId") and item.get("enabled", True)), None)
            if not endpoint:
                raise RuntimeFailure("ENDPOINT_NOT_FOUND", "Registered endpoint is unavailable.", {"endpointId": config.get("endpointId")})
            result = execute_http_action(action, endpoint, inputs)
            if result.get("httpError"):
                raise RuntimeFailure("ACTION_HTTP_ERROR", "HTTP action returned an error response.", result)
        elif action_type in {"controller-status", "rpc-start", "rpc-stop"}:
            machine = next((item for item in state["machines"] if item["id"] == config.get("machineId") and item.get("enabled", True)), None)
            if not machine:
                raise RuntimeFailure("MACHINE_NOT_FOUND", "Action target machine is unavailable.", {"machineId": config.get("machineId")})
            if action_type == "controller-status":
                result = controller_status(machine)
            else:
                result = controller_rpc(machine, "start" if action_type == "rpc-start" else "stop")
        elif action_type == "models-scan":
            sources = [item for item in state.get("modelSources", []) if item.get("enabled", True)]
            models = scan_gguf(sources)
            STORE.mutate(lambda st: st.update({"models": models}) or models)
            result = {"modelCount": len(models)}
        elif action_type == "profile-select":
            profile = next((item for item in state["profiles"] if item["id"] == config.get("profileId")), None)
            if not profile:
                raise RuntimeFailure("PROFILE_NOT_FOUND", "Action profile is unavailable.", {"profileId": config.get("profileId")})
            result = {"profile": profile}
        else:
            raise RuntimeFailure("ACTION_TYPE_UNSUPPORTED", "Action type is not supported.", {"type": action_type})
        job_evidence(job["id"], "execute", "pass", result=result)
        update_job(job["id"], phase="verify", progress=85)
        return {"actionId": action["id"], "result": result}
    return task


def launch_task(body: dict[str,Any]):
    def task(job):
        state=STORE.snapshot(); model=next((m for m in state["models"] if m["id"]==body.get("modelId")),None)
        if not model: raise RuntimeFailure("MODEL_NOT_FOUND","Selected model is not registered.",{"modelId":body.get("modelId")})
        profile=next((p for p in state["profiles"] if p["id"]==body.get("profileId")),None) if body.get("profileId") else None
        update_job(job["id"],phase="validate",progress=10)
        launch_body = dict(body)
        profile_values = (profile or {}).get("values", {})
        configured_executable = state.get("settings", {}).get("paths", {}).get("llamaServerPath")
        if configured_executable and not any((launch_body.get("executable"), launch_body.get("runtimePath"), profile_values.get("executable"), profile_values.get("runtimePath"))):
            launch_body["executable"] = configured_executable
        exe,args,cwd,port,host=build_llama_command(model,profile,state["machines"],launch_body); job_evidence(job["id"],"validate","pass",command=[exe,*args])
        rpc_ids=(profile or {}).get("values",{}).get("rpcMachineIds") or body.get("rpcMachineIds") or []
        update_job(job["id"],phase="test-machines",progress=25)
        for mid in rpc_ids:
            m=next(x for x in state["machines"] if x["id"]==mid); probe=tcp_probe(m["addresses"][0],m.get("rpc",{}).get("port",50052),3)
            job_evidence(job["id"],"test-machines","pass" if probe["reachable"] else "fail",machineId=mid,**probe)
            if not probe["reachable"]: raise RuntimeFailure("RPC_MACHINE_UNREADY","Required RPC worker is not ready.",{"machineId":mid,**probe})
        update_job(job["id"],phase="start-host",progress=50)
        proc=PROCESS.start(exe,args,cwd); job_evidence(job["id"],"start-host","pass",**proc)
        STORE.mutate(lambda st: st["runtime"].update({"state":"starting","activeModelId":model["id"],"activeProfileId":body.get("profileId"),"pid":proc["pid"],"port":port,"host":host,"command":proc["command"],"logPath":proc["logPath"]}))
        update_job(job["id"],phase="verify-api",progress=75)
        probe_host='127.0.0.1' if host in {'0.0.0.0','::'} else host; deadline=time.monotonic()+float(body.get("readinessTimeoutSec",45)); last=None
        while time.monotonic()<deadline:
            if not PROCESS.status()["running"]: raise RuntimeFailure("RUNTIME_EXITED","llama-server exited before readiness.",PROCESS.status())
            last=tcp_probe(probe_host,port,.8)
            if last["reachable"]: break
            time.sleep(.5)
        job_evidence(job["id"],"verify-api","pass" if last and last["reachable"] else "fail",probe=last)
        if not last or not last["reachable"]:
            PROCESS.stop(); raise RuntimeFailure("API_NOT_READY","llama-server did not become reachable before timeout.",last)
        STORE.mutate(lambda st: st["runtime"].update({"state":"ready","readyAt":now_ms()}))
        return {"runtime":STORE.snapshot()["runtime"]}
    return task


def stop_task(body: dict[str,Any]):
    def task(job):
        try:
            update_job(job["id"],phase="drain-requests",progress=10); drain=GATEWAY.drain(float(body.get("drainTimeoutSec",30))); job_evidence(job["id"],"drain-requests","pass" if drain["drained"] else "fail",**drain)
            if not drain["drained"] and not body.get("force",False): raise RuntimeFailure("REQUESTS_NOT_DRAINED","Active gateway requests did not drain before timeout.",drain)
            update_job(job["id"],phase="stop-host",progress=30); stopped=PROCESS.stop(float(body.get("timeoutSec",10))); job_evidence(job["id"],"stop-host","pass",**stopped)
            state=STORE.snapshot(); selected=body.get("machineIds")
            workers=[m for m in state["machines"] if m.get("rpc",{}).get("enabled") and (selected is None or m["id"] in selected)]
            update_job(job["id"],phase="stop-workers",progress=55)
            worker_results=[]
            for m in workers:
                try:
                    response=controller_rpc(m,"stop"); worker_results.append({"machineId":m["id"],"ok":True,"response":response}); job_evidence(job["id"],"stop-workers","pass",machineId=m["id"])
                except RuntimeFailure as exc:
                    worker_results.append({"machineId":m["id"],"ok":False,"error":{"code":exc.code,"message":str(exc)}}); job_evidence(job["id"],"stop-workers","fail",machineId=m["id"],code=exc.code)
            update_job(job["id"],phase="verify-stopped",progress=85)
            proc=PROCESS.status(); job_evidence(job["id"],"verify-stopped","pass" if not proc["running"] else "fail",process=proc)
            if proc["running"]: raise RuntimeFailure("HOST_STILL_RUNNING","Managed host process is still running.",proc)
            STORE.mutate(lambda st: st.update({"runtime":{"state":"stopped","activeModelId":None,"activeProfileId":None}}))
            failed_workers = [item for item in worker_results if not item["ok"]]
            if failed_workers:
                raise RuntimeFailure("WORKERS_NOT_STOPPED", "One or more selected worker runtimes could not be stopped.", {"workers": failed_workers})
            result = {"host":stopped,"workers":worker_results}
            if body.get("shutdownControlServer") is True:
                update_job(job["id"], phase="shutdown-control-server", progress=95)
                shutdown = schedule_control_server_shutdown()
                job_evidence(job["id"], "shutdown-control-server", "scheduled", **shutdown)
                result["controlServerShutdown"] = shutdown
            return result
        finally:
            GATEWAY.set_draining(False)
    return task


class Handler(BaseHTTPRequestHandler):
    server_version = "LetterblackPhase4/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _request_id(self) -> str:
        return self.headers.get("X-Request-ID") or new_id("req")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Request-ID", payload.get("requestId", self._request_id()))
            self.end_headers()
            self.wfile.write(body)

        except (
            BrokenPipeError,
            ConnectionAbortedError,
            ConnectionResetError,
        ):
            # The browser navigated, refreshed, or cancelled the request.
            # This is not a server-side application failure.
            return

    def _ok(self, data: Any, status: int = 200) -> None:
        self._send_json(status, envelope(data, request_id=self._request_id()))

    def _fail(self, code: str, message: str, status: int = 400, details: Any = None) -> None:
        status_code, payload = error(code, message, status=status, details=details, request_id=self._request_id())
        self._send_json(status_code, payload)

    def _json_body(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("Payload exceeds 1 MB.")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _parts(self) -> list[str]:
        path = urllib.parse.urlparse(self.path).path
        return [urllib.parse.unquote(p) for p in path.strip("/").split("/") if p]

    def _raw_body(self, max_bytes: int = 8_000_000) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        if length > max_bytes:
            raise ValueError(f"Payload exceeds {max_bytes} bytes.")
        return self.rfile.read(length) if length else b""

    def _gateway_error(self, exc: GatewayError) -> None:
        payload = {"error": {"message": str(exc), "type": exc.code.lower(), "code": exc.code, "details": exc.details}}
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(exc.status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Request-ID", self._request_id())
        self.end_headers()
        self.wfile.write(body)

    def _gateway_get(self, path: str) -> None:
        state = STORE.snapshot()
        if path == "/v1/models":
            body = json.dumps(model_list(state["runtime"], state["models"])).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if path == "/api/tags":
            body = json.dumps(ollama_tags(state["runtime"], state["models"])).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        self._gateway_error(GatewayError("COMPATIBILITY_ROUTE_UNSUPPORTED", "This compatibility route is not implemented.", status=404, details={"path": path}))

    def _gateway_post(self, path: str) -> None:
        protocol = "openai" if path.startswith("/v1/") else "ollama"
        mapping = OPENAI_ROUTES if protocol == "openai" else OLLAMA_ROUTES
        if path not in mapping:
            self._gateway_error(GatewayError("COMPATIBILITY_ROUTE_UNSUPPORTED", "This compatibility route is not implemented.", status=404, details={"path": path, "protocol": protocol})); return
        request_id = self._request_id()
        try:
            raw = self._raw_body()
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            state = STORE.snapshot()
            runtime = state["runtime"]
            req = ActiveRequest(id=request_id, route=path, protocol=protocol, started_at=now_ms(), client=self.client_address[0] if self.client_address else None, model=parsed.get("model"), stream=bool(parsed.get("stream")))
            GATEWAY.begin(req)
            url = upstream_base(runtime) + mapping[path]
            headers = {k: v for k, v in self.headers.items()}
            upstream = proxy_request(url=url, method="POST", headers=headers, body=raw)
            status = getattr(upstream, "status", getattr(upstream, "code", 502))
            content_type = upstream.headers.get("Content-Type", "application/json")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Request-ID", request_id)
            self.send_header("Connection", "close")
            self.end_headers()
            sent = 0
            while True:
                chunk = upstream.read(64 * 1024)
                if not chunk: break
                self.wfile.write(chunk); self.wfile.flush(); sent += len(chunk)
            GATEWAY.finish(request_id, state="completed" if status < 400 else "failed", upstream_status=status, bytes_sent=sent)
        except GatewayError as exc:
            GATEWAY.finish(request_id, state="failed", error={"code": exc.code, "message": str(exc)})
            self._gateway_error(exc)
        except (ValueError, json.JSONDecodeError) as exc:
            GATEWAY.finish(request_id, state="failed", error={"code":"INVALID_JSON","message":str(exc)})
            self._gateway_error(GatewayError("INVALID_JSON", str(exc), status=400))
        except (BrokenPipeError, ConnectionResetError):
            GATEWAY.finish(request_id, state="client-disconnected", error={"code":"CLIENT_DISCONNECTED","message":"The downstream client disconnected."})
        except Exception as exc:
            GATEWAY.finish(request_id, state="failed", error={"code":"GATEWAY_INTERNAL_ERROR","message":str(exc)})
            self._gateway_error(GatewayError("GATEWAY_INTERNAL_ERROR", "Gateway forwarding failed.", details=str(exc)))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Allow", "GET,POST,PUT,DELETE,OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        parts = self._parts()
        if parts[:2] == ["api", "v1"]:
            self._api_get(parts[2:])
        elif path in {"/v1/models", "/api/tags"}:
            self._gateway_get(path)
        else:
            self._serve_static()

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path in OPENAI_ROUTES or path in OLLAMA_ROUTES:
            self._gateway_post(path); return
        parts = self._parts()
        if parts[:2] != ["api", "v1"]:
            self._fail("ROUTE_NOT_FOUND", "Unknown route.", 404)
            return
        try:
            body = self._json_body()
        except (ValueError, json.JSONDecodeError) as exc:
            self._fail("INVALID_JSON", str(exc), 400)
            return
        self._api_post(parts[2:], body)

    def do_PUT(self) -> None:
        parts = self._parts()
        if parts[:3] == ["api", "v1", "profiles"] and len(parts) == 4:
            try: body = self._json_body()
            except (ValueError, json.JSONDecodeError) as exc: self._fail("INVALID_JSON", str(exc), 400); return
            profile_id = parts[3]; body["id"] = profile_id
            issues = validate_profile(body)
            if issues: self._fail("VALIDATION_FAILED", "Profile validation failed.", 422, issues); return
            def update_profile(state):
                for index, item in enumerate(state["profiles"]):
                    if item["id"] == profile_id:
                        updated = dict(body); updated.setdefault("schemaVersion", item.get("schemaVersion", 1)); updated.setdefault("validationState", item.get("validationState", "unknown")); state["profiles"][index] = updated
                        add_log(state, "info", "profiles", "Profile updated.", profileId=profile_id); return updated
                return None
            result = STORE.mutate(update_profile)
            if result is None: self._fail("PROFILE_NOT_FOUND", "Profile was not found.", 404)
            else: self._ok(result)
            return
        if parts[:3] == ["api", "v1", "actions"] and len(parts) == 4:
            try: body = self._json_body()
            except (ValueError, json.JSONDecodeError) as exc: self._fail("INVALID_JSON", str(exc), 400); return
            action_id = parts[3]; body["id"] = action_id
            issues = validate_action(body)
            if issues: self._fail("VALIDATION_FAILED", "Action validation failed.", 422, issues); return
            def update_action(state):
                for index, item in enumerate(state.get("actions", [])):
                    if item["id"] == action_id:
                        updated = dict(body); updated.setdefault("createdAt", item.get("createdAt", now_ms())); updated["updatedAt"] = now_ms(); state["actions"][index] = updated
                        add_log(state, "info", "actions", "Custom action updated.", actionId=action_id); return updated
                return None
            result = STORE.mutate(update_action)
            if result is None: self._fail("ACTION_NOT_FOUND", "Only user-created actions can be updated.", 404)
            else: self._ok(result)
            return
        if parts[:3] == ["api", "v1", "endpoints"] and len(parts) == 4:
            try: body = self._json_body()
            except (ValueError, json.JSONDecodeError) as exc: self._fail("INVALID_JSON", str(exc), 400); return
            endpoint_id = parts[3]; body["id"] = endpoint_id
            issues = validate_endpoint(body)
            if issues: self._fail("VALIDATION_FAILED", "Endpoint validation failed.", 422, issues); return
            def update_endpoint(state):
                for index, item in enumerate(state.get("customEndpoints", [])):
                    if item["id"] == endpoint_id:
                        updated = dict(body); updated.setdefault("createdAt", item.get("createdAt", now_ms())); updated["updatedAt"] = now_ms(); state["customEndpoints"][index] = updated
                        add_log(state, "info", "endpoints", "Custom endpoint updated.", endpointId=endpoint_id); return updated
                return None
            result = STORE.mutate(update_endpoint)
            if result is None: self._fail("ENDPOINT_NOT_FOUND", "Only user-created endpoints can be updated.", 404)
            else: self._ok(result)
            return
        if parts[:3] == ["api", "v1", "extensions"] and len(parts) == 4:
            try: body = self._json_body()
            except (ValueError, json.JSONDecodeError) as exc: self._fail("INVALID_JSON", str(exc), 400); return
            extension_id = parts[3]
            def update_extension(state):
                for item in state.get("extensions", []):
                    if item["id"] == extension_id:
                        if "enabled" in body: item["enabled"] = bool(body["enabled"])
                        item["updatedAt"] = now_ms(); add_log(state, "info", "extensions", "Extension state updated.", extensionId=extension_id, enabled=item.get("enabled", True)); return item
                return None
            result = STORE.mutate(update_extension)
            if result is None: self._fail("EXTENSION_NOT_FOUND", "Extension was not found.", 404)
            else: self._ok(result)
            return
        if parts[:3] == ["api", "v1", "workspaces"] and len(parts) == 4:
            try:
                body = self._json_body()
            except (ValueError, json.JSONDecodeError) as exc:
                self._fail("INVALID_JSON", str(exc), 400)
                return
            workspace_id = parts[3]
            body["id"] = workspace_id
            issues = validate_workspace(body)
            if issues:
                self._fail("VALIDATION_FAILED", "Workspace validation failed.", 422, issues)
                return
            def update_workspace(state):
                for index, workspace in enumerate(state.get("workspaces", [])):
                    if workspace["id"] == workspace_id:
                        updated = dict(body)
                        updated.setdefault("createdAt", workspace.get("createdAt", now_ms()))
                        updated["updatedAt"] = now_ms()
                        state["workspaces"][index] = updated
                        add_log(state, "info", "workspace", "Workspace saved.", workspaceId=workspace_id, widgetCount=len(updated.get("widgets", [])))
                        return updated
                return None
            result = STORE.mutate(update_workspace)
            if result is None:
                self._fail("WORKSPACE_NOT_FOUND", "Workspace was not found.", 404)
            else:
                self._ok(result)
            return
        if parts[:3] != ["api", "v1", "machines"] or len(parts) != 4:
            self._fail("ROUTE_NOT_FOUND", "Unknown route.", 404)
            return
        try:
            body = self._json_body()
        except (ValueError, json.JSONDecodeError) as exc:
            self._fail("INVALID_JSON", str(exc), 400)
            return
        machine_id = parts[3]
        body["id"] = machine_id
        issues = validate_machine(body)
        if issues:
            self._fail("VALIDATION_FAILED", "Machine validation failed.", 422, issues)
            return
        def update(state):
            for index, machine in enumerate(state["machines"]):
                if machine["id"] == machine_id:
                    body.setdefault("status", machine.get("status", "unknown"))
                    state["machines"][index] = body
                    add_log(state, "info", "machines", "Machine updated.", machineId=machine_id)
                    return body
            return None
        result = STORE.mutate(update)
        if result is None:
            self._fail("MACHINE_NOT_FOUND", "Machine was not found.", 404)
        else:
            self._ok(result)

    def do_DELETE(self) -> None:
        parts = self._parts()
        if parts[:3] == ["api", "v1", "profiles"] and len(parts) == 4:
            profile_id = parts[3]
            def remove_profile(state):
                before = len(state["profiles"]); state["profiles"] = [item for item in state["profiles"] if item["id"] != profile_id]
                if len(state["profiles"]) != before: add_log(state, "warning", "profiles", "Profile deleted.", profileId=profile_id); return True
                return False
            if STORE.mutate(remove_profile): self._ok({"deleted": profile_id})
            else: self._fail("PROFILE_NOT_FOUND", "Profile was not found.", 404)
            return
        if parts[:3] == ["api", "v1", "actions"] and len(parts) == 4:
            action_id = parts[3]
            def remove_action(state):
                before = len(state.get("actions", [])); state["actions"] = [item for item in state.get("actions", []) if item["id"] != action_id]
                if len(state["actions"]) != before: add_log(state, "warning", "actions", "Custom action deleted.", actionId=action_id); return True
                return False
            if STORE.mutate(remove_action): self._ok({"deleted": action_id})
            else: self._fail("ACTION_NOT_FOUND", "Only user-created actions can be deleted.", 404)
            return
        if parts[:3] == ["api", "v1", "endpoints"] and len(parts) == 4:
            endpoint_id = parts[3]
            def remove_endpoint(state):
                before = len(state.get("customEndpoints", [])); state["customEndpoints"] = [item for item in state.get("customEndpoints", []) if item["id"] != endpoint_id]
                if len(state["customEndpoints"]) != before: add_log(state, "warning", "endpoints", "Custom endpoint deleted.", endpointId=endpoint_id); return True
                return False
            if STORE.mutate(remove_endpoint): self._ok({"deleted": endpoint_id})
            else: self._fail("ENDPOINT_NOT_FOUND", "Only user-created endpoints can be deleted.", 404)
            return
        if parts[:3] == ["api", "v1", "extensions"] and len(parts) == 4:
            extension_id = parts[3]
            def remove_extension(state):
                before = len(state.get("extensions", [])); state["extensions"] = [item for item in state.get("extensions", []) if item["id"] != extension_id]
                if len(state["extensions"]) != before: add_log(state, "warning", "extensions", "Extension uninstalled.", extensionId=extension_id); return True
                return False
            if STORE.mutate(remove_extension): self._ok({"deleted": extension_id})
            else: self._fail("EXTENSION_NOT_FOUND", "Extension was not found.", 404)
            return
        if parts[:3] == ["api", "v1", "workspaces"] and len(parts) == 4:
            workspace_id = parts[3]
            def remove_workspace(state):
                items = state.get("workspaces", [])
                if len(items) <= 1:
                    return "last"
                before = len(items)
                state["workspaces"] = [w for w in items if w["id"] != workspace_id]
                if len(state["workspaces"]) == before:
                    return False
                if state.get("activeWorkspaceId") == workspace_id:
                    state["activeWorkspaceId"] = state["workspaces"][0]["id"]
                add_log(state, "warning", "workspace", "Workspace deleted.", workspaceId=workspace_id)
                return True
            result = STORE.mutate(remove_workspace)
            if result == "last":
                self._fail("LAST_WORKSPACE", "The final workspace cannot be deleted.", 409)
            elif result:
                self._ok({"deleted": workspace_id})
            else:
                self._fail("WORKSPACE_NOT_FOUND", "Workspace was not found.", 404)
        elif parts[:3] == ["api", "v1", "machines"] and len(parts) == 4:
            machine_id = parts[3]
            def remove(state):
                before = len(state["machines"])
                state["machines"] = [m for m in state["machines"] if m["id"] != machine_id]
                if len(state["machines"]) != before:
                    add_log(state, "warning", "machines", "Machine removed.", machineId=machine_id)
                    return True
                return False
            if STORE.mutate(remove):
                self._ok({"deleted": machine_id})
            else:
                self._fail("MACHINE_NOT_FOUND", "Machine was not found.", 404)
        else:
            self._fail("ROUTE_NOT_FOUND", "Unknown route.", 404)

    def _api_get(self, parts: list[str]) -> None:
        state = STORE.snapshot()
        if parts == ["capabilities"]:
            self._ok(CAPABILITIES)
        elif parts == ["system", "status"]:
            self._ok({
                "state": "extensibility-integrated",
                "phase": 6,
                "simulation": False,
                "runtime": {**state["runtime"], "process": PROCESS.status()},
                "counts": {k: len(state[k]) for k in ("workspaces", "machines", "models", "profiles", "jobs")},
                "contractVersion": CAPABILITIES["contractVersion"],
            })
        elif parts == ["workspaces"]:
            self._ok({"activeWorkspaceId": state.get("activeWorkspaceId"), "items": state.get("workspaces", [])})
        elif len(parts) == 2 and parts[0] == "workspaces":
            workspace = next((w for w in state.get("workspaces", []) if w["id"] == parts[1]), None)
            if workspace:
                self._ok(workspace)
            else:
                self._fail("WORKSPACE_NOT_FOUND", "Workspace was not found.", 404)
        elif parts == ["widgets", "registry"]:
            self._ok(combined_widgets(WIDGET_REGISTRY, state.get("extensions", [])))
        elif parts == ["actions"]:
            self._ok(combined_actions(state.get("actions", []), state.get("extensions", [])))
        elif len(parts) == 2 and parts[0] == "actions":
            action = next((item for item in combined_actions(state.get("actions", []), state.get("extensions", [])) if item["id"] == parts[1]), None)
            if action: self._ok(action)
            else: self._fail("ACTION_NOT_FOUND", "Action was not found.", 404)
        elif parts == ["extensions"]:
            self._ok(state.get("extensions", []))
        elif len(parts) == 2 and parts[0] == "extensions":
            extension = next((item for item in state.get("extensions", []) if item["id"] == parts[1]), None)
            if extension: self._ok(extension)
            else: self._fail("EXTENSION_NOT_FOUND", "Extension was not found.", 404)
        elif parts == ["endpoints"]:
            self._ok(combined_endpoints(state.get("customEndpoints", []), state.get("extensions", [])))
        elif parts == ["machines"]:
            self._ok(state["machines"])
        elif parts == ["models"]:
            self._ok(state["models"])
        elif parts == ["profiles"]:
            self._ok(state["profiles"])
        elif parts == ["jobs"]:
            self._ok(state["jobs"])
        elif len(parts) == 2 and parts[0] == "jobs":
            job = next((j for j in state["jobs"] if j["id"] == parts[1]), None)
            if job:
                self._ok(job)
            else:
                self._fail("JOB_NOT_FOUND", "Job was not found.", 404)
        elif parts == ["requests"]:
            self._ok(GATEWAY.snapshot())
        elif parts == ["gateway", "status"]:
            listener = control_plane_listener()
            self._ok({
                "state": "draining" if GATEWAY.snapshot()["draining"] else "accepting",
                "requests": GATEWAY.snapshot(),
                "runtime": state["runtime"],
                "controlPlane": listener,
                "routes": {
                    "openai": f"{listener['url']}/v1",
                    "ollama": listener["url"],
                },
            })
        elif parts == ["logs"]:
            self._ok(state["logs"][:200])
        elif parts == ["telemetry"]:
            local = local_telemetry()
            machines = []
            for machine in state["machines"]:
                item = {"machineId": machine["id"], "name": machine["name"], "state": "unknown", "telemetry": None}
                if machine.get("enabled") and "host" not in machine.get("tags", []):
                    try:
                        remote = controller_status(machine, timeout=TELEMETRY_CONTROLLER_TIMEOUT_SECONDS)
                        item.update({"state": "online", "telemetry": remote.get("telemetry", remote)})
                    except RuntimeFailure as exc:
                        item.update({"state": "offline", "error": {"code": exc.code, "message": str(exc)}})
                machines.append(item)
            self._ok({"state":"live","timestamp":now_ms(),"runtimeProcess":PROCESS.status(),"local":local,"machines":machines})
        elif parts == ["hardware"]:
            self._ok(local_telemetry())
        elif len(parts) == 3 and parts[0] == "models" and parts[2] == "allocation":
            model = next((m for m in state["models"] if m["id"] == parts[1]), None)
            if not model:
                self._fail("MODEL_NOT_FOUND", "Model was not found.", 404)
            else:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                values = {k: v[-1] for k, v in query.items()}
                for key in ("gpuLayers", "contextSize", "batchSize"):
                    if key in values:
                        try: values[key] = int(values[key])
                        except ValueError: pass
                self._ok(estimate_allocation(model, values, local_telemetry()))
        elif parts == ["openapi.json"]:
            try:
                data = json.loads((CONTRACT_ROOT / "openapi.json").read_text(encoding="utf-8"))
                self._ok(data)
            except OSError:
                self._fail("CONTRACT_MISSING", "OpenAPI contract is missing.", 500)
        else:
            self._fail("ROUTE_NOT_FOUND", "Unknown API route.", 404)

    def _api_post(self, parts: list[str], body: Any) -> None:
        if parts == ["workspaces"]:
            issues = validate_workspace(body)
            if issues:
                self._fail("VALIDATION_FAILED", "Workspace validation failed.", 422, issues)
                return
            def add_workspace(state):
                if any(w["id"] == body["id"] for w in state.get("workspaces", [])):
                    return None
                workspace = dict(body)
                workspace.setdefault("layoutVersion", 1)
                workspace.setdefault("mode", "operate")
                workspace.setdefault("navigation", {"hidden": [], "order": []})
                workspace.setdefault("theme", {"name": "blueprint-dark"})
                workspace["createdAt"] = now_ms()
                workspace["updatedAt"] = workspace["createdAt"]
                state.setdefault("workspaces", []).append(workspace)
                state["activeWorkspaceId"] = workspace["id"]
                add_log(state, "info", "workspace", "Workspace created.", workspaceId=workspace["id"])
                return workspace
            result = STORE.mutate(add_workspace)
            if result is None:
                self._fail("WORKSPACE_EXISTS", "A workspace with this ID already exists.", 409)
            else:
                self._ok(result, 201)
            return
        if len(parts) == 3 and parts[0] == "workspaces" and parts[2] == "activate":
            workspace_id = parts[1]
            def activate(state):
                if not any(w["id"] == workspace_id for w in state.get("workspaces", [])):
                    return None
                state["activeWorkspaceId"] = workspace_id
                add_log(state, "info", "workspace", "Workspace activated.", workspaceId=workspace_id)
                return {"activeWorkspaceId": workspace_id}
            result = STORE.mutate(activate)
            if result is None:
                self._fail("WORKSPACE_NOT_FOUND", "Workspace was not found.", 404)
            else:
                self._ok(result)
            return
        if parts == ["actions"]:
            issues = validate_action(body)
            if issues:
                self._fail("VALIDATION_FAILED", "Action validation failed.", 422, issues); return
            def add_action(state):
                if any(item["id"] == body["id"] for item in combined_actions(state.get("actions", []), state.get("extensions", []))):
                    return None
                action = dict(body)
                action.setdefault("description", "")
                action.setdefault("confirmation", "always")
                action.setdefault("enabled", True)
                action["createdAt"] = now_ms(); action["updatedAt"] = action["createdAt"]
                state.setdefault("actions", []).append(action)
                add_log(state, "info", "actions", "Custom action created.", actionId=action["id"], actionType=action["type"])
                return action
            result = STORE.mutate(add_action)
            if result is None: self._fail("ACTION_EXISTS", "An action with this ID already exists.", 409)
            else: self._ok(result, 201)
            return
        if len(parts) == 3 and parts[0] == "actions" and parts[2] == "execute":
            state = STORE.snapshot()
            action = next((item for item in combined_actions(state.get("actions", []), state.get("extensions", [])) if item["id"] == parts[1] and item.get("enabled", True)), None)
            if not action:
                self._fail("ACTION_NOT_FOUND", "Action was not found or is disabled.", 404); return
            job = create_job("action.execute", {"actionId": action["id"]}, ["validate-permissions", "execute", "verify"])
            STORE.mutate(lambda st: st["jobs"].insert(0, job) or add_log(st, "info", "actions", "Action execution requested.", actionId=action["id"], jobId=job["id"]) or job)
            run_job(job, action_task(action, body.get("inputs", {}) if isinstance(body, dict) else {}))
            self._ok(job, 202); return
        if parts == ["endpoints"]:
            issues = validate_endpoint(body)
            if issues:
                self._fail("VALIDATION_FAILED", "Endpoint validation failed.", 422, issues); return
            def add_endpoint(state):
                if any(item["id"] == body["id"] for item in combined_endpoints(state.get("customEndpoints", []), state.get("extensions", []))):
                    return None
                endpoint = dict(body); endpoint.setdefault("enabled", True); endpoint["createdAt"] = now_ms(); endpoint["updatedAt"] = endpoint["createdAt"]
                state.setdefault("customEndpoints", []).append(endpoint)
                add_log(state, "info", "endpoints", "Custom endpoint registered.", endpointId=endpoint["id"])
                return endpoint
            result = STORE.mutate(add_endpoint)
            if result is None: self._fail("ENDPOINT_EXISTS", "An endpoint with this ID already exists.", 409)
            else: self._ok(result, 201)
            return
        if len(parts) == 3 and parts[0] == "endpoints" and parts[2] == "test":
            state = STORE.snapshot()
            endpoint = next((item for item in combined_endpoints(state.get("customEndpoints", []), state.get("extensions", [])) if item["id"] == parts[1] and item.get("enabled", True)), None)
            if not endpoint:
                self._fail("ENDPOINT_NOT_FOUND", "Endpoint was not found or is disabled.", 404); return
            result = test_endpoint(endpoint)
            STORE.mutate(lambda st: add_log(st, "info" if result["reachable"] else "warning", "endpoints", "Endpoint test completed.", endpointId=endpoint["id"], result=result))
            self._ok(result); return
        if parts == ["extensions"]:
            issues = validate_extension(body, CAPABILITIES["contractVersion"])
            if issues:
                self._fail("EXTENSION_VALIDATION_FAILED", "Extension manifest validation failed.", 422, issues); return
            manifest = normalized_extension(body)
            def install_extension(state):
                if any(item["id"] == manifest["id"] for item in state.get("extensions", [])):
                    return None
                existing_widget_types = {item["type"] for item in combined_widgets(WIDGET_REGISTRY, state.get("extensions", []))}
                existing_action_ids = {item["id"] for item in combined_actions(state.get("actions", []), state.get("extensions", []))}
                existing_endpoint_ids = {item["id"] for item in combined_endpoints(state.get("customEndpoints", []), state.get("extensions", []))}
                conflicts = {
                    "widgets": sorted(existing_widget_types & {item["type"] for item in manifest.get("widgets", [])}),
                    "actions": sorted(existing_action_ids & {item["id"] for item in manifest.get("actions", [])}),
                    "endpoints": sorted(existing_endpoint_ids & {item["id"] for item in manifest.get("endpoints", [])}),
                }
                if any(conflicts.values()): return {"conflicts": conflicts}
                state.setdefault("extensions", []).append(manifest)
                add_log(state, "info", "extensions", "Extension installed.", extensionId=manifest["id"], permissions=manifest.get("permissions", []))
                return manifest
            result = STORE.mutate(install_extension)
            if result is None: self._fail("EXTENSION_EXISTS", "An extension with this ID already exists.", 409)
            elif "conflicts" in result: self._fail("EXTENSION_CONFLICT", "Extension assets conflict with installed assets.", 409, result["conflicts"])
            else: self._ok(result, 201)
            return
        if parts == ["machines"]:
            issues = validate_machine(body)
            if issues:
                self._fail("VALIDATION_FAILED", "Machine validation failed.", 422, issues)
                return
            def add(state):
                if any(m["id"] == body["id"] for m in state["machines"]):
                    return None
                machine = dict(body)
                machine.setdefault("enabled", True)
                machine.setdefault("tags", [])
                machine.setdefault("paths", {})
                machine["status"] = "unknown"
                state["machines"].append(machine)
                add_log(state, "info", "machines", "Machine registered.", machineId=machine["id"])
                return machine
            result = STORE.mutate(add)
            if result is None:
                self._fail("MACHINE_EXISTS", "A machine with this ID already exists.", 409)
            else:
                self._ok(result, 201)
            return
        if len(parts) == 3 and parts[0] == "machines" and parts[2] == "test":
            machine_id = parts[1]
            state = STORE.snapshot()
            machine = next((m for m in state["machines"] if m["id"] == machine_id), None)
            if not machine:
                self._fail("MACHINE_NOT_FOUND", "Machine was not found.", 404)
                return
            address = machine["addresses"][0]
            port = machine["controller"]["port"]
            started = time.monotonic()
            reachable = False
            diagnostic = None
            try:
                with socket.create_connection((address, port), timeout=1.0):
                    reachable = True
            except OSError as exc:
                diagnostic = str(exc)
            latency = round((time.monotonic() - started) * 1000, 2)
            controllerInfo = None
            if reachable:
                try: controllerInfo = controller_status(machine)
                except RuntimeFailure as exc: diagnostic = f"TCP reachable; status contract failed: {exc}"
            result = {"machineId": machine_id, "reachable": reachable, "latencyMs": latency, "diagnostic": diagnostic, "controller": controllerInfo, "testedAt": now_ms()}
            def record(state):
                for item in state["machines"]:
                    if item["id"] == machine_id:
                        item["status"] = "reachable" if reachable else "offline"
                        item["lastTest"] = result
                add_log(state, "info" if reachable else "warning", "machines", "Connection test completed.", **result)
                return result
            self._ok(STORE.mutate(record))
            return
        if len(parts) == 4 and parts[0] == "machines" and parts[2] == "rpc" and parts[3] in {"start", "stop"}:
            machine_id, action = parts[1], parts[3]
            state = STORE.snapshot()
            if not any(m["id"] == machine_id for m in state["machines"]):
                self._fail("MACHINE_NOT_FOUND", "Machine was not found.", 404)
                return
            job = create_job(f"rpc.{action}", {"machineId": machine_id}, ["validate", "dispatch", "verify"])
            STORE.mutate(lambda st: st["jobs"].insert(0,job) or add_log(st,"info","rpc",f"RPC {action} requested.",machineId=machine_id,jobId=job["id"]) or job)
            run_job(job,rpc_task(next(m for m in state["machines"] if m["id"]==machine_id),action))
            self._ok(job, 202)
            return
        if parts == ["models", "scan"]:
            job = create_job("models.scan", body, ["validate-sources", "enumerate", "register"])
            STORE.mutate(lambda state: state["jobs"].insert(0, job) or job)
            run_job(job, scan_task(body if isinstance(body,dict) else {}))
            self._ok(job, 202)
            return
        if parts == ["profiles"]:
            issues = validate_profile(body)
            if issues: self._fail("VALIDATION_FAILED", "Profile validation failed.", 422, issues); return
            def add(state):
                if any(p["id"] == body["id"] for p in state["profiles"]):
                    return None
                profile = dict(body)
                profile.setdefault("schemaVersion", 1)
                profile.setdefault("validationState", "unknown")
                state["profiles"].append(profile)
                return profile
            result = STORE.mutate(add)
            if result is None:
                self._fail("PROFILE_EXISTS", "A profile with this ID already exists.", 409)
            else:
                self._ok(result, 201)
            return
        if parts == ["runtime", "preflight"]:
            if not isinstance(body, dict) or not body.get("modelId"):
                self._fail("VALIDATION_FAILED", "modelId is required.", 422); return
            state = STORE.snapshot()
            model = next((m for m in state["models"] if m["id"] == body.get("modelId")), None)
            if not model:
                self._fail("MODEL_NOT_FOUND", "Selected model is not registered.", 404); return
            profile = next((p for p in state["profiles"] if p["id"] == body.get("profileId")), None) if body.get("profileId") else None
            values = dict((profile or {}).get("values", {})); values.update(body.get("overrides", {}))
            estimate = estimate_allocation(model, values, local_telemetry(), safety_margin=float(body.get("safetyMargin", 0.10)))
            self._ok({"modelId": model["id"], "profileId": body.get("profileId"), "allocation": estimate, "launchAllowed": estimate["risk"] not in {"high"}, "overrideRequired": estimate["risk"] == "high"})
            return
        if parts == ["runtime", "launch"]:
            if not isinstance(body, dict) or not body.get("modelId"):
                self._fail("VALIDATION_FAILED", "modelId is required.", 422); return
            state = STORE.snapshot()
            model = next((m for m in state["models"] if m["id"] == body.get("modelId")), None)
            profile = next((p for p in state["profiles"] if p["id"] == body.get("profileId")), None) if body.get("profileId") else None
            values = dict((profile or {}).get("values", {})); values.update(body.get("overrides", {}))
            allocation = estimate_allocation(model, values, local_telemetry(), safety_margin=float(body.get("safetyMargin", 0.10))) if model else None
            if allocation and allocation["risk"] == "high" and not body.get("allowUnsafe"):
                self._fail("UNSAFE_ALLOCATION_BLOCKED", "Predicted VRAM allocation exceeds safe capacity. Run preflight or set allowUnsafe with explicit acknowledgement.", 409, allocation); return
            job = create_job("runtime.launch", body, ["validate","test-machines","start-host","verify-api"])
            job["preflight"] = allocation
            STORE.mutate(lambda st: st["jobs"].insert(0,job) or st["runtime"].update({"state":"starting"}) or add_log(st,"info","runtime","Runtime launch requested.",jobId=job["id"]) or job)
            run_job(job,launch_task(body)); self._ok(job,202); return
        if parts == ["runtime", "stop"]:
            job = create_job("runtime.stop", body if isinstance(body,dict) else {}, ["drain-requests","stop-host","stop-workers","verify-stopped"])
            STORE.mutate(lambda st: st["jobs"].insert(0,job) or add_log(st,"warning","runtime","Stop All requested.",jobId=job["id"]) or job)
            run_job(job,stop_task(body if isinstance(body,dict) else {})); self._ok(job,202); return
        if len(parts) == 3 and parts[0] == "requests" and parts[2] == "cancel":
            result = GATEWAY.cancel(parts[1])
            if not result["found"]: self._fail("REQUEST_NOT_FOUND", "Request was not found.", 404)
            elif result.get("cancelUnsupported"): self._fail("ACTIVE_CANCELLATION_UNSUPPORTED", result["reason"], 409, result)
            else: self._ok(result)
            return
        self._fail("ROUTE_NOT_FOUND", "Unknown API route.", 404)

    def _serve_static(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        rel = parsed.path.lstrip("/") or "index.html"
        target = (WEB_ROOT / rel).resolve()
        if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.exists() or not target.is_file():
            if "." not in Path(rel).name:
                target = WEB_ROOT / "index.html"
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Letterblack Local Inference Workspace Phase 6 extensibility server")
    parser.add_argument("--host", default=CONTROL_PLANE_HOST)
    parser.add_argument("--port", type=int, default=CONTROL_PLANE_PORT)
    args = parser.parse_args()
    if args.host != CONTROL_PLANE_HOST or args.port != CONTROL_PLANE_PORT:
        parser.error("Remote control is unsupported; the control plane is fixed to http://127.0.0.1:8088.")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    configure_control_server_shutdown(server.shutdown)
    print(f"Letterblack Phase 6 serving http://{args.host}:{args.port}")
    print("Phase 6 declarative extensions, custom actions, widgets, and endpoints enabled.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
