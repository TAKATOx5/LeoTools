import unittest

from leotools.utils.speedtest import cat


class TierTests(unittest.TestCase):
    def test_idle(self):
        self.assertEqual(cat.tier_for(0).key, "idle")
        self.assertEqual(cat.tier_for(0.5).key, "idle")

    def test_thresholds(self):
        self.assertEqual(cat.tier_for(1).key, "slow")
        self.assertEqual(cat.tier_for(19.9).key, "slow")
        self.assertEqual(cat.tier_for(20).key, "medium")
        self.assertEqual(cat.tier_for(99.9).key, "medium")
        self.assertEqual(cat.tier_for(100).key, "fast")
        self.assertEqual(cat.tier_for(299.9).key, "fast")
        self.assertEqual(cat.tier_for(300).key, "turbo")

    def test_negative_is_idle(self):
        self.assertEqual(cat.tier_for(-50).key, "idle")

    def test_fps_increases_with_speed(self):
        values = [cat.tier_for(speed).fps for speed in (0, 10, 50, 150, 500)]
        self.assertEqual(values, sorted(values))


class FrameTests(unittest.TestCase):
    def test_frame_cycles(self):
        tier = cat.tier_for(50)
        first = cat.frame_for(tier, 0)
        self.assertIn("/\\_/\\", first)
        frames = {cat.frame_for(tier, step) for step in range(20)}
        self.assertGreater(len(frames), 1)

    def test_idle_has_sleep(self):
        self.assertIn("zZ", cat.frame_for(cat.tier_for(0), 0))


class SparklineTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(cat.sparkline([]), "")

    def test_width(self):
        self.assertEqual(len(cat.sparkline([1, 2, 3])), 60)

    def test_values_render(self):
        line = cat.sparkline([0, 50, 100], width=3)
        self.assertEqual(len(line), 3)
        self.assertEqual(line[-1], "█")


if __name__ == "__main__":
    unittest.main()
