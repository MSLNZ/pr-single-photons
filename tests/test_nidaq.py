import numpy as np

from photons.equipment.nidaq import NIDAQ
from photons.equipment.nidaq import Timing
from photons.equipment.nidaq import Trigger


def test_time_array():
    x1 = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    x2 = NIDAQ.time_array(10, 0.1)
    assert x2.size == 10
    assert x2.shape == (10,)
    assert np.allclose(x1, x2)

    x2 = NIDAQ.time_array(np.array(x1), 0.1)
    assert x2.size == 10
    assert x2.shape == (10,)
    assert np.allclose(x1, x2)

    x1 = [0.0, 0.1234, 0.2468, 0.3702, 0.4936]
    x2 = NIDAQ.time_array(5, 0.1234)
    assert x2.size == 5
    assert x2.shape == (5,)
    assert np.allclose(x1, x2)

    x1 = [0.0, -0.1234, -0.2468, -0.3702, -0.4936]
    x2 = NIDAQ.time_array(5, -0.1234)
    assert x2.size == 5
    assert x2.shape == (5,)
    assert np.allclose(x1, x2)

    x = NIDAQ.time_array(0, 0)
    assert x.size == 0

    x = NIDAQ.time_array(0, 1000)
    assert x.size == 0

    x = NIDAQ.time_array(1, 0)
    assert x.size == 1
    assert x.shape == (1,)
    assert np.sum(x) == 0.0

    x = NIDAQ.time_array(100, 0)
    assert x.size == 100
    assert x.shape == (100,)
    assert np.sum(x) == 0.0

    x = NIDAQ.time_array(np.empty((1000,)), 0.1)
    assert x.size == 1000
    assert x.shape == (1000,)

    x = NIDAQ.time_array(np.empty((8, 1000)), 0.1)
    assert x.size == 1000
    assert x.shape == (1000,)


def test_wait_until_done():
    task = NIDAQ.Task()
    NIDAQ.wait_until_done(task)

    task1 = NIDAQ.Task()
    task2 = NIDAQ.Task()
    NIDAQ.wait_until_done(task1, task2)

    tasks = [NIDAQ.Task() for _ in range(10)]
    NIDAQ.wait_until_done(*tasks)


def test_wait_infinity_constant():
    # the docstrings indicate to use -1 to wait forever
    assert NIDAQ.WAIT_INFINITELY == -1


def test_trigger_repr():
    t = Trigger(source='/Dev1/PFI1', delay=0, level=None, hysteresis=0, retriggerable=False, rising=True)
    assert str(t) == 'Trigger<source=/Dev1/PFI1, edge=RISING>'
    assert repr(t) == 'Trigger<source=/Dev1/PFI1, edge=RISING>'

    t = Trigger(source='/Dev1/PFI0', delay=0.1, level=None, hysteresis=0, retriggerable=False, rising=True)
    assert str(t) == 'Trigger<source=/Dev1/PFI0, edge=RISING, delay=0.1>'

    t = Trigger(source='/Dev1/PFI1', delay=0, level=None, hysteresis=0, retriggerable=False, rising=False)
    assert str(t) == 'Trigger<source=/Dev1/PFI1, edge=FALLING>'

    t = Trigger(source='/Dev1/PFI1', delay=0, level=None, hysteresis=0, retriggerable=True, rising=False)
    assert str(t) == 'Trigger<source=/Dev1/PFI1, edge=FALLING, retriggerable=True>'

    t = Trigger(source='/Dev1/PFI0', delay=-0.1, level=None, hysteresis=0, retriggerable=False, rising=True)
    assert str(t) == 'Trigger<source=/Dev1/PFI0, edge=RISING, delay=-0.1>'

    t = Trigger(source='source', delay=0, level=None, hysteresis=0, retriggerable=True, rising=True)
    assert str(t) == 'Trigger<source=source, edge=RISING, retriggerable=True>'

    t = Trigger(source='Whatever', delay=0, level=0, hysteresis=0, retriggerable=False, rising=True)
    assert str(t) == 'Trigger<source=Whatever, slope=RISING, level=0>'

    t = Trigger(source='/Dev2/APFI0', delay=-1.2, level=0, hysteresis=0, retriggerable=False, rising=False)
    assert str(t) == 'Trigger<source=/Dev2/APFI0, slope=FALLING, level=0, delay=-1.2>'

    t = Trigger(source='/Dev2/APFI0', delay=0, level=2.2, hysteresis=-0.01, retriggerable=False, rising=True)
    assert str(t) == 'Trigger<source=/Dev2/APFI0, slope=RISING, level=2.2, hysteresis=-0.01>'

    t = Trigger(source='/Dev2/APFI0', delay=-1.2, level=-1.1, hysteresis=0.21, retriggerable=True, rising=True)
    assert str(t) == 'Trigger<source=/Dev2/APFI0, slope=RISING, level=-1.1, ' \
                     'delay=-1.2, retriggerable=True, hysteresis=0.21>'


def test_timing_repr():
    t = Timing(source='', rate=1000, finite=True, rising=True)
    assert str(t) == 'Timing<rate=1000, edge=RISING, mode=FINITE>'
    assert repr(t) == 'Timing<rate=1000, edge=RISING, mode=FINITE>'

    t = Timing(source='whatever', rate=1, finite=False, rising=True)
    assert str(t) == 'Timing<rate=1, edge=RISING, mode=CONTINUOUS, source=whatever>'

    t = Timing(source='/Dev2/PFI0', rate=0.1, finite=True, rising=False)
    assert str(t) == 'Timing<rate=0.1, edge=FALLING, mode=FINITE, source=/Dev2/PFI0>'
