import unittest
from continue_deferred_retakes import ready


class RetakeHandoff(unittest.TestCase):
    def test_requires_main_completion_and_own_export_completion(self):
        self.assertFalse(ready({'state':'CAPTURING'},{'state':'COMPLETE'},False))
        self.assertFalse(ready({'state':'ALL_CAPTURES_FINISHED'},
                               {'state':'FINALIZING','captureReleased':True},False))
        self.assertTrue(ready({'state':'ALL_CAPTURES_FINISHED'},
                              {'state':'COMPLETE_WITH_FAILURES'},False))

    def test_thermal_pause_blocks_even_finished_campaign(self):
        self.assertFalse(ready({'state':'ALL_CAPTURES_FINISHED'},{'state':'COMPLETE'},True))


if __name__=='__main__':unittest.main()
