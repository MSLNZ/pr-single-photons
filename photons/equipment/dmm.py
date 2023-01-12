"""
Base class for a digital multimeter.
"""
from msl.equipment import Backend
from msl.equipment import EquipmentRecord
from msl.equipment.connection_message_based import ConnectionMessageBased
from msl.qt import MICRO
from msl.qt import QtCore
from msl.qt import Signal

from .base import BaseEquipment
from ..samples import Samples


class DMM(BaseEquipment):

    connection: ConnectionMessageBased

    FUNCTIONS: dict[str, str] = {
        'DCV': 'VOLTAGE',
        'VOLT': 'VOLTAGE',
        'VOLTAGE': 'VOLTAGE',
        '"VOLT:DC"': 'VOLTAGE',
        'CURR': 'CURRENT',
        'CURRENT': 'CURRENT',
        'DCI': 'CURRENT',
        '"CURR:DC"': 'CURRENT',
    }

    RANGES: dict[str, str | float] = {
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

    NPLCS: dict[float, float] = {
        100.0: 100,
        10.0: 10,
        1.0: 1,
        0.2: 0.2,
        0.06: 0.06,
        0.02: 0.02,
    }

    EDGES: dict[str, str] = {
        'RISING': 'POSITIVE',
        'POSITIVE': 'POSITIVE',
        'POS': 'POSITIVE',
        'FALLING': 'NEGATIVE',
        'NEGATIVE': 'NEGATIVE',
        'NEG': 'NEGATIVE',
    }

    TRIGGERS: dict[str, str] = {
        'IMM': 'IMMEDIATE',
        'IMMEDIATE': 'IMMEDIATE',
        'EXT': 'EXTERNAL',
        'EXTERNAL': 'EXTERNAL',
        'BUS': 'BUS',
        'INT': 'INTERNAL',
        'INTERNAL': 'INTERNAL',
    }

    AUTO: dict[bool | int | str, str] = {
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

    fetched: QtCore.SignalInstance = Signal(Samples)
    settings_changed: QtCore.SignalInstance = Signal(dict)

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Base class for a digital multimeter.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        if record.connection.backend == Backend.PyVISA:
            # "pop" this item from the properties to avoid the following
            #   ValueError: 'clear' is not a valid attribute for type *Instrument
            #   ValueError: 'reset' is not a valid attribute for type *Instrument
            pop_or_get = record.connection.properties.pop
        else:
            pop_or_get = record.connection.properties.get

        clear = pop_or_get('clear', False)
        reset = pop_or_get('reset', False)

        super().__init__(record, **kwargs)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes('fetched', 'settings_changed')

        if clear:
            self.clear()
        if reset:
            self.reset()

    def acquisition_time(self,
                         *,
                         line_freq: float = 50,
                         settings: dict = None) -> float:
        """Get the approximate number of seconds it takes to acquire samples.

        Args:
            line_freq: The line frequency, in Hz.
            settings: The configuration settings of the digital multimeter.
        """
        if not settings:
            settings = self.settings()
        x = settings['nsamples'] * settings['trigger_count'] * settings['nplc']
        if settings['auto_zero'] == 'ON':
            x *= 2
        return x / float(line_freq)

    def bus_trigger(self) -> None:
        """Send a software trigger to the digital multimeter."""
        self.logger.info(f'software trigger {self.alias!r}')
        self.write('INIT;*TRG')

    software_trigger = bus_trigger

    def check_errors(self) -> None:
        """Query the error queue of the digital multimeter.

        If there is an error then raise an exception.
        """
        raise NotImplementedError

    def clear(self) -> None:
        """Clears the event registers in all register groups and the error queue."""
        self.logger.info(f'clear {self.alias!r}')
        self._send_command_with_opc('*CLS')

    def configure(self,
                  *,
                  function: str = 'voltage',
                  range: float | str = 10,  # noqa: Shadows built-in name 'range'
                  nsamples: int = 10,
                  nplc: float = 10,
                  auto_zero: bool | int | str = True,
                  trigger: str = 'bus',
                  edge: str = 'falling',
                  ntriggers: int = 1,
                  delay: float = None) -> dict[str, ...]:
        """Configure the digital multimeter.

        Returns:
            The result of :meth:`.settings` after applying the configuration.
        """
        raise NotImplementedError

    def fetch(self, initiate: bool = False) -> Samples:
        """Fetch the samples.

        Args:
            initiate: Whether to send INIT before FETCH?.
        """
        if initiate:
            self.logger.info(f'send INIT to {self.alias!r}')
            self.connection.write('INIT')
        samples = self.connection.query('FETCH?')
        return self._average_and_emit(samples)

    def reset(self) -> None:
        """Resets the digital multimeter to the factory default state."""
        self.logger.info(f'reset {self.alias!r}')
        self._send_command_with_opc('*RST')

    def settings(self) -> dict[str, ...]:
        """Returns the configuration settings of the digital multimeter."""
        raise NotImplementedError

    def _send_command_with_opc(self, command: str) -> None:
        """Appends ``'*OPC?'`` to the end of a command.

        The *OPC? command guarantees that commands that were previously sent
        to the device have completed.
        """
        command += ';*OPC?'
        reply = self.connection.query(command)
        assert reply.startswith('1'), f'{command!r} did not return "1"'

    def _average_and_emit(self, samples: str | list[str]) -> Samples:
        """Compute the average and standard deviation and emit.

        Args:
            samples: A comma-separated string of readings or a list of readings.

        Returns:
           The average value and the standard deviation.
        """
        self.logger.info(f'fetch {self.alias!r} samples={samples!r}')
        s = Samples(samples)
        self.fetched.emit(s)
        self.maybe_emit_notification(s.mean, s.std)
        return s
