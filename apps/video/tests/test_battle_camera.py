"""Focused checks for the opt-in Shorts action camera."""
import json
import unittest

import numpy as np

from overlay.battle_camera import action_box, plan_camera, BattleCamera


class BattleCameraTests(unittest.TestCase):
    def test_push_waits_for_contact_and_does_not_chase_last_survivors_left(self):
        times = np.arange(281) / 10
        boxes = ([[1000, 150, 1750, 1250]] * 30 +
                 [[1000, 550, 1750, 850]] * 150 +
                 [[1000, 600, 1400, 800]] * 60 +
                 [[1025, 650, 1250, 800]] * 41)
        keys = plan_camera(boxes, times, 2560, 1440, engagement_time=3)
        sizes = np.array([k['size'] for k in keys])
        centers = np.array([k['x']+k['size']/2 for k in keys])
        np.testing.assert_allclose(sizes[times <= 3], sizes[0])
        np.testing.assert_allclose(centers[times <= 3], centers[0])
        self.assertLessEqual(np.ptp(centers), 40)
        self.assertLess(sizes[150], sizes[0] - 250)
        self.assertLess(sizes[-1], 950)
        self.assertTrue(np.all(np.diff(sizes) <= 1e-8))
        self.assertLess(np.max(np.abs(np.diff(sizes, n=2))), 2)

    def test_reframed_enhancement_tracks_source_coordinates_and_keeps_uncovered_source(self):
        from overlay.battle_camera import reframe_enhanced
        enhanced = np.zeros((100,100,3), dtype=np.uint8)
        enhanced[40:60,60:80] = (255,0,0)
        clean = np.full((100,100,3), 55, dtype=np.uint8)
        # World point (170,150) maps from old pixel (70,50) to new (40,60).
        result = reframe_enhanced(enhanced, (100,100,100), (150,120,50), clean)
        np.testing.assert_array_equal(result[60,40], [255,0,0])
        uncovered = reframe_enhanced(enhanced, (100,100,100), (50,100,100), clean)
        np.testing.assert_array_equal(uncovered[50,20], [55,55,55])

    def test_detected_bounds_can_be_saved_in_camera_manifest(self):
        frame = np.zeros((1440, 2560, 3), dtype=np.uint8)
        frame[600:640, 1200:1240] = (255, 0, 0)
        bounds = action_box(frame)
        self.assertIsNotNone(bounds)
        try:
            saved = json.dumps({'bounds': bounds})
        except TypeError as error:
            self.fail(f'Camera observations cannot be saved: {error}')
        self.assertLessEqual(json.loads(saved)['bounds'][0], 1200)
        self.assertGreaterEqual(bounds[2], 1240)

    def test_static_melee_has_no_camera_drift(self):
        keys = plan_camera([[1150, 550, 1350, 750]] * 20,
                           np.arange(20) / 10, 2560, 1440)
        positions = [BattleCamera(keys).at(t) for t in [0, .5, 1, 1.9]]
        np.testing.assert_allclose(positions, np.tile(positions[0], (4, 1)))
        self.assertLess(positions[0][2], 1440)

    def test_wide_ranged_armies_remain_inside_view(self):
        key = plan_camera([[300, 500, 2250, 850]], [0], 2560, 1440)[0]
        self.assertLessEqual(key['x'], 300)
        self.assertGreaterEqual(key['x'] + key['size'], 2250)

    def test_single_frame_scenery_detection_does_not_zoom_out(self):
        boxes = [[1000, 250, 1700, 1100] for _ in range(31)]
        boxes[15] = [100, 140, 2450, 1300]
        keys = plan_camera(boxes, np.arange(31) / 10, 2560, 1440)
        self.assertLess(max(k['size'] for k in keys), 1440)

    def test_camera_never_reverses_or_zooms_out_when_army_retreats(self):
        boxes = ([[700, 600, 1500, 1100]] * 20 +
                 [[1000, 300, 1500, 700]] * 20 +
                 [[600, 500, 1750, 1000]] * 20 +
                 [[1000, 250, 1550, 650]] * 40)
        keys = plan_camera(boxes, np.arange(100) / 10, 2560, 1440)
        sizes = np.array([k['size'] for k in keys])
        centers = np.array([[k['x']+k['size']/2, k['y']+k['size']/2] for k in keys])
        self.assertTrue(np.all(np.diff(sizes) <= 1e-8), 'Zoom reversed')
        direction = centers[-1]-centers[0]
        self.assertTrue(np.all(np.diff(centers, axis=0)*direction >= -1e-8), 'Pan reversed')
        self.assertLess(np.max(np.abs(np.diff(sizes, n=2))), 2, 'Zoom has an abrupt speed change')

    def test_push_can_follow_fight_toward_top_of_source(self):
        boxes = [[1000, 200, 1700, 1250-70*i] for i in range(11)]
        keys = plan_camera(boxes, np.arange(11), 2560, 1440)
        start, end = keys[0], keys[-1]
        self.assertLess(end['size'], start['size']-100)
        self.assertLess(end['y']+end['size']/2, start['y']+start['size']/2-100)

    def test_live_camera_positions_include_screen_but_not_corpses(self):
        from overlay.unit_timeline import camera_positions
        def entity(owner, hp):
            return {'__type__': 11, 1: 441, 2: owner, 3: 10.5, 4: 9.5, 12: hp}
        units = camera_positions({1: entity(2, 25), 2: entity(3, 0),
                                  3: entity(4, 90), 4: entity(1, 45)})
        self.assertEqual([u['id'] for u in units], [1, 3])
        self.assertEqual(units[1]['owner'], 4)
        self.assertEqual(units[1]['x'], 10.5)

    def test_telemetry_projection_uses_hp_matches_and_live_positions(self):
        from overlay.battle_camera import calibrate_projection, position_bounds
        world = [(1, 1), (2, 1), (1, 2), (4, 3), (5, 2), (2, 4)]
        rows, evidence = [], []
        for i, (x, y) in enumerate(world):
            rows.append({'videoSeconds': i, 'sides': {'3': [
                {'id': 1, 'hp': 50, 'maxHp': 100, 'x': x, 'y': y}]}})
            evidence.append({'videoSeconds': i, 'bars': [
                {'owner': '3', 'fraction': .5, 'x': 100*(x+y)+10-34,
                 'y': 50*(y-x)+500-60}]})
        matrix, quality = calibrate_projection(rows, evidence)
        np.testing.assert_allclose(matrix, [[100, 100, 10], [-50, 50, 500]], atol=.001)
        self.assertEqual(quality['inliers'], 6)
        self.assertEqual(position_bounds([{'x': 1, 'y': 1}, {'x': 2, 'y': 1}], matrix),
                         [210, 450, 310, 500])


if __name__ == '__main__':
    unittest.main()
