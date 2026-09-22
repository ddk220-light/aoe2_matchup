"""Floating overlay behavior and recorded cost/effect data."""
import unittest
import os
import json
from pathlib import Path
import numpy as np
from PIL import Image
from overlay import static_stats


class CardDetailsTests(unittest.TestCase):
    def test_cost_uses_discounted_per_unit_plan_values(self):
        side = {'baseCost': {'food':75, 'wood':0, 'gold':35},
                'effectiveCost': {'food':53, 'wood':0, 'gold':25}}
        self.assertEqual(static_stats.effective_cost(side), {'food':53, 'wood':0, 'gold':25})
        side['effectiveCost'] = {'food':0, 'wood':17.5, 'gold':22.5}
        self.assertEqual(static_stats.effective_cost(side), {'food':0, 'wood':17.5, 'gold':22.5})

    def test_poison_is_in_effect_notes_not_folded_into_base_attack(self):
        unit = {'unit_slug':'elite_blackwood_archer_tupi', 'bleed_dps':.133,
                'bleed_duration':15, 'ignores_pierce_armor':0, 'ignores_melee_armor':0}
        self.assertEqual(static_stats.special_effects(unit), ['Poison damage'])
        unit.update(unit_slug='elite_huskarl_goths', bleed_dps=0, bleed_duration=0)
        self.assertEqual(static_stats.special_effects(unit), [])

    def test_selected_matchups_show_their_recorded_special_effects(self):
        unit = {'unit_slug':'elite_obuch_poles', 'ignores_melee_armor':0,
                'ignores_pierce_armor':0, 'armor_strip_per_hit':1}
        self.assertEqual(static_stats.special_effects(unit), ['Strips armor on each hit'])
        unit.update(unit_slug='elite_samurai_japanese', armor_strip_per_hit=0, charge_attack_melee=1)
        self.assertEqual(static_stats.special_effects(unit), ['Melee charge attack'])
        unit.update(unit_slug='elite_monaspa_georgians', charge_attack_melee=0,
                    attack_bonus_nearby=1, hp_regen=14)
        self.assertEqual(static_stats.special_effects(unit), ['Nearby cavalry boost attack', 'Regenerates HP'])

    def test_four_relics_are_disclosed_without_adding_attack_twice(self):
        unit = {'unit_slug':'elite_leitis_lithuanians', 'ignores_melee_armor':1,
                'ignores_pierce_armor':0, 'final_attack':22}
        self.assertEqual(static_stats.special_effects(unit, relics=4),
                         ['Attacks ignore melee armor.', '4 relics (+4 attack)'])
        self.assertEqual(unit['final_attack'], 22)

    def test_replacement_cards_disclose_projectile_effects_without_changing_stats(self):
        base = {'unit_slug':'replacement', 'ignores_melee_armor':0,
                'ignores_pierce_armor':0, 'final_attack':12,
                'splash_on_hit_radius':0, 'total_projectiles':1,
                'charge_projectile_count':0}
        for field, value, expected in (
            ('splash_on_hit_radius', .65, 'Splash damage on impact'),
            ('total_projectiles', 6, 'Fires multiple projectiles'),
            ('charge_projectile_count', 5, 'Charged projectile volley'),
        ):
            with self.subTest(field=field):
                unit = {**base, field:value}
                before = unit.copy()
                self.assertEqual(static_stats.special_effects(unit), [expected])
                self.assertEqual(unit, before)
        self.assertEqual(static_stats.special_effects(base), [])


