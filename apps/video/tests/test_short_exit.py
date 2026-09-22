"""The outgoing battle HUD and incoming victory screen form one smooth exit."""
import inspect
import os
import subprocess
import unittest

import numpy as np
from PIL import Image
from overlay import shorts_story, shorts_battle


class ExitTests(unittest.TestCase):
    def test_cards_leave_outward_and_fade_without_modifying_source_cards(self):
        leave = getattr(shorts_battle, 'exit_cards', None)
        self.assertIsNotNone(leave)
        base = Image.new('RGBA', (200,80))
        cards = [Image.new('RGBA',(60,20),'red'),Image.new('RGBA',(60,20),'blue')]
        start = leave(base,cards,0,y=40)
        self.assertEqual(start.getpixel((20,50)),(255,0,0,255))
        middle = leave(base,cards,.5,y=40)
        self.assertEqual(middle.getpixel((5,50)),(255,0,0,128))
        self.assertEqual(middle.getpixel((194,50)),(0,0,255,128))
        self.assertEqual(middle.getpixel((60,50))[3],0)
        self.assertIsNone(leave(base,cards,1,y=40).getbbox())
        self.assertEqual(cards[0].getpixel((0,0)),(255,0,0,255))

    def test_background_sweeps_down_before_victory_details_fade_in(self):
        transition = getattr(shorts_story, 'sweep_to_victory', None)
        self.assertIsNotNone(transition)
        battle = Image.new('RGBA',(20,40),'green')
        background = Image.new('RGBA',battle.size,'red')
        content = Image.new('RGBA',battle.size)
        content.paste('blue',(5,5,15,35))
        self.assertEqual(transition(battle,background,content,0).tobytes(),battle.tobytes())
        middle = transition(battle,background,content,.4)
        self.assertEqual(middle.getpixel((10,5)),(255,0,0,255))
        self.assertEqual(middle.getpixel((10,35)),(0,128,0,255))
        fading = transition(battle,background,content,5/6)
        self.assertEqual(fading.getpixel((10,20)),(127,0,128,255))
        self.assertEqual(transition(battle,background,content,1).tobytes(),
                         Image.alpha_composite(background,content).tobytes())

    @unittest.skipUnless(os.environ.get('AOE2_GAME_DIR'),'Installed artwork smoke opt-in')
    def test_victory_foreground_has_no_opaque_background_or_old_stat_cards(self):
        from build_story_short import ending_background, game_panel
        self.assertIn('transparent',inspect.signature(ending_background).parameters)
        unit = {'unit':'Grenadier','stats':{'civ_name':'Jurchens'}}
        content = ending_background(unit,0,1,transparent=True)
        self.assertEqual(content.getpixel((30,1450))[3],0)
        self.assertEqual(Image.alpha_composite(game_panel((1080,1920)),content).tobytes(),
                         ending_background(unit,0,1).tobytes())

    @unittest.skipUnless(os.environ.get('AOE2_TEST_FFMPEG'),'FFmpeg smoke opt-in')
    def test_exit_audio_gap_preserves_combat_and_all_of_the_victory_cue(self):
        self.assertIn('transition',inspect.signature(shorts_story.story_audio_filter).parameters)
        graph = shorts_story.story_audio_filter(.2,4,9,intro=5,ending=5.4,
            input_label='0:a',victory_label='1:a',intro_label='2:a',transition=.8)
        command = [os.environ['AOE2_TEST_FFMPEG'],'-v','error']
        for frequency,duration in ((440,9),(880,5.5),(220,5)):
            command += ['-f','lavfi','-i',f'sine=frequency={frequency}:sample_rate=48000:duration={duration}']
        samples = np.frombuffer(subprocess.check_output(command+['-filter_complex',graph,
            '-map','[a]','-ac','1','-ar','48000','-f','f32le','pipe:1']),dtype='<f4')
        self.assertAlmostEqual(len(samples)/48000,15.2,places=3)
        self.assertEqual(float(abs(samples[9*48000:round(9.8*48000)]).max()),0)
        for start,frequency,phase in ((6,440,1.2),(10,880,.2),(14,880,4.2)):
            section = samples[start*48000:(start+1)*48000]
            expected = np.sin(2*np.pi*frequency*(np.arange(48000)/48000+phase))
            self.assertGreater(float(np.corrcoef(section,expected)[0,1]),.999)


if __name__ == '__main__':
    unittest.main()
