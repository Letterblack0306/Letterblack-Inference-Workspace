from __future__ import annotations

import unittest

from backend.cline_provider import (
    ClineProviderError,
    build_guarded_prompt,
    classify_failure,
    validate_evidence_output,
    validate_profile,
)


class ClineProviderContractTests(unittest.TestCase):
    def test_guarded_prompt_binds_workspace_and_evidence_contract(self):
        prompt = build_guarded_prompt("Find the runtime bug.", r"C:\workspace")
        self.assertIn("Use the workspace as the only source of truth.", prompt)
        self.assertIn("Never invent files", prompt)
        self.assertIn("WORKSPACE ROOT:", prompt)
        self.assertIn("Find the runtime bug.", prompt)
        self.assertIn("End with an EVIDENCE section", prompt)

    def test_evidence_gate_accepts_file_backed_result(self):
        validate_evidence_output(
            "VERIFIED\nbackend/server.py: route exists.\n"
            "EVIDENCE\nInspected backend/server.py and ran python -m py_compile."
        )

    def test_evidence_gate_accepts_conservative_unknown(self):
        validate_evidence_output("UNKNOWN: insufficient evidence to make a repository claim.")

    def test_evidence_gate_rejects_unsupported_confident_result(self):
        with self.assertRaises(ClineProviderError) as raised:
            validate_evidence_output("Everything is fixed and all tests pass.")
        self.assertEqual(raised.exception.code, "CLINE_EVIDENCE_INSUFFICIENT")

    def test_profile_rejects_credential_material(self):
        issues = validate_profile(
            {
                "id": "profile-a",
                "configDirectory": r"C:\cline-a",
                "provider": "cline",
                "freeModels": ["free-model"],
                "apiKey": "secret",
            }
        )
        self.assertTrue(any("Credential material" in item["message"] for item in issues))

    def test_retryable_failures_are_classified(self):
        self.assertEqual(classify_failure("HTTP 429 too many requests"), "CLOUD_RATE_LIMITED")
        self.assertEqual(classify_failure("usage limit reached"), "CLOUD_QUOTA_EXHAUSTED")
        self.assertEqual(classify_failure("expired token"), "CLOUD_AUTH_EXPIRED")


if __name__ == "__main__":
    unittest.main()
