# Version: V26.284.1800
import random
import unittest

from radclouds import clouds


class Scale(unittest.TestCase):
    def test_moves_at_each_speed_are_whole_numbers(self):
        expect = {
            1.0: [-4, -2, 0, 2, 4],
            1.5: [-6, -3, 0, 3, 6],
            2.0: [-8, -4, 0, 4, 8],
            2.5: [-10, -5, 0, 5, 10],
            3.0: [-12, -6, 0, 6, 12],
        }
        for sp, want in expect.items():
            got = [clouds.move_for(r, sp) for r in (1, 2, 3, 4, 5)]
            self.assertEqual(got, want, sp)

    def test_default_scale_is_unchanged(self):
        self.assertEqual([clouds.next_value(50, 20, 80, r) for r in (1, 2, 3, 4, 5)], [46, 48, 50, 52, 54])

    def test_scaled_step(self):
        self.assertEqual([clouds.next_value(50, 20, 80, r, 3.0) for r in (1, 2, 3, 4, 5)],
                         [38, 44, 50, 56, 62])

    def test_edge_rules_still_hold_when_scaled(self):
        self.assertEqual(clouds.next_value(80, 20, 80, 5, 3.0), 68)   # at max, +12 reversed
        self.assertEqual(clouds.next_value(20, 20, 80, 1, 3.0), 32)   # at min, -12 reversed
        self.assertEqual(clouds.next_value(75, 20, 80, 5, 3.0), 80)   # +12 would pass: stop at max
        self.assertEqual(clouds.next_value(25, 20, 80, 1, 3.0), 20)

    def test_narrowest_range_never_escapes_at_max_speed(self):
        rng = random.Random(3)
        v = 40
        for _ in range(20000):
            v = clouds.next_value(v, 40, 56, rng.randint(1, 5), 3.0)   # delta 16
            self.assertTrue(40 <= v <= 56)

    def test_step_passes_scale(self):
        ranges = {k: {"min": 20, "max": 80} for k in clouds.KEYS}
        out = clouds.step({k: 50 for k in clouds.KEYS}, ranges, 2.0, roll=lambda: 5)
        self.assertTrue(all(v == 58 for v in out.values()))


class Validation(unittest.TestCase):
    def test_speed(self):
        for ok in (1, 1.0, 1.5, "2", 2.5, 3):
            clouds.validate_speed(ok)
        for bad in (0.5, 1.25, 3.5, "x", None, 4):
            with self.assertRaises(ValueError):
                clouds.validate_speed(bad)

    def test_interval(self):
        self.assertEqual(clouds.validate_interval(15), 15)
        self.assertEqual(clouds.validate_interval("120"), 120)
        for bad in (14, 121, "x", None):
            with self.assertRaises(ValueError):
                clouds.validate_interval(bad)


if __name__ == "__main__":
    unittest.main()
