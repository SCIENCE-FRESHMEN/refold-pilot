import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[2] / "bin"
sys.path.insert(0, str(BIN))
import evaluate_refold_selection as evaluation


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pool = [{"stable_id": str(n), "target_id": "target", "file_sha256": str(n),
                      "candidate": f"candidate_{n}.pdb", "binder_sequence": "A" * (n + 1),
                      "pae_interaction": float(n), "plddt_binder": 90.0} for n in range(4)]
        self.manifest = {"candidates": self.pool, "rejected": [], "input_count": 4}
        self.outcomes = self.root / "outcomes.tsv"
        self.outcomes.write_text("stable_id\tquality_pass\trefold_seconds\n0\t1\t2\n1\t0\t3\n2\t1\t4\n3\t0\t5\n")

    def tearDown(self):
        self.temp.cleanup()

    def test_known_frozen_pool_metrics(self):
        labels = evaluation.read_labels(self.outcomes, {str(n) for n in range(4)})
        rows = evaluation.evaluate(self.manifest, labels, [2], [0])
        score = next(row for row in rows if row["policy"] == "score")
        self.assertEqual(score["selected_positive_count"], 1)
        self.assertEqual(score["reference_recall"], 0.5)
        self.assertEqual(score["selected_precision"], 0.5)
        self.assertEqual(score["candidate_refold_fraction"], 0.5)
        self.assertEqual(score["selected_recorded_refold_seconds"], 5)

    def test_missing_duplicate_unknown_and_nonfinite_outcomes_fail(self):
        original = self.outcomes.read_text()
        for text in (original.rsplit("3\t", 1)[0], original + "0\t1\t2\n",
                     original + "unknown\t1\t2\n", original.replace("0\t1\t2", "0\t1\tnan")):
            self.outcomes.write_text(text)
            with self.assertRaises(ValueError):
                evaluation.read_labels(self.outcomes, {str(n) for n in range(4)})

    def test_missing_pre_scores_report_budget_shortfall(self):
        self.pool[0]["pae_interaction"] = None
        labels = evaluation.read_labels(self.outcomes, {str(n) for n in range(4)})
        rows = evaluation.evaluate(self.manifest, labels, [4], [0])
        self.assertEqual(next(x for x in rows if x["policy"] == "score")["budget_shortfall"], 1)
        self.assertEqual(next(x for x in rows if x["policy"] == "hash")["budget_shortfall"], 0)

    def test_unknown_duration_and_zero_budget_are_not_fabricated(self):
        labels = evaluation.read_labels(self.outcomes, {str(n) for n in range(4)})
        labels["0"]["refold_seconds"] = None
        rows = evaluation.evaluate(self.manifest, labels, [0, 4], [0])
        self.assertTrue(all(x["selected_precision"] is None for x in rows if x["budget"] == 0))
        self.assertTrue(all(x["selected_recorded_refold_seconds"] is None for x in rows if x["budget"] == 4))

    def test_cli_labels_synthetic_and_refuses_overwrite(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps(self.manifest))
        output = self.root / "result.json"
        command = [sys.executable, str(BIN / "evaluate_refold_selection.py"), "--manifest", str(manifest),
                   "--outcomes", str(self.outcomes), "--label-kind", "synthetic", "--output", str(output)]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(json.loads(output.read_text())["label_kind"], "synthetic")
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
