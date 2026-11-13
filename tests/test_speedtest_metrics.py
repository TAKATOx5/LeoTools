import unittest

from leotools.utils.speedtest import metrics
from leotools.utils.speedtest.models import LatencyStats, TransferResult


def linear_transfer(rate_before: float, rate_after: float, switch: float, total_time: float):
    """Transferencia sintetica con rampa inicial y regimen estable."""
    samples = []
    total = 0.0
    steps = int(total_time / 0.1)
    for i in range(1, steps + 1):
        timestamp = round(i * 0.1, 3)
        rate = rate_before if timestamp < switch else rate_after
        total += rate * 1_000_000 / 8 * 0.1
        samples.append((timestamp, int(total)))
    return TransferResult(
        direction="down",
        samples=samples,
        bytes_total=int(total),
        elapsed=total_time,
    )


class PercentileTests(unittest.TestCase):
    def test_percentile_edges(self):
        self.assertEqual(metrics.percentile([], 50), 0.0)
        self.assertEqual(metrics.percentile([42], 90), 42)
        self.assertEqual(metrics.percentile([1, 2, 3, 4, 5], 50), 3)
        self.assertAlmostEqual(metrics.percentile([1, 2, 3, 4], 50), 2.5)

    def test_percentile_90(self):
        values = list(range(1, 101))
        self.assertAlmostEqual(metrics.percentile(values, 90), 90.1, places=1)


class JitterTests(unittest.TestCase):
    def test_jitter_constant(self):
        self.assertEqual(metrics.jitter_ms([10, 10, 10, 10]), 0.0)

    def test_jitter_known_value(self):
        self.assertAlmostEqual(metrics.jitter_ms([10, 12, 11, 15]), 7 / 3)

    def test_jitter_needs_two_samples(self):
        self.assertEqual(metrics.jitter_ms([10]), 0.0)


class TransferTests(unittest.TestCase):
    def test_discards_ramp_up(self):
        transfer = linear_transfer(rate_before=50, rate_after=100, switch=1, total_time=10)
        stats = metrics.transfer_stats(transfer)
        self.assertAlmostEqual(stats["avg"], 100, delta=1)
        self.assertAlmostEqual(stats["p90"], 100, delta=1)
        self.assertLessEqual(stats["peak"], 101)

    def test_empty_transfer(self):
        stats = metrics.transfer_stats(None)
        self.assertEqual(stats["avg"], 0.0)
        self.assertEqual(stats["peak"], 0.0)

    def test_no_samples_falls_back_to_average(self):
        transfer = TransferResult(direction="up", samples=[], bytes_total=12_500_000, elapsed=1.0)
        stats = metrics.transfer_stats(transfer)
        self.assertAlmostEqual(stats["avg"], 100, delta=0.1)


class BufferbloatTests(unittest.TestCase):
    def test_grade_a(self):
        bloat = metrics.bufferbloat(LatencyStats([8, 9, 8, 10]), [26, 28, 30])
        self.assertEqual(bloat.grade, "A")
        self.assertAlmostEqual(bloat.delta_ms, 19.5, places=1)

    def test_grade_f(self):
        bloat = metrics.bufferbloat(LatencyStats([10, 10]), [300, 320])
        self.assertEqual(bloat.grade, "F")

    def test_no_loaded_samples(self):
        bloat = metrics.bufferbloat(LatencyStats([8, 9]), [])
        self.assertIsNone(bloat.delta_ms)
        self.assertEqual(bloat.grade, "-")


class FormatTests(unittest.TestCase):
    def test_mbps(self):
        self.assertEqual(metrics.format_mbps(486.3), "486.3 Mbps")

    def test_gbps(self):
        self.assertEqual(metrics.format_mbps(1500), "1.50 Gbps")

    def test_delta(self):
        self.assertAlmostEqual(metrics.delta_pct(110, 100), 10.0)
        self.assertIsNone(metrics.delta_pct(110, 0))


if __name__ == "__main__":
    unittest.main()
