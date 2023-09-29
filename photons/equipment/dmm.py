"""
Base class for a digital multimeter.
"""
from enum import StrEnum
from typing import Sequence

import numpy as np
from msl.equipment import Backend
from msl.equipment import EquipmentRecord
from msl.equipment.connection_message_based import ConnectionMessageBased
from msl.qt import QtCore
from msl.qt import Signal

from .base import BaseEquipment
from ..samples import Samples


class Auto(StrEnum):
    """For settings that can be in an auto mode (e.g., RANGE, ZERO)."""
    OFF = 'OFF'
    ON = 'ON'
    ONCE = 'ONCE'

    @classmethod
    def _missing_(cls, value):
        s = str(value).upper()
        if s in ('0', 'OFF', 'FALSE'):
            return cls.OFF
        if s in ('1', 'ON', 'TRUE'):
            return cls.ON
        if s in ('2', 'ONCE'):
            return cls.ONCE


class Edge(StrEnum):
    """The trigger edge."""
    RISING = 'RISING'
    FALLING = 'FALLING'
    BOTH = 'BOTH'

    @classmethod
    def _missing_(cls, value):
        s = str(value).upper()
        if s in ('RISING', 'RIS', 'POSITIVE', 'POS'):
            return cls.RISING
        if s in ('FALLING', 'FALL', 'NEGATIVE', 'NEG'):
            return cls.FALLING
        if s in ('BOTH', 'EITHER'):
            return cls.BOTH


class Function(StrEnum):
    """The measurement function."""
    DCV = 'DCV'
    DCI = 'DCI'

    @classmethod
    def _missing_(cls, value):
        s = str(value).upper()
        if s in ('DCV', 'VOLT', 'VOLT:DC', 'VOLTAGE'):
            return cls.DCV
        if s in ('DCI', 'CURR', 'CURR:DC', 'CURRENT'):
            return cls.DCI


class Mode(StrEnum):
    """The trigger mode."""
    IMMEDIATE = 'IMMEDIATE'
    BUS = 'BUS'
    EXTERNAL = 'EXTERNAL'

    @classmethod
    def _missing_(cls, value):
        s = str(value).upper()
        if s in ('IMMEDIATE', 'IMM', 'NONE'):
            return cls.IMMEDIATE
        if s in ('BUS', 'COMMAND', 'COMM'):
            return cls.BUS
        if s in ('EXTERNAL', 'EXT'):
            return cls.EXTERNAL


class Range(StrEnum):
    """Function range."""
    AUTO = 'AUTO'
    MINIMUM = 'MINIMUM'
    MAXIMUM = 'MAXIMUM'
    DEFAULT = 'DEFAULT'

    @classmethod
    def _missing_(cls, value):
        s = str(value).upper()
        if s == 'AUTO':
            return cls.AUTO
        if s in ('MIN', 'MINIMUM'):
            return cls.MINIMUM
        if s in ('MAX', 'MAXIMUM'):
            return cls.MAXIMUM
        if s in ('DEF', 'DEFAULT'):
            return cls.DEFAULT


class Trigger:

    def __init__(self, **kwargs) -> None:
        """The trigger settings of a DMM."""
        self.auto_delay: bool = bool(kwargs['auto_delay'])

        # first convert to float to avoid the following error
        #   ValueError: invalid literal for int() with base 10: '+1.00000000E+00'
        self.count: int = int(float(kwargs['count']))

        self.delay: float = float(kwargs['delay'])
        self.edge: Edge = Edge(kwargs['edge'])
        self.mode: Mode = Mode(kwargs['mode'])

    def __repr__(self) -> str:
        return (f'Trigger('
                f'auto_delay={self.auto_delay}, '
                f'count={self.count}, '
                f'delay={self.delay}, '
                f'edge={self.edge}, '
                f'mode={self.mode})')

    def to_json(self) -> dict[str, bool | int | float | str]:
        return {
            'auto_delay': self.auto_delay,
            'count': self.count,
            'delay': self.delay,
            'edge': self.edge.value,
            'mode': self.mode.value,
        }


class Settings:

    def __init__(self, **kwargs) -> None:
        """The configuration settings of a DMM."""
        self.auto_range: Auto = Auto(kwargs['auto_range'])
        self.auto_zero: Auto = Auto(kwargs['auto_zero'])
        self.function: Function = Function(kwargs['function'])
        self.nplc: float = float(kwargs['nplc'])
        self.nsamples: int = int(kwargs['nsamples'])
        self.range: float = float(kwargs['range'])
        trigger = kwargs['trigger']
        if isinstance(trigger, dict):
            trigger = Trigger(**trigger)
        self.trigger: Trigger = trigger

    def __repr__(self) -> str:
        return (f'Settings('
                f'auto_range={self.auto_range}, '
                f'auto_zero={self.auto_zero}, '
                f'function={self.function}, '
                f'nplc={self.nplc}, '
                f'nsamples={self.nsamples}, '
                f'range={self.range}, '
                f'trigger={self.trigger})')

    def to_json(self) -> dict[str, int | float | str | dict]:
        return {
            'auto_range': self.auto_range.value,
            'auto_zero': self.auto_zero.value,
            'function': self.function.value,
            'nplc': self.nplc,
            'nsamples': self.nsamples,
            'range': self.range,
            'trigger': self.trigger.to_json(),
        }


