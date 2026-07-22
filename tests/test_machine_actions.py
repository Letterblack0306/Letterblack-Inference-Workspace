import json
import tempfile
import unittest
from pathlib import Path

from backend.machine_actions import machine_action_catalog
from backend.store import JsonStore


class MachineActionTests(unittest.TestCase):
    def test_catalog_is_local_json_with_connect_and_disconnect(self):
        actions = {item["id"]: item for item in machine_action_catalog()["actions"]}
        self.assertEqual(actions["connect"]["operation"], "set-enabled")
        self.assertTrue(actions["connect"]["enabled"])
        self.assertEqual(actions["disconnect"]["operation"], "set-enabled")
        self.assertFalse(actions["disconnect"]["enabled"])

    def test_existing_machine_gains_configurable_actions_without_changing_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps({"machines": [{
                "id": "worker-01", "name": "Worker 01", "addresses": ["192.168.1.155"],
                "controller": {"scheme": "http", "port": 1234}, "rpc": {"port": 50052, "enabled": True}
            }]}), encoding="utf-8")
            machine = JsonStore(path).snapshot()["machines"][0]
            self.assertEqual(machine["addresses"], ["192.168.1.155"])
            self.assertIn("disconnect", machine["actions"])


if __name__ == "__main__":
    unittest.main()
