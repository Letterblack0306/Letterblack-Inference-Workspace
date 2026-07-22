from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "machine-actions.json"


def machine_action_catalog() -> dict[str, Any]:
    """Read the operator-editable machine-action catalog from local JSON."""
    try:
        value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Machine action catalog is unavailable: {exc}") from exc
    actions = value.get("actions") if isinstance(value, dict) else None
    if not isinstance(actions, list) or not all(isinstance(item, dict) and isinstance(item.get("id"), str) for item in actions):
        raise ValueError("Machine action catalog must contain an actions array with IDs.")
    return value


def default_machine_action_ids() -> list[str]:
    return [item["id"] for item in machine_action_catalog()["actions"]]


def valid_machine_action_ids() -> set[str]:
    return set(default_machine_action_ids())
