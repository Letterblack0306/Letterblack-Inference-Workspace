from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "state"
MEMORY_DIR = ROOT / "memory"
CONFIG_PATH = ROOT / "config.json"
GOVERNANCE_PATH = ROOT / "governance.json"


class GovernanceError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


@dataclass(frozen=True)
class Context:
    config: dict[str, Any]
    governance: dict[str, Any]
    workspace: Path

    @classmethod
    def load(cls) -> "Context":
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"Create {CONFIG_PATH.name} from config.example.json before running."
            )
        config = load_json(CONFIG_PATH)
        governance = load_json(GOVERNANCE_PATH)
        workspace = Path(config["workspace_root"]).expanduser().resolve()
        if not workspace.exists() or not workspace.is_dir():
            raise FileNotFoundError(f"Workspace does not exist: {workspace}")
        return cls(config=config, governance=governance, workspace=workspace)


def relative_posix(ctx: Context, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ctx.workspace).as_posix()
    except ValueError as exc:
        raise GovernanceError(f"Path escapes workspace: {resolved}") from exc


def matches_any(path_text: str, patterns: list[str]) -> bool:
    normalized = path_text.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def path_allowed(path_text: str, allowed: list[str]) -> bool:
    normalized = path_text.replace("\\", "/").strip("/")
    for entry in allowed:
        entry = entry.replace("\\", "/").strip("/")
        if entry in {"", ".", "*", "**"}:
            return True
        if normalized == entry or normalized.startswith(entry + "/"):
            return True
    return False


def assert_read_allowed(ctx: Context, path: Path) -> str:
    rel = relative_posix(ctx, path)
    if matches_any(rel, ctx.governance.get("forbidden_globs", [])):
        raise GovernanceError(f"Read blocked by forbidden pattern: {rel}")
    if not path_allowed(rel, ctx.governance.get("allowed_read_paths", [])):
        raise GovernanceError(f"Read path not allowlisted: {rel}")
    return rel


def assert_write_allowed(ctx: Context, path: Path) -> str:
    if not ctx.config.get("write_enabled", False):
        raise GovernanceError("Writes are disabled in config.json")
    rel = relative_posix(ctx, path)
    if matches_any(rel, ctx.governance.get("forbidden_globs", [])):
        raise GovernanceError(f"Write blocked by forbidden pattern: {rel}")
    if not path_allowed(rel, ctx.governance.get("allowed_write_paths", [])):
        raise GovernanceError(f"Write path not allowlisted: {rel}")
    return rel


def list_workspace_files(ctx: Context) -> list[dict[str, Any]]:
    max_bytes = int(ctx.config.get("max_file_bytes", 2_000_000))
    records: list[dict[str, Any]] = []
    for path in sorted(ctx.workspace.rglob("*")):
        if not path.is_file():
            continue
        rel = relative_posix(ctx, path)
        if matches_any(rel, ctx.governance.get("forbidden_globs", [])):
            continue
        if not path_allowed(rel, ctx.governance.get("allowed_read_paths", [])):
            continue
        stat = path.stat()
        record = {
            "path": rel,
            "size": stat.st_size,
            "modified_ns": stat.st_mtime_ns,
        }
        if stat.st_size <= max_bytes:
            record["sha256"] = sha256_file(path)
        else:
            record["sha256"] = None
            record["skipped_hash_reason"] = "file_too_large"
        records.append(record)
    return records


def trace_workspace(ctx: Context) -> dict[str, Any]:
    missing_required = [
        item for item in ctx.governance.get("required_files", [])
        if not (ctx.workspace / item).exists()
    ]
    files = list_workspace_files(ctx)
    trace = {
        "created_at": utc_now(),
        "workspace_root": str(ctx.workspace),
        "write_enabled": bool(ctx.config.get("write_enabled", False)),
        "missing_required_files": missing_required,
        "governance_sha256": sha256_file(GOVERNANCE_PATH),
        "file_count": len(files),
        "top_level_groups": sorted({item["path"].split("/", 1)[0] for item in files}),
        "files": files,
    }
    write_json(STATE_DIR / "workspace_trace.json", trace)
    return trace


