import math

import numpy as np
import pytest
import requests
from msl.loadlib.utils import get_available_port

from photons import utils


@pytest.mark.parametrize(
    ('value', 'expect'),
    [(0, 0),
     (0., 0),
     (1, 0),
     (1.00000000, 0),
     (10, 0),
     (123, 0),
     (1e2, 0),
     (1.0e9, 0),
     (1e99, 0),
     (0.1, 1),
     (0.01, 2),
     (0.7632517862305610836108356018518365, 16),  # gets truncated
     (0.002341, 6),
     (2.341e-3, 6),
     (1000.1, 1),
     (1000.123456, 6),
     (1e-4, 4),
     (0.01234e-8, 13),
     (100e-8, 6),
     (1.234e-10, 13),
     (1000000000000.001, 3)])
def test_decimals(value, expect):
    assert utils.get_decimals(value) == expect
    assert utils.get_decimals(-value) == expect


def test_array_central():
    f = utils.array_central

    with pytest.raises(ValueError, match='integer multiple'):
        f(9.54, 0.4, 0.125)

    with pytest.raises(ValueError, match="'step' cannot be negative"):
        f(9.54, 0.5, -0.125)

    with pytest.raises(ValueError, match="'width' cannot be negative"):
        f(9.54, -0.5, 0.125)

    expected = np.array([0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5])
    assert np.array_equal(f(1, 1, 0.1), expected)
    randomized = f(1, 1, 0.1, randomize=True)
    assert not np.array_equal(randomized, expected)
    assert expected.shape == randomized.shape
    for item in expected:
        assert item in randomized

    assert np.array_equal(f(9.54, 1, 0), np.array([9.54]))
    assert np.array_equal(f(9.54, 0, 1), np.array([9.54]))
    assert np.array_equal(f(9.54, 0, 0), np.array([9.54]))

    expected = np.array([9.29, 9.415, 9.54, 9.665, 9.79])
    assert np.array_equal(f(9.54, 0.5, 0.125), expected)

    expected = np.array([
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
    ])
    assert np.array_equal(f(5e-6, 1e-5, 2e-7), expected)

    expected = np.array([4.99e-10, 4.995e-10, 5e-10, 5.005e-10, 5.01e-10])
    assert np.array_equal(f(5e-10, 2e-12, 5e-13), expected)

    expected = np.array([47.0001, 48.0001, 49.0001, 50.0001, 51.0001, 52.0001, 53.0001])
    assert np.array_equal(f(50.0001, 6, 1), expected)

    expected = np.array([47.0, 48.0, 49.0, 50.0, 51.0, 52.0, 53.0])
    assert np.array_equal(f(50.0001, 6, 1, decimals=1), expected)


