"""Observable timing for the longer, attack-sound-led Short preview."""
import inspect
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import numpy as np
from PIL import Image
from overlay import battle_end, shorts_story


class RevisionTimingTests(unittest.TestCase):
    def test_intro_speed_changes_pose_time_without_changing_default_victory_speed(self):
        self.assertIn('speed', inspect.signature(shorts_story.AttackAnimation.at).parameters)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'attack.gif'
            Image.new('RGBA',(8,8),'red').save(path,save_all=True,
                append_images=[Image.new('RGBA',(8,8),'blue')],duration=[100,100],loop=0)
            attack = shorts_story.AttackAnimation(path,(8,8))
            self.assertEqual(attack.at(.08).getpixel((0,0)),(255,0,0,255))
            self.assertEqual(attack.at(.08,speed=1.5).getpixel((0,0)),(0,0,255,255))
            self.assertEqual(attack.at(.15,speed=1.5).getpixel((0,0)),(255,0,0,255))

    def test_aftermath_adds_real_frames_but_never_reads_past_source(self):
        count = getattr(battle_end,'recorded_battle_frames',None)
        self.assertIsNotNone(count)
        self.assertEqual(count(.2,11.136,60,825),658)
        self.assertEqual(count(.2,11.136,60,825,aftermath=2),778)
        self.assertEqual(count(.2,11.136,60,825,aftermath=3),813)

    @unittest.skipUnless(os.environ.get('AOE2_TEST_FFMPEG') or shutil.which('ffmpeg'),'FFmpeg smoke opt-in')
    def test_dedicated_five_second_intro_keeps_aftermath_then_victory_aligned(self):
        self.assertIn('intro_label', inspect.signature(shorts_story.story_audio_filter).parameters)
        ffmpeg = os.environ.get('AOE2_TEST_FFMPEG') or shutil.which('ffmpeg')
        graph = shorts_story.story_audio_filter(.2,4,9,intro=5,ending=5,
            input_label='0:a',victory_label='1:a',intro_label='2:a')
        command = [ffmpeg,'-v','error']
        for frequency,duration in ((440,9),(880,5.5),(220,5)):
            command += ['-f','lavfi','-i',f'sine=frequency={frequency}:sample_rate=48000:duration={duration}']
        pcm = subprocess.check_output(command+['-filter_complex',graph,'-map','[a]',
            '-ac','1','-ar','48000','-f','f32le','pipe:1'])
        samples = np.frombuffer(pcm,dtype='<f4')
        self.assertAlmostEqual(len(samples)/48000,14,places=3)
        for start,frequency,phase in ((1,220,1),(6,440,1.2),(8,440,3.2),(9,880,0)):
            section = samples[start*48000:(start+1)*48000]
            expected = np.sin(2*np.pi*frequency*(np.arange(48000)/48000+phase))
            self.assertGreater(float(np.corrcoef(section,expected)[0,1]),.999)


if __name__ == '__main__':
    unittest.main()
