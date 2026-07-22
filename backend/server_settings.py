from __future__ import annotations

import argparse
import os
from copy import deepcopy
from http.server import ThreadingHTTPServer
from pathlib import Path, PureWindowsPath
from typing import Any

from . import server as base


_ALLOWED_TOP_LEVEL = {"paths", "ports", "runtime", "safety"}
_PORT_KEYS = ("dashboard", "openaiGateway", "ollamaGateway", "workerController", "rpc")
_RESTART_FIELDS = {
    "paths.llamaServerPath",
}


def _default_settings(state: dict[str, Any]) -> dict[str, Any]:
    model_sources = [
        item.get("path")
        for item in state.get("modelSources", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    ]
    gateway = state.get("gateway", {})
    safety = state.get("hardwareSafety", {})
    return {
        "paths": {
            "applicationRoot": str(base.ROOT),
            "modelSources": model_sources,
            "llamaServerPath": os.environ.get("LB_LLAMA_SERVER", ""),
        },
        "ports": {
            "dashboard": base.CONTROL_PLANE_PORT,
            "openaiGateway": int(base.CAPABILITIES["defaultPorts"]["openai"]),
            "ollamaGateway": int(base.CAPABILITIES["defaultPorts"]["ollama"]),
            "workerController": int(base.CAPABILITIES["defaultPorts"]["controller"]),
            "rpc": int(base.CAPABILITIES["defaultPorts"]["rpc"]),
        },
        "runtime": {
            "bindAddress": base.CONTROL_PLANE_HOST,
            "pollIntervalMs": 5000,
            "requestDrainTimeoutSec": int(gateway.get("drainTimeoutSec", 30)),
        },
        "safety": {
            "blockUnsafeLaunch": bool(safety.get("blockHighRisk", True)),
            "allowRemoteDashboard": False,
        },
    }


def _current_settings(state: dict[str, Any]) -> dict[str, Any]:
    current = state.get("settings")
    if not isinstance(current, dict):
        return _default_settings(state)
    merged = _default_settings(state)
    for section in _ALLOWED_TOP_LEVEL:
        if isinstance(current.get(section), dict):
            merged[section].update(deepcopy(current[section]))
    merged["paths"]["applicationRoot"] = str(base.ROOT)
    merged["ports"]["dashboard"] = base.CONTROL_PLANE_PORT
    merged["runtime"]["bindAddress"] = base.CONTROL_PLANE_HOST
    merged["safety"]["allowRemoteDashboard"] = False
    return merged


def _is_absolute_path(value: str) -> bool:
    if not value:
        return False
    return Path(value).is_absolute() or PureWindowsPath(value).is_absolute()


def validate_settings(body: Any) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(body, dict):
        return [{"path": "$", "message": "Settings payload must be an object."}]

    unknown = sorted(set(body) - _ALLOWED_TOP_LEVEL)
    if unknown:
        issues.append({"path": "$", "message": "Unsupported top-level settings keys.", "keys": unknown})

    for section in _ALLOWED_TOP_LEVEL:
        if not isinstance(body.get(section), dict):
            issues.append({"path": section, "message": "Section must be an object."})

    if issues:
        return issues

    paths = body["paths"]
    expected_path_keys = {"applicationRoot", "modelSources", "llamaServerPath"}
    extra = sorted(set(paths) - expected_path_keys)
    if extra:
        issues.append({"path": "paths", "message": "Unsupported path settings.", "keys": extra})
    app_root = paths.get("applicationRoot")
    if app_root != str(base.ROOT):
        issues.append({"path": "paths.applicationRoot", "message": "Application root is reported by the running control plane and cannot be changed from settings."})
    model_sources = paths.get("modelSources")
    if not isinstance(model_sources, list):
        issues.append({"path": "paths.modelSources", "message": "Model sources must be an array."})
    elif any(not isinstance(item, str) or not _is_absolute_path(item) for item in model_sources):
        issues.append({"path": "paths.modelSources", "message": "Every model source must be an absolute path."})
    llama_path = paths.get("llamaServerPath")
    if not isinstance(llama_path, str):
        issues.append({"path": "paths.llamaServerPath", "message": "llama-server path must be a string."})
    elif llama_path and not _is_absolute_path(llama_path):
        issues.append({"path": "paths.llamaServerPath", "message": "llama-server path must be absolute when provided."})

    ports = body["ports"]
    extra = sorted(set(ports) - set(_PORT_KEYS))
    if extra:
        issues.append({"path": "ports", "message": "Unsupported port settings.", "keys": extra})
    values: list[int] = []
    for key in _PORT_KEYS:
        value = ports.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
            issues.append({"path": f"ports.{key}", "message": "Port must be an integer from 1 to 65535."})
        else:
            values.append(value)
    if len(values) == len(_PORT_KEYS) and len(set(values)) != len(values):
        issues.append({"path": "ports", "message": "Port assignments must be unique."})
    if ports.get("dashboard") != base.CONTROL_PLANE_PORT:
        issues.append({"path": "ports.dashboard", "message": "The control-plane listener is fixed to 127.0.0.1:8088."})

    runtime = body["runtime"]
    expected_runtime = {"bindAddress", "pollIntervalMs", "requestDrainTimeoutSec"}
    extra = sorted(set(runtime) - expected_runtime)
    if extra:
        issues.append({"path": "runtime", "message": "Unsupported runtime settings.", "keys": extra})
    bind = runtime.get("bindAddress")
    if bind != base.CONTROL_PLANE_HOST:
        issues.append({"path": "runtime.bindAddress", "message": "Remote control is unsupported; the control plane is fixed to 127.0.0.1."})
    poll = runtime.get("pollIntervalMs")
    if isinstance(poll, bool) or not isinstance(poll, int) or not 1000 <= poll <= 60000:
        issues.append({"path": "runtime.pollIntervalMs", "message": "Polling interval must be 1000 to 60000 ms."})
    drain = runtime.get("requestDrainTimeoutSec")
    if isinstance(drain, bool) or not isinstance(drain, int) or not 1 <= drain <= 600:
        issues.append({"path": "runtime.requestDrainTimeoutSec", "message": "Drain timeout must be 1 to 600 seconds."})

    safety = body["safety"]
    expected_safety = {"blockUnsafeLaunch", "allowRemoteDashboard"}
    extra = sorted(set(safety) - expected_safety)
    if extra:
        issues.append({"path": "safety", "message": "Unsupported safety settings.", "keys": extra})
    for key in expected_safety:
        if not isinstance(safety.get(key), bool):
            issues.append({"path": f"safety.{key}", "message": "Value must be boolean."})
    if safety.get("allowRemoteDashboard") is not False:
        issues.append({"path": "safety.allowRemoteDashboard", "message": "Remote control is unsupported until authentication is implemented."})

    return issues


def changed_restart_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    changed = []
    for dotted in sorted(_RESTART_FIELDS):
        section, key = dotted.split(".", 1)
        if before.get(section, {}).get(key) != after.get(section, {}).get(key):
            changed.append(dotted)
    return changed


class SettingsHandler(base.Handler):
    def do_GET(self) -> None:
        if self._parts() == ["api", "v1", "settings"]:
            state = base.STORE.snapshot()
            self._ok({"settings": _current_settings(state), "restartRequired": []})
            return
        super().do_GET()

    def do_PUT(self) -> None:
        if self._parts() != ["api", "v1", "settings"]:
            super().do_PUT()
            return
        try:
            body = self._json_body()
        except (ValueError, base.json.JSONDecodeError) as exc:
            self._fail("INVALID_JSON", str(exc), 400)
            return

        issues = validate_settings(body)
        if issues:
            self._fail("VALIDATION_FAILED", "Settings validation failed.", 422, issues)
            return

        before = _current_settings(base.STORE.snapshot())
        restart_required = changed_restart_fields(before, body)

        def persist(state: dict[str, Any]):
            state["settings"] = deepcopy(body)
            state["modelSources"] = [
                {"id": f"source-settings-{index + 1}", "name": f"Model source {index + 1}", "path": path, "enabled": True}
                for index, path in enumerate(body["paths"]["modelSources"])
            ]
            state.setdefault("gateway", {})["drainTimeoutSec"] = body["runtime"]["requestDrainTimeoutSec"]
            state.setdefault("hardwareSafety", {})["blockHighRisk"] = body["safety"]["blockUnsafeLaunch"]
            base.add_log(
                state,
                "warning" if restart_required else "info",
                "settings",
                "Settings updated.",
                restartRequired=restart_required,
            )
            return deepcopy(body)

        saved = base.STORE.mutate(persist)
        self._ok({"settings": saved, "restartRequired": restart_required})


def main() -> None:
    base.CAPABILITIES["contractVersion"] = "6.1.0"
    base.CAPABILITIES["features"]["settingsContract"] = True
    parser = argparse.ArgumentParser(description="Letterblack Inference Workspace server with settings contract")
    parser.add_argument("--host", default=base.CONTROL_PLANE_HOST)
    parser.add_argument("--port", type=int, default=base.CONTROL_PLANE_PORT)
    args = parser.parse_args()
    if args.host != base.CONTROL_PLANE_HOST or args.port != base.CONTROL_PLANE_PORT:
        parser.error("Remote control is unsupported; the control plane is fixed to http://127.0.0.1:8088.")
    server = ThreadingHTTPServer((args.host, args.port), SettingsHandler)
    base.configure_control_server_shutdown(server.shutdown)
    print(f"Letterblack Phase 6.1 serving http://{args.host}:{args.port}")
    print("Truthful settings contract enabled at GET/PUT /api/v1/settings.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
