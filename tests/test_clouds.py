# Version: V26.284.1723
import itertools
import random
import unittest

from radclouds import clouds


class NextValue(unittest.TestCase):
    def test_roll_table(self):
        got = [clouds.next_value(50, 20, 80, r) for r in (1, 2, 3, 4, 5)]
        self.assertEqual(got, [46, 48, 50, 52, 54])

    def test_at_max_moving_out_reverses(self):
        self.assertEqual(clouds.next_value(80, 20, 80, 4), 78)   # +2 -> -2
        self.assertEqual(clouds.next_value(80, 20, 80, 5), 76)   # +4 -> -4

    def test_at_min_moving_out_reverses(self):
        self.assertEqual(clouds.next_value(20, 20, 80, 1), 24)   # -4 -> +4
        self.assertEqual(clouds.next_value(20, 20, 80, 2), 22)   # -2 -> +2

    def test_at_edge_moving_in_or_still(self):
        self.assertEqual(clouds.next_value(80, 20, 80, 1), 76)
        self.assertEqual(clouds.next_value(80, 20, 80, 3), 80)
        self.assertEqual(clouds.next_value(20, 20, 80, 5), 24)

    def test_not_at_edge_overshoot_stops_at_edge(self):
        self.assertEqual(clouds.next_value(78, 20, 80, 5), 80)   # +4 would be 82
        self.assertEqual(clouds.next_value(22, 20, 80, 1), 20)   # -4 would be 18
        self.assertEqual(clouds.next_value(79, 20, 80, 4), 80)

    def test_value_outside_narrowed_range_is_pulled_in(self):
        self.assertEqual(clouds.next_value(95, 20, 80, 3), 80)
        self.assertEqual(clouds.next_value(5, 20, 80, 3), 20)

    def test_never_leaves_range(self):
        rng = random.Random(7)
        v = 50
        for _ in range(5000):
            v = clouds.next_value(v, 20, 40, rng.randint(1, 5))
            self.assertTrue(20 <= v <= 40)


class Step(unittest.TestCase):
    ranges = {k: {"min": 20, "max": 80} for k in clouds.KEYS}

    def test_each_channel_rolls_its_own_die(self):
        rolls = itertools.cycle([1, 5])
        vals = {k: 50 for k in clouds.KEYS}
        out = clouds.step(vals, self.ranges, roll=lambda: next(rolls))
        self.assertEqual(sorted(set(out.values())), [46, 54])
        self.assertEqual(out["white"], 46)
        self.assertEqual(out["blue"], 54)

    def test_covers_all_nine(self):
        self.assertEqual(len(clouds.KEYS), 9)
        self.assertEqual(clouds.data_key("end"), "max")
        self.assertEqual(clouds.data_key("rBlue"), "rBlue")


class HeldValue(unittest.TestCase):
    def test_equal_range_never_moves(self):
        for roll in (1, 2, 3, 4, 5):
            for scale in (1.0, 2.0, 3.0):
                self.assertEqual(clouds.next_value(40, 40, 40, roll, scale), 40)

    def test_value_elsewhere_snaps_to_the_held_value(self):
        self.assertEqual(clouds.next_value(77, 40, 40, 5, 3.0), 40)

    def test_step_holds_one_color_while_others_walk(self):
        ranges = {k: {"min": 20, "max": 80} for k in clouds.KEYS}
        ranges["green"] = {"min": 60, "max": 60}
        vals = {k: 50 for k in clouds.KEYS}
        vals["green"] = 60
        out = clouds.step(vals, ranges, 2.0, roll=lambda: 5)
        self.assertEqual(out["green"], 60)
        self.assertEqual(out["white"], 58)
        self.assertEqual(clouds.medians(ranges)["green"], 60)


class Medians(unittest.TestCase):
    def test_medians(self):
        r = {k: {"min": 10, "max": 90} for k in clouds.KEYS}
        r["white"] = {"min": 20, "max": 41}
        m = clouds.medians(r)
        self.assertEqual(m["blue"], 50)
        self.assertEqual(m["white"], 31)  # 30.5 rounds up


class Validate(unittest.TestCase):
    def good(self):
        return {k: {"min": 20, "max": 80} for k in clouds.KEYS}

    def test_ok(self):
        self.assertEqual(clouds.validate_ranges(self.good())["UV"], {"min": 20, "max": 80})

    def test_delta_must_exceed_15(self):
        r = self.good()
        r["green"] = {"min": 40, "max": 55}          # delta 15 -> rejected
        with self.assertRaisesRegex(ValueError, "Green.*more than 15"):
            clouds.validate_ranges(r)
        r["green"] = {"min": 40, "max": 56}          # delta 16 -> ok
        clouds.validate_ranges(r)

    def test_equal_min_and_max_is_allowed(self):
        r = self.good()
        r["red"] = {"min": 40, "max": 40}
        self.assertEqual(clouds.validate_ranges(r)["red"], {"min": 40, "max": 40})
        r["red"] = {"min": 0, "max": 0}
        clouds.validate_ranges(r)

    def test_max_below_min_is_rejected(self):
        r = self.good()
        r["red"] = {"min": 50, "max": 40}
        with self.assertRaises(ValueError):
            clouds.validate_ranges(r)

    def test_bounds_and_missing(self):
        r = self.good()
        r["red"] = {"min": -1, "max": 50}
        with self.assertRaises(ValueError):
            clouds.validate_ranges(r)
        r = self.good()
        del r["violet"]
        with self.assertRaisesRegex(ValueError, "Violet"):
            clouds.validate_ranges(r)


if __name__ == "__main__":
    unittest.main()
