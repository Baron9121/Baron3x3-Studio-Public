from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import model_eval


class ModelEvalTests(unittest.TestCase):
    def test_paths_keep_eval_outside_active_job(self):
        result = model_eval.paths("sample")
        self.assertIn("analysis/evals/sample-director", str(result["directory"]))
        self.assertNotIn("instructions/jobs", str(result["candidate"]))

    def test_paid_run_rejects_missing_or_different_budget_before_key_access(self):
        with patch.object(model_eval, "paths") as mocked_paths:
            mocked_paths.return_value = {"input": Path("missing"), "manifest": Path("missing")}
            with self.assertRaisesRegex(RuntimeError, "0.03 USD"):
                model_eval.run("sample", None)
            with self.assertRaisesRegex(RuntimeError, "0.03 USD"):
                model_eval.run("sample", 0.04)

    def test_atomic_json_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.json"
            model_eval.write_json(path, {"tekst": "Bordeaux"})
            self.assertEqual(model_eval.read_json(path), {"tekst": "Bordeaux"})

    def test_rubric_weights_sum_to_one_hundred(self):
        self.assertEqual(sum(item["weight"] for item in model_eval.rubric()["criteria"]), 100)


if __name__ == "__main__":
    unittest.main()
