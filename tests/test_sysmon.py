import time
import unittest

from leotools.utils import sysmon


class RateTests(unittest.TestCase):
    def test_rate(self):
        self.assertAlmostEqual(sysmon.rate_mbps(1_250_000, 1.0), 10.0)

    def test_rate_guards(self):
        self.assertEqual(sysmon.rate_mbps(1000, 0), 0.0)
        self.assertEqual(sysmon.rate_mbps(-5, 1), 0.0)


class NvidiaTests(unittest.TestCase):
    def test_parse(self):
        text = "NVIDIA GeForce RTX 4050 Laptop GPU, 44.54, 15, 2271, 6141"
        temps = sysmon.parse_nvidia_smi(text)
        self.assertIsNotNone(temps)
        self.assertAlmostEqual(temps.gpu, 44.54)
        self.assertEqual(temps.gpu_util, 15.0)
        self.assertEqual(temps.gpu_mem_used, 2271)
        self.assertEqual(temps.source, "nvidia-smi")

    def test_invalid(self):
        self.assertIsNone(sysmon.parse_nvidia_smi(""))
        self.assertIsNone(sysmon.parse_nvidia_smi("basura"))


class LhmTests(unittest.TestCase):
    def test_prefers_package(self):
        text = (
            '[{"Name":"CPU Core #1","Value":55.0},'
            '{"Name":"CPU Package","Value":61.5},'
            '{"Name":"GPU Core","Value":40.0}]'
        )
        self.assertAlmostEqual(sysmon.parse_lhm(text), 61.5)

    def test_average_cores(self):
        text = '[{"Name":"CPU Core #1","Value":40},{"Name":"CPU Core #2","Value":60}]'
        self.assertAlmostEqual(sysmon.parse_lhm(text), 50.0)

    def test_ignores_non_cpu(self):
        text = '[{"Name":"GPU Core","Value":40}]'
        self.assertIsNone(sysmon.parse_lhm(text))

    def test_invalid_json(self):
        self.assertIsNone(sysmon.parse_lhm("no-json"))


class AcpiTests(unittest.TestCase):
    def test_celsius_conversion(self):
        text = '[{"CurrentTemperature":3000}]'
        self.assertAlmostEqual(sysmon.parse_acpi(text), 26.85)

    def test_implausible_returns_none(self):
        text = '[{"CurrentTemperature":100}]'
        self.assertIsNone(sysmon.parse_acpi(text))


class SamplerTests(unittest.TestCase):
    def test_snapshot_values(self):
        sampler = sysmon.SystemSampler()
        first = sampler.sample()
        time.sleep(0.2)
        second = sampler.sample()
        for snapshot in (first, second):
            self.assertGreater(snapshot.cores, 0)
            self.assertGreaterEqual(snapshot.cpu_percent, 0)
            self.assertLessEqual(snapshot.cpu_percent, 100)
            self.assertGreater(snapshot.ram_total, 0)
            self.assertTrue(snapshot.net_name)
        self.assertGreaterEqual(second.net_down_mbps, 0)


if __name__ == "__main__":
    unittest.main()
