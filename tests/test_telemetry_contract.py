import unittest
from unittest.mock import patch

from backend.runtime import controller_status


class TelemetryContractTests(unittest.TestCase):
    def test_controller_status_honors_explicit_timeout(self):
        machine = {"addresses": ["10.77.0.1"], "controller": {"scheme": "http", "port": 50053}}
        with patch("backend.runtime.http_json", return_value={"body": {"state": "ready"}}) as request:
            self.assertEqual(controller_status(machine, timeout=0.75), {"state": "ready"})
        request.assert_called_once_with("GET", "http://10.77.0.1:50053/status", timeout=0.75)


if __name__ == "__main__":
    unittest.main()
