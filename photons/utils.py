"""
General classes and functions.
"""
import time
from decimal import Decimal

import numpy as np
import requests
from numpy.lib import recfunctions

from .log import logger


def array_central(
        centre: float,
        width: float,
        step: float,
        *,
        randomize: bool = False,
        decimals: int = None) -> np.ndarray:
    """Get an array about a central value, for a given full width and step size.

    Args:
        centre: The central value in the array.
        width: The full width about `centre`. Must be an integer multiple of `step`.
        step: The step size. Must be a positive number.
        randomize: Whether to randomize the values in the array.
        decimals: The number of decimals to use in :func:`numpy.around`.
            If not specified then uses the value of `step` to determine
            the number of decimals.

    Returns:
        The requested array.
    """
    if step < 0:
        raise ValueError("'step' cannot be negative")

    if width < 0:
        raise ValueError("'width' cannot be negative")

    if step == 0 or width == 0:
        return np.array([centre])

    ratio = width / step
    rounded = round(ratio)
    if abs(rounded - ratio) > 1e-12:
        raise ValueError(f'The width, {width}, must be an integer multiple '
                         f'of the step size, {step}')

    num = rounded + 1
    half_width = width * 0.5
    start = centre - half_width
    stop = centre + half_width
    array, np_step = np.linspace(start, stop, num, retstep=True, endpoint=True)
    assert abs(step - np_step) < 1e-12, f'requested step size {step} != actual step size {np_step}'
    d = decimals or max(get_decimals(centre), get_decimals(step))
    array = np.around(array, decimals=d)
    if randomize:
        np.random.shuffle(array)
    return array


def array_evenly(
        start: float,
        stop: float,
        step: float,
        *,
        randomize: bool = False,
        decimals: int = None) -> np.ndarray:
    """Return evenly-spaced values within a given interval.

    The values are generated within the interval [start, stop].

    Args:
        start: Start value (the interval includes this value).
        stop: Stop value (the interval includes this value).
        step: The step size.
        randomize: Whether to randomize the values in the array.
        decimals: The number of decimals to use in :func:`numpy.around`.
            If not specified then uses the value of `step` to determine
            the number of decimals.

    Returns:
        The requested array.
    """
    if step == 0:
        return np.array([start])

    centre = (stop + start) * 0.5
    width = stop - start

    if step > 0:
        if start > stop:
            raise ValueError("'start' must be less than 'stop' for a positive step size")
        return array_central(centre, width, step, randomize=randomize, decimals=decimals)

    if stop > start:
        raise ValueError("'start' must be greater than 'stop' for a negative step size")
    array = array_central(centre, -width, -step, randomize=randomize, decimals=decimals)
    return np.flip(array)


def array_merge(*vectors: np.ndarray) -> np.ndarray:
    """Merge 1-D arrays, field by field, to create a new structured N-D array."""
    size = None
    for vector in vectors:
        if vector.ndim != 1:
            raise ValueError(f'A vector can only have dimension 1, '
                             f'got dimension {vector.ndim}')

        if size is None:
            size = vector.size
        elif size != vector.size:
            raise ValueError(f'All vectors must have the same size, '
                             f'{size} != {vector.size}')

    if size is None:
        return np.array([])
    return recfunctions.merge_arrays(vectors)


def array_photodiode_centre(
        centre: float,
        *,
        width: float = 10,
        step: float = 0.1,
        randomize: bool = False,
        decimals: int = None) -> np.ndarray:
    """Useful when trying to find the centre position of a photodiode.

    The returned array has values at the two edges of the photodiode
    and in the central region of the photodiode (in one-dimension only).

    Args:
        centre: The position of a translation stage where the
            centre of the photodiode is believed to be.
        width: The width of the photodiode or the diameter of the aperture.
            Must have the same unit as `step`.
        step: The step size to move the translation stage
            within each of the three regions (not between regions).
        randomize: Whether to randomize the values in the array.
        decimals: The number of decimals to use in :func:`numpy.around`.
            If not specified then uses the values of `centre` and `step`
            to determine the number of decimals.

    Returns:
        The requested array.
    """
    if step == 0:
        return np.array([centre])
    half_width = width * 0.5
    region_width = step * round(width * 0.1 / step)
    rising = array_central(centre-half_width, region_width, step, decimals=decimals)
    central = array_central(centre, region_width, step, decimals=decimals)
    falling = array_central(centre+half_width, region_width, step, decimals=decimals)
    array = np.concatenate((rising, central, falling))
    if randomize:
        np.random.shuffle(array)
    return array


