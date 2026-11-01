import gzip
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

from civ_reviewed_phase import digest, load_reviewed_phase


class ReviewedPhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'adaptive/phases').mkdir(parents=True)
        (self.root / 'latest-inference').mkdir()
        self.write('adaptive/state.json', {'completedPhases': ['025']})
        self.write('adaptive/phases/025.json', {'pairKeys': ['a|b', 'c|d']})
        self.review = {'status': 'passed', 'pairs': 2, 'blockedPairs': [],
                       'missingSeeds': 0, 'inferenceHash': 'reviewed-build'}
        self.write('adaptive/phases/025-review.json', self.review)
        self.rows = [{'pairKey': key, 'evidenceType': 'observed', 'outcome': 'a_win'}
                     for key in ('a|b', 'c|d')]
        self.snapshot()

    def write(self, path, value):
        (self.root / path).write_text(json.dumps(value))

    def snapshot(self):
        outputs = []
        for name, content in (
                ('profile-matchups.jsonl.gz', gzip.compress(
                    '\n'.join(json.dumps(row) for row in self.rows).encode())),
                ('variant-profiles.json', b'[]')):
            (self.root / 'latest-inference' / name).write_bytes(content)
            outputs.append({'file': name, 'sha256': digest(content), 'rows': len(self.rows)})
        self.write('latest-inference/manifest.json',
                   {'buildHash': 'reviewed-build', 'outputs': outputs})

    def test_complete_review_returns_all_planned_observations(self):
        rows, _, provenance = load_reviewed_phase(self.root, 25)
        self.assertEqual(len(rows), 2)
        self.assertEqual(provenance['missingSeeds'], 0)

    def test_unreviewed_phase_cannot_report_zero_error_success(self):
        with self.assertRaisesRegex(ValueError, 'no completed review'):
            load_reviewed_phase(self.root, 26)

    def test_changed_output_hash_rejected(self):
        (self.root / 'latest-inference/variant-profiles.json').write_bytes(b'[{}]')
        with self.assertRaisesRegex(ValueError, 'manifest hash'):
            load_reviewed_phase(self.root, 25)

    def test_different_review_snapshot_rejected(self):
        self.review['inferenceHash'] = 'other-build'
        self.write('adaptive/phases/025-review.json', self.review)
        with self.assertRaisesRegex(ValueError, 'snapshot does not match'):
            load_reviewed_phase(self.root, 25)

    def test_missing_planned_observation_rejected_even_with_valid_hash(self):
        self.rows.pop()
        self.snapshot()
        with self.assertRaisesRegex(ValueError, 'missing planned pair'):
            load_reviewed_phase(self.root, 25)

    def test_blocked_pair_stays_excluded_and_explicit(self):
        self.review.update(status='complete_with_blocked', blockedPairs=['c|d'], missingSeeds=1)
        self.write('adaptive/phases/025-review.json', self.review)
        self.rows[1].update(evidenceType='none', outcome='unresolved')
        self.snapshot()
        rows, _, provenance = load_reviewed_phase(self.root, 25)
        self.assertEqual([row['pairKey'] for row in rows], ['a|b'])
        self.assertEqual(provenance['blockedPairs'], ['c|d'])
        self.assertEqual(provenance['missingSeeds'], 1)

    def test_classified_blocked_pair_rejected(self):
        self.review.update(status='complete_with_blocked', blockedPairs=['c|d'], missingSeeds=1)
        self.write('adaptive/phases/025-review.json', self.review)
        with self.assertRaisesRegex(ValueError, 'blocked pair has been classified'):
            load_reviewed_phase(self.root, 25)

    def test_candidate_report_cannot_hide_a_blocked_prediction(self):
        self.review.update(status='complete_with_blocked', blockedPairs=['c|d'], missingSeeds=1)
        self.write('adaptive/phases/025-review.json', self.review)
        self.rows[1].update(evidenceType='none', outcome='unresolved')
        self.snapshot()
        predictions = self.root / 'predictions.jsonl.gz'
        predictions.write_bytes(gzip.compress('\n'.join(json.dumps({
            'pairKey': key, 'family': 'test', 'predictedOutcome': 'a_win',
            'supportingMethods': {'test': {}}}) for key in ('a|b', 'c|d')).encode()))
        output = self.root / 'validation.json'
        subprocess.run([sys.executable, str(Path(__file__).with_name('validate_civ_candidate_pool.py')),
            '--campaign', str(self.root), '--phase', '25', '--predictions', str(predictions),
            '--output', str(output)], check=True, capture_output=True)
        report = json.loads(output.read_text())
        self.assertEqual(report['selected'], 1)
        self.assertEqual(report['plannedCandidatePairs'], 2)
        self.assertEqual(report['blockedCandidatePairs'], ['c|d'])
        self.assertFalse(report['completeForPlannedCandidates'])


if __name__ == '__main__':
    unittest.main()