class DMM(BaseEquipment):

    Auto = Auto
    Edge = Edge
    Function = Function
    Mode = Mode
    Range = Range

    connection: ConnectionMessageBased

    fetched: QtCore.SignalInstance = Signal(Samples)
    settings_changed: QtCore.SignalInstance = Signal(Settings)

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Base class for a digital multimeter.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        self._initiate_cmd: str = 'updated in subclass()'
        self._trigger_cmd: str = 'updated in subclass()'
        self._zero_once_cmd: str = 'updated in subclass()'

        if record.connection.backend == Backend.PyVISA:
            # "pop" this item from the properties to avoid the following
            #   ValueError: 'clear' is not a valid attribute for type *Instrument
            #   ValueError: 'reset' is not a valid attribute for type *Instrument
            pop_or_get = record.connection.properties.pop
            self._timeout_factor = 1000
        else:
            pop_or_get = record.connection.properties.get
            self._timeout_factor = 1

        abort = pop_or_get('abort', False)
        clear = pop_or_get('clear', False)
        reset = pop_or_get('reset', False)

        super().__init__(record, **kwargs)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes('fetched', 'settings_changed')

        if abort:
            self.abort()
        if clear:
            self.clear()
        if reset:
            self.reset()

    def _average_and_emit(self, samples: str | Sequence[str | int | float]) -> Samples:
        """Compute the average and standard deviation and emit.

        Args:
            samples: A comma-separated string of readings or a sequence of readings.

        Returns:
           The :class:`.Samples`.
        """
        s = Samples(samples)
        a = np.array2string(s.samples, max_line_width=4096, separator=' ')
        self.logger.info(f'samples {self.alias!r} {a}')
        self.fetched.emit(s)
        self.maybe_emit_notification(s.mean, s.stdev, s.size)
        return s

    def _configure(self, command: str, opc: bool = True) -> Settings:
        """Send the configure() command."""
        self.logger.info(f'configure {self.alias!r} using {command!r}')
        if opc:
            self._send_command_with_opc(command)
        else:
            self.connection.write(command)
        self.check_errors()
        settings = self.settings()
        self.timeout = round(10 + self.acquisition_time(settings=settings)) * self._timeout_factor
        self.settings_changed.emit(settings)
        self.maybe_emit_notification(settings)
        return settings

    def _get_range(self, value) -> float | Range:
        """Get the range parameter."""
        if isinstance(value, int):
            return float(value)
        if isinstance(value, (float, self.Range)):
            return value
        if isinstance(value, str):
            return self.Range(value)
        raise ValueError(f'Invalid range {value}')

    def _send_command_with_opc(self, command: str) -> None:
        """Appends ``'*OPC?'`` to the end of a command.

        The *OPC? command guarantees that commands that were previously sent
        to the device have completed.
        """
        command += ';*OPC?'
        reply = self.connection.query(command)
        assert reply.startswith('1'), f'{command!r} did not return 1, {reply=!r}'

    def abort(self) -> None:
        """Abort a measurement in progress."""
        self.logger.info(f'abort measurement {self.alias!r}')
        self.connection.write('ABORT')

    def acquisition_time(self,
                         *,
                         settings: Settings = None,
                         all_triggers: bool = True,
                         line_freq: float = 50.) -> float:
        """Get the approximate number of seconds it takes to acquire samples.

        Args:
            settings: The configuration settings of the digital multimeter.
            all_triggers: Whether to include the time to acquire all triggers.
            line_freq: The line frequency, in Hz.
        """
        if settings is None:
            settings = self.settings()

        seconds_per_sample = settings.nplc / line_freq
        t = settings.nsamples * seconds_per_sample

        if settings.auto_zero == Auto.ON:
            t *= 2
        elif settings.auto_zero == Auto.ONCE:
            t += seconds_per_sample

        if all_triggers:
            t *= settings.trigger.count

        return t + settings.trigger.delay

    def check_errors(self) -> None:
        """Query the error queue.

        Raises an exception if there is an error.
        """
        raise NotImplementedError

    def clear(self) -> None:
        """Clears the event registers in all register groups and the error queue."""
        self.logger.info(f'clear {self.alias!r}')
        self._send_command_with_opc('*CLS')

    def configure(self,
                  *,
                  function: Function | str = Function.DCV,
                  range: float | str = 10,  # noqa: Shadows built-in name 'range'
                  nsamples: int = 10,
                  nplc: float = 10,
                  auto_zero: Auto | bool | int | str = Auto.ON,
                  trigger: Mode | str = Mode.IMMEDIATE,
                  edge: Edge | str = Edge.FALLING,
                  ntriggers: int = 1,
                  delay: float = None) -> Settings:
        """Configure the digital multimeter.

        Returns:
            The result of :meth:`.settings` after applying the configuration.
        """
        raise NotImplementedError

    def fetch(self, initiate: bool = False) -> Samples:
        """Fetch the samples.

        Args:
            initiate: Whether to call :meth:`.initiate` before fetching the data.
        """
        raise NotImplementedError

    def initiate(self) -> None:
        """Put the digital multimeter in the wait-for-trigger state (arm the trigger)."""
        self.logger.info(f'initiate trigger {self.alias!r}')
        self.connection.write(self._initiate_cmd)

    def reset(self) -> None:
        """Resets the digital multimeter to the factory default state."""
        self.logger.info(f'reset {self.alias!r}')
        self._send_command_with_opc('*RST')

    def settings(self) -> Settings:
        """Returns the configuration settings of the digital multimeter."""
        raise NotImplementedError

    def trigger(self) -> None:
        """Send a software trigger."""
        self.logger.info(f'software trigger {self.alias!r}')
        self.connection.write(self._trigger_cmd)

    def zero(self) -> None:
        """Reset the zero value.

        When the multimeter is configured with `auto_zero` set to OFF, the
        multimeter may gradually drift out of specification. To minimize the
        drift, you may call this method to take a new zero measurement.
        """
        self.logger.info(f'auto zero {self.alias!r}')
        self._send_command_with_opc(self._zero_once_cmd)
        self.check_errors()