def test_array_evenly():
    f = utils.array_evenly

    with pytest.raises(ValueError, match='integer multiple'):
        f(0, 10, 3)

    with pytest.raises(ValueError, match="'start' must be less than 'stop'"):
        f(2, 1, 0.125)  # since step > 0

    with pytest.raises(ValueError, match="'start' must be greater than 'stop'"):
        f(1, 2, -0.125)  # since step < 0

    expected = np.array([10])
    assert np.array_equal(f(10, 100, 0), expected)
    assert np.array_equal(f(10, 10, 0.1), expected)

    expected = np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5])
    assert np.array_equal(f(0, 0.5, 0.1), expected)

    expected = np.array([0.0, -0.25, -0.5, -0.75, -1.0])
    assert np.array_equal(f(0, -1, -0.25), expected)

    expected = np.array([10, 12, 14, 16, 18, 20])
    assert np.array_equal(f(10, 20, 2), expected)

    expected = np.array([1.0, 1.001, 1.002, 1.003, 1.004, 1.005,
                         1.006, 1.007, 1.008, 1.009, 1.01])
    assert np.array_equal(f(1, 1.01, 0.001), expected)

    expected = np.array([
        23., 23.1, 23.2, 23.3, 23.4, 23.5, 23.6, 23.7, 23.8, 23.9,
        24., 24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7, 24.8, 24.9,
        25., 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7, 25.8, 25.9,
        26., 26.1, 26.2, 26.3, 26.4, 26.5, 26.6, 26.7, 26.8, 26.9, 27.
    ])
    assert np.array_equal(f(23, 27, 0.1), expected)
    randomized = f(23, 27, 0.1, randomize=True)
    assert not np.array_equal(randomized, expected)
    assert expected.shape == randomized.shape
    for item in expected:
        assert item in randomized

    expected = np.array([
        -1e-7, -9.9e-8, -9.8e-8, -9.7e-8, -9.6e-8, -9.5e-8, -9.4e-8, -9.3e-8, -9.2e-8, -9.1e-8,
        -9e-8, -8.9e-8, -8.8e-8, -8.7e-8, -8.6e-8, -8.5e-8, -8.4e-8, -8.3e-8, -8.2e-8, -8.1e-8,
        -8e-8, -7.9e-8, -7.8e-8, -7.7e-8, -7.6e-8, -7.5e-8, -7.4e-8, -7.3e-8, -7.2e-8, -7.1e-8,
        -7e-8, -6.9e-8, -6.8e-8, -6.7e-8, -6.6e-8, -6.5e-8, -6.4e-8, -6.3e-8, -6.2e-8, -6.1e-8,
        -6e-8, -5.9e-8, -5.8e-8, -5.7e-8, -5.6e-8, -5.5e-8, -5.4e-8, -5.3e-8, -5.2e-8, -5.1e-8,
        -5e-8, -4.9e-8, -4.8e-8, -4.7e-8, -4.6e-8, -4.5e-8, -4.4e-8, -4.3e-8, -4.2e-8, -4.1e-8,
        -4e-8, -3.9e-8, -3.8e-8, -3.7e-8, -3.6e-8, -3.5e-8, -3.4e-8, -3.3e-8, -3.2e-8, -3.1e-8,
        -3e-8, -2.9e-8, -2.8e-8, -2.7e-8, -2.6e-8, -2.5e-8, -2.4e-8, -2.3e-8, -2.2e-8, -2.1e-8,
        -2e-8, -1.9e-8, -1.8e-8, -1.7e-8, -1.6e-8, -1.5e-8, -1.4e-8, -1.3e-8, -1.2e-8, -1.1e-8,
        -1e-8, -9e-9, -8e-9, -7e-9, -6e-9, -5e-9, -4e-9, -3e-9, -2e-9, -1e-9,
        0.0, 1e-9, 2e-9, 3e-9, 4e-9, 5e-9, 6e-9, 7e-9, 8e-9, 9e-9,
        1e-8, 1.1e-8, 1.2e-8, 1.3e-8, 1.4e-8, 1.5e-8, 1.6e-8, 1.7e-8, 1.8e-8, 1.9e-8,
        2e-8, 2.1e-8, 2.2e-8, 2.3e-8, 2.4e-8, 2.5e-8, 2.6e-8, 2.7e-8, 2.8e-8, 2.9e-8,
        3e-8, 3.1e-8, 3.2e-8, 3.3e-8, 3.4e-8, 3.5e-8, 3.6e-8, 3.7e-8, 3.8e-8, 3.9e-8,
        4e-8, 4.1e-8, 4.2e-8, 4.3e-8, 4.4e-8, 4.5e-8, 4.6e-8, 4.7e-8, 4.8e-8, 4.9e-8,
        5e-8, 5.1e-8, 5.2e-8, 5.3e-8, 5.4e-8, 5.5e-8, 5.6e-8, 5.7e-8, 5.8e-8, 5.9e-8,
        6e-8, 6.1e-8, 6.2e-8, 6.3e-8, 6.4e-8, 6.5e-8, 6.6e-8, 6.7e-8, 6.8e-8, 6.9e-8,
        7e-8, 7.1e-8, 7.2e-8, 7.3e-8, 7.4e-8, 7.5e-8, 7.6e-8, 7.7e-8, 7.8e-8, 7.9e-8,
        8e-8, 8.1e-8, 8.2e-8, 8.3e-8, 8.4e-8, 8.5e-8, 8.6e-8, 8.7e-8, 8.8e-8, 8.9e-8,
        9e-8, 9.1e-8, 9.2e-8, 9.3e-8, 9.4e-8, 9.5e-8, 9.6e-8, 9.7e-8, 9.8e-8, 9.9e-8, 1e-7])
    assert np.array_equal(f(-1e-7, 1e-7, 1e-9, decimals=10), expected)


