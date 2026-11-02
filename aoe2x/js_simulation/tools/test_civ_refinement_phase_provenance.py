import json
from pathlib import Path
import tempfile
import unittest

from audit_civ_common_c_refinements import phase_provenance, sha


class PhaseProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        (self.source / "adaptive/phases").mkdir(parents=True)
        (self.source / "latest-inference").mkdir()
        self.write("adaptive/state.json", {"completedPhases": ["047", "048"]})
        self.write("adaptive/phases/048-review.json", {"status": "passed"})
        self.snapshot(48)

    def write(self, name, value):
        (self.source / name).write_text(json.dumps(value))

    def snapshot(self, phase):
        self.write("latest-inference/manifest.json", {"sourceFiles": [
            {"path": f"campaign/adaptive/runs/{phase:03d}.jsonl"}]})

    def test_review_without_new_eligible_cases_keeps_its_own_phase(self):
        result = phase_provenance(self.source, 48, 47)
        self.assertEqual(result["sourcePhase"], 48)
        self.assertEqual(result["latestEligibleObservationPhase"], 47)
        self.assertEqual(result["sourceReviewSha256"], sha(
            self.source / "adaptive/phases/048-review.json"))

    def test_empty_eligible_set_still_has_reviewed_snapshot_provenance(self):
        result = phase_provenance(self.source, 48, None)
        self.assertEqual(result["sourcePhase"], 48)
        self.assertIsNone(result["latestEligibleObservationPhase"])

    def test_unreviewed_or_future_observations_are_rejected(self):
        for phase, eligible in [(49, 47), (48, 49)]:
            with self.subTest(phase=phase, eligible=eligible), self.assertRaises(AssertionError):
                phase_provenance(self.source, phase, eligible)

    def test_stale_or_future_inference_snapshots_are_rejected(self):
        for snapshot in [47, 49]:
            with self.subTest(snapshot=snapshot):
                self.snapshot(snapshot)
                with self.assertRaises(AssertionError):
                    phase_provenance(self.source, 48, 47)


if __name__ == "__main__":
    unittest.main()
