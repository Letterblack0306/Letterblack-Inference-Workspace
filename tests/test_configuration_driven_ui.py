from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.store import JsonStore


ROOT = Path(__file__).resolve().parents[1]


class ConfigurationDrivenUiTests(unittest.TestCase):
    def test_fresh_state_does_not_contain_a_machine_specific_model_path(self):
        with TemporaryDirectory() as directory:
            state = JsonStore(Path(directory) / "state.json").snapshot()
        self.assertEqual(state["modelSources"], [])

    def test_models_page_does_not_suggest_a_machine_specific_path(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('placeholder="Absolute folder path containing GGUF files"', html)
        self.assertNotIn("Z:\\\\LLM_Proxy\\\\Models", html)

    def test_source_scan_uses_the_backend_sources_contract(self):
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        server = (ROOT / "backend" / "server.py").read_text(encoding="utf-8")
        self.assertIn("scanModels({sources:[sources[Number(button.dataset.index)]]})", app)
        self.assertIn('body.get("sources")', server)

    def test_machine_dialog_can_disable_rpc_for_non_rpc_systems(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('name="rpcEnabled"', html)
        self.assertIn("enabled:form.elements.rpcEnabled.checked", app)


if __name__ == "__main__":
    unittest.main()