def test_array_photodiode_centre():
    f = utils.array_photodiode_centre

    with pytest.raises(ValueError, match="'step' cannot be negative"):
        f(10, step=-0.125)

    with pytest.raises(ValueError, match="'width' cannot be negative"):
        f(10, width=-5)

    expected = np.array([
        -5.5, -5.4, -5.3, -5.2, -5.1, -5.0, -4.9, -4.8, -4.7, -4.6, -4.5,  # rising
        -0.5, -0.4, -0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5,  # central
        4.5, 4.6, 4.7, 4.8, 4.9, 5.0, 5.1, 5.2, 5.3, 5.4, 5.5  # falling
    ])
    assert np.array_equal(f(0), expected)

    expected = np.array([
        118.252, 118.452, 118.652, 118.852, 119.052, 119.252,  # rising
        123.252, 123.452, 123.652, 123.852, 124.052, 124.252,  # central
        128.252, 128.452, 128.652, 128.852, 129.052, 129.252   # falling
    ])
    assert np.array_equal(f(123.752, step=0.2), expected)

    expected = np.array([
        4.901, 4.903, 4.905, 4.907, 4.909, 4.911, 4.913, 4.915, 4.917, 4.919,  # rising
        4.991, 4.993, 4.995, 4.997, 4.999, 5.001, 5.003, 5.005, 5.007, 5.009,  # central
        5.081, 5.083, 5.085, 5.087, 5.089, 5.091, 5.093, 5.095, 5.097, 5.099   # falling
    ])
    assert np.array_equal(f(5, width=0.18, step=0.002), expected)

    expected = np.array([
        19.1, 19.15, 19.2, 19.25, 19.3, 19.35, 19.4, 19.45, 19.5,
        19.55, 19.6, 19.65, 19.7, 19.75, 19.8, 19.85, 19.9,   # rising
        23.1, 23.15, 23.2, 23.25, 23.3, 23.35, 23.4, 23.45, 23.5,
        23.55, 23.6, 23.65, 23.7, 23.75, 23.8, 23.85, 23.9,   # central
        27.1, 27.15, 27.2, 27.25, 27.3, 27.35, 27.4, 27.45, 27.5,
        27.55, 27.6, 27.65, 27.7, 27.75, 27.8, 27.85, 27.9,   # falling
    ])
    assert np.array_equal(f(23.5, step=0.05, width=8), expected)
    randomized = f(23.5, step=0.05, width=8, randomize=True)
    assert not np.array_equal(randomized, expected)
    assert expected.shape == randomized.shape
    for item in expected:
        assert item in randomized

    assert np.array_equal(f(1.23, step=0, width=0), np.array([1.23]))
    assert np.array_equal(f(100, step=0, width=10), np.array([100]))


