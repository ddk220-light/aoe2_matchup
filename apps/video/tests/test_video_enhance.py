"""Optional real-model smoke check; set AOE2_UPSCALE_MODEL to a local weight file."""
import os
import unittest

import numpy as np


@unittest.skipUnless(os.environ.get('AOE2_UPSCALE_MODEL'), 'Local GPU model not configured')
class LocalUpscalerTests(unittest.TestCase):
    def test_model_preserves_frame_geometry_and_color_order(self):
        from overlay.video_enhance import LocalUpscaler
        frame = np.full((32, 48, 3), (30, 60, 180), dtype=np.uint8)
        frame[8:24, 12:36] = (180, 60, 30)
        original = frame.copy()
        result = LocalUpscaler(os.environ['AOE2_UPSCALE_MODEL'])(frame)
        self.assertEqual(result.shape, frame.shape)
        self.assertEqual(result.dtype, np.uint8)
        np.testing.assert_array_equal(frame, original)
        self.assertGreater(int(result[16, 24, 0]), int(result[16, 24, 2]))
        self.assertGreater(int(result[2, 2, 2]), int(result[2, 2, 0]))
        self.assertFalse(np.array_equal(result, original), 'Model output was not applied')


if __name__ == '__main__':
    unittest.main()
