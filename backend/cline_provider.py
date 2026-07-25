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

EVIDENCE_CONTRACT = """
You are operating inside a repository through Letterblack Inference Workspace.
Use the approved workspace root as the only source of truth.

Execution contract:
1. Inspect relevant files before diagnosing or proposing a change.
2. Never invent files, APIs, symbols, commands, tests, outputs, or runtime state.
3. Separate findings into VERIFIED, SUSPECTED, and UNKNOWN.
4. Every VERIFIED claim must include an exact workspace-relative file path and concrete evidence. Include line numbers when available.
5. Never claim a fix, test pass, or successful command unless the corresponding command output was observed in this run.
6. When evidence is insufficient, report UNKNOWN and stop instead of guessing.
7. Do not broaden scope beyond the user request.
8. End with an EVIDENCE section containing inspected workspace-relative paths and commands actually executed.
""".strip()

_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_EVIDENCE_SECTION = re.compile(r"(?ims)^\s*EVIDENCE\s*:?[ \t]*\n(?P<body>.*)$")
_PATH_TOKEN = re.compile(r"(?<![\w.-])(?:[A-Za-z]:[\\/][^\r\n:*?\"<>|]+|(?:[\w.-]+[\\/])+[\w.-]+)")
_FORBIDDEN_PATH_PARTS = {".cline", ".ssh", ".aws", ".azure", ".config", "credentials", "secrets"}
_SECRET_FILE_NAMES = {"providers.json", ".env", ".env.local", "id_rsa", "id_ed25519"}


