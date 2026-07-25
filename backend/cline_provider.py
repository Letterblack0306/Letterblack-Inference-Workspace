from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


PROFILE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
FALLBACK_FAILURES = {"CLOUD_QUOTA_EXHAUSTED", "CLOUD_RATE_LIMITED", "CLOUD_MODEL_UNAVAILABLE", "CLOUD_AUTH_EXPIRED", "CLINE_TIMEOUT"}


class ClineProviderError(RuntimeError):
    def __init__(self, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.code = code
        self.details = details


def validate_profile(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return [{"path": "", "message": "Profile must be an object."}]
    issues: list[dict[str, str]] = []
    profile_id = str(value.get("id", ""))
    if not PROFILE_ID.fullmatch(profile_id):
        issues.append({"path": "id", "message": "Use 2-64 lowercase letters, numbers, dots, underscores, or hyphens."})
    config = value.get("configDirectory")
    if not isinstance(config, str) or not Path(config).is_absolute():
        issues.append({"path": "configDirectory", "message": "Use an absolute Cline-managed configuration directory."})
    if not isinstance(value.get("provider", "cline"), str) or not value.get("provider", "cline").strip():
        issues.append({"path": "provider", "message": "Provider is required."})
    models = value.get("freeModels", [])
    if not isinstance(models, list) or not models or not all(isinstance(item, str) and item.strip() for item in models):
        issues.append({"path": "freeModels", "message": "Register one or more explicitly authorized free model IDs."})
    if not isinstance(value.get("priority", 100), int):
        issues.append({"path": "priority", "message": "Priority must be an integer."})
    if not isinstance(value.get("timeoutSec", 90), int) or not 5 <= int(value.get("timeoutSec", 90)) <= 600:
        issues.append({"path": "timeoutSec", "message": "Timeout must be between 5 and 600 seconds."})
    forbidden = {"token", "apikey", "apiKey", "providers", "providersJson", "backup", "credentials"}
    if forbidden & set(value):
        issues.append({"path": "", "message": "Credential material and backup files are never accepted by LIW."})
    return issues


def public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": profile["id"],
        "configDirectory": profile["configDirectory"],
        "provider": profile.get("provider", "cline"),
        "freeModels": list(profile.get("freeModels", [])),
        "enabled": profile.get("enabled", True),
        "priority": int(profile.get("priority", 100)),
        "timeoutSec": int(profile.get("timeoutSec", 90)),
        "configDirectoryExists": Path(profile["configDirectory"]).is_dir(),
        "authentication": "unknown",
    }


def status(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    executable = shutil.which("cline")
    return {
        "cliAvailable": executable is not None,
        "cliPath": executable,
        "profiles": [public_profile(item) for item in sorted(profiles, key=lambda item: (int(item.get("priority", 100)), item["id"]))],
        "catalogue": "manual-free-model-registry",
        "catalogueReason": "Cline CLI exposes no documented non-secret model catalogue command; LIW never reads provider configuration files.",
    }


def classify_failure(text: str, timed_out: bool = False) -> str:
    value = text.lower()
    if timed_out: return "CLINE_TIMEOUT"
    if any(token in value for token in ("quota", "insufficient credits", "usage limit", "billing")): return "CLOUD_QUOTA_EXHAUSTED"
    if any(token in value for token in ("rate limit", "too many requests", "429")): return "CLOUD_RATE_LIMITED"
    if any(token in value for token in ("model not found", "model unavailable", "unsupported model")): return "CLOUD_MODEL_UNAVAILABLE"
    if any(token in value for token in ("unauthorized", "authentication", "login", "expired token", "401")): return "CLOUD_AUTH_EXPIRED"
    return "CLINE_EXECUTION_FAILED"


def _extract_text(stdout: str) -> str:
    texts: list[str] = []
    for line in stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            for key in ("text", "content", "message"):
                value = item.get(key)
                if isinstance(value, str) and value.strip(): texts.append(value.strip())
                elif isinstance(value, dict) and isinstance(value.get("text"), str): texts.append(value["text"].strip())
    return "\n".join(dict.fromkeys(texts)).strip()


def complete(profiles: list[dict[str, Any]], prompt: str, *, cwd: str) -> dict[str, Any]:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ClineProviderError("INVALID_PROMPT", "A non-empty prompt is required.")
    executable = shutil.which("cline")
    if not executable:
        raise ClineProviderError("CLINE_UNAVAILABLE", "Cline CLI is not installed or not on PATH.")
    attempts = []
    for profile in sorted((item for item in profiles if item.get("enabled", True)), key=lambda item: (int(item.get("priority", 100)), item["id"])):
        config = Path(profile["configDirectory"])
        if not config.is_dir():
            attempts.append({"profileId": profile["id"], "result": "skipped", "code": "CONFIG_DIRECTORY_MISSING"})
            continue
        for model in profile.get("freeModels", []):
            command = [executable, "--config", str(config), "--provider", str(profile.get("provider", "cline")), "--model", model, "--json", "--timeout", str(int(profile.get("timeoutSec", 90))), "--auto-approve", "false", "--plan", "--cwd", cwd, prompt]
            started = time.monotonic()
            try:
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=int(profile.get("timeoutSec", 90)), check=False)
            except subprocess.TimeoutExpired:
                attempts.append({"profileId": profile["id"], "model": model, "result": "failed", "code": "CLINE_TIMEOUT"})
                continue
            elapsed_ms = round((time.monotonic() - started) * 1000, 2)
            text = _extract_text(result.stdout)
            if result.returncode == 0 and text:
                return {"text": text, "route": {"kind": "cline", "profileId": profile["id"], "model": model}, "latencyMs": elapsed_ms, "attempts": attempts + [{"profileId": profile["id"], "model": model, "result": "success", "latencyMs": elapsed_ms}]}
            code = classify_failure((result.stderr or "") + "\n" + (result.stdout or ""))
            attempts.append({"profileId": profile["id"], "model": model, "result": "failed", "code": code, "exitCode": result.returncode, "latencyMs": elapsed_ms})
            if code not in FALLBACK_FAILURES:
                raise ClineProviderError(code, "Cline request failed without a retryable provider condition.", {"attempts": attempts})
    raise ClineProviderError("ALL_CLOUD_ROUTES_EXHAUSTED", "No registered Cline free-model route completed. Start the local GGUF runtime or correct an authorized Cline profile.", {"attempts": attempts, "localFallback": "available-if-runtime-ready"})
