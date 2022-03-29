import numpy as np

from photons.equipment.nidaq import NIDAQ


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


def test_wait_inifinity_constant():
    # the docstrings indicate to use -1 to wait forever
    assert NIDAQ.WAIT_INFINITELY == -1