def ave_std(data: np.ndarray,
            *,
            axis: int | tuple[int] = None) -> tuple[float | np.ndarray, float | np.ndarray]:
    """Calculate the average and standard deviation.

    Args:
        data: The values to compute the average and standard deviation of.
        axis: Axis or axes along which the average and standard deviation is computed.
            The default is to compute the values of the flattened array.

    Returns:
        The average value and the standard deviation.
    """
    if data.size > 1:
        return np.average(data, axis=axis), np.std(data, axis=axis, ddof=1)
    if data.size == 1:
        return data[0], np.NaN
    return np.NaN, np.NaN


def get_decimals(value: int | float) -> int:
    """Get the number of digits after the decimal point.

    This function returns a sensible result only if `value` was explicitly
    defined for a parameter (for example a value from a QSpinbox).
    If `value` is the result from a calculation then there will be
    floating-point issues, and will most likely return nonsense
    (e.g., a number > 15).
    """
    if value == int(value):
        return 0
    return -Decimal(str(value)).as_tuple().exponent


def lab_logging(root_url: str,
                *aliases: str,
                corrected: bool = True,
                strict: bool = True,
                timeout: float = 10) -> dict:
    """Read the current temperature, humidity and dewpoint of (an) OMEGA iServer(s).

    Args:
        root_url: The root url of the webapp, e.g., ``'http://hostname:port/'``
        aliases: The iServer alias(es) to retrieve the data from. If not specified
            then retrieves the data from all iServers.
        corrected: Whether to return corrected (True) or uncorrected (False) values.
        strict: Whether to raise an exception if the connection to the webapp
            cannot be established.
        timeout: The maximum number of seconds to wait for a reply from the webapp.

    Returns:
        The temperature, humidity and dewpoint from the iServer(s).
    """
    url = root_url.rstrip('/')
    params = {'corrected': corrected}
    if aliases:
        params['alias'] = ','.join(aliases)

    try:
        reply = requests.get(f'{url}/now/?', params=params, timeout=timeout)
    except requests.exceptions.RequestException as e:
        if strict:
            raise
        logger.error(str(e))
        return {}

    if not reply.ok:
        msg = reply.content.decode()
        if strict:
            raise RuntimeError(msg)
        logger.error(msg)
        return {}

    data = reply.json()
    for key, value in data.items():
        if value['error']:
            error = value['error']
            alias = value['alias']
            msg = f'{error} [Serial:{key}, Alias:{alias}]'
            if strict:
                raise RuntimeError(msg)
            logger.error(msg)
            return {}

    return data


def std_relative(array: np.ndarray,
                 *,
                 axis: int | tuple[int] = None) -> float | np.ndarray:
    """Calculate the relative standard deviation.

    Args:
        array: The values to compute the relative standard deviation of.
        axis: Axis or axes along which the relative standard deviation is computed.
            The default is to compute the value of the flattened array.

    Returns:
        The relative standard deviation.
    """
    ave, std = ave_std(array, axis=axis)
    if array.size > 1 and np.any(ave == 0):
        if ave.ndim == 0:
            raise ZeroDivisionError('The average value is 0')
        raise ZeroDivisionError('The average value along an axis is 0')
    return std / np.abs(ave)


def hhmmss(seconds: float) -> str:
    """Convert seconds to a hh:mm:ss representation."""
    one_day = 86400
    if seconds < one_day:
        return time.strftime('%H:%M:%S', time.gmtime(seconds))

    days = int(seconds // one_day)
    hms = hhmmss(seconds - (days * one_day))
    out = f'{hms} (+{days} day'
    if days == 1:
        return f'{out})'
    return f'{out}s)'


def mean_max_n(array: np.ndarray, n: int) -> float:
    """Return the mean of the maximum *n* values in *array*."""
    indices = np.argpartition(array, -n)[-n:]
    return float(np.mean(array[indices]))


def mean_min_n(array: np.ndarray, n: int) -> float:
    """Return the mean of the minimum *n* values in *array*."""
    indices = np.argpartition(array, n)[:n]
    return float(np.mean(array[indices]))