def inspect_file(ctx: Context, relative_path: str) -> dict[str, Any]:
    path = (ctx.workspace / relative_path).resolve()
    rel = assert_read_allowed(ctx, path)
    max_bytes = int(ctx.config.get("max_file_bytes", 2_000_000))
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise GovernanceError(f"File exceeds max_file_bytes: {rel}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GovernanceError(f"Only UTF-8 text files are supported: {rel}") from exc
    return {"path": rel, "sha256": sha256_bytes(data), "content": text}


def search_workspace(
    ctx: Context,
    query: str,
    *,
    max_results: int = 50,
    extensions: list[str] | None = None,
) -> dict[str, Any]:
    query = query.strip()
    if not query:
        raise GovernanceError("Search query cannot be empty")

    max_results = max(1, min(int(max_results), 200))
    default_extensions = [
        ".js", ".jsx", ".mjs", ".cjs", ".json", ".md",
        ".html", ".htm", ".xml", ".css", ".txt"
    ]
    allowed_extensions = {
        ext.lower() if ext.startswith(".") else "." + ext.lower()
        for ext in (extensions or default_extensions)
    }

    query_lower = query.lower()
    terms = [term for term in re.split(r"\s+", query_lower) if term]
    max_bytes = int(ctx.config.get("max_file_bytes", 2_000_000))
    results: list[dict[str, Any]] = []

    for path in ctx.workspace.rglob("*"):
        if not path.is_file():
            continue

        rel = relative_posix(ctx, path)
        if matches_any(rel, ctx.governance.get("forbidden_globs", [])):
            continue
        if not path_allowed(rel, ctx.governance.get("allowed_read_paths", [])):
            continue
        if path.suffix.lower() not in allowed_extensions:
            continue

        score = 0
        rel_lower = rel.lower()
        if query_lower in rel_lower:
            score += 100
        score += sum(15 for term in terms if term in rel_lower)

        size = path.stat().st_size
        snippet = ""
        line_number = None

        if size <= max_bytes:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            content_lower = content.lower()
            if query_lower in content_lower:
                score += 80
            score += sum(10 for term in terms if term in content_lower)

            if score > 0:
                lines = content.splitlines()
                best_index = 0
                for index, line in enumerate(lines):
                    line_lower = line.lower()
                    if query_lower in line_lower or any(term in line_lower for term in terms):
                        best_index = index
                        break
                start = max(0, best_index - 2)
                end = min(len(lines), best_index + 3)
                snippet = "\n".join(lines[start:end])[:1200]
                line_number = best_index + 1
        elif score == 0:
            continue

        if score > 0:
            results.append({
                "path": rel,
                "score": score,
                "size": size,
                "line": line_number,
                "snippet": snippet,
                "sha256": sha256_file(path) if size <= max_bytes else None,
            })

    results.sort(key=lambda item: (-item["score"], item["path"].lower()))
    results = results[:max_results]

    output = {
        "query": query,
        "result_count": len(results),
        "results": results,
    }
    write_json(STATE_DIR / "last_search.json", output)
    return output


def load_verified_memory(limit: int = 50) -> list[dict[str, Any]]:
    path = MEMORY_DIR / "verified_repairs.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows[-limit:]


def call_local_model(ctx: Context, issue: str, trace: dict[str, Any]) -> dict[str, Any]:
    model_cfg = ctx.config.get("model", {})
    if not model_cfg.get("enabled", False):
        return {
            "status": "model_disabled",
            "message": "Enable model in config.json or create proposal manually.",
            "proposal_schema": proposal_schema(issue),
        }

    relevant_files = [
        f for f in trace.get("files", [])
        if f["path"].endswith((".js", ".jsx", ".json", ".xml", ".html", ".css", ".mjs", ".cjs"))
    ][:120]

    prompt = {
        "role": "CEP repair engine",
        "issue": issue,
        "constraints": ctx.governance,
        "workspace_inventory": relevant_files,
        "verified_memory": load_verified_memory(30),
        "required_output": proposal_schema(issue),
        "rules": [
            "Return JSON only.",
            "Do not claim validation was run.",
            "Do not edit files outside allowed_write_paths.",
            "Every edited file must include its current base_sha256.",
            "Use complete replacement content, not prose patches.",
        ],
    }

    body = json.dumps({
        "model": model_cfg["model_name"],
        "messages": [
            {"role": "system", "content": "You are a constrained Adobe CEP code repair engine. Output valid JSON only."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}
        ],
        "temperature": 0.1
    }).encode("utf-8")

    url = model_cfg["base_url"].rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model_cfg.get('api_key', 'local')}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = payload["choices"][0]["message"]["content"]
    proposal = json.loads(content)
    validate_proposal_shape(proposal)
    return proposal


def proposal_schema(issue: str) -> dict[str, Any]:
    return {
        "issue": issue,
        "diagnosis": "",
        "governance_rules_used": [],
        "files_inspected": [],
        "changes": [
            {
                "path": "relative/path.js",
                "base_sha256": "current-file-sha256",
                "new_content": "complete replacement file content"
            }
        ],
        "validation_commands": [["npm", "test"]],
        "expected_result": ""
    }


def validate_proposal_shape(proposal: dict[str, Any]) -> None:
    required = ["issue", "diagnosis", "changes", "validation_commands"]
    missing = [key for key in required if key not in proposal]
    if missing:
        raise GovernanceError(f"Proposal missing keys: {missing}")
    if not isinstance(proposal["changes"], list):
        raise GovernanceError("changes must be a list")


def command_allowed(ctx: Context, command: list[str]) -> bool:
    return command in ctx.governance.get("allowed_commands", [])


