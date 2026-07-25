from __future__ import annotations

import argparse
import json
from http.server import ThreadingHTTPServer
from typing import Any

from . import server as base
from .cline_provider import (
    ClineProviderError,
    complete as cline_complete,
    status as cline_status,
    validate_profile as validate_cline_profile,
)
from .server_gateway import GatewayCapabilityHandler


def _stored_profile(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": body["id"],
        "configDirectory": body["configDirectory"],
        "provider": body.get("provider", "cline"),
        "freeModels": list(body["freeModels"]),
        "enabled": bool(body.get("enabled", True)),
        "priority": int(body.get("priority", 100)),
        "timeoutSec": int(body.get("timeoutSec", 90)),
    }


class ClineProviderHandler(GatewayCapabilityHandler):
    """Optional Cline routes layered over the unchanged local GGUF gateway."""

    @staticmethod
    def _provider(state: dict[str, Any]) -> dict[str, Any]:
        return state.setdefault("clineProvider", {"enabled": False, "profiles": []})

    @staticmethod
    def _approved_workspace_roots() -> list[str]:
        return [str(base.ROOT.resolve())]

    def do_GET(self) -> None:
        if self._parts() == ["api", "v1", "providers", "cline"]:
            provider = self._provider(base.STORE.snapshot())
            self._ok({
                "enabled": bool(provider.get("enabled", False)),
                **cline_status(provider.get("profiles", [])),
                "evidenceGuard": "verified-existing-workspace-files",
                "approvedWorkspaceRoots": self._approved_workspace_roots(),
                "localRuntimePolicy": "unchanged",
            })
            return
        super().do_GET()

    def do_POST(self) -> None:
        parts = self._parts()
        if parts not in (
            ["api", "v1", "providers", "cline", "profiles"],
            ["api", "v1", "providers", "cline", "complete"],
        ):
            super().do_POST()
            return
        try:
            body = self._json_body()
        except (ValueError, json.JSONDecodeError) as exc:
            self._fail("INVALID_JSON", str(exc), 400)
            return

        if parts[-1] == "profiles":
            issues = validate_cline_profile(body)
            if issues:
                self._fail("VALIDATION_FAILED", "Cline profile validation failed.", 422, issues)
                return

            def add_profile(state: dict[str, Any]):
                provider = self._provider(state)
                if any(item["id"] == body["id"] for item in provider["profiles"]):
                    return None
                profile = _stored_profile(body)
                provider["profiles"].append(profile)
                base.add_log(state, "info", "cline", "Authorized Cline profile registered.", profileId=profile["id"])
                return profile

            result = base.STORE.mutate(add_profile)
            if result is None:
                self._fail("CLINE_PROFILE_EXISTS", "A Cline profile with this ID already exists.", 409)
            else:
                self._ok(result, 201)
            return

        state = base.STORE.snapshot()
        provider = self._provider(state)
        if not provider.get("enabled", False):
            self._fail("CLINE_PROVIDER_DISABLED", "Cline provider is disabled.", 409)
            return
        prompt = body.get("prompt", "") if isinstance(body, dict) else ""
        cwd = body.get("cwd", str(base.ROOT)) if isinstance(body, dict) else str(base.ROOT)
        try:
            result = cline_complete(
                provider.get("profiles", []),
                prompt,
                cwd=str(cwd),
                approved_roots=self._approved_workspace_roots(),
            )
        except ClineProviderError as exc:
            self._fail(exc.code, str(exc), 503, exc.details)
            return
        base.STORE.mutate(lambda current: base.add_log(
            current,
            "info",
            "cline",
            "Evidence-guarded Cline request completed.",
            route=result.get("route"),
            workspaceRoot=result.get("workspaceRoot"),
            evidencePaths=result.get("evidencePaths"),
            latencyMs=result.get("latencyMs"),
        ))
        self._ok(result)

    def do_PUT(self) -> None:
        parts = self._parts()
        if parts == ["api", "v1", "providers", "cline"]:
            try:
                body = self._json_body()
            except (ValueError, json.JSONDecodeError) as exc:
                self._fail("INVALID_JSON", str(exc), 400)
                return
            if not isinstance(body, dict) or not isinstance(body.get("enabled"), bool):
                self._fail("VALIDATION_FAILED", "enabled must be a boolean.", 422)
                return

            def set_enabled(state: dict[str, Any]):
                provider = self._provider(state)
                provider["enabled"] = body["enabled"]
                return provider

            self._ok(base.STORE.mutate(set_enabled))
            return

        if parts[:4] == ["api", "v1", "providers", "cline"] and len(parts) == 5:
            try:
                body = self._json_body()
            except (ValueError, json.JSONDecodeError) as exc:
                self._fail("INVALID_JSON", str(exc), 400)
                return
            profile_id = parts[4]
            body["id"] = profile_id
            issues = validate_cline_profile(body)
            if issues:
                self._fail("VALIDATION_FAILED", "Cline profile validation failed.", 422, issues)
                return

            def update_profile(state: dict[str, Any]):
                provider = self._provider(state)
                for index, item in enumerate(provider["profiles"]):
                    if item["id"] == profile_id:
                        provider["profiles"][index] = _stored_profile(body)
                        base.add_log(state, "info", "cline", "Authorized Cline profile updated.", profileId=profile_id)
                        return provider["profiles"][index]
                return None

            result = base.STORE.mutate(update_profile)
            if result is None:
                self._fail("CLINE_PROFILE_NOT_FOUND", "Cline profile was not found.", 404)
            else:
                self._ok(result)
            return
        super().do_PUT()

    def do_DELETE(self) -> None:
        parts = self._parts()
        if parts[:4] == ["api", "v1", "providers", "cline"] and len(parts) == 5:
            profile_id = parts[4]

            def remove_profile(state: dict[str, Any]):
                provider = self._provider(state)
                before = len(provider["profiles"])
                provider["profiles"] = [item for item in provider["profiles"] if item["id"] != profile_id]
                if len(provider["profiles"]) == before:
                    return False
                base.add_log(state, "warning", "cline", "Authorized Cline profile removed.", profileId=profile_id)
                return True

            if base.STORE.mutate(remove_profile):
                self._ok({"deleted": profile_id})
            else:
                self._fail("CLINE_PROFILE_NOT_FOUND", "Cline profile was not found.", 404)
            return
        super().do_DELETE()


def main() -> None:
    base.CAPABILITIES["contractVersion"] = "6.2.1"
    base.CAPABILITIES["features"]["clineProvider"] = "authorized-profiles-verified-evidence"
    parser = argparse.ArgumentParser(description="LIW optional evidence-guarded Cline provider")
    parser.add_argument("--host", default=base.CONTROL_PLANE_HOST)
    parser.add_argument("--port", type=int, default=base.CONTROL_PLANE_PORT)
    args = parser.parse_args()
    if args.host != base.CONTROL_PLANE_HOST or args.port != base.CONTROL_PLANE_PORT:
        parser.error("Remote control is unsupported; the control plane is fixed to http://127.0.0.1:8088.")
    server = ThreadingHTTPServer((args.host, args.port), ClineProviderHandler)
    base.configure_control_server_shutdown(server.shutdown)
    print(f"Letterblack Phase 6.2.1 serving http://{args.host}:{args.port}")
    print("Local GGUF routing unchanged; optional Cline provider available through explicit launch.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
