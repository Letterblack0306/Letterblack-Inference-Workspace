import unittest

from backend.contracts import validate_profile


def valid_profile():
    return {
        "id": "local-profile",
        "name": "Local profile",
        "description": "",
        "values": {"contextSize": 8192, "gpuLayers": 35, "batchSize": 512, "threads": 8, "parallel": 1, "flashAttention": True},
    }


class ProfileContractTests(unittest.TestCase):
    def test_profile_contract_accepts_complete_launch_values(self):
        self.assertEqual(validate_profile(valid_profile()), [])

    def test_profile_contract_rejects_missing_launch_value(self):
        profile = valid_profile()
        del profile["values"]["threads"]
        self.assertTrue(any(issue["field"] == "values.threads" for issue in validate_profile(profile)))


if __name__ == "__main__":
    unittest.main()
