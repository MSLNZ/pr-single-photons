import numpy as np

from photons.equipment.nidaq import NIDAQ


def test_time_array():
    x1 = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    x2 = NIDAQ.time_array(0.1, 10)
    assert x2.size == 10
    assert x2.shape == (10,)
    assert np.allclose(x1, x2)

    x1 = [0.0, 0.1234, 0.2468, 0.3702, 0.4936]
    x2 = NIDAQ.time_array(0.1234, 5)
    assert x2.size == 5
    assert x2.shape == (5,)
    assert np.allclose(x1, x2)

    x = NIDAQ.time_array(0, 100000)
    assert x[0] == 0.0
    assert x.size == 1
