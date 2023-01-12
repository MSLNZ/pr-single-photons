"""
Keithley 6430 sub-femtoAmp SourceMeter.
"""
from time import perf_counter

from msl.equipment import EquipmentRecord
from msl.qt import QtCore
from msl.qt import Signal

from .base import equipment
from .dmm import DMM


@equipment(manufacturer='Keithley', model='6430')
class Keithley6430(DMM):

    MODES: dict[str, str] = {
        'FIX': 'FIXED',
        'FIXED': 'FIXED',
        'LIST': 'LIST',
        'SWE': 'SWEEP',
        'SWEEP': 'SWEEP',
    }

    TRIGGERS: dict[str, str] = {
        'IMM': 'IMMEDIATE',
        'IMMEDIATE': 'IMMEDIATE',
        'TLIN': 'TLINK',
        'TLINK': 'TLINK',
        'TIM': 'TIMER',
        'TIMER': 'TIMER',
        'MAN': 'MANUAL',
        'MANUAL': 'MANUAL',
        'BUS': 'BUS',
        'NST': 'NSTEST',
        'NSTEST': 'NSTEST',
        'PST': 'PSTEST',
        'PSTEST': 'PSTEST',
        'BST': 'BSTEST',
        'BSTEST': 'BSTEST',
    }

    source_settings_changed: QtCore.SignalInstance = Signal(dict)  # the result of settings_source()

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Keithley 6430 sub-femtoAmp SourceMeter.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)
        self._output_function: str = ''
        self._output_level: float | None = None
        self._output_range: float = 9e9
        self.disconnect = self._disconnect

    def check_errors(self) -> None:
        """Query the error queue of the SourceMeter.

        If there is an error then raise an exception.
        """
        message = self.connection.query(':SYSTEM:ERROR:NEXT?')
        if not message.startswith('0,'):
            self.raise_exception(message)

    def configure(self,
                  *,
                  function: str = 'current',
                  range: float | str = 1.05e-6,  # noqa: Shadows built-in name 'range'
                  nsamples: int = 10,
                  nplc: int = 10,
                  auto_zero: bool | int | str = True,
                  trigger: str = 'bus',
                  edge: None = None,
                  ntriggers: int = 1,
                  delay: float = 0.0,
                  cmpl: float = 105e-6,
                  enable: bool = True) -> dict[str, ...]:
        """Configure the Sense subsystem.

        Args:
            function: The function to measure.
                Can be any key in :attr:`.DMM.FUNCTIONS` (case insensitive).
            range: The range to use for the measurement.
                Can be any key in :attr:`.DMM.RANGES`.
            nsamples: The number of samples to acquire after a trigger event.
            nplc: The number of power-line cycles.
            auto_zero: The auto-zero mode.
                Can be any key in :attr:`.DMM.AUTO`.
            trigger: The trigger mode.
                Can be any key in :attr:`Keithley6430.TRIGGERS` (case insensitive).
            edge: Not supported and must be None (the edge to trigger on).
            ntriggers: The number of triggers that are accepted by the SourceMeter
                before returning to the wait-for-trigger state.
            delay: The trigger delay in seconds (auto delay is not supported).
            cmpl: The protection (compliance) value.
            enable: Whether to enable the output.

        Returns:
            The result of :meth:`.settings` after applying the configuration.
        """
        if edge is not None:
            self.raise_exception('Changing the trigger edge is not supported')

        function = DMM.FUNCTIONS[function.upper()]
        range_ = DMM.RANGES.get(range, range)
        auto_zero = DMM.AUTO[auto_zero]
        trigger = Keithley6430.TRIGGERS[trigger.upper()]

        source_function = 'CURRENT' if function == 'VOLTAGE' else 'VOLTAGE'
        range_ = ':AUTO ON' if range_ == 'AUTO' else f' {range_}'

        command = f':SOURCE:FUNCTION {source_function};' \
                  f':SOURCE:{source_function}:MODE FIXED;' \
                  f':SENSE:FUNCTION "{function}";' \
                  f':SOURCE:{source_function}:RANGE MIN;LEVEL 0;' \
                  f':SENSE:{function}:NPLC {nplc};PROTECTION {cmpl};RANGE{range_};' \
                  f':SYSTEM:AZERO {auto_zero};' \
                  f':TRIGGER:COUNT {ntriggers * nsamples};DELAY {delay};' \
                  f':ARM:SOURCE {trigger};' \
                  f':FORMAT:ELEMENTS {function}'

        self.logger.info(f'configure {self.alias!r} using {command!r}')
        self._send_command_with_opc(command)
        self.check_errors()
        settings = self.settings()
        self.settings_changed.emit(settings)
        self.maybe_emit_notification(**settings)
        if enable:
            self.enable_output()
        return settings

    def configure_source(self,
                         *,
                         function: str = 'current',
                         range: float = 1e-6,  # noqa: Shadows built-in name 'range'
                         nsamples: int = 10,
                         auto_zero: bool | int | str = True,
                         trigger: str = 'bus',
                         delay: float = 0.0,
                         mode: str = 'fixed',
                         cmpl: float = 0.01,
                         cmpl_range: float = 0.21) -> dict[str, ...]:
        """Configure the Source subsystem.

        Args:
            function: The output source.
                Can be any key in :attr:`.DMM.FUNCTIONS` (case insensitive).
            range: The range to use for the output level.
            nsamples: The number of samples to acquire after a trigger event.
            auto_zero: The auto-zero mode.
                Can be any key in :attr:`.DMM.AUTO`.
            trigger: The trigger mode.
                Can be any key in :attr:`Keithley6430.TRIGGERS` (case insensitive).
            delay: The trigger delay in seconds.
            mode: The output mode.
                Can be any key in :attr:`Keithley6430.MODES` (case insensitive).
            cmpl: The protection (compliance) value.
            cmpl_range: The range to use for the protection (compliance).

        Returns:
            The result of :meth:`.settings_source` after applying the configuration.
        """
        function = DMM.FUNCTIONS[function.upper()]
        mode = Keithley6430.MODES[mode.upper()]
        trigger = Keithley6430.TRIGGERS[trigger.upper()]
        auto_zero = DMM.AUTO[auto_zero]

        sense_function = 'CURRENT' if function == 'VOLTAGE' else 'VOLTAGE'

        command = f':SOURCE:FUNCTION {function};' \
                  f':SOURCE:{function}:MODE {mode};RANGE {range};LEVEL 0;' \
                  f':SENSE:{sense_function}:RANGE {cmpl_range};PROTECTION {cmpl};' \
                  f':SYSTEM:AZERO {auto_zero};' \
                  f':TRIGGER:COUNT {nsamples};DELAY {delay};' \
                  f':ARM:SOURCE {trigger};' \
                  f':FORMAT:ELEMENTS {function}'

        self.logger.info(f'configure {self.alias!r} output using {command!r}')
        self._send_command_with_opc(command)
        self.check_errors()
        settings = self.settings_source()
        self._output_function = settings['function']
        self._output_range = settings['range']
        self.source_settings_changed.emit(settings)
        self.maybe_emit_notification(**settings)
        return settings

    def disable_output(self) -> None:
        """Turn the output off."""
        self._set_output_state(False)

    def enable_output(self) -> None:
        """Turn the output on."""
        self._set_output_state(True)

    def get_output_level(self) -> float:
        """Returns the output level."""
        return float(self.connection.query(':READ?'))

    def is_output_enabled(self) -> bool:
        """Returns whether the source output is on or off."""
        return self.connection.query(':OUTPUT?').startswith('1')

    def is_output_stable(self, tol: float = 1e-3) -> bool:
        """Whether the output level has stabilized.

        You must call :meth:`.set_output_level` once before calling this
        method, otherwise the level comparison is meaningless.

        Args:
            tol: The fractional tolerance for the output to be considered stable.
        """
        if self._output_level is None:
            self.raise_exception(f'Must call set_output_level() first')

        # TODO should check a history of values, not just 1 value
        value = self.get_output_level()
        if self._output_level == 0 and abs(value) < self._output_range * 1e-4:
            return True
        if abs(1.0 - self._output_level / value) < tol:
            return True
        return False

    def set_output_level(self,
                         level: float,
                         *,
                         wait: bool = False,
                         tol: float = 1e-3,
                         timeout: float = 60) -> None:
        """Set the level of the Source output.

        Args:
            level: The value to set the output to.
            wait: Whether to wait for the output level to stabilize before returning.
            tol: The fractional tolerance for the level to be considered stable.
            timeout: The maximum number of seconds to wait.
        """
        self._output_level = level
        command = f':SOURCE:{self._output_function}:LEVEL {self._output_level}'
        self.logger.info(f'set {self.alias!r} {self._output_function} level to {self._output_level}')
        self._send_command_with_opc(command)
        self.check_errors()
        if wait:
            # The self.is_output_stable() method sends the READ? command which
            # is not compatible if the device has been configured for a BUS trigger.
            # Temporarily change the :ARM:SOURCE if this is the case.
            # Also, ensure that the trigger count is 1.
            src, cnt = self.connection.query(':ARM:SOURCE?;:TRIGGER:COUNT?').split(';')
            trigger = Keithley6430.TRIGGERS[src]
            trigger_count = int(cnt)
            update_settings = trigger != 'IMMEDIATE' or trigger_count != 1
            if update_settings:
                self._send_command_with_opc(':ARM:SOURCE IMMEDIATE;:TRIGGER:COUNT 1')

            t0 = perf_counter()
            while True:
                if self.is_output_stable(tol=tol):
                    break

                if perf_counter() - t0 > timeout:
                    self.disable_output()
                    raise TimeoutError(f'Setting the level for {self.alias!r} '
                                       f'took more than {timeout} seconds')

            if update_settings:
                self._send_command_with_opc(f':ARM:SOURCE {trigger};'
                                            f':TRIGGER:COUNT {trigger_count}')

    def settings(self) -> dict[str, ...]:
        """Returns the configuration settings of the Sense subsystem.
        ::

            {
              'auto_range': str,
              'auto_zero': str,
              'cmpl': float,
              'function': str,
              'nplc': float,
              'nsamples': 1,
              'range': float,
              'trigger_count': int,
              'trigger_delay': float,
              'trigger_delay_auto': False,
              'trigger_edge': 'N/A',
              'trigger_mode': str
            }
        """
        function = DMM.FUNCTIONS[self.connection.query(':SENSE:FUNCTION?')]
        command = f':SENSE:{function}:NPLC?;PROTECTION?;RANGE?;RANGE:AUTO?;' \
                  f':SYSTEM:AZERO?;' \
                  f':ARM:SOURCE?;' \
                  f':TRIGGER:COUNT?;DELAY?'
        reply = self.connection.query(command)
        nplc, cmpl, rng, arange, azero, arm, cnt, delay = reply.split(';')
        return {
            'auto_range': DMM.AUTO[arange],
            'auto_zero': DMM.AUTO[azero],
            'cmpl': float(cmpl),
            'function': function,
            'nplc': float(nplc),
            'nsamples': 1,
            'range': float(rng),
            'trigger_count': int(cnt),
            'trigger_delay': float(delay),
            'trigger_delay_auto': False,
            'trigger_edge': 'N/A',
            'trigger_mode': Keithley6430.TRIGGERS[arm]
        }

    def settings_source(self) -> dict[str, ...]:
        """Returns the configuration settings of the Source subsystem.
        ::

            {
              'auto_zero': str,
              'cmpl': float,
              'cmpl_range': float,
              'function': str,
              'mode': str,
              'nsamples': int,
              'range': float,
              'trigger_delay': float,
              'trigger_mode': str
            }
        """
        function = DMM.FUNCTIONS[self.connection.query(':SOURCE:FUNCTION?')]
        sense_function = 'CURRENT' if function == 'VOLTAGE' else 'VOLTAGE'
        command = f':SOURCE:{function}:MODE?;RANGE?;' \
                  f':SENSE:{sense_function}:RANGE?;PROTECTION?;' \
                  f':SYSTEM:AZERO?;' \
                  f':ARM:SOURCE?;' \
                  f':TRIGGER:COUNT?;DELAY?'
        reply = self.connection.query(command)
        mode, rng, cmpl_range, cmpl, azero, arm, cnt, delay = reply.split(';')
        return {
            'auto_zero': DMM.AUTO[azero],
            'cmpl': float(cmpl),
            'cmpl_range': float(cmpl_range),
            'function': function,
            'mode': Keithley6430.MODES[mode],
            'nsamples': int(cnt),
            'range': float(rng),
            'trigger_delay': float(delay),
            'trigger_mode': Keithley6430.TRIGGERS[arm]
        }

    def _disconnect(self) -> None:
        """Turn the output off and disconnect."""
        self.disable_output()
        self.connection.disconnect()

    def _set_output_state(self, state: bool) -> None:
        """Turn the output on or off."""
        on_off = 'ON' if state else 'OFF'
        self.logger.info(f'turn {self.alias!r} {on_off}')
        self._send_command_with_opc(f':OUTPUT:STATE {on_off}')
        self.check_errors()
