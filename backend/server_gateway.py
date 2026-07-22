from __future__ import annotations

import argparse
import os
from copy import deepcopy
from http.server import ThreadingHTTPServer

from . import server as base
from .server_settings import SettingsHandler


class GatewayCapabilityHandler(SettingsHandler):
    def do_GET(self) -> None:
        if self._parts() == ["api", "v1", "capabilities"]:
            capabilities = deepcopy(base.CAPABILITIES)
            features = capabilities.get("features", {})
            capabilities["compatibility"] = {
                "openai": features.get("openAICompatibility"),
                "ollama": features.get("ollamaCompatibility"),
            }
            self._ok(capabilities)
            return
        super().do_GET()


def main() -> None:
    base.CAPABILITIES["contractVersion"] = "6.1.1"
    base.CAPABILITIES["features"]["settingsContract"] = True
    parser = argparse.ArgumentParser(
        description="Letterblack Inference Workspace server with settings and gateway capability contracts"
    )
    parser.add_argument("--host", default=base.CONTROL_PLANE_HOST)
    parser.add_argument("--port", type=int, default=base.CONTROL_PLANE_PORT)
    args = parser.parse_args()
    if args.host != base.CONTROL_PLANE_HOST or args.port != base.CONTROL_PLANE_PORT:
        parser.error("Remote control is unsupported; the control plane is fixed to http://127.0.0.1:8088.")
    server = ThreadingHTTPServer((args.host, args.port), GatewayCapabilityHandler)
    base.configure_control_server_shutdown(server.shutdown)
    print(f"Letterblack Phase 6.1.1 serving http://{args.host}:{args.port}")
    print("Settings and gateway capability contracts enabled.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
