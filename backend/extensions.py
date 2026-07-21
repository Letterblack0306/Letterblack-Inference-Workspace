from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from copy import deepcopy
from typing import Any

from .contracts import ID_PATTERN, new_id, now_ms

ALLOWED_PERMISSIONS = {
    "widget.register",
    "action.register",
    "endpoint.register",
    "network.http",
    "machine.status",
    "machine.rpc.start",
    "machine.rpc.stop",
    "models.scan",
    "profile.read",
}

ALLOWED_ACTION_TYPES = {
    "http-request",
    "controller-status",
    "rpc-start",
    "rpc-stop",
    "models-scan",
    "profile-select",
}

ALLOWED_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.split(".") if part != "")
    except ValueError:
        return (0,)


def validate_endpoint(value: Any) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(value, dict):
        return [{"field": "$", "message": "Endpoint must be an object."}]
    if not isinstance(value.get("id"), str) or not ID_PATTERN.match(value["id"]):
        issues.append({"field": "id", "message": "Endpoint ID is invalid."})
    if not isinstance(value.get("name"), str) or not value["name"].strip():
        issues.append({"field": "name", "message": "Name is required."})
    base_url = value.get("baseUrl")
    if not isinstance(base_url, str) or not re.match(r"^https?://[^\s/]+(?::\d+)?(?:/.*)?$", base_url):
        issues.append({"field": "baseUrl", "message": "Use an explicit http:// or https:// URL."})
    health = value.get("healthCheck", {})
    if health and not isinstance(health, dict):
        issues.append({"field": "healthCheck", "message": "Health check must be an object."})
    return issues


def validate_action(value: Any) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(value, dict):
        return [{"field": "$", "message": "Action must be an object."}]
    if not isinstance(value.get("id"), str) or not ID_PATTERN.match(value["id"]):
        issues.append({"field": "id", "message": "Action ID is invalid."})
    if not isinstance(value.get("name"), str) or not value["name"].strip():
        issues.append({"field": "name", "message": "Name is required."})
    if value.get("type") not in ALLOWED_ACTION_TYPES:
        issues.append({"field": "type", "message": f"Supported types: {', '.join(sorted(ALLOWED_ACTION_TYPES))}."})
    permissions = value.get("permissions", [])
    if not isinstance(permissions, list) or not all(isinstance(p, str) for p in permissions):
        issues.append({"field": "permissions", "message": "Permissions must be an array of strings."})
    else:
        unknown = sorted(set(permissions) - ALLOWED_PERMISSIONS)
        if unknown:
            issues.append({"field": "permissions", "message": f"Unknown permissions: {', '.join(unknown)}."})
    config = value.get("config", {})
    if not isinstance(config, dict):
        issues.append({"field": "config", "message": "Config must be an object."})
    action_type = value.get("type")
    if action_type == "http-request":
        if not config.get("endpointId"):
            issues.append({"field": "config.endpointId", "message": "HTTP actions must reference a registered endpoint."})
        method = str(config.get("method", "GET")).upper()
        if method not in ALLOWED_HTTP_METHODS:
            issues.append({"field": "config.method", "message": "HTTP method is not allowed."})
    if action_type in {"controller-status", "rpc-start", "rpc-stop"} and not config.get("machineId"):
        issues.append({"field": "config.machineId", "message": "Machine action must reference a registered machine."})
    return issues


