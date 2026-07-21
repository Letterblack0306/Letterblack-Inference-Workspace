from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
_SECRET_KEYS = {
    "authorization",
    "proxy-authorization",
    "api_key",
    "apikey",
    "api-key",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "passwd",
    "secret",
    "cookie",
    "set-cookie",
}
_BEARER_RE = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+\-/=]+")
_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:api[_-]?key|token|access_token|password|secret)=)[^&#\s]+"
)


@dataclass(frozen=True)
class ValidationRun:
    run_id: str
    schema_version: int
    area: str
    test_type: str
    result: str
    started_at: float
    finished_at: float
    duration_ms: int
    target: Any
    config_snapshot: Any
    request: Any
    response_status: Any
    metrics: dict[str, Any]
    evidence: Any
    retest_of: str | None = None


class ValidationAuditStore:
    """Append-only JSONL store for durable validation evidence.

    The store is intentionally independent from mutable runtime state. Writes are
    serialized, flushed, fsynced, and never rewrite prior records.
    """

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @staticmethod
    def redact(value: Any, key: str | None = None) -> Any:
        if key and key.lower() in _SECRET_KEYS:
            return "[REDACTED]"
        if isinstance(value, dict):
            return {
                str(k): ValidationAuditStore.redact(v, str(k))
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [ValidationAuditStore.redact(item) for item in value]
        if isinstance(value, str):
            redacted = _BEARER_RE.sub(lambda m: f"{m.group(1)} [REDACTED]", value)
            redacted = _QUERY_SECRET_RE.sub(lambda m: f"{m.group(1)}[REDACTED]", redacted)
            return redacted
        return value

    def append(
        self,
        *,
        area: str,
        test_type: str,
        result: str,
        started_at: float,
        finished_at: float | None = None,
        target: Any = None,
        config_snapshot: Any = None,
        request: Any = None,
        response_status: Any = None,
        metrics: dict[str, Any] | None = None,
        evidence: Any = None,
        retest_of: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        if result not in {"pass", "fail", "unknown"}:
            raise ValueError("result must be pass, fail, or unknown")
        if not area or not test_type:
            raise ValueError("area and test_type are required")
        finished = time.time() if finished_at is None else float(finished_at)
        started = float(started_at)
        record = ValidationRun(
            run_id=run_id or str(uuid.uuid4()),
            schema_version=SCHEMA_VERSION,
            area=area,
            test_type=test_type,
            result=result,
            started_at=started,
            finished_at=finished,
            duration_ms=max(0, round((finished - started) * 1000)),
            target=self.redact(target),
            config_snapshot=self.redact(config_snapshot),
            request=self.redact(request),
            response_status=self.redact(response_status),
            metrics=self.redact(metrics or {}),
            evidence=self.redact(evidence),
            retest_of=retest_of,
        )
        payload = asdict(record)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return payload

    def iter_runs(
        self,
        *,
        area: str | None = None,
        test_type: str | None = None,
        result: str | None = None,
    ) -> Iterable[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if area is not None and row.get("area") != area:
                    continue
                if test_type is not None and row.get("test_type") != test_type:
                    continue
                if result is not None and row.get("result") != result:
                    continue
                rows.append(row)
        return rows

    def export_json(
        self,
        destination: str | os.PathLike[str],
        *,
        area: str | None = None,
        test_type: str | None = None,
        result: str | None = None,
    ) -> Path:
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "exportedAt": time.time(),
            "filters": {"area": area, "testType": test_type, "result": result},
            "runs": list(self.iter_runs(area=area, test_type=test_type, result=result)),
        }
        fd, temp_name = tempfile.mkstemp(
            prefix=destination_path.name + ".", dir=str(destination_path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, destination_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return destination_path
