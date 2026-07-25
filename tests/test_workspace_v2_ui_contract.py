from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WorkspaceV2UiContractTests(unittest.TestCase):
    def test_v2_assets_are_loaded_after_existing_frontend(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn('href="css/workspace-v2.css"', html)
        self.assertIn('src="js/workspace-v2.js"', html)
        self.assertLess(html.index('src="js/app.js"'), html.index('src="js/workspace-v2.js"'))

    def test_v2_layer_preserves_runtime_authority(self):
        script = (ROOT / "web" / "js" / "workspace-v2.js").read_text(encoding="utf-8")

        self.assertNotIn("fetch(", script)
        self.assertNotIn("/api/v1", script)
        self.assertIn("dispatchClick('#startSelectedModel')", script)
        self.assertIn("dispatchClick('#scanModelsBtn')", script)
        self.assertIn("dispatchClick('#sendChat')", script)

    def test_operator_interactions_are_persistent_and_keyboard_accessible(self):
        script = (ROOT / "web" / "js" / "workspace-v2.js").read_text(encoding="utf-8")

        for token in (
            "inspectorWidth",
            "inspectorCollapsed",
            "sidebarCollapsed",
            "localStorage.setItem",
            "aria-orientation",
            "Ctrl/Cmd+K",
            "event.key === 'Enter'",
            "event.key !== 'Escape'",
        ):
            self.assertIn(token, script)

    def test_responsive_operator_shell_contract_is_present(self):
        stylesheet = (ROOT / "web" / "css" / "workspace-v2.css").read_text(encoding="utf-8")

        for token in (
            "--v2-sidebar",
            "--chat-inspector-width",
            ".workspace-v2-resizer",
            "body.v2-sidebar-collapsed",
            "@media (max-width: 860px)",
            ".workspace-v2-command-overlay",
        ):
            self.assertIn(token, stylesheet)


if __name__ == "__main__":
    unittest.main()
