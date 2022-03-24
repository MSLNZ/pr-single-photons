import pytest
import numpy as np

from photons import utils


def test_decimals():
    assert utils.get_decimals(0.) == 0
    assert utils.get_decimals(0) == 0
    assert utils.get_decimals(1) == 0
    assert utils.get_decimals(1.0) == 0
    assert utils.get_decimals(-1) == 0
    assert utils.get_decimals(10) == 0
    assert utils.get_decimals(-10) == 0
    assert utils.get_decimals(1e99) == 0
    assert utils.get_decimals(1.0e9) == 0
    assert utils.get_decimals(-1.0e9) == 0
    assert utils.get_decimals(0.1) == 1
    assert utils.get_decimals(-0.1) == 1
    assert utils.get_decimals(0.01) == 2
    assert utils.get_decimals(-0.01) == 2
    assert utils.get_decimals(0.002341) == 6
    assert utils.get_decimals(2.341e-3) == 6
    assert utils.get_decimals(-0.002341) == 6
    assert utils.get_decimals(-2.341e-3) == 6
    assert utils.get_decimals(1000.1) == 1
    assert utils.get_decimals(-1000.1) == 1
    assert utils.get_decimals(1000.123456) == 6
    assert utils.get_decimals(-1000.123456) == 6
    assert utils.get_decimals(1e-4) == 4
    assert utils.get_decimals(-1e-8) == 8
    assert utils.get_decimals(100e-8) == 6
    assert utils.get_decimals(1.234e-10) == 13
    assert utils.get_decimals(1000000000000000.1) == 1
    assert utils.get_decimals(-1000000000000000.1) == 1


def test_linspace():
    # NOTE linspace() has its own assert statement as well

    expected = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
    assert np.array_equal(utils.linspace(1, 1, 0.1), expected)
    assert np.array_equal(sorted(utils.linspace(1, 1, 0.1, randomize=True)), expected)

    assert utils.linspace(9.54, 1, 0) == [9.54]
    assert utils.linspace(9.54, 0, 1) == [9.54]
    assert utils.linspace(9.54, 0, 0) == [9.54]

    expected = [9.29, 9.415, 9.54, 9.665, 9.79]
    assert np.array_equal(utils.linspace(9.54, 0.5, 0.125), expected)

    with pytest.raises(ValueError, match='integer multiple'):
        utils.linspace(9.54, 0.4, 0.125)

    with pytest.raises(ValueError, match='negative'):
        utils.linspace(9.54, 0.5, -0.125)

    expected = [
        0.0e-6, 0.2e-6, 0.4e-6, 0.6e-6, 0.8e-6,
        1.0e-6, 1.2e-6, 1.4e-6, 1.6e-6, 1.8e-6,
        2.0e-6, 2.2e-6, 2.4e-6, 2.6e-6, 2.8e-6,
        3.0e-6, 3.2e-6, 3.4e-6, 3.6e-6, 3.8e-6,
        4.0e-6, 4.2e-6, 4.4e-6, 4.6e-6, 4.8e-6,
        5.0e-6, 5.2e-6, 5.4e-6, 5.6e-6, 5.8e-6,
        6.0e-6, 6.2e-6, 6.4e-6, 6.6e-6, 6.8e-6,
        7.0e-6, 7.2e-6, 7.4e-6, 7.6e-6, 7.8e-6,
        8.0e-6, 8.2e-6, 8.4e-6, 8.6e-6, 8.8e-6,
        9.0e-6, 9.2e-6, 9.4e-6, 9.6e-6, 9.8e-6,
        1.0e-5
    ]
    assert np.array_equal(utils.linspace(5e-6, 1e-5, 2e-7), expected)

    expected = [4.99e-10, 4.995e-10, 5e-10, 5.005e-10, 5.01e-10]
    assert np.array_equal(utils.linspace(5e-10, 2e-12, 5e-13), expected)

    with pytest.raises(ValueError, match='integer multiple'):
        utils.linspace(0, 1e-12, 3e-13)


def test_arange():
    assert np.array_equal(utils.arange(10, 100, 0), [10])

    assert np.array_equal(utils.arange(0, 0.5, 0.1), [0.0, 0.1, 0.2, 0.3, 0.4, 0.5])
    assert np.array_equal(utils.arange(0, -1, -0.25), [0.0, -0.25, -0.5, -0.75, -1.0])
    assert np.array_equal(utils.arange(10, 20, 2), [10, 12, 14, 16, 18, 20])

    expected = [1.0, 1.001, 1.002, 1.003, 1.004, 1.005, 1.006, 1.007, 1.008, 1.009, 1.01]
    assert np.array_equal(utils.arange(1, 1.01, 0.001), expected)

    expected = [
        23., 23.1, 23.2, 23.3, 23.4, 23.5, 23.6, 23.7, 23.8, 23.9,
        24., 24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7, 24.8, 24.9,
        25., 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7, 25.8, 25.9,
        26., 26.1, 26.2, 26.3, 26.4, 26.5, 26.6, 26.7, 26.8, 26.9, 27.
    ]
    assert np.array_equal(utils.arange(23, 27, 0.1), expected)

    with pytest.raises(ValueError, match=r'10 is not in \[\s*0\s+3\s+6\s+9\s+12\s*\]'):
        utils.arange(0, 10, 3)


def test_linspace_photometer():
    expected = [
        5.75, 5.85, 5.95, 6.05, 6.15, 6.25,  # rising
        9.75, 9.85, 9.95, 10.05, 10.15, 10.25,  # central
        13.75, 13.85, 13.95, 14.05, 14.15, 14.25  # falling
    ]
    assert np.array_equal(utils.linspace_photometer(10, 0.1), expected)

    expected = [
        19.17, 19.22, 19.27, 19.32, 19.37, 19.42, 19.47, 19.52, 19.57, 19.62, 19.67,  # rising
        23.17, 23.22, 23.27, 23.32, 23.37, 23.42, 23.47, 23.52, 23.57, 23.62, 23.67,  # central
        27.17, 27.22, 27.27, 27.32, 27.37, 27.42, 27.47, 27.52, 27.57, 27.62, 27.67   # falling
    ]
    assert np.array_equal(utils.linspace_photometer(23.42, 0.05), expected)

    with pytest.raises(ValueError, match='integer multiple'):
        utils.linspace_photometer(10, 0.3)

    with pytest.raises(ValueError, match='negative'):
        utils.linspace_photometer(10, -0.125)