def validate_extension(value: Any, contract_version: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(value, dict):
        return [{"field": "$", "message": "Extension manifest must be an object."}]
    for key in ("id", "name", "version"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            issues.append({"field": key, "message": f"{key} is required."})
    if isinstance(value.get("id"), str) and not ID_PATTERN.match(value["id"]):
        issues.append({"field": "id", "message": "Extension ID is invalid."})
    api_version = value.get("apiVersion", "1")
    if str(api_version) != "1":
        issues.append({"field": "apiVersion", "message": "Only extension API version 1 is supported."})
    minimum = str(value.get("compatibility", {}).get("minContractVersion", "0.0.0"))
    if _version_tuple(minimum) > _version_tuple(contract_version):
        issues.append({"field": "compatibility.minContractVersion", "message": "Extension requires a newer control-plane contract."})
    permissions = value.get("permissions", [])
    if not isinstance(permissions, list):
        issues.append({"field": "permissions", "message": "Permissions must be an array."})
    else:
        unknown = sorted(set(permissions) - ALLOWED_PERMISSIONS)
        if unknown:
            issues.append({"field": "permissions", "message": f"Unknown permissions: {', '.join(unknown)}."})
    for index, widget in enumerate(value.get("widgets", [])):
        if not isinstance(widget, dict) or not widget.get("type") or not widget.get("name"):
            issues.append({"field": f"widgets.{index}", "message": "Widget type and name are required."})
    for index, action in enumerate(value.get("actions", [])):
        action_copy = dict(action) if isinstance(action, dict) else action
        if isinstance(action_copy, dict):
            action_copy.setdefault("permissions", permissions)
        for item in validate_action(action_copy):
            issues.append({"field": f"actions.{index}.{item['field']}", "message": item["message"]})
    for index, endpoint in enumerate(value.get("endpoints", [])):
        for item in validate_endpoint(endpoint):
            issues.append({"field": f"endpoints.{index}.{item['field']}", "message": item["message"]})
    if value.get("code") or value.get("script") or value.get("entrypoint"):
        issues.append({"field": "entrypoint", "message": "Executable extension code is not supported in Phase 6; manifests are declarative only."})
    return issues


def normalized_extension(value: dict[str, Any]) -> dict[str, Any]:
    manifest = deepcopy(value)
    manifest.setdefault("apiVersion", "1")
    manifest.setdefault("description", "")
    manifest.setdefault("permissions", [])
    manifest.setdefault("widgets", [])
    manifest.setdefault("actions", [])
    manifest.setdefault("endpoints", [])
    manifest.setdefault("enabled", True)
    manifest["installedAt"] = now_ms()
    for action in manifest["actions"]:
        action.setdefault("permissions", list(manifest["permissions"]))
        action.setdefault("confirmation", "always")
        action.setdefault("enabled", True)
        action["extensionId"] = manifest["id"]
    for widget in manifest["widgets"]:
        widget["extensionId"] = manifest["id"]
        widget.setdefault("category", "custom")
        widget.setdefault("minSize", {"w": 3, "h": 2})
        widget.setdefault("defaultSize", {"w": 4, "h": 3})
    for endpoint in manifest["endpoints"]:
        endpoint["extensionId"] = manifest["id"]
        endpoint.setdefault("enabled", True)
    return manifest


def combined_widgets(core_widgets: list[dict[str, Any]], extensions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = deepcopy(core_widgets)
    for extension in extensions:
        if extension.get("enabled", True):
            result.extend(deepcopy(extension.get("widgets", [])))
    return result


def combined_actions(actions: list[dict[str, Any]], extensions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = deepcopy(actions)
    for extension in extensions:
        if extension.get("enabled", True):
            result.extend(deepcopy(extension.get("actions", [])))
    return result


def combined_endpoints(endpoints: list[dict[str, Any]], extensions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = deepcopy(endpoints)
    for extension in extensions:
        if extension.get("enabled", True):
            result.extend(deepcopy(extension.get("endpoints", [])))
    return result


def test_endpoint(endpoint: dict[str, Any], timeout: float = 4.0) -> dict[str, Any]:
    health = endpoint.get("healthCheck", {})
    path = health.get("path", "/")
    method = str(health.get("method", "GET")).upper()
    url = endpoint["baseUrl"].rstrip("/") + "/" + str(path).lstrip("/")
    started = time.monotonic()
    request = urllib.request.Request(url=url, method=method, headers={"User-Agent": "Letterblack-Control/6"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            body = response.read(4096)
            return {
                "reachable": True,
                "status": status,
                "latencyMs": round((time.monotonic() - started) * 1000, 2),
                "contentType": response.headers.get("Content-Type"),
                "sample": body.decode("utf-8", errors="replace"),
                "testedAt": now_ms(),
            }
    except urllib.error.HTTPError as exc:
        return {
            "reachable": True,
            "status": exc.code,
            "latencyMs": round((time.monotonic() - started) * 1000, 2),
            "error": str(exc),
            "testedAt": now_ms(),
        }
    except Exception as exc:
        return {
            "reachable": False,
            "status": None,
            "latencyMs": round((time.monotonic() - started) * 1000, 2),
            "error": str(exc),
            "testedAt": now_ms(),
        }


def execute_http_action(action: dict[str, Any], endpoint: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    config = action.get("config", {})
    method = str(config.get("method", "GET")).upper()
    path = str(config.get("path", "/"))
    if ".." in path:
        raise ValueError("Parent path traversal is not allowed.")
    url = endpoint["baseUrl"].rstrip("/") + "/" + path.lstrip("/")
    payload = inputs if inputs else config.get("body")
    raw = None if payload is None or method == "GET" else json.dumps(payload).encode("utf-8")
    headers = {"User-Agent": "Letterblack-Control/6", "Accept": "application/json"}
    if raw is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url=url, method=method, data=raw, headers=headers)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=float(config.get("timeoutSec", 10))) as response:
            body = response.read(1024 * 1024)
            text = body.decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(text)
            except json.JSONDecodeError:
                parsed = text
            return {
                "status": getattr(response, "status", response.getcode()),
                "latencyMs": round((time.monotonic() - started) * 1000, 2),
                "contentType": response.headers.get("Content-Type"),
                "body": parsed,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(1024 * 1024).decode("utf-8", errors="replace")
        return {
            "status": exc.code,
            "latencyMs": round((time.monotonic() - started) * 1000, 2),
            "body": body,
            "httpError": True,
        }
