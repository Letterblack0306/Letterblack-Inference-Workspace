from __future__ import annotations

import re
import time
import uuid
from typing import Any

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def envelope(data: Any, *, request_id: str | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "requestId": request_id or new_id("req"),
        "timestamp": now_ms(),
        "data": data,
    }


def error(code: str, message: str, *, status: int = 400, details: Any = None, request_id: str | None = None):
    payload = {
        "ok": False,
        "requestId": request_id or new_id("req"),
        "timestamp": now_ms(),
        "error": {"code": code, "message": message, "details": details},
    }
    return status, payload


def validate_machine(value: Any) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(value, dict):
        return [{"field": "$", "message": "Machine must be an object."}]
    machine_id = value.get("id")
    if not isinstance(machine_id, str) or not ID_PATTERN.match(machine_id):
        issues.append({"field": "id", "message": "Use 2-64 lowercase letters, numbers, dot, underscore or hyphen."})
    if not isinstance(value.get("name"), str) or not value["name"].strip():
        issues.append({"field": "name", "message": "Name is required."})
    addresses = value.get("addresses")
    if not isinstance(addresses, list) or not addresses or not all(isinstance(v, str) and v.strip() for v in addresses):
        issues.append({"field": "addresses", "message": "At least one hostname or IP is required."})
    for field in ("controller", "rpc"):
        section = value.get(field)
        if not isinstance(section, dict):
            issues.append({"field": field, "message": f"{field} configuration is required."})
            continue
        port = section.get("port")
        if not isinstance(port, int) or not 1 <= port <= 65535:
            issues.append({"field": f"{field}.port", "message": "Port must be an integer from 1 to 65535."})
    return issues


def create_job(job_type: str, target: Any, phases: list[str]) -> dict[str, Any]:
    return {
        "id": new_id("job"),
        "type": job_type,
        "target": target,
        "state": "queued",
        "phase": phases[0] if phases else "queued",
        "progress": 0,
        "phases": phases,
        "evidence": [],
        "error": None,
        "createdAt": now_ms(),
        "updatedAt": now_ms(),
        "simulation": False,
    }


def validate_workspace(value: Any) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(value, dict):
        return [{"field": "$", "message": "Workspace must be an object."}]
    workspace_id = value.get("id")
    if not isinstance(workspace_id, str) or not ID_PATTERN.match(workspace_id):
        issues.append({"field": "id", "message": "Use 2-64 lowercase letters, numbers, dot, underscore or hyphen."})
    if not isinstance(value.get("name"), str) or not value["name"].strip():
        issues.append({"field": "name", "message": "Name is required."})
    grid = value.get("grid")
    if not isinstance(grid, dict):
        issues.append({"field": "grid", "message": "Grid configuration is required."})
    else:
        columns = grid.get("columns")
        if not isinstance(columns, int) or columns < 4 or columns > 24:
            issues.append({"field": "grid.columns", "message": "Columns must be an integer from 4 to 24."})
    widgets = value.get("widgets")
    if not isinstance(widgets, list):
        issues.append({"field": "widgets", "message": "Widgets must be an array."})
    else:
        ids: set[str] = set()
        for index, widget in enumerate(widgets):
            if not isinstance(widget, dict):
                issues.append({"field": f"widgets.{index}", "message": "Widget must be an object."})
                continue
            wid = widget.get("id")
            wtype = widget.get("type")
            if not isinstance(wid, str) or not ID_PATTERN.match(wid):
                issues.append({"field": f"widgets.{index}.id", "message": "Widget ID is invalid."})
            elif wid in ids:
                issues.append({"field": f"widgets.{index}.id", "message": "Widget IDs must be unique."})
            else:
                ids.add(wid)
            if not isinstance(wtype, str) or not wtype.strip():
                issues.append({"field": f"widgets.{index}.type", "message": "Widget type is required."})
            for key in ("position", "size"):
                if not isinstance(widget.get(key), dict):
                    issues.append({"field": f"widgets.{index}.{key}", "message": f"{key.title()} is required."})
    return issues
