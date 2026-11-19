"""The correction must never drop unrelated recordings or escape its folder."""
import unittest
from pathlib import Path

from run_detailed_cavalier_retakes import replace_rows, safe_child


class ReplacementTests(unittest.TestCase):
    def test_only_mapped_rows_change_and_order_is_preserved(self):
        index = dict(matchups=[dict(jobId='other',value=1),dict(jobId='old',value=180)],finalVideo='keep')
        updated = replace_rows(index,[dict(oldJobId='old',jobId='new')],[dict(jobId='new',value=140)])
        self.assertEqual(updated['matchups'],[dict(jobId='other',value=1),dict(jobId='new',value=140)])
        self.assertEqual(updated['finalVideo'],'keep')
        self.assertEqual(index['matchups'][1]['value'],180)

    def test_missing_old_row_refuses_projection(self):
        with self.assertRaises(ValueError):
            replace_rows(dict(matchups=[]),[dict(oldJobId='old',jobId='new')],[dict(jobId='new')])

    def test_duplicate_new_identity_refuses_projection(self):
        with self.assertRaises(ValueError):
            replace_rows(dict(matchups=[dict(jobId='old'),dict(jobId='new')]),
                         [dict(oldJobId='old',jobId='new')],[dict(jobId='new')])

    def test_delete_paths_cannot_escape_run_folder(self):
        root=Path('C:/test/archive')
        for name in ('../unrelated.mp4','subdir/file.bin','C:/outside.mp4'):
            with self.assertRaises(ValueError):
                safe_child(root,dict(path=name))
        self.assertEqual(safe_child(root,dict(path='exact.mp4')),root/'exact.mp4')


if __name__ == '__main__':
    unittest.main()