def test_ave_std(recwarn):
    a, s = utils.ave_std(np.array([]))
    assert isinstance(a, float)
    assert isinstance(s, float)
    assert math.isnan(a)
    assert math.isnan(s)

    a, s = utils.ave_std(np.array([1.23]))
    assert isinstance(a, float)
    assert isinstance(s, float)
    assert a == pytest.approx(1.23)
    assert math.isnan(s)

    a, s = utils.ave_std(np.array(range(10)))
    assert isinstance(a, float)
    assert isinstance(s, float)
    assert a == pytest.approx(4.5)
    assert s == pytest.approx(3.0276503540975)

    a, s = utils.ave_std(np.array([[1, 2], [3, 4], [5, 6]]), axis=1)
    assert isinstance(a, np.ndarray)
    assert isinstance(s, np.ndarray)
    assert np.array_equal(a, [1.5, 3.5, 5.5])
    assert s.shape == (3,)
    assert s[0] == pytest.approx(0.707106781186548)
    assert s[1] == pytest.approx(0.707106781186548)
    assert s[2] == pytest.approx(0.707106781186548)

    a, s = utils.ave_std(np.array([[1, 2], [3, 4], [5, 6]]), axis=0)
    assert isinstance(a, np.ndarray)
    assert isinstance(s, np.ndarray)
    assert np.array_equal(a, [3., 4.])
    assert np.array_equal(s, [2., 2.])

    assert len(recwarn) == 0


def test_std_relative(recwarn):
    rsd = utils.std_relative(np.array([]))
    assert isinstance(rsd, float)
    assert math.isnan(rsd)

    rsd = utils.std_relative(np.array([0.]))
    assert isinstance(rsd, float)
    assert math.isnan(rsd)

    rsd = utils.std_relative(np.array([1.234]))
    assert isinstance(rsd, float)
    assert math.isnan(rsd)

    rsd = utils.std_relative(-1.0 * np.array(range(10)))
    assert isinstance(rsd, float)
    assert rsd == pytest.approx(3.02765035409749 / 4.5)

    rsd = utils.std_relative(1.23 * np.ones((12, 12)))
    assert isinstance(rsd, float)
    assert rsd == pytest.approx(0.0)

    rsd = utils.std_relative(np.array([[1, 2], [3, 4], [5, 6]]))
    assert isinstance(rsd, float)
    assert rsd == pytest.approx(1.87082869338697 / 3.5)

    rsd = utils.std_relative(np.array([[1, 2], [3, 4], [5, 6]]), axis=0)
    assert isinstance(rsd, np.ndarray)
    assert rsd.shape == (2,)
    assert rsd[0] == pytest.approx(2. / 3.)
    assert rsd[1] == pytest.approx(2. / 4.)

    rsd = utils.std_relative(np.array([[1, 2], [3, 4], [5, 6]]), axis=1)
    assert isinstance(rsd, np.ndarray)
    assert rsd.shape == (3,)
    assert rsd[0] == pytest.approx(0.707106781186548 / 1.5)
    assert rsd[1] == pytest.approx(0.707106781186548 / 3.5)
    assert rsd[2] == pytest.approx(0.707106781186548 / 5.5)

    with pytest.raises(ZeroDivisionError, match='The average value is 0'):
        utils.std_relative(np.zeros((2,)))

    with pytest.raises(ZeroDivisionError, match='The average value along an axis is 0'):
        a = np.ones((10, 10))
        a[:, 3] = 0.
        utils.std_relative(a, axis=0)

    with pytest.raises(ZeroDivisionError, match='The average value along an axis is 0'):
        a = np.ones((10, 10))
        a[3, :] = 0.
        utils.std_relative(a, axis=1)

    a = np.ones((10, 10))
    a[2, 3] = 0.
    rsd = utils.std_relative(a, axis=0)
    assert isinstance(rsd, np.ndarray)
    for index, value in enumerate(rsd):
        if index == 3:
            assert value == pytest.approx(0.351364184463153)
        else:
            assert value == 0.

    rsd = utils.std_relative(a, axis=1)
    assert isinstance(rsd, np.ndarray)
    for index, value in enumerate(rsd):
        if index == 2:
            assert value == pytest.approx(0.351364184463153)
        else:
            assert value == 0.

    assert len(recwarn) == 0


def test_lab_monitoring():
    port = get_available_port()
    url = f'http://127.0.0.1:{port}'

    with pytest.raises(requests.exceptions.RequestException):
        utils.lab_logging(url, 'alias', timeout=1)

    reply = utils.lab_logging(url, strict=False, timeout=1)
    assert isinstance(reply, dict)
    assert len(reply) == 0


