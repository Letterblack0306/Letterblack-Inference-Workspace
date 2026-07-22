from __future__ import annotations

import unittest

from backend.server_settings import changed_restart_fields, validate_settings
from backend import server as base


def valid_settings():
    return {
        "paths": {
            "applicationRoot": str(base.ROOT),
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

    def test_empty_model_sources_are_valid_for_a_new_workspace(self):
        value = valid_settings()
        value["paths"]["modelSources"] = []
        self.assertEqual(validate_settings(value), [])

    def test_application_root_must_match_the_running_control_plane(self):
        value = valid_settings()
        value["paths"]["applicationRoot"] = "C:\\Not-The-Running-Workspace"
        issues = validate_settings(value)
        self.assertTrue(any(item["path"] == "paths.applicationRoot" for item in issues))

    def test_duplicate_ports_rejected(self):
        value = valid_settings()
        value["ports"]["rpc"] = value["ports"]["workerController"]
        issues = validate_settings(value)
        self.assertTrue(any(item["path"] == "ports" for item in issues))

    def test_remote_bind_is_rejected_even_when_legacy_flag_is_enabled(self):
        value = valid_settings()
        value["runtime"]["bindAddress"] = "0.0.0.0"
        value["safety"]["allowRemoteDashboard"] = True
        issues = validate_settings(value)
        self.assertTrue(any(item["path"] == "runtime.bindAddress" for item in issues))
        self.assertTrue(any(item["path"] == "safety.allowRemoteDashboard" for item in issues))

    def test_control_plane_port_is_fixed(self):
        value = valid_settings()
        value["ports"]["dashboard"] = 8090
        issues = validate_settings(value)
        self.assertTrue(any(item["path"] == "ports.dashboard" for item in issues))

    def test_restart_fields_are_reported(self):
        before = valid_settings()
        after = valid_settings()
        after["paths"]["llamaServerPath"] = "Z:\\Tools\\llama-server.exe"
        self.assertEqual(changed_restart_fields(before, after), ["paths.llamaServerPath"])


if __name__ == "__main__":
    unittest.main()
