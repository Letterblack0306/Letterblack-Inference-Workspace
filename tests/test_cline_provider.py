from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.cline_provider import (
    ClineProviderError,
    build_guarded_prompt,
    classify_failure,
    validate_evidence_output,
    validate_profile,
    validate_workspace_root,
)


class ClineProviderContractTests(unittest.TestCase):
    def test_guarded_prompt_binds_workspace_and_evidence_contract(self):
        with tempfile.TemporaryDirectory() as root:
            prompt = build_guarded_prompt("Find the runtime bug.", root)
            self.assertIn("approved workspace root", prompt)
            self.assertIn("Never invent files", prompt)
            self.assertIn("WORKSPACE ROOT:", prompt)
            self.assertIn("Find the runtime bug.", prompt)
            self.assertIn("End with an EVIDENCE section", prompt)

    def test_workspace_root_accepts_registered_root(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(validate_workspace_root(root, [root]), str(Path(root).resolve()))

    def test_workspace_root_rejects_outside_path(self):
        with tempfile.TemporaryDirectory() as approved, tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(ClineProviderError) as raised:
                validate_workspace_root(outside, [approved])
            self.assertEqual(raised.exception.code, "CLINE_WORKSPACE_NOT_APPROVED")

    def test_evidence_gate_accepts_existing_workspace_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "backend", "server.py")
            path.parent.mkdir()
            path.write_text("pass\n", encoding="utf-8")
            result = validate_evidence_output(
                "VERIFIED\nEVIDENCE\nInspected backend/server.py.", root
            )
            self.assertEqual(result, ["backend/server.py"])

    def test_evidence_gate_rejects_unknown_without_real_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ClineProviderError) as raised:
                validate_evidence_output("UNKNOWN: insufficient evidence.", root)
            self.assertEqual(raised.exception.code, "CLINE_EVIDENCE_INSUFFICIENT")

    def test_evidence_gate_rejects_nonexistent_path(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ClineProviderError) as raised:
                validate_evidence_output("EVIDENCE\nInspected backend/missing.py.", root)
            self.assertEqual(raised.exception.code, "CLINE_EVIDENCE_INVALID")

    def test_profile_rejects_credential_material(self):
        issues = validate_profile({
            "id": "profile-a",
            "configDirectory": r"C:\cline-a",
            "provider": "cline",
            "freeModels": ["free-model"],
            "apiKey": "secret",
        })
        self.assertTrue(any("Credential material" in item["message"] for item in issues))

    def test_retryable_failures_are_classified(self):
        self.assertEqual(classify_failure("HTTP 429 too many requests"), "CLOUD_RATE_LIMITED")
        self.assertEqual(classify_failure("usage limit reached"), "CLOUD_QUOTA_EXHAUSTED")
        self.assertEqual(classify_failure("expired token"), "CLOUD_AUTH_EXPIRED")


if __name__ == "__main__":
    unittest.main()
