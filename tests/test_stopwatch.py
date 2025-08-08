import time

from fast_app import Stopwatch


def test_stopwatch_measures_time():
    with Stopwatch() as sw:
        time.sleep(0.05)
    assert sw.stop() >= 0.05