def run_validation(ctx: Context, commands: list[list[str]] | None = None) -> dict[str, Any]:
    commands = commands or ctx.governance.get("required_validation_commands", [])
    results = []
    all_passed = True
    for command in commands:
        if not command_allowed(ctx, command):
            raise GovernanceError(f"Command is not allowlisted: {command}")
        completed = subprocess.run(
            command,
            cwd=ctx.workspace,
            capture_output=True,
            text=True,
            timeout=600,
            shell=False,
        )
        result = {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-20000:],
            "stderr": completed.stderr[-20000:],
        }
        results.append(result)
        if completed.returncode != 0:
            all_passed = False
    return {"passed": all_passed, "results": results}


def apply_proposal(ctx: Context, proposal_path: Path) -> dict[str, Any]:
    proposal = load_json(proposal_path)
    validate_proposal_shape(proposal)

    changes = proposal["changes"]
    max_files = int(ctx.governance.get("max_changed_files", 12))
    if len(changes) > max_files:
        raise GovernanceError(f"Proposal changes {len(changes)} files; limit is {max_files}")

    total_bytes = sum(len(change.get("new_content", "").encode("utf-8")) for change in changes)
    if total_bytes > int(ctx.governance.get("max_patch_bytes", 300000)):
        raise GovernanceError("Proposal exceeds max_patch_bytes")

    backups: dict[Path, bytes] = {}
    applied = []
    try:
        for change in changes:
            path = (ctx.workspace / change["path"]).resolve()
            rel = assert_write_allowed(ctx, path)
            if not path.exists():
                current = b""
                current_hash = sha256_bytes(current)
            else:
                current = path.read_bytes()
                current_hash = sha256_bytes(current)

            if ctx.governance.get("require_clean_base_hash", True):
                expected = change.get("base_sha256")
                if expected != current_hash:
                    raise GovernanceError(
                        f"Base hash mismatch for {rel}: expected {expected}, current {current_hash}"
                    )

            backups[path] = current
            path.parent.mkdir(parents=True, exist_ok=True)
            new_data = change["new_content"].encode("utf-8")
            path.write_bytes(new_data)
            applied.append({
                "path": rel,
                "before_sha256": current_hash,
                "after_sha256": sha256_bytes(new_data),
            })

        validation = run_validation(ctx, proposal.get("validation_commands"))
        if not validation["passed"]:
            raise GovernanceError("Validation failed; changes will be rolled back")

    except Exception:
        for path, content in backups.items():
            path.write_bytes(content)
        raise

    record = {
        "verified_at": utc_now(),
        "issue": proposal["issue"],
        "diagnosis": proposal.get("diagnosis", ""),
        "governance_rules_used": proposal.get("governance_rules_used", []),
        "files_inspected": proposal.get("files_inspected", []),
        "changes": applied,
        "validation": validation,
        "result": "passed",
    }
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with (MEMORY_DIR / "verified_repairs.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_json(STATE_DIR / "last_apply_result.json", record)
    return record


def cmd_trace(_: argparse.Namespace) -> None:
    ctx = Context.load()
    print(json.dumps(trace_workspace(ctx), indent=2))


def cmd_inspect(args: argparse.Namespace) -> None:
    ctx = Context.load()
    print(json.dumps(inspect_file(ctx, args.path), indent=2))


def cmd_validate(_: argparse.Namespace) -> None:
    ctx = Context.load()
    print(json.dumps(run_validation(ctx), indent=2))


def cmd_search(args: argparse.Namespace) -> None:
    ctx = Context.load()
    extensions = args.extensions.split(",") if args.extensions else None
    print(json.dumps(
        search_workspace(
            ctx,
            args.query,
            max_results=args.max_results,
            extensions=extensions,
        ),
        indent=2,
    ))


def cmd_propose(args: argparse.Namespace) -> None:
    ctx = Context.load()
    trace = trace_workspace(ctx)
    proposal = call_local_model(ctx, args.issue, trace)
    write_json(STATE_DIR / "latest_proposal.json", proposal)
    print(json.dumps(proposal, indent=2))


def cmd_apply(args: argparse.Namespace) -> None:
    ctx = Context.load()
    print(json.dumps(apply_proposal(ctx, Path(args.proposal)), indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Constrained CEP repair agent")
    sub = parser.add_subparsers(required=True)

    trace = sub.add_parser("trace")
    trace.set_defaults(func=cmd_trace)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("path")
    inspect.set_defaults(func=cmd_inspect)

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--max-results", type=int, default=50)
    search.add_argument(
        "--extensions",
        help="Comma-separated extensions, e.g. js,jsx,md,json"
    )
    search.set_defaults(func=cmd_search)

    validate = sub.add_parser("validate")
    validate.set_defaults(func=cmd_validate)

    propose = sub.add_parser("propose")
    propose.add_argument("--issue", required=True)
    propose.set_defaults(func=cmd_propose)

    apply_cmd = sub.add_parser("apply")
    apply_cmd.add_argument("proposal")
    apply_cmd.set_defaults(func=cmd_apply)

    return parser


if __name__ == "__main__":
    STATE_DIR.mkdir(exist_ok=True)
    MEMORY_DIR.mkdir(exist_ok=True)
    args = build_parser().parse_args()
    try:
        args.func(args)
    except (GovernanceError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, indent=2), file=sys.stderr)
        sys.exit(2)
