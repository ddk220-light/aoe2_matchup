"""One attack cycle per unit, in sequence, using the longest native voice."""
import inspect
import os
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from overlay import shorts_story


class IntroSequenceTests(unittest.TestCase):
    def test_battle_start_tracks_animation_duration_and_speed_with_one_second_gap(self):
        duration = getattr(shorts_story,'sequential_intro_seconds',None)
        self.assertIsNotNone(duration)
        with tempfile.TemporaryDirectory() as folder:
            attacks = []
            for index,ms in enumerate((500,800)):
                path = Path(folder)/f'attack-{index}.gif'
                frames = [Image.new('RGBA',(8,8),c) for c in ('red','blue','green')]
                frames[0].save(path,save_all=True,append_images=frames[1:],duration=ms,loop=0)
                attacks.append(shorts_story.AttackAnimation(path,(8,8)))
            self.assertAlmostEqual(duration([attacks[0],attacks[0]],[.25,1.45],speed=1.5),3.45)
            self.assertAlmostEqual(duration(attacks,[.25,1.45],speed=1.5),4.05)
            self.assertAlmostEqual(duration(attacks,[.25,1.45],speed=1),4.85)

    def test_longest_voice_is_selected_within_the_requested_civilization(self):
        choose = getattr(shorts_story,'longest_command_voice',None)
        self.assertIsNotNone(choose)
        variants = [dict(civilization='Jurchens',durationSeconds=.47,mediaId=11),
                    dict(civilization='Goths',durationSeconds=.78,mediaId=22),
                    dict(civilization='Jurchens',durationSeconds=.41,mediaId=33)]
        self.assertEqual(choose(variants,'Jurchens')['mediaId'],11)
        self.assertEqual(choose(variants,'Goths')['mediaId'],22)

    def test_one_shot_holds_first_before_start_and_last_after_one_cycle(self):
        self.assertIn('loop',inspect.signature(shorts_story.AttackAnimation.at).parameters)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'attack.gif'
            frames = [Image.new('RGBA',(8,8),c) for c in ('red','blue','green')]
            frames[0].save(path,save_all=True,append_images=frames[1:],duration=100,loop=0)
            attack = shorts_story.AttackAnimation(path,(8,8))
            for t,color in ((-.3,(255,0,0,255)),(.08,(0,0,255,255)),
                            (.2,(0,128,0,255)),(3,(0,128,0,255))):
                self.assertEqual(attack.at(t,speed=1.5,loop=False).getpixel((0,0)),color)
            self.assertEqual(attack.at(.32).getpixel((0,0)),(255,0,0,255))

    @unittest.skipUnless(os.environ.get('AOE2_GAME_DIR'),'Renderer smoke opt-in')
    def test_only_one_unit_animates_at_a_time_and_both_hold_before_opening(self):
        import build_story_short
        compose = getattr(build_story_short,'intro_frame',None)
        self.assertIsNotNone(compose)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'attack.gif'
            frames = [Image.new('RGBA',(8,8),c) for c in ('red','blue','green')]
            frames[0].save(path,save_all=True,append_images=frames[1:],duration=100,loop=0)
            attacks = [shorts_story.AttackAnimation(path,(8,8)) for _ in range(2)]
            base = Image.new('RGBA',(1080,1920),'black')
            for t,top,bottom in ((.36,(0,0,255,255),(255,0,0,255)),
                                 (2.6,(0,128,0,255),(0,0,255,255)),
                                 (4,(0,128,0,255),(0,128,0,255))):
                im = compose(base,attacks,t,base,intro_seconds=5,speed=1,
                             attack_starts=(.25,2.45),fps=60)
                self.assertEqual(im.getpixel((540,515)),top)
                self.assertEqual(im.getpixel((540,1380)),bottom)


if __name__ == '__main__':
    unittest.main()