class ClineProviderError(RuntimeError):
    def __init__(self, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.code = code
        self.details = details


def _is_absolute(value: str | Path) -> bool:
    text = str(value)
    return Path(text).is_absolute() or bool(_WINDOWS_ABSOLUTE.match(text))


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_sensitive(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return bool(parts & _FORBIDDEN_PATH_PARTS) or path.name.lower() in _SECRET_FILE_NAMES


def validate_workspace_root(cwd: str, approved_roots: list[str]) -> str:
    if not isinstance(cwd, str) or not cwd.strip() or not _is_absolute(cwd):
        raise ClineProviderError("CLINE_WORKSPACE_INVALID", "Cline workspace must be an absolute directory path.", {"cwd": cwd})
    root = _resolved(cwd)
    if not root.exists() or not root.is_dir():
        raise ClineProviderError("CLINE_WORKSPACE_NOT_FOUND", "Cline workspace directory does not exist.", {"cwd": str(root)})
    if _is_sensitive(root):
        raise ClineProviderError("CLINE_WORKSPACE_FORBIDDEN", "Cline cannot operate inside configuration or credential directories.", {"cwd": str(root)})
    approved = [_resolved(value) for value in approved_roots if isinstance(value, str) and value.strip()]
    if not approved or not any(root == item or _inside(root, item) for item in approved):
        raise ClineProviderError("CLINE_WORKSPACE_NOT_APPROVED", "Cline workspace is outside the registered LIW workspace roots.", {"cwd": str(root), "approvedRoots": [str(item) for item in approved]})
    return str(root)


def validate_profile(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return [{"path": "", "message": "Profile must be an object."}]
    issues: list[dict[str, str]] = []
    profile_id = str(value.get("id", ""))
    if not PROFILE_ID.fullmatch(profile_id):
        issues.append({"path": "id", "message": "Use 2-64 lowercase letters, numbers, dots, underscores, or hyphens."})
    config = value.get("configDirectory")
    if not isinstance(config, str) or not _is_absolute(config):
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


def build_guarded_prompt(prompt: str, cwd: str) -> str:
    workspace = str(_resolved(cwd))
    return f"""{EVIDENCE_CONTRACT}

WORKSPACE ROOT: {workspace}
USER TASK:
{prompt.strip()}
"""


def _evidence_paths(text: str) -> list[str]:
    match = _EVIDENCE_SECTION.search(text)
    if not match:
        return []
    return [item.strip().rstrip(".,:;)") for item in _PATH_TOKEN.findall(match.group("body"))]


def validate_evidence_output(text: str, workspace_root: str) -> list[str]:
    root = _resolved(workspace_root)
    raw_paths = _evidence_paths(text)
    if not raw_paths:
        raise ClineProviderError("CLINE_EVIDENCE_INSUFFICIENT", "Cline returned no usable EVIDENCE section with file references.", {"responseSample": text[:2000]})
    validated = []
    rejected = []
    for raw in raw_paths:
        candidate = _resolved(raw) if _is_absolute(raw) else _resolved(root / raw.replace("\\", "/"))
        if not _inside(candidate, root) and candidate != root:
            rejected.append({"path": raw, "reason": "outside-workspace"})
            continue
        if _is_sensitive(candidate):
            rejected.append({"path": raw, "reason": "sensitive-path"})
            continue
        if not candidate.exists() or not candidate.is_file():
            rejected.append({"path": raw, "reason": "file-not-found"})
            continue
        validated.append(candidate.relative_to(root).as_posix())
    if not validated:
        raise ClineProviderError("CLINE_EVIDENCE_INVALID", "Cline evidence did not resolve to an existing file inside the approved workspace.", {"rejected": rejected, "responseSample": text[:2000]})
    return sorted(set(validated))


def complete(profiles: list[dict[str, Any]], prompt: str, *, cwd: str, approved_roots: list[str]) -> dict[str, Any]:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ClineProviderError("INVALID_PROMPT", "A non-empty prompt is required.")
    workspace = validate_workspace_root(cwd, approved_roots)
    executable = shutil.which("cline")
    if not executable:
        raise ClineProviderError("CLINE_UNAVAILABLE", "Cline CLI is not installed or not on PATH.")
    attempts = []
    guarded_prompt = build_guarded_prompt(prompt, workspace)
    for profile in sorted((item for item in profiles if item.get("enabled", True)), key=lambda item: (int(item.get("priority", 100)), item["id"])):
        config = Path(profile["configDirectory"])
        if not config.is_dir():
            attempts.append({"profileId": profile["id"], "result": "skipped", "code": "CONFIG_DIRECTORY_MISSING"})
            continue
        for model in profile.get("freeModels", []):
            command = [executable, "--config", str(config), "--provider", str(profile.get("provider", "cline")), "--model", model, "--json", "--timeout", str(int(profile.get("timeoutSec", 90))), "--auto-approve", "false", "--plan", "--cwd", workspace, guarded_prompt]
            started = time.monotonic()
            try:
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=int(profile.get("timeoutSec", 90)), check=False)
            except subprocess.TimeoutExpired:
                attempts.append({"profileId": profile["id"], "model": model, "result": "failed", "code": "CLINE_TIMEOUT"})
                continue
            elapsed_ms = round((time.monotonic() - started) * 1000, 2)
            text = _extract_text(result.stdout)
            if result.returncode == 0 and text:
                evidence_paths = validate_evidence_output(text, workspace)
                return {"text": text, "route": {"kind": "cline", "profileId": profile["id"], "model": model}, "latencyMs": elapsed_ms, "workspaceRoot": workspace, "evidenceGuard": "passed", "evidencePaths": evidence_paths, "attempts": attempts + [{"profileId": profile["id"], "model": model, "result": "success", "latencyMs": elapsed_ms}]}
            code = classify_failure((result.stderr or "") + "\n" + (result.stdout or ""))
            attempts.append({"profileId": profile["id"], "model": model, "result": "failed", "code": code, "exitCode": result.returncode, "latencyMs": elapsed_ms})
            if code not in FALLBACK_FAILURES:
                raise ClineProviderError(code, "Cline request failed without a retryable provider condition.", {"attempts": attempts})
    raise ClineProviderError("ALL_CLOUD_ROUTES_EXHAUSTED", "No registered Cline free-model route completed. The existing local GGUF runtime remains unchanged.", {"attempts": attempts, "localRuntimePolicy": "unchanged"})
