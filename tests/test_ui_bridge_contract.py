from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOM_CONTRACT = ROOT / "contracts" / "ui-prototype-dom.json"
BINDING_CONTRACT = ROOT / "contracts" / "ui-prototype-binding.json"
API_MODULE = ROOT / "web" / "js" / "api.js"
EXPECTED_SOURCE_SHA256 = "ebf939a291ae0a2852db96d78fbaec68ac25c5b2ab9134bfa13437bfdb024352"


class UiBridgeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dom = json.loads(DOM_CONTRACT.read_text(encoding="utf-8"))
        cls.binding = json.loads(BINDING_CONTRACT.read_text(encoding="utf-8"))
        cls.api_source = API_MODULE.read_text(encoding="utf-8-sig")

    def test_contracts_reference_exact_prototype(self) -> None:
        self.assertEqual(self.dom["sourceSha256"], EXPECTED_SOURCE_SHA256)
        self.assertEqual(self.binding["sourceSha256"], EXPECTED_SOURCE_SHA256)
        self.assertEqual(self.dom["dom"]["idCount"], len(self.dom["dom"]["ids"]))
        self.assertEqual(
            self.dom["dom"]["inlineHandlerCount"],
            len(self.dom["dom"]["inlineHandlers"]),
        )
        self.assertEqual(
            self.dom["script"]["functionCount"],
            len(self.dom["script"]["functions"]),
        )

    def test_every_binding_targets_real_prototype_functions_and_selectors(self) -> None:
        functions = set(self.dom["script"]["functions"])
        selectors = set(self.dom["dom"]["ids"])
        for item in self.binding["bindings"]:
            with self.subTest(function=item["prototypeFunction"]):
                self.assertIn(item["prototypeFunction"], functions)
                for selector in item.get("selectors", []):
                    self.assertIn(selector, selectors)

    def test_every_repository_api_call_exists(self) -> None:
        api_block = self.api_source.split("export const api = {", 1)[1].split("\n};", 1)[0]
        api_methods = set(re.findall(r"^\s{2}([A-Za-z_$][\w$]*):", api_block, re.MULTILINE))
        referenced = {
            call.removeprefix("api.")
            for item in self.binding["bindings"]
            for call in item.get("repositoryCalls", [])
        }
        self.assertFalse(referenced - api_methods, f"Missing API methods: {sorted(referenced - api_methods)}")

    def test_prototype_only_routes_are_absent_from_active_frontend(self) -> None:
        active_files = [ROOT / "web" / "index.html", *[p for p in sorted((ROOT / "web" / "js").glob("*.js")) if p.name != "api.js"]]
        active_text = "\n".join(path.read_text(encoding="utf-8-sig") for path in active_files)
        found = []
        for route in self.binding["forbiddenActiveRoutes"]:
            exact_literal = re.compile(rf"(['\"])" + re.escape(route) + r"\1")
            if exact_literal.search(active_text):
                found.append(route)
        self.assertEqual(found, [], f"Prototype-only routes remain active: {found}")

    def test_backend_affecting_functions_are_explicitly_bound(self) -> None:
        expected = {
            "checkRuntimeHealth",
            "refreshTelemetry",
            "refreshModels",
            "handleSendPrompt",
            "rescanDirectories",
            "launchServerForModel",
            "stopServerProcess",
            "restartServerProcess",
            "confirmSwapModel",
            "shutdownWorkspace",
            "testNodeConnection",
            "confirmAddNode",
            "saveProfileChanges",
            "saveWorkspaceSettings",
            "saveExtensionManifest",
            "clearLogStream",
            "exportLogsJSON",
        }
        actual = {item["prototypeFunction"] for item in self.binding["bindings"]}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
