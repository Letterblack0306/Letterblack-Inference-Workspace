from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_STATE: dict[str, Any] = {
    "schemaVersion": 7,
    "workspaces": [
        {
            "id": "workspace-default",
            "name": "Inference Lab",
            "layoutVersion": 1,
            "mode": "operate",
            "grid": {"columns": 12, "rowHeight": 72, "density": "comfortable"},
            "widgets": [
                {"id": "widget-active-model", "type": "active-model", "position": {"x": 0, "y": 0}, "size": {"w": 8, "h": 3}, "settings": {}, "visibility": True},
                {"id": "widget-topology", "type": "machine-topology", "position": {"x": 8, "y": 0}, "size": {"w": 4, "h": 3}, "settings": {}, "visibility": True},
                {"id": "widget-telemetry", "type": "gpu-telemetry", "position": {"x": 0, "y": 3}, "size": {"w": 7, "h": 3}, "settings": {}, "visibility": True},
                {"id": "widget-requests", "type": "request-table", "position": {"x": 7, "y": 3}, "size": {"w": 5, "h": 3}, "settings": {}, "visibility": True},
            ],
            "navigation": {"hidden": [], "order": ["overview","models","machines","playground","api","telemetry","logs","profiles","extensions","settings"]},
            "theme": {"name": "blueprint-dark"},
            "createdAt": 0,
            "updatedAt": 0,
        }
    ],
    "activeWorkspaceId": "workspace-default",
    "machines": [
        {
            "id": "machine-host",
            "name": "Host",
            "addresses": ["192.168.1.240"],
            "controller": {"scheme": "http", "port": 50053},
            "rpc": {"port": 50052, "enabled": False},
            "paths": {"runtime": "Z:\\LLM_Proxy", "models": "Z:\\LLM_Proxy\\Models"},
            "enabled": True,
            "tags": ["host", "lan"],
            "status": "unknown",
        },
        {
            "id": "machine-worker-01",
            "name": "Worker 01",
            "addresses": ["192.168.1.155"],
            "controller": {"scheme": "http", "port": 50053},
            "rpc": {"port": 50052, "enabled": True},
            "paths": {"runtime": "D:\\Developement\\LLM_Proxy", "models": "D:\\Developement\\LLM_Proxy\\Models"},
            "enabled": True,
            "tags": ["worker", "lan"],
            "status": "unknown",
        },
    ],
    "modelSources": [{"id":"source-host-models","name":"Host models","path":"Z:\\LLM_Proxy\\Models","enabled":True}],
    "models": [],
    "profiles": [],
    "jobs": [],
    "requests": [],
    "logs": [],
    "runtime": {"state": "stopped", "activeModelId": None, "activeProfileId": None},
    "gateway": {"openaiEnabled": True, "ollamaEnabled": True, "drainTimeoutSec": 30},
    "hardwareSafety": {"safetyMargin": 0.10, "reserveBytes": None, "blockHighRisk": True},
    "actions": [],
    "extensions": [],
    "customEndpoints": [],
}


def _strip_legacy_gguf_raw(value: Any) -> bool:
    """Remove persisted GGUF raw metadata from models and historical job results."""
    changed = False
    if isinstance(value, dict):
        metadata = value.get("metadata")
        if isinstance(metadata, dict) and "raw" in metadata:
            del metadata["raw"]
            changed = True
        for item in value.values():
            changed = _strip_legacy_gguf_raw(item) or changed
    elif isinstance(value, list):
        for item in value:
            changed = _strip_legacy_gguf_raw(item) or changed
    return changed


class JsonStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(DEFAULT_STATE)

    def _read(self) -> dict[str, Any]:
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            changed = False
            for key, value in DEFAULT_STATE.items():
                if key not in state:
                    state[key] = deepcopy(value)
                    changed = True
            # GGUF scanner versions before schema 7 persisted complete tokenizer
            # metadata. A single model can contain hundreds of thousands of tokens,
            # making every API snapshot slow or unavailable.
            if _strip_legacy_gguf_raw(state):
                changed = True
            if state.get("schemaVersion", 0) < DEFAULT_STATE["schemaVersion"]:
                state["schemaVersion"] = DEFAULT_STATE["schemaVersion"]
                changed = True
            if changed:
                self._write(state)
            return state
        except (OSError, json.JSONDecodeError):
            backup = self.path.with_suffix(".corrupt.json")
            try:
                self.path.replace(backup)
            except OSError:
                pass
            self._write(DEFAULT_STATE)
            return deepcopy(DEFAULT_STATE)

    def _write(self, state: dict[str, Any]) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._read())

    def mutate(self, fn):
        with self._lock:
            state = self._read()
            result = fn(state)
            self._write(state)
            return deepcopy(result)
