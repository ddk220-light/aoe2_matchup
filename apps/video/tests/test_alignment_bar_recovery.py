import unittest
import numpy as np
from overlay.auto_alignment import visible_bars

class HealthBarRecovery(unittest.TestCase):
    def test_colored_fill_recovers_outline_connected_to_sprite(self):
        frame=np.full((90,130,3),180,dtype=np.uint8)
        frame[8:20,20:90]=0
        frame[10:18,22:60]=(220,120,30)
        frame[18:70,50:100]=0  # Sprite joins the black outline below the fill.
        self.assertEqual(visible_bars(frame),[])
        found=visible_bars(frame,color_components=True)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['owner'],'2')
        self.assertAlmostEqual(found[0]['fraction'],38/66)

    def test_colored_unit_details_without_black_border_are_rejected(self):
        frame=np.full((90,130,3),180,dtype=np.uint8)
        frame[10:18,22:60]=(220,120,30)
        self.assertEqual(visible_bars(frame,color_components=True),[])

if __name__=='__main__':unittest.main()
