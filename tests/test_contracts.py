from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.contracts import create_job, envelope, validate_machine, validate_workspace
from backend.store import JsonStore


class ContractTests(unittest.TestCase):
    def test_envelope(self):
        result = envelope({"ready": True}, request_id="req-test")
        self.assertTrue(result["ok"])
        self.assertEqual(result["requestId"], "req-test")
        self.assertEqual(result["data"], {"ready": True})

    def test_machine_validation_rejects_bad_ports(self):
        issues = validate_machine({"id": "Worker 1", "name": "", "addresses": [], "controller": {"port": 0}, "rpc": {"port": 70000}})
        fields = {item["field"] for item in issues}
        self.assertIn("id", fields)
        self.assertIn("name", fields)
        self.assertIn("addresses", fields)
        self.assertIn("controller.port", fields)
        self.assertIn("rpc.port", fields)

    def test_machine_validation_accepts_valid_machine(self):
        issues = validate_machine({"id": "machine-worker-02", "name": "Worker 02", "addresses": ["192.168.1.156"], "controller": {"scheme": "http", "port": 50053}, "rpc": {"port": 50052, "enabled": True}})
        self.assertEqual(issues, [])

    def test_job_contract(self):
        job = create_job("runtime.launch", {"modelId": "model-1"}, ["validate", "start", "verify"])
        self.assertEqual(job["state"], "queued")
        self.assertEqual(job["progress"], 0)
        self.assertFalse(job["simulation"])

    def test_store_persists(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            store = JsonStore(path)
            store.mutate(lambda state: state["profiles"].append({"id": "p1"}) or state)
            reloaded = JsonStore(path).snapshot()
            self.assertEqual(reloaded["profiles"][0]["id"], "p1")

    def test_contract_files_are_valid_json(self):
        root = Path(__file__).resolve().parents[1] / "contracts"
        for path in root.glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))

    def test_valid_workspace_contract(self):
        workspace = {
            "id": "workspace-test", "name": "Test",
            "grid": {"columns": 12},
            "widgets": [{"id": "widget-one", "type": "logs", "position": {"x": 0, "y": 0}, "size": {"w": 4, "h": 3}}]
        }
        self.assertEqual(validate_workspace(workspace), [])

    def test_workspace_rejects_duplicate_widget_ids(self):
        workspace = {
            "id": "workspace-test", "name": "Test", "grid": {"columns": 12},
            "widgets": [
                {"id": "widget-one", "type": "logs", "position": {"x": 0, "y": 0}, "size": {"w": 4, "h": 3}},
                {"id": "widget-one", "type": "api-health", "position": {"x": 4, "y": 0}, "size": {"w": 4, "h": 3}},
            ]
        }
        issues = validate_workspace(workspace)
        self.assertTrue(any("unique" in issue["message"].lower() for issue in issues))


if __name__ == "__main__":
    unittest.main()
