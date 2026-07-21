from __future__ import annotations

import unittest

from backend.server_settings import changed_restart_fields, validate_settings


def valid_settings():
    return {
        "paths": {
            "applicationRoot": "Z:\\LLM_Proxy\\ControlUI",
            "modelSources": ["Z:\\LLM_Proxy\\Models"],
            "llamaServerPath": "",
        },
        "ports": {
            "dashboard": 8088,
            "openaiGateway": 1234,
            "ollamaGateway": 11434,
            "workerController": 50053,
            "rpc": 50052,
        },
        "runtime": {
            "bindAddress": "127.0.0.1",
            "pollIntervalMs": 5000,
            "requestDrainTimeoutSec": 30,
        },
        "safety": {
            "blockUnsafeLaunch": True,
            "allowRemoteDashboard": False,
        },
    }


class SettingsContractTests(unittest.TestCase):
    def test_valid_settings(self):
        self.assertEqual(validate_settings(valid_settings()), [])

    def test_duplicate_ports_rejected(self):
        value = valid_settings()
        value["ports"]["rpc"] = value["ports"]["workerController"]
        issues = validate_settings(value)
        self.assertTrue(any(item["path"] == "ports" for item in issues))

    def test_remote_bind_requires_explicit_approval(self):
        value = valid_settings()
        value["runtime"]["bindAddress"] = "0.0.0.0"
        issues = validate_settings(value)
        self.assertTrue(any(item["path"] == "safety.allowRemoteDashboard" for item in issues))

    def test_restart_fields_are_reported(self):
        before = valid_settings()
        after = valid_settings()
        after["ports"]["dashboard"] = 8090
        self.assertEqual(changed_restart_fields(before, after), ["ports.dashboard"])


if __name__ == "__main__":
    unittest.main()
