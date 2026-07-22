import json
import tempfile
import unittest
from pathlib import Path

from backend.store import JsonStore


class StoreMigrationTests(unittest.TestCase):
    def test_removes_legacy_raw_gguf_metadata(self):
        state = {
            "schemaVersion": 6,
            "models": [{"id": "model-1", "metadata": {"architecture": "llama", "raw": {"tokenizer.ggml.tokens": ["a"] * 512}}}],
            "jobs": [{"result": {"models": [{"metadata": {"raw": {"tokenizer.ggml.tokens": ["a"] * 512}}}]}}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps(state), encoding="utf-8")
            snapshot = JsonStore(path).snapshot()
            persisted = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["schemaVersion"], 7)
        self.assertNotIn("raw", snapshot["models"][0]["metadata"])
        self.assertNotIn("raw", persisted["models"][0]["metadata"])
        self.assertNotIn("raw", snapshot["jobs"][0]["result"]["models"][0]["metadata"])


if __name__ == "__main__":
    unittest.main()
