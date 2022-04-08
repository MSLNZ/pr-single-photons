"""
Base class for a digital multimeter.
"""
import numpy as np
from msl.equipment import Backend
from msl.qt import (
    Signal,
    MICRO,
)

from . import BaseEquipment
from ..utils import ave_std


class DMM(BaseEquipment):

    FUNCTIONS = {
        'DCV': 'VOLTAGE',
        'VOLT': 'VOLTAGE',
        'VOLTAGE': 'VOLTAGE',
        '"VOLT:DC"': 'VOLTAGE',
        'CURR': 'CURRENT',
        'CURRENT': 'CURRENT',
        'DCI': 'CURRENT',
        '"CURR:DC"': 'CURRENT',
    }

    RANGES = {
        'AUTO': 'AUTO',
        'auto': 'AUTO',
        'DEF': 'DEFAULT',
        'def': 'DEFAULT',
        'DEFAULT': 'DEFAULT',
        'default': 'DEFAULT',
        'MAX': 'MAXIMUM',
        'max': 'MAXIMUM',
        'MAXIMUM': 'MAXIMUM',
        'maximum': 'MAXIMUM',
        'MIN': 'MINIMUM',
        'min': 'MINIMUM',
        'MINIMUM': 'MINIMUM',
        'minimum': 'MINIMUM',
        '100 mV': 0.1,
        '1 V': 1.0,
        '10 V': 10.0,
        '100 V': 100.0,
        '1000 V': 1000.0,
        f'1 {MICRO}A': 1e-6,
        f'10 {MICRO}A': 10e-6,
        f'100 {MICRO}A': 100e-6,
        '1 uA': 1e-6,
        '10 uA': 10e-6,
        '100 uA': 100e-6,
        '1 mA': 0.001,
        '10 mA': 0.01,
        '100 mA': 0.1,
        '1 A': 1.0,
        '3 A': 3.0,
        '10 A': 10.0,
    }

    NPLCS = {
        100.0: 100,
        10.0: 10,
        1.0: 1,
        0.2: 0.2,
        0.06: 0.06,
        0.02: 0.02,
    }

    EDGES = {
        'RISING': 'POSITIVE',
        'POSITIVE': 'POSITIVE',
        'POS': 'POSITIVE',
        'FALLING': 'NEGATIVE',
        'NEGATIVE': 'NEGATIVE',
        'NEG': 'NEGATIVE',
    }

    TRIGGERS = {
        'IMM': 'IMMEDIATE',
        'IMMEDIATE': 'IMMEDIATE',
        'EXT': 'EXTERNAL',
        'EXTERNAL': 'EXTERNAL',
        'BUS': 'BUS',
        'INT': 'INTERNAL',
        'INTERNAL': 'INTERNAL',
    }

    AUTO = {
        'OFF': 'OFF',
        'off': 'OFF',
        '0': 'OFF',
        False: 'OFF',
        0: 'OFF',
        'ON': 'ON',
        'on': 'ON',
        '1': 'ON',
        True: 'ON',
        1: 'ON',
        'ONCE': 'ONCE',
        'once': 'ONCE',
        '2': 'ONCE',
        2: 'ONCE',
    }

    fetched = Signal(float, float)  # average, stdev
    config_changed = Signal(dict)  # the result of info()

    def __init__(self, app, record, *, demo=None):
        """Base class for a digital multimeter.

        Parameters
        ----------
        app : :class:`photons.App`
            The main application entry point.
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment record.
        demo : :class:`bool`, optional
            Whether to simulate a connection to the equipment by opening
            a connection in demo mode.
        """
        if record.connection.backend == Backend.PyVISA:
            # `pop` this item from the properties to avoid the following if using PyVISA for the connection
            #   ValueError: 'clear' is not a valid attribute for type *Instrument
            #   ValueError: 'reset' is not a valid attribute for type *Instrument
            pop_or_get = record.connection.properties.pop
        else:
            # use `get` if the backend is MSL so that clear/reset remains in
            # the properties if it has been defined
            pop_or_get = record.connection.properties.get

        clear = pop_or_get('clear', False)
        reset = pop_or_get('reset', False)

        super(DMM, self).__init__(app, record, demo=demo)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes(['fetched', 'config_changed'])

        if clear:
            self.clear()
        if reset:
            self.reset()

    def reset(self) -> None:
        """Resets device to factory default state."""
        self.logger.info(f'reset {self.alias!r}')
        self._send_command_with_opc('*RST')

    def clear(self) -> None:
        """Clears the event registers in all register groups and the error queue."""
        self.logger.info(f'clear {self.alias!r}')
        self._send_command_with_opc('*CLS')

    def bus_trigger(self) -> None:
        """Send a software trigger."""
        self.logger.info(f'software trigger {self.alias!r}')
        self.write('INIT;*TRG')

    software_trigger = bus_trigger

    def fetch(self, initiate: bool = False) -> tuple:
        """Fetch the samples.

        Parameters
        ----------
        initiate : :class:`bool`
            Whether to send the ``'INIT'`` command before sending ``'FETCH?'``.

        Returns
        -------
        :class:`float`
           The average value.
        :class:`float`
           The standard deviation.
        """
        if initiate:
            self.logger.info(f'send INIT to {self.alias!r}')
            self.connection.write('INIT')
        samples = self.connection.query('FETCH?').rstrip()
        return self._average_and_emit(samples)

    def acquisition_time(self, *,
                         info: dict = None,
                         line_freq: float = 50.) -> float:
        """Get the approximate number of seconds it takes to acquire the data.

        Parameters
        ----------
        info : :class:`dict`, optional
            The value returned by :meth:`.info`. If not specified then it
            will be automatically retrieved.
        line_freq : :class:`float`, optional
            The line frequency, in Hz.

        Returns
        -------
        :class:`float`
            The number of seconds.
        """
        if not info:
            info = self.info()
        duration = info['nsamples'] * info['trigger_count'] * info['nplc'] / line_freq
        if info['auto_zero'] == 'ON':
            duration *= 2.
        return duration

    def check_errors(self):
        """Query the digital multimeter’s error queue.

        If there is an error then raise an exception.
        """
        raise NotImplementedError

    def info(self) -> dict:
        """Get the configuration information of the digital multimeter."""
        raise NotImplementedError

    def configure(self, *, function='voltage', range=10, nsamples=10, nplc=10, auto_zero=True,
                  trigger='bus', edge='falling', ntriggers=1, delay=None) -> dict:
        """Configure the digital multimeter.

        Parameters
        ----------
        function : :class:`str`, optional
            The function to measure. Can be any key in :attr:`.DMM.FUNCTIONS` (case insensitive).
        range : :class:`float` or :class:`str`, optional
            The range to use for the measurement. Can be any key in :attr:`.DMM.RANGES`.
        nsamples : :class:`int`, optional
            The number of samples to acquire after receiving a trigger.
        nplc : :class:`float`, optional
            The number of power line cycles.
        auto_zero : :class:`bool` or :class:`str`, optional
            The auto-zero mode. Can be any key in :attr:`.DMM.AUTO_ZEROS`.
        trigger : :class:`str`, optional
            The trigger mode. Can be any key in :attr:`.DMM.TRIGGERS` (case insensitive).
        edge : :class:`str` or :attr:`.DMM.TriggerEdge`, optional
            The edge to trigger on. Can be any key in :attr:`.DMM.EDGES` (case insensitive).
        ntriggers : :class:`int`, optional
            The number of triggers that are accepted by the digital multimeter
            before returning to the *wait-for-trigger* state.
        delay : :class:`float` or :data:`None`, optional
            The trigger delay in seconds. If :data:`None` then enables the auto-delay
            feature where the digital multimeter automatically determines the delay
            based on the function, range and NPLC.

        Returns
        -------
        :class:`dict`
            The result of :meth:`.info` after the settings have been written.
        """
        raise NotImplementedError

    def _send_command_with_opc(self, command: str):
        """Appends ``'*OPC?'`` to the end of a command.

        The *OPC? command guarantees that command's that were previously sent
        to the device have completed.
        """
        command += ';*OPC?'
        assert self.connection.query(command).startswith('1'), f'{command!r} did not return "1"'

    def _average_and_emit(self, samples) -> tuple:
        """Compute the average and emit the value.

        Parameters
        ----------
        samples : :class:`str` or :class:`list`
            A comma-separated string of readings or a list of readings.

        Returns
        -------
        :class:`float`
           The average value.
        :class:`float`
           The standard deviation.
        """
        if isinstance(samples, str):
            samples = samples.split(',')
        samples = [float(val) for val in samples]
        self.logger.info(f'fetch {self.alias!r} {samples}')
        ave, stdev = ave_std(np.asarray(samples))
        if abs(ave) > 1e30:  # overload
            ave, stdev = np.NaN, np.NaN
        self.fetched.emit(ave, stdev)
        self.emit_notification(ave, stdev)  # emit to all linked Clients
        return ave, stdev
