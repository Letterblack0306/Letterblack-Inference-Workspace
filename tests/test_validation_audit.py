from pathlib import Path
import json
import tempfile
import time
import unittest

from backend.validation_audit import ValidationAuditStore


class ValidationAuditStoreTests(unittest.TestCase):
    def test_append_redacts_secrets_and_preserves_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ValidationAuditStore(Path(temp) / "audit" / "runs.jsonl")
            started = time.time() - 0.25
            run = store.append(
                area="provider.health",
                test_type="authenticated-model-list",
                result="pass",
                started_at=started,
                target="http://127.0.0.1:1234/v1/models?api_key=secret-value",
                config_snapshot={"api_key": "secret-value", "model": "qwen"},
                request={"headers": {"Authorization": "Bearer abc.def"}},
                response_status=200,
                metrics={"latency_ms": 21, "tokens_per_second": 18.4},
                evidence={"body": "Bearer should-not-survive"},
            )

            self.assertEqual(run["result"], "pass")
            self.assertEqual(run["config_snapshot"]["api_key"], "[REDACTED]")
            self.assertIn("[REDACTED]", run["target"])
            self.assertEqual(run["request"]["headers"]["Authorization"], "[REDACTED]")
            self.assertEqual(run["metrics"]["tokens_per_second"], 18.4)
            self.assertGreaterEqual(run["duration_ms"], 0)

    def test_filter_and_export(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "runs.jsonl"
            store = ValidationAuditStore(path)
            now = time.time()
            first = store.append(
                area="gateway.openai",
                test_type="compatibility",
                result="pass",
                started_at=now,
                finished_at=now + 0.1,
            )
            store.append(
                area="gateway.ollama",
                test_type="compatibility",
                result="fail",
                started_at=now,
                finished_at=now + 0.2,
                retest_of=first["run_id"],
            )

            passed = list(store.iter_runs(result="pass"))
            self.assertEqual(len(passed), 1)
            self.assertEqual(passed[0]["area"], "gateway.openai")

            destination = Path(temp) / "export.json"
            store.export_json(destination, test_type="compatibility")
            payload = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(payload["schemaVersion"], 1)
            self.assertEqual(len(payload["runs"]), 2)

    def test_invalid_result_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ValidationAuditStore(Path(temp) / "runs.jsonl")
            with self.assertRaises(ValueError):
                store.append(
                    area="network.direct-link",
                    test_type="latency",
                    result="successful",
                    started_at=time.time(),
                )


if __name__ == "__main__":
    unittest.main()
