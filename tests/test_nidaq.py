import numpy as np

from photons.equipment.nidaq import (
    NIDAQ,
    Trigger,
)


def test_time_array():
    x1 = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    x2 = NIDAQ.time_array(0.1, 10)
    assert x2.size == 10
    assert x2.shape == (10,)
    assert np.allclose(x1, x2)

    x2 = NIDAQ.time_array(0.1, np.array(x1))
    assert x2.size == 10
    assert x2.shape == (10,)
    assert np.allclose(x1, x2)

    x1 = [0.0, 0.1234, 0.2468, 0.3702, 0.4936]
    x2 = NIDAQ.time_array(0.1234, 5)
    assert x2.size == 5
    assert x2.shape == (5,)
    assert np.allclose(x1, x2)

    x1 = [0.0, -0.1234, -0.2468, -0.3702, -0.4936]
    x2 = NIDAQ.time_array(-0.1234, 5)
    assert x2.size == 5
    assert x2.shape == (5,)
    assert np.allclose(x1, x2)

    x = NIDAQ.time_array(0, 0)
    assert x.size == 0

    x = NIDAQ.time_array(1000, 0)
    assert x.size == 0

    x = NIDAQ.time_array(0, 1)
    assert x.size == 1
    assert x.shape == (1,)
    assert np.sum(x) == 0.0

    x = NIDAQ.time_array(0, 100)
    assert x.size == 100
    assert x.shape == (100,)
    assert np.sum(x) == 0.0


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
    t = Trigger(1, 'Dev1')
    assert str(t) == 'Trigger<source=/Dev1/PFI1, edge=Edge.RISING>'
    assert repr(t) == 'Trigger<source=/Dev1/PFI1, edge=Edge.RISING>'

    t = Trigger(0, 'Dev1', delay=0.1)
    assert str(t) == 'Trigger<source=/Dev1/PFI0, edge=Edge.RISING, delay=0.1>'

    t = Trigger(1, 'Dev1', rising=False)
    assert str(t) == 'Trigger<source=/Dev1/PFI1, edge=Edge.FALLING>'

    t = Trigger(0, 'Dev1', delay=-0.1)
    assert str(t) == 'Trigger<source=/Dev1/PFI0, edge=Edge.RISING, delay=-0.1>'

    t = Trigger(0, 'Whatever', level=0)
    assert str(t) == 'Trigger<source=/Whatever/APFI0, slope=Slope.RISING, level=0>'

    t = Trigger(0, 'Dev2', level=0, rising=False, delay=-1.2)
    assert str(t) == 'Trigger<source=/Dev2/APFI0, slope=Slope.FALLING, level=0, delay=-1.2>'

    t = Trigger(0, 'Dev2', level=2.2, hysteresis=-0.01)
    assert str(t) == 'Trigger<source=/Dev2/APFI0, slope=Slope.RISING, level=2.2, hysteresis=-0.01>'

    t = Trigger(0, 'Dev2', level=-1.1, rising=True, delay=-1.2, hysteresis=0.21)
    assert str(t) == 'Trigger<source=/Dev2/APFI0, slope=Slope.RISING, level=-1.1, delay=-1.2, hysteresis=0.21>'
