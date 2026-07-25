from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from agent import (
    CONFIG_PATH,
    STATE_DIR,
    Context,
    GovernanceError,
    apply_proposal,
    call_local_model,
    inspect_file,
    load_json,
    run_validation,
    search_workspace,
    trace_workspace,
    write_json,
)


class Handler(BaseHTTPRequestHandler):
    server_version = "CEPRepairAgent/0.1"

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 2_000_000:
            raise GovernanceError("Invalid request body size")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self.send_json(200, {"status": "ok"})
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        try:
            ctx = Context.load()
            path = urlparse(self.path).path
            payload = self.read_json() if self.headers.get("Content-Length") else {}

            if path == "/trace":
                result = trace_workspace(ctx)
            elif path == "/inspect":
                result = inspect_file(ctx, payload["path"])
            elif path == "/search":
                result = search_workspace(
                    ctx,
                    payload["query"],
                    max_results=payload.get("max_results", 50),
                    extensions=payload.get("extensions"),
                )
            elif path == "/validate":
                result = run_validation(ctx, payload.get("commands"))
            elif path == "/propose":
                trace = trace_workspace(ctx)
                result = call_local_model(ctx, payload["issue"], trace)
                write_json(STATE_DIR / "latest_proposal.json", result)
            elif path == "/apply":
                proposal = payload.get("proposal")
                if proposal is not None:
                    temp = STATE_DIR / "api_proposal.json"
                    write_json(temp, proposal)
                    result = apply_proposal(ctx, temp)
                else:
                    proposal_path = Path(payload.get("proposal_path", STATE_DIR / "latest_proposal.json"))
                    result = apply_proposal(ctx, proposal_path)
            else:
                self.send_json(404, {"error": "not_found"})
                return

            self.send_json(200, result)

        except (GovernanceError, FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": type(exc).__name__, "message": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": type(exc).__name__, "message": str(exc)})

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    config = load_json(CONFIG_PATH)
    host = config.get("server_host", "127.0.0.1")
    if host not in {"127.0.0.1", "localhost"}:
        raise GovernanceError("Server host must remain local-only")
    port = int(config.get("server_port", 8765))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"CEP repair agent listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
