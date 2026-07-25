import unittest

from backend.cline_provider import classify_failure, status, validate_profile


class ClineProviderTests(unittest.TestCase):
    def valid_profile(self):
        return {
            "id": "cline-profile-a",
            "configDirectory": "C:\\Users\\operator\\.cline-liw\\profile-a\\settings",
            "provider": "cline",
            "freeModels": ["free-model-1"],
            "enabled": True,
            "priority": 10,
            "timeoutSec": 90,
        }

    def test_profile_never_accepts_credential_material(self):
        profile = self.valid_profile()
        profile["token"] = "must-not-be-stored"
        self.assertTrue(validate_profile(profile))

    def test_profile_requires_explicit_free_model_registry(self):
        profile = self.valid_profile()
        profile["freeModels"] = []
        self.assertTrue(any(issue["path"] == "freeModels" for issue in validate_profile(profile)))

    def test_only_provider_conditions_are_classified_as_fallback_candidates(self):
        self.assertEqual(classify_failure("HTTP 429 rate limit"), "CLOUD_RATE_LIMITED")
        self.assertEqual(classify_failure("workspace failed to open"), "CLINE_EXECUTION_FAILED")

    def test_status_does_not_include_credentials(self):
        result = status([self.valid_profile()])
        profile = result["profiles"][0]
        self.assertNotIn("token", profile)
        self.assertEqual(profile["authentication"], "unknown")


if __name__ == "__main__":
    unittest.main()
