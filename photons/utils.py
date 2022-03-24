"""
General classes and functions.
"""
import re

import numpy as np


class Register(object):

    PATTERN = r'^[^_].+\.py$'  # Python files that do not start with an underscore

    def __init__(self, manufacturer, model, flags, cls):
        """Register a class to allow for filtering based on .

        Parameters
        ----------
        manufacturer : :class:`str` or :data:`None`
            The name of the manufacturer. Can be a regex pattern.
        model : :class:`str` or :data:`None`
            The model number of the equipment. Can be a regex pattern.
        flags : :class:`int`
            The flags to use for the regex pattern.
        cls
            The class to register. The class is not instantiated.
        """
        self.manufacturer = re.compile(manufacturer, flags=flags) if manufacturer else None
        self.model = re.compile(model, flags=flags) if model else None
        self.cls = cls

    def matches(self, record) -> bool:
        """Check if the `equipment_record` is a match for the registered class.

        Parameters
        ----------
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment equipment_record to check if the manufacturer and the model number are
            a match for the registered class.

        Returns
        -------
        :class:`bool`
            Whether `equipment_record` is a match.
        """
        if self.manufacturer is None and self.model is None:
            return False
        if self.manufacturer and not self.manufacturer.search(record.manufacturer):
            return False
        if self.model and not self.model.search(record.model):
            return False
        return True


def get_decimals(value) -> int:
    """Get the number of decimal places required to represent a value.

    Parameters
    ----------
    value : :class:`int` or :class:`float`
        The value.

    Returns
    -------
    :class:`int`
        The number of decimal places.
    """
    val = abs(value)
    fraction = val - int(val)
    if fraction == 0:
        return 0

    string = str(val)
    split = string.split('e-')
    if len(split) == 1:
        return len(string) - split[0].index('.') - 1

    number, exponential = split
    d = int(exponential)
    if '.' in number:
        return d + len(number) - number.index('.') - 1
    return d


def linspace(center, width, step, *, randomize=False, decimals=None):
    """Get a range of values based on a central point, a range width and step size.

    Parameters
    ----------
    center : :class:`float`
        The central point.
    width : :class:`float`
        The full width of the range. Must be an integer multiple of the `step` size.
    step : :class:`float`
        The step size.
    randomize : :class:`bool`, optional
        Whether to randomize the values.
    decimals : :class:`int`, optional
        The number of decimals to use in :class:`numpy.round`. If not specified
        then uses the value of `step` to determine the value of `decimals`.

    Returns
    -------
    :class:`numpy.ndarray`
        The requested values.
    """
    if step == 0 or width == 0:
        return np.array([center])
    elif step < 0:
        raise ValueError(f'The step size, {step}, cannot be negative')

    step = float(step)
    ratio = width / step
    if abs(round(ratio) - ratio) > 1e-12:
        raise ValueError(f'The width {width} must be an integer multiple of the step size {step}, ratio={ratio}')

    start = center - width * 0.5
    stop = center + width * 0.5
    num = int(width / step) + 1
    values, np_step = np.linspace(start, stop, num, retstep=True, endpoint=True)
    assert abs(step - np_step) < 1e-12, f'requested step size {step}, actual step size {np_step}'
    d = decimals or get_decimals(step)
    values = np.round(values, decimals=d)
    if randomize:
        np.random.shuffle(values)
    return values


def arange(start, stop, step, *, randomize=False, decimals=None):
    """Return evenly spaced values within a given interval.

    Values are generated within the interval ``[start, stop]``

    Parameters
    ----------
    start : :class:`int` or :class:`float`
        Start of interval. The interval includes this value.
    stop : :class:`int` or :class:`float`
        End of interval. The interval includes this value.
    step : integer or real, optional
        Spacing between values.
    randomize : :class:`bool`, optional
        Whether to randomize the values.
    decimals : :class:`int`, optional
        The number of decimals to use in :class:`numpy.round`. If not specified
        then uses the value of `step` to determine the value of `decimals`.

    Returns
    -------
    :class:`numpy.ndarray`
        The requested values.
    """
    if step == 0:
        return np.array([start])
    values = np.arange(start, stop+step, step)
    d = decimals or get_decimals(step)
    values = np.round(values, decimals=d)
    if values[-1] != stop:
        if values[-2] != stop:
            raise ValueError(f'The stop value {stop} is not in {values}')
        values = values[:-1:]
    if randomize:
        np.random.shuffle(values)
    return values


def linspace_photometer(center: float, step: float):
    """Useful when performing a spatial scan of a photometer.

    Parameters
    ----------
    center : :class:`float`
        The central point, in mm.
    step : :class:`float`
        The step size, in mm.

    Returns
    -------
    :class:`numpy.ndarray`
        The requested values.
    """
    if step == 0:
        return np.array([center])

    width = 8  # the diameter of the aperture is 8 mm
    step = float(step)
    if not (width / step).is_integer():
        raise ValueError(f'The width {width} is not an integer multiple of the step size {step}')

    central = linspace(center, 0.5, step/2)[::2]
    rising = linspace(center-width/2, 0.5, step/2)[::2]
    falling = linspace(center+width/2, 0.5, step/2)[::2]
    return np.concatenate((rising, central, falling))


def ave_std(data, *, axis=None):
    """Return the average and standard deviation of an array.

    Parameters
    ----------
    data : :class:`numpy.ndarray`
        The data.
    axis : None or int or tuple of ints, optional
        Axis or axes along which the average and standard
        deviation is computed.

    Returns
    -------
    :class:`float` or :class:`numpy.ndarray`
        The average value.
    :class:`float` or :class:`numpy.ndarray`
        The standard deviation.
    """
    if data.size > 1:
        return np.average(data, axis=axis), np.std(data, axis=axis, ddof=1)
    if data.size == 1:
        return data[0], np.NaN
    return np.NaN, np.NaN
