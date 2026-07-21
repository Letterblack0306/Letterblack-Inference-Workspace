from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.extensions import (
    combined_actions,
    combined_endpoints,
    combined_widgets,
    normalized_extension,
    validate_action,
    validate_endpoint,
    validate_extension,
)


class ExtensionContractTests(unittest.TestCase):
    def test_sample_extension_is_valid(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "examples" / "sample-extension.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_extension(manifest, "6.0.0"), [])

    def test_executable_extension_code_is_rejected(self):
        manifest = {
            "id": "extension-bad", "name": "Bad", "version": "1.0.0", "apiVersion": "1",
            "permissions": [], "entrypoint": "evil.py"
        }
        issues = validate_extension(manifest, "6.0.0")
        self.assertTrue(any(item["field"] == "entrypoint" for item in issues))

    def test_action_requires_registered_endpoint_reference(self):
        issues = validate_action({
            "id": "action-test", "name": "Test", "type": "http-request",
            "permissions": ["network.http"], "config": {}
        })
        self.assertTrue(any(item["field"] == "config.endpointId" for item in issues))

    def test_endpoint_requires_explicit_http_scheme(self):
        issues = validate_endpoint({"id": "endpoint-test", "name": "Test", "baseUrl": "localhost:9000"})
        self.assertTrue(any(item["field"] == "baseUrl" for item in issues))

    def test_enabled_extension_assets_are_merged(self):
        extension = normalized_extension({
            "id": "extension-test", "name": "Test", "version": "1.0.0", "apiVersion": "1",
            "permissions": ["widget.register", "action.register", "endpoint.register", "models.scan"],
            "widgets": [{"type": "test-widget", "name": "Test widget"}],
            "actions": [{"id": "action-test", "name": "Test action", "type": "models-scan", "permissions": ["models.scan"], "config": {}}],
            "endpoints": [{"id": "endpoint-test", "name": "Test endpoint", "baseUrl": "http://127.0.0.1:1"}],
        })
        self.assertEqual(combined_widgets([], [extension])[0]["type"], "test-widget")
        self.assertEqual(combined_actions([], [extension])[0]["id"], "action-test")
        self.assertEqual(combined_endpoints([], [extension])[0]["id"], "endpoint-test")


if __name__ == "__main__":
    unittest.main()
