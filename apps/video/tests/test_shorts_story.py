"""Observable story transitions and perspective, without game/GPU dependencies."""
import tempfile
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from overlay.shorts_story import AttackAnimation, split_reveal, featured_result
from overlay import shorts_story


class StoryTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('AOE2_GAME_DIR'), 'Installed artwork smoke opt-in')
    def test_direct_enhancement_uses_current_camera_and_returns_rgb_delivery_pixels(self):
        import build_story_short
        from overlay.battle_camera import BattleCamera
        enhance = getattr(build_story_short, 'enhance_battle_frame', None)
        self.assertIsNotNone(enhance, 'Missing direct-frame enhancement path')
        recording = np.zeros((120,240,3), dtype=np.uint8)
        recording[:, :120] = (20,40,80)
        recording[:, 120:] = (90,60,30)
        camera = BattleCamera([{'time':0,'x':0,'y':0,'size':120},
                               {'time':1,'x':120,'y':0,'size':120}])
        # Stand in only for GPU inference; real camera sampling and RGB conversion.
        def invert(frame):
            self.assertEqual(frame.shape, (1080,1080,3))
            return 255-frame
        early = enhance(recording,camera,0,invert)
        late = enhance(recording,camera,1,invert)
        self.assertEqual(early.size, (1080,1080))
        self.assertEqual(early.getpixel((540,540)), (175,215,235))
        self.assertEqual(late.getpixel((540,540)), (225,195,165))

    @unittest.skipUnless(os.environ.get('AOE2_GAME_DIR'), 'Installed artwork smoke opt-in')
    def test_attack_uses_registered_native_shadow_not_padded_canvas_bottom(self):
        from build_story_short import paste_attack
        tile = Image.new('RGBA', (100,100))
        tile.paste((255,0,0,255), (45,20,55,60))
        shadow = Image.new('RGBA', (30,10), (0,0,0,130))
        tile.info['nativeShadow'] = (shadow, (35,55))
        canvas = Image.new('RGBA', (500,500), 'white')
        paste_attack(canvas, tile, (250,250))
        self.assertEqual(canvas.getpixel((250,259)), (255,0,0,255))
        self.assertLess(canvas.getpixel((250,261))[0], 255)
        self.assertEqual(canvas.getpixel((250,292)), (255,255,255,255))

    def test_teutonic_shadow_keeps_native_registration_and_all_attack_poses(self):
        from prepare_story_attacks import native_shadow_frames
        source = Path(__file__).resolve().parents[3]/'graphics/game_raw_files/u_inf_teutonic_knight_elite_attackA_x2.sld'
        if not source.is_file():
            self.skipTest('Local native game sprite unavailable')
        shadows = native_shadow_frames(source, (129,136))
        self.assertEqual(len(shadows), 60)
        self.assertEqual(shadows[0][1], (26,8))
        self.assertEqual(shadows[0][0].size, (80,108))
        self.assertGreater(shadows[0][0].getchannel('A').getextrema()[1], 0)

    def test_output_name_matches_the_recorded_units(self):
        naming = getattr(shorts_story, 'story_video_name', None)
        self.assertIsNotNone(naming)
        self.assertEqual(naming(['Elite Obuch', 'Elite Teutonic Knight']),
                         'Obuch-vs-Teutonic-Knight-Short-v8.mp4')
        self.assertEqual(naming(['Elite Blackwood Archer', 'Elite Huskarl']),
                         'Blackwood-Archer-vs-Huskarl-Short-v8.mp4')

    def test_intro_names_omit_elite_and_heavy_upgrade_prefixes(self):
        self.assertEqual(shorts_story.intro_unit_name('Elite Blackwood Archer'),'Blackwood Archer')
        self.assertEqual(shorts_story.intro_unit_name('Elite Huskarl'),'Huskarl')
        self.assertEqual(shorts_story.intro_unit_name('Heavy Cavalry Archer'),'Cavalry Archer')
        self.assertEqual(shorts_story.intro_unit_name('Paladin'),'Paladin')

    def test_game_image_frame_preserves_corners_and_reveals_background(self):
        background = Image.new('RGBA', (40,40), (155,118,78,255))
        frame = Image.new('RGBA', (12,12))
        frame.paste('red',(0,0,2,2))
        frame.paste('blue',(10,0,12,2))
        frame.paste('green',(0,10,2,12))
        frame.paste('yellow',(10,10,12,12))
        result = shorts_story.framed_panel(background, frame, (40,60), edge=2)
        self.assertEqual(result.getpixel((20,30)), (155,118,78,255))
        self.assertEqual(result.crop((0,0,2,2)).tobytes(), frame.crop((0,0,2,2)).tobytes())
        self.assertEqual(result.getpixel((39,0)), (0,0,255,255))
        self.assertEqual(result.getpixel((0,59)), (0,128,0,255))
        self.assertEqual(result.getpixel((39,59)), (255,255,0,255))

    def test_panels_open_outward_and_fully_reveal_battle(self):
        panel = Image.new('RGBA', (20, 40), 'red')
        panel.paste('blue', (0, 20, 20, 40))
        battle = Image.new('RGBA', panel.size, 'green')
        self.assertEqual(split_reveal(panel, battle, 0).tobytes(), panel.tobytes())
        mid = split_reveal(panel, battle, .5)
        self.assertEqual(mid.getpixel((10, 0)), (255, 0, 0, 255))
        self.assertEqual(mid.getpixel((10, 19)), (0, 128, 0, 255))
        self.assertEqual(mid.getpixel((10, 39)), (0, 0, 255, 255))
        revealed = [sum(np.all(np.array(split_reveal(panel, battle, p)) == (0,128,0,255), axis=2).flat)
                    for p in (0, .25, .5, .75, 1)]
        self.assertEqual(revealed, sorted(revealed))
        self.assertEqual(split_reveal(panel, battle, 1).tobytes(), battle.tobytes())

    def test_attack_animation_uses_gif_durations_and_loops(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'attack.gif'
            Image.new('RGBA', (8,8), 'red').save(path, save_all=True,
                append_images=[Image.new('RGBA', (8,8), 'blue')], duration=[100,300], loop=0)
            animation = AttackAnimation(path, (8,8))
            self.assertEqual(animation.at(.05).getpixel((4,4)), (255,0,0,255))
            self.assertEqual(animation.at(.15).getpixel((4,4)), (0,0,255,255))
            self.assertEqual(animation.at(.45).getpixel((4,4)), (255,0,0,255))

    def test_result_uses_top_army_not_last_surviving_side_or_buffer(self):
        row = {'sides': {'2':[{'hp':0}], '3':[{'hp':14}], '4':[{'hp':90}]}}
        self.assertEqual(featured_result(row), ('Defeated', 0, 0))
        self.assertEqual(featured_result(row, '3'), ('Victorious', 1, 14))
        row['sides']['3'][0]['hp'] = 0
        self.assertEqual(featured_result(row), ('Draw', 0, 0))

    def test_twenty_fps_attack_advances_on_exact_sixty_fps_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'attack.gif'
            frames = [Image.new('RGBA', (8,8), color) for color in ('red','blue','green','yellow')]
            frames[0].save(path, save_all=True, append_images=frames[1:], duration=50, loop=0)
            animation = AttackAnimation(path, (8,8))
            # Video frame 9 is exactly the start of GIF frame 3, not frame 2.
            self.assertEqual(animation.at(9/60).getpixel((4,4)), (255,255,0,255))

    def test_ending_holds_for_five_seconds_or_the_shorter_victory_cue(self):
        self.assertEqual(shorts_story.ending_frame_count(5.5, 60), 300)
        self.assertEqual(shorts_story.ending_frame_count(2.24, 60), 134)

    @unittest.skipUnless(os.environ.get('AOE2_GAME_DIR'), 'Installed artwork smoke opt-in')
    def test_ending_extends_game_art_instead_of_cards_and_adds_website_message(self):
        from build_story_short import ending_background, game_panel
        unit = {'unit':'Elite Blackwood Archer', 'stats':{'civ_name':'Tupi'}}
        end = ending_background(unit, 0, 4/9)
        background = game_panel((1080,1920))
        self.assertEqual(end.size, background.size)
        for region in ((30,1425,1050,1515), (30,1800,1050,1870)):
            self.assertEqual(end.crop(region).tobytes(), background.crop(region).tobytes())
        message = (130,1550,950,1750)
        self.assertNotEqual(end.crop(message).tobytes(), background.crop(message).tobytes())

    def test_hp_percentage_uses_starting_main_army_not_survivor_max_hp(self):
        initial = {'sides': {'2':[{'hp':25} for _ in range(27)], '3':[{'hp':70}], '4':[{'hp':100}]}}
        final = {'sides': {'2':[{'hp':25} for _ in range(12)], '3':[], '4':[{'hp':100}]}}
        fraction = shorts_story.featured_hp_fraction(initial, final)
        self.assertAlmostEqual(fraction, 4/9)
        self.assertEqual(shorts_story.hp_label(fraction), '44% HP')

    def test_lossless_attack_keeps_soft_alpha_and_original_timing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            Image.new('RGBA', (8,8), (40,90,200,96)).save(path/'0000.png')
            Image.new('RGBA', (8,8), (50,100,210,128)).save(path/'0001.png')
            (path/'animation.json').write_text(json.dumps({'frames':['0000.png','0001.png'],
                                                          'durationsMs':[50,50]}))
            animation = AttackAnimation(path, (8,8))
            self.assertEqual(animation.at(.025).getpixel((4,4)), (40,90,200,96))
            self.assertEqual(animation.at(.05).getpixel((4,4)), (50,100,210,128))
            self.assertEqual(animation.at(.1).getpixel((4,4)), (40,90,200,96))

    def test_result_backing_spans_entire_canvas_not_just_ornament(self):
        base = Image.new('RGBA', (1080,1920), 'black')
        result = shorts_story.result_backing(base, 800, 1250)
        self.assertEqual(result.getpixel((0,900)), result.getpixel((540,900)))
        self.assertEqual(result.getpixel((1079,900)), result.getpixel((540,900)))
        self.assertNotEqual(result.getpixel((0,900)), base.getpixel((0,900)))
        self.assertEqual(result.getpixel((0,1400)), base.getpixel((0,1400)))

    def test_result_backing_keeps_the_background_visible(self):
        base = Image.new('RGBA', (20,40), (200,160,120,255))
        base.paste((140,100,60,255), (10,0,20,40))
        result = shorts_story.result_backing(base, 10, 30)
        left, right = result.getpixel((5,20)), result.getpixel((15,20))
        self.assertGreater(left[0], right[0])
        self.assertGreater(right[0], 35)
        self.assertLess(left[0], 200)
        self.assertEqual(left[3], 255)

    def test_winning_army_drives_the_ending_even_when_bottom_wins(self):
        initial = {'sides': {'2':[{'hp':25}], '3':[{'hp':70},{'hp':70}], '4':[{'hp':100}]}}
        final = {'sides': {'2':[], '3':[{'hp':35}], '4':[{'hp':100}]}}
        result = shorts_story.winning_result(initial, final)
        self.assertEqual(result, {'owner':'3', 'unitIndex':1, 'title':'Victorious',
                                 'survivors':1, 'hp':35, 'hpFraction':.25})
        final['sides']['2'] = [{'hp':20}]
        final['sides']['3'] = []
        result = shorts_story.winning_result(initial, final)
        self.assertEqual(result, {'owner':'2', 'unitIndex':0, 'title':'Victorious',
                                 'survivors':1, 'hp':20, 'hpFraction':.8})

    def test_partial_team_mask_does_not_apply_full_tint_to_face_details(self):
        from prepare_story_attacks import tint_native
        native = Image.new('RGBA', (3,1), (160,120,80,255))
        mask = Image.new('L', (3,1)); mask.putdata([0,128,255])
        result = tint_native(native, mask, (.25,.5,1))
        self.assertEqual(result.getpixel((0,0)), (160,120,80,255))
        self.assertEqual(result.getpixel((1,0)), (100,90,80,255))
        self.assertEqual(result.getpixel((2,0)), (40,60,80,255))

    def test_shadow_recovery_preserves_sprite_hue_alpha_and_white(self):
        from prepare_story_attacks import recover_shadows
        native = Image.new('RGBA', (3,1))
        native.putdata([(32,64,128,96),(255,255,255,255),(0,0,0,0)])
        result = recover_shadows(native, .6)
        self.assertEqual(result.getpixel((0,0)), (42,84,169,96))
        self.assertEqual(result.getpixel((1,0)), (255,255,255,255))
        self.assertEqual(result.getpixel((2,0)), (0,0,0,0))
        self.assertEqual(recover_shadows(native, 1).tobytes(), native.tobytes())

    def test_native_attack_retains_aligned_canvas_and_team_color_mask(self):
        from prepare_story_attacks import native_attack
        source = Path(__file__).resolve().parents[3]/'graphics/game_raw_files/u_arc_blackwood_archer_elite_attackA_x2.sld'
        if not source.is_file():
            self.skipTest('Local native game sprite unavailable')
        blue = native_attack(source, 'blue')
        red = native_attack(source, 'red')
        self.assertEqual(len(blue), 30)
        self.assertEqual(len({frame.size for frame in blue}), 1)
        self.assertEqual(blue[0].getchannel('A').tobytes(), red[0].getchannel('A').tobytes())
        self.assertNotEqual(blue[0].tobytes(), red[0].tobytes())
        # Native face detail (141,80): RGB (66,72,66), mask 166, crop origin (93,49).
        # A partial mask must blend, not turn it into the old near-black (10,15,59).
        self.assertEqual(blue[0].getpixel((48,31)), (30,35,62,255))

    @unittest.skipUnless(os.environ.get('AOE2_GAME_DIR'), 'Installed artwork smoke opt-in')
    def test_result_ornament_can_be_composed_without_its_narrow_backing(self):
        from build_champi_comparison_overlay import result_art
        opaque = result_art('Tupi', '2', 44, 4)
        clear = result_art('Tupi', '2', 44, 4, backing=False)
        self.assertGreater(opaque.getpixel((45,200))[3], 0)
        self.assertEqual(clear.getpixel((45,200))[3], 0)
        self.assertEqual(opaque.getpixel((320,50)), clear.getpixel((320,50)))

    @unittest.skipUnless(os.environ.get('AOE2_TEST_FFMPEG') or shutil.which('ffmpeg'), 'FFmpeg smoke opt-in')
    def test_victory_audio_starts_only_at_ending_and_combat_stays_aligned(self):
        ffmpeg = os.environ.get('AOE2_TEST_FFMPEG') or shutil.which('ffmpeg')
        graph = shorts_story.story_audio_filter(.2, 2, 9, ending=5,
                                                input_label='0:a', victory_label='1:a')
        pcm = subprocess.check_output([ffmpeg, '-v','error','-f','lavfi','-i',
            'sine=frequency=440:sample_rate=48000:duration=9', '-f','lavfi','-i',
            'sine=frequency=880:sample_rate=48000:duration=5.5', '-filter_complex', graph,
            '-map','[a]','-ac','1','-ar','48000','-f','f32le','pipe:1'])
        samples = np.frombuffer(pcm, dtype='<f4')
        self.assertAlmostEqual(len(samples)/48000, 10, places=3)
        for start in (.2, 9.8):
            section = samples[round(start*48000):round((start+.05)*48000)]
            self.assertGreater(float(np.sqrt(np.mean(section**2))), .02)
        # At final t=4, source t=1.2: the three-second intro must not shift combat.
        section = samples[4*48000:5*48000]
        expected = np.sin(2*np.pi*440*(np.arange(48000)/48000+1.2))
        self.assertGreater(float(np.corrcoef(section, expected)[0,1]), .999)
        # Exactly at t=5 the win cue replaces, rather than mixes with, game audio.
        section = samples[5*48000:6*48000]
        expected = np.sin(2*np.pi*880*np.arange(48000)/48000)
        self.assertGreater(float(np.corrcoef(section, expected)[0,1]), .999)
        self.assertLess(float(np.sqrt(np.mean(samples[-240:]**2))), .01)


if __name__ == '__main__':
    unittest.main()