class FloatingOverlayTests(unittest.TestCase):
    def test_recorded_notification_strip_is_excluded_without_cropping_the_battle(self):
        from overlay.shorts_battle import battlefield_canvas
        field = Image.new('RGBA',(20,20),(170,130,70,255))
        recording = np.full((40,60,3),(20,70,140),dtype=np.uint8)
        recording[:4] = (0,255,255)  # Native game notification, not battlefield.
        result = battlefield_canvas(field,recording,(10,8,20),size=(20,60),
                                     game_y=20,recording_top=4)
        self.assertEqual(result.getpixel((10,14)),(0,0,0,255))
        self.assertEqual(result.getpixel((10,18)),(140,70,20,255))
        self.assertEqual(result.crop((0,20,20,40)).tobytes(),field.tobytes())

    def test_scrim_fades_to_clear_and_never_blocks_the_background(self):
        from overlay.shorts_battle import readability_scrim
        scrim = readability_scrim((20,60), top=15, bottom=20)
        alpha = scrim.getchannel('A')
        self.assertEqual(alpha.getpixel((10,30)), 0)
        for y in (0,59):
            self.assertGreater(alpha.getpixel((10,y)), 0)
            self.assertEqual(alpha.getpixel((10,y)), round(255*.15))
        self.assertGreater(alpha.getpixel((10,0)), alpha.getpixel((10,8)))
        self.assertLess(alpha.getpixel((10,45)), alpha.getpixel((10,59)))

    def test_original_crop_is_preserved_with_genuine_recorded_surroundings(self):
        from overlay.shorts_battle import battlefield_canvas
        field = Image.new('RGBA', (20,20), (170,130,70,255))
        field.putpixel((10,10),(40,120,220,255))
        recording = np.full((40,60,3),(20,70,140),dtype=np.uint8)
        result = battlefield_canvas(field,recording,(10,8,20),size=(20,60),game_y=20)
        self.assertEqual(result.size, (20,60))
        self.assertEqual(result.crop((0,20,20,40)).tobytes(), field.tobytes())
        for point in ((10,15),(10,45)):
            self.assertEqual(result.getpixel(point),(140,70,20,255))
        for point in ((0,0),(19,59)):
            self.assertEqual(result.getpixel(point),(0,0,0,255))

    def test_surroundings_use_the_same_camera_transform_not_a_second_crop(self):
        from overlay.shorts_battle import battlefield_canvas
        recording = np.zeros((50,60,3),dtype=np.uint8)
        recording[5,13] = (90,120,240)
        field = Image.new('RGBA',(20,20),'green')
        for crop in ((10,10,20),(12,12,10)):
            result = battlefield_canvas(field,recording,crop,size=(20,80),game_y=30)
            x,y,extent = crop
            scale = 20/extent
            expected = (round((13-x)*scale),round(30+(5-y)*scale))
            self.assertEqual(result.getpixel(expected),(240,120,90,255))
            self.assertEqual(result.crop((0,30,20,50)).tobytes(),field.tobytes())

    def test_cards_slide_in_from_opposite_sides_without_reversing(self):
        from overlay.shorts_battle import slide_cards
        base = Image.new('RGBA',(200,80))
        cards = [Image.new('RGBA',(60,20),'red'), Image.new('RGBA',(60,20),'blue')]
        first = slide_cards(base, cards, 0, y=40)
        self.assertIsNone(first.getbbox())
        left_edges, right_edges = [], []
        for t in (.1,.2,.35,.5,.65):
            result = slide_cards(base,cards,t,y=40)
            line = [result.getpixel((x,50)) for x in range(200)]
            left_edges.append(max(x for x,p in enumerate(line) if p==(255,0,0,255)))
            right_edges.append(min(x for x,p in enumerate(line) if p==(0,0,255,255)))
        self.assertEqual(left_edges, sorted(left_edges))
        self.assertEqual(right_edges, sorted(right_edges,reverse=True))
        settled = slide_cards(base,cards,.65,y=40)
        self.assertEqual(settled.getpixel((20,50)), (255,0,0,255))
        self.assertEqual(settled.getpixel((179,50)), (0,0,255,255))
        self.assertEqual(slide_cards(base,cards,3,y=40).tobytes(), settled.tobytes())


@unittest.skipUnless(os.environ.get('AOE2_GAME_DIR'), 'Installed artwork smoke opt-in')
class RealOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from overlay.shorts_battle import BattleOverlay
        run = Path(__file__).resolve().parents[3]/'data/local/video-recreate-blackwood-20260917/blackwood-vs-huskarl/live/run_001'
        units = json.loads((run/'static-stats-overlay/stats.json').read_text())['units']
        rows = json.loads((run/'unit-hp-overlay/units.json').read_text())['rows']
        plan = json.loads((run.parent.parent/'plan.json').read_text())
        cls.units, cls.plan = units, plan
        cls.overlay = BattleOverlay(units,rows,plan,static_stats.GAME)

    def test_cost_row_has_only_nonzero_prices_without_a_label(self):
        class RecordingFont(static_stats.GameFont):
            def __init__(self, game):
                super().__init__(game)
                self.cost_text = []

            def draw(self, canvas, xy, text, size, color=static_stats.INK):
                if xy[1] >= 300:
                    self.cost_text.append(text)
                return super().draw(canvas,xy,text,size,color)

        for index, expected in enumerate((['17.5','22.5'],['53','25'])):
            with self.subTest(side=index):
                font = RecordingFont(static_stats.GAME)
                static_stats.panel(self.units[index]['stats'],self.units[1-index]['stats'],
                    font,static_stats.GAME,(88,140,255,255),details={
                        'cost':static_stats.effective_cost(self.plan[f'side{index+2}']),
                        'effects':[]})
                self.assertEqual(font.cost_text, expected)

    def test_header_is_transparent_outside_portraits_and_labels(self):
        self.assertEqual(self.overlay.header(0).getpixel((1060,319))[3], 0)

    def test_hud_never_covers_the_original_battle_viewport(self):
        field = Image.new('RGBA',(1080,1080),(80,140,200,255))
        recording = np.full((1440,2560,3),70,dtype=np.uint8)
        for seconds in (0,.325,.65,9,18):
            result = self.overlay.compose(field,seconds,recording=recording,crop=(780,100,1190))
            self.assertEqual(result.crop((0,330,1080,1410)).tobytes(),field.tobytes())

    def test_victory_footer_has_plain_background_and_settled_cards(self):
        end = self.overlay.victory_footer(Image.new('RGBA',(1080,1920),'black'))
        self.assertEqual(end.getpixel((0,1800)), (205,183,147,255))
        self.assertNotEqual(end.getpixel((250,1530)), (205,183,147,255))

    def test_poison_text_is_green_below_the_stats_divider(self):
        pixels = np.asarray(self.overlay.cards[0].convert('RGB'))
        details = pixels[222:257,160:450].astype(float)
        green = (details[...,1]>details[...,0]*1.3)&(details[...,1]>details[...,2]*1.3)&(details[...,1]>80)
        self.assertGreater(int(green.sum()),100)


if __name__ == '__main__':
    unittest.main()
