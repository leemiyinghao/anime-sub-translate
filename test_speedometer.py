import unittest
from time import time
from tqdm import tqdm
from unittest.mock import patch

from speedometer import Speedometer, _speedometer


class TestSpeedometer(unittest.TestCase):
    def test_increment(self):
        with tqdm(total=100) as t:
            speedometer = Speedometer(tqdm=t)
            with speedometer:
                Speedometer.increment(10)
                self.assertEqual(speedometer._accumulated, 10)

    def test_increment_no_speedometer(self):
        Speedometer.increment(10)
        self.assertIsNone(_speedometer.get())

    def test_refresh_maybe(self):
        with tqdm(total=100) as t:
            speedometer = Speedometer(tqdm=t)
            with speedometer:
                speedometer._accumulated = 1000
                speedometer._last_refresh = 0
                with patch.object(speedometer, "_report") as mock_report:
                    speedometer._refresh_maybe()
                    mock_report.assert_called_once()
                self.assertEqual(speedometer._accumulated, 0)

    def test_refresh_maybe_not_enough_time(self):
        with tqdm(total=100) as t:
            speedometer = Speedometer(tqdm=t)
            with speedometer:
                speedometer._accumulated = 10
                speedometer._last_refresh = time()
                with patch.object(speedometer, "_report") as mock_report:
                    speedometer._refresh_maybe()
                    mock_report.assert_not_called()

    def test_refresh_maybe_not_enough_accumulated(self):
        with tqdm(total=100) as t:
            speedometer = Speedometer(tqdm=t)
            with speedometer:
                speedometer._accumulated = 10
                speedometer._last_refresh = time()
                with patch.object(speedometer, "_report") as mock_report:
                    speedometer._refresh_maybe()
                    mock_report.assert_not_called()

    def test_report(self):
        with tqdm(total=100) as t:
            speedometer = Speedometer(tqdm=t, unit="test")
            with speedometer:
                speedometer._accumulated = 10
                speedometer._last_refresh = time() - 0.1
                speedometer._report(time())
                self.assertIn("test/s", t.postfix)

    def test_context_manager(self):
        with tqdm(total=100) as t:
            speedometer = Speedometer(tqdm=t)
            with speedometer:
                self.assertIs(speedometer, _speedometer.get())
            self.assertIsNone(_speedometer.get())

    def test_context_manager_report(self):
        with tqdm(total=100) as t:
            speedometer = Speedometer(tqdm=t)
            speedometer._accumulated = 10
            speedometer._last_refresh = time() - 0.1
            with patch.object(speedometer, "_report") as mock_report:
                with speedometer:
                    pass
                mock_report.assert_called()
