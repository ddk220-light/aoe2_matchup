"""Safety checks for repeated-trial delivery and redundant MOV retirement."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import copy_norse_standard_to_share as delivery
from compact_recording_archive import digest
from run_champi_comparison_capture import save


class DeliveryTests(unittest.TestCase):
    def test_trial_names_include_condition_and_iteration(self):
        original = dict(name='test', files={'battle.mp4': {}, 'frames.bin': {}})
        names = set()
        for setting in ('with_hussars', 'no_buffer'):
            for iteration in range(1, 6):
                item = dict(jobId='job', iteration=iteration, opponentIndex=1,
                            bufferSetting=setting, bufferComparisonApplicable=True, reused=False)
                names.add(delivery.repeated_row(copy.deepcopy(original), item)['name'])
        self.assertEqual(len(names), 10)

    def fixture(self, base):
        source = base / 'runs/job/live/run_001'
        source.mkdir(parents=True)
        dest = base / 'archive'
        dest.mkdir()
        files = {}
        for key, name in [('video', 'raw.mov'), ('battleVideo', 'battle.mp4'),
                          ('frames', 'frames.bin'), ('battleHp', 'battle.hp.json')]:
            path = source / name
            path.write_bytes(name.encode())
            files[key] = dict(path=name, bytes=path.stat().st_size, sha256=digest(path))
        save(source / 'recording.json', dict(files=files))
        archived = {}
        for key in ('battleVideo', 'frames'):
            info = files[key]
            (dest / info['path']).write_bytes((source / info['path']).read_bytes())
            archived[key] = info
        save(dest / 'run.json', dict(matchups=[dict(jobId='job', files=archived)]))
        state = dict(packages={'unit': dict(state='COMPLETE', identity={'destination': str(dest)},
                     indexSha256=digest(dest / 'run.json'))})
        return source, dest, state

    def run_retirement(self, base, source, state):
        with patch.object(delivery, 'RUNS', base / 'runs'), patch.object(delivery, 'guard', lambda: None):
            delivery.retire_untrimmed({'folder': 'unit'}, [({'jobId': 'job'}, source)], state, base / 'receipt.json')

    def test_retirement_preserves_battle_frames_metadata_and_is_resumable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            source, dest, state = self.fixture(base)
            self.run_retirement(base, source, state)
            self.assertFalse((source / 'raw.mov').exists())
            for name in ('battle.mp4', 'frames.bin', 'battle.hp.json', 'recording.json'):
                self.assertTrue((source / name).is_file())
            self.assertTrue((dest / 'battle.mp4').is_file())
            self.run_retirement(base, source, state)
            self.assertEqual(state['packages']['unit']['retiredUntrimmed']['job']['state'], 'REMOVED')

    def test_remote_corruption_preserves_untrimmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            source, dest, state = self.fixture(base)
            (dest / 'frames.bin').write_bytes(b'corrupt')
            with self.assertRaises(RuntimeError):
                self.run_retirement(base, source, state)
            self.assertTrue((source / 'raw.mov').is_file())

    def test_escaped_source_preserves_untrimmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            source, _, state = self.fixture(base)
            bundle = delivery.read(source / 'recording.json')
            bundle['files']['video']['path'] = '../../outside.mov'
            save(source / 'recording.json', bundle)
            with self.assertRaises(ValueError):
                self.run_retirement(base, source, state)
            self.assertTrue((source / 'raw.mov').is_file())


if __name__ == '__main__':
    unittest.main()