@pytest.mark.parametrize(
    ('seconds', 'expect'),
    [(0, '00:00:00'),
     (1.234567, '00:00:01'),
     (12, '00:00:12'),
     (123, '00:02:03'),
     (1234, '00:20:34'),
     (12345, '03:25:45'),
     (86399, '23:59:59'),
     (86400, '00:00:00 (+1 day)'),
     (86401, '00:00:01 (+1 day)'),
     (172800, '00:00:00 (+2 days)'),
     (315201.3696, '15:33:21 (+3 days)')])
def test_hhmmss(seconds, expect):
    assert utils.hhmmss(seconds) == expect


def test_array_merge():
    x = np.zeros((3, 3))
    y = np.arange(3)
    with pytest.raises(ValueError, match=r'dimension 2'):
        utils.array_merge(x, y)

    x = np.arange(4)
    y = np.arange(3)
    with pytest.raises(ValueError, match=r'4 != 3'):
        utils.array_merge(x, y)

    assert utils.array_merge().size == 0

    x = np.arange(5)
    merged = utils.array_merge(x)
    expected = np.array([(0,), (1,), (2,), (3,), (4,)], dtype=[('f0', '<i4')])
    assert np.array_equal(merged, expected)
    assert merged.dtype == expected.dtype
    assert np.array_equal(merged['f0'], [0, 1, 2, 3, 4])

    x = np.arange(3)
    merged = utils.array_merge(x, y)
    expected = np.array([(0, 0), (1, 1), (2, 2)], dtype=[('f0', '<i4'), ('f1', '<i4')])
    assert np.array_equal(merged, expected)
    assert merged.dtype == expected.dtype
    assert np.array_equal(merged['f0'], [0, 1, 2])
    assert np.array_equal(merged['f1'], [0, 1, 2])

    x = np.array([1, 2, 3])
    y = np.array([4., 5., 6.], dtype=[('abc', float)])
    merged = utils.array_merge(x, y)
    expected = np.array([(1, 4.), (2, 5.), (3, 6.)], dtype=[('f0', int), ('abc', float)])
    assert np.array_equal(merged, expected)
    assert merged.dtype == expected.dtype
    assert np.array_equal(merged['f0'], [1, 2, 3])
    assert np.array_equal(merged['abc'], [4., 5., 6.])

    a = np.array(['x', 'y', 'z'], dtype=[('xyz', 'U1')])
    b = np.array([4., 5., 6.], dtype=[('abc', float)])
    c = np.array([True, False, False], dtype=[('booleans', bool)])
    d = np.arange(3)
    merged = utils.array_merge(a, b, c, d)
    expected = np.array([('x', 4., True, 0), ('y', 5., False, 1), ('z', 6., False, 2)],
                        dtype=[('xyz', 'U1'), ('abc', float), ('booleans', bool), ('f3', int)])
    assert np.array_equal(merged, expected)
    assert merged.dtype == expected.dtype
    assert np.array_equal(merged['xyz'], ['x', 'y', 'z'])
    assert np.array_equal(merged['abc'], [4., 5., 6.])
    assert np.array_equal(merged['booleans'], [True, False, False])
    assert np.array_equal(merged['f3'], [0, 1, 2])


def test_mean_max_n():
    a = np.arange(1234)
    np.random.shuffle(a)
    assert utils.mean_max_n(a, 1) == 1233.
    assert utils.mean_max_n(a, 2) == sum([1232, 1233]) / 2.0
    assert utils.mean_max_n(a, 10) == sum([1224, 1225, 1226, 1227, 1228,
                                           1229, 1230, 1231, 1232, 1233]) / 10.0


def test_mean_min_n():
    a = np.arange(1234)
    np.random.shuffle(a)
    assert utils.mean_min_n(a, 1) == 0.0
    assert utils.mean_min_n(a, 2) == sum([0, 1]) / 2.0
    assert utils.mean_min_n(a, 10) == sum([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]) / 10.0
