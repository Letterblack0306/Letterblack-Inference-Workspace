from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TruthfulUiTests(unittest.TestCase):
    def test_only_current_ui_controller_is_loaded(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn('src="js/app.js"', html)

        self.assertNotIn('src="js/ux.js"', html)
        self.assertNotIn('src="js/state.js"', html)
        self.assertNotIn('src="js/phase2.js"', html)
        self.assertNotIn('src="js/phase6.js"', html)
        self.assertNotIn('src="js/truthful-ui.js"', html)

    def test_api_client_exists(self):
        api_path = ROOT / "web" / "js" / "api.js"
        self.assertTrue(api_path.exists())

        api = api_path.read_text(encoding="utf-8")

        required_routes = (
            "/capabilities",
            "/system/status",
            "/machines",
            "/models",
            "/models/scan",
            "/profiles",
            "/runtime/preflight",
            "/runtime/launch",
            "/runtime/stop",
            "/jobs",
            "/telemetry",
            "/logs",
            "/requests",
            "/gateway/status",
            "/workspaces",
            "/extensions",
            "/actions",
            "/endpoints",
        )

        for route in required_routes:
            self.assertIn(route, api)

    def test_known_prototype_evidence_is_not_in_active_ui(self):
        active_files = (
            ROOT / "web" / "index.html",
            ROOT / "web" / "js" / "app.js",
            ROOT / "web" / "js" / "api.js",
        )

        active_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in active_files
        )

        forbidden_markers = (
            "All required evidence checks passed",
            "Connection verified",
            "Connection evidence recorded",
            "#R7F2",
            "#R7F1",
            "#R7F0",
            "6.1 tok/s",
            "14.2 / 16 GB",
            "1.2 ms median latency",
            "defaultMachines",
            "modelRows",
            "simulated-starting",
            "simulate_job(",
        )

        for marker in forbidden_markers:
            self.assertNotIn(marker, active_text)

    def test_operational_unknown_states_exist(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn("Host unknown", html)
        self.assertIn("Machines unknown", html)
        self.assertIn("OpenAI unknown", html)
        self.assertIn("Ollama unknown", html)
        self.assertIn("Loading runtime evidence", html)

    def test_only_one_application_module_is_loaded(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        application_scripts = [
            line.strip()
            for line in html.splitlines()
            if '<script type="module"' in line
        ]

        self.assertEqual(
            application_scripts,
            ['<script type="module" src="js/app.js"></script>'],
        )


if __name__ == "__main__":
    unittest.main()