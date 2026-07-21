from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ExtensionsUiContractTests(unittest.TestCase):
    def test_extensions_surface_is_loaded(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="extensions"', html)
        self.assertIn('data-page-view="extensions"', html)
        self.assertIn('src="js/extensions.js"', html)
        self.assertIn('href="css/extensions.css"', html)

    def test_extensions_controls_are_present(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        for element_id in (
            "importExtensionBtn",
            "extensionList",
            "createActionBtn",
            "actionList",
            "createEndpointBtn",
            "endpointList",
            "extensionImportDialog",
            "actionDialog",
            "endpointDialog",
        ):
            self.assertIn(f'id="{element_id}"', html)

    def test_frontend_routes_match_openapi_contract(self):
        script = (ROOT / "web" / "js" / "extensions.js").read_text(encoding="utf-8")
        openapi = (ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8")
        for route in ("/extensions", "/actions", "/endpoints"):
            self.assertIn(route, script)
            self.assertIn(f'"/api/v1{route}', openapi)

    def test_action_lifecycle_is_wired(self):
        script = (ROOT / "web" / "js" / "extensions.js").read_text(encoding="utf-8")
        for token in (
            "action-edit",
            "action-toggle",
            "openActionDialog",
            "saveAction",
            "method:editing ? 'PUT' : 'POST'",
            "/execute",
            "method:'DELETE'",
        ):
            self.assertIn(token, script)

    def test_endpoint_lifecycle_is_wired(self):
        script = (ROOT / "web" / "js" / "extensions.js").read_text(encoding="utf-8")
        for token in (
            "endpoint-edit",
            "endpoint-toggle",
            "openEndpointDialog",
            "saveEndpoint",
            "method:editing ? 'PUT' : 'POST'",
            "/test",
            "method:'DELETE'",
        ):
            self.assertIn(token, script)

    def test_security_boundary_is_visible(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("No executable extension code is loaded", html)
        self.assertIn("Executable code, shell commands, scripts", html)


if __name__ == "__main__":
    unittest.main()
