"""
Keysight 344(60|61|65|70)A digital multimeter.
"""
import re

from .base import equipment
from .dmm import DMM

_info_regex: re.Pattern[str] = re.compile(
    r':FUNC "(?P<FUNCTION>[A-Z]+)".*'
    r';:TRIG:SOUR (?P<TRIGGER_SOURCE>[A-Z]+).*'
    r';:TRIG:COUN (?P<TRIGGER_COUNT>\+\d\.\d+E[-+]\d+).*'
    r';:TRIG:DEL (?P<TRIGGER_DELAY>\+\d\.\d+E[-+]\d+).*'
    r';:TRIG:DEL:AUTO (?P<TRIGGER_DELAY_AUTO>\d).*'
    r';:TRIG:SLOP (?P<TRIGGER_EDGE>[A-Z]+).*'
    r';:SAMP:COUN \+(?P<NSAMPLES>\d+).*'
    r';:CURR:NPLC (?P<CURRENT_NPLC>\+\d\.\d+E[-+]\d+).*'
    r';:CURR:RANG (?P<CURRENT_RANGE>\+\d\.\d+E[-+]\d+).*'
    r';:CURR:RANG:AUTO (?P<CURRENT_RANGE_AUTO>\d).*'
    r';:CURR:ZERO:AUTO (?P<CURRENT_AUTO_ZERO>\d).*'
    r';:VOLT:NPLC (?P<VOLTAGE_NPLC>\+\d\.\d+E[-+]\d+).*'
    r';:VOLT:RANG (?P<VOLTAGE_RANGE>\+\d\.\d+E[-+]\d+).*'
    r';:VOLT:RANG:AUTO (?P<VOLTAGE_RANGE_AUTO>\d).*'
    r';:VOLT:ZERO:AUTO (?P<VOLTAGE_AUTO_ZERO>\d).*'
)


@equipment(manufacturer=r'Keysight', model=r'344(60|61|65|70)A')
class Keysight344XXA(DMM):
    """Keysight 344(60|61|65|70)A digital multimeter."""

    def check_errors(self) -> None:
        """Query the digital multimeter’s error queue.

        If there is an error then raise an exception.
        """
        message = self.connection.query('SYSTEM:ERROR:NEXT?').rstrip()
        if message != '+0,"No error"':
            self.raise_exception(message)

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
                Can be any key in :attr:`.DMM.TRIGGERS` (case insensitive).
            edge: The edge to trigger on.
                Can be any key in :attr:`.DMM.EDGES` (case insensitive).
            ntriggers: The number of triggers that are accepted by the digital
                multimeter before returning to the wait-for-trigger state.
            delay: The trigger delay in seconds. If None, then the auto-delay
                feature is enabled where the digital multimeter automatically
                determines the delay based on the function, range and NPLC.

        Returns:
            The result of :meth:`.settings` after applying the configuration.
        """
        function = DMM.FUNCTIONS[function.upper()]
        range_ = DMM.RANGES.get(range, range)
        nplc = DMM.NPLCS[float(nplc)]
        auto_zero = DMM.AUTO[auto_zero]
        trigger = DMM.TRIGGERS[trigger.upper()]
        edge = DMM.EDGES[edge.upper()]
        delay = ':AUTO ON' if delay is None else f' {delay}'  # must include a space before {delay}

        command = f'CONFIGURE:{function} {range_};' \
                  f':{function}:NPLC {nplc};ZERO:AUTO {auto_zero};' \
                  f':SAMPLE:COUNT {nsamples};' \
                  f':TRIGGER:SOURCE {trigger};SLOPE {edge};COUNT {ntriggers};DELAY{delay}'

        self.logger.info(f'configure {self.alias!r} using {command!r}')
        self._send_command_with_opc(command)
        self.check_errors()
        settings = self.settings()
        self.settings_changed.emit(settings)
        self.maybe_emit_notification(**settings)
        return settings

    def settings(self) -> dict[str, ...]:
        """Returns the configuration settings of the digital multimeter.
        ::

            {
              'auto_range': str,
              'auto_zero': str,
              'function': str,
              'nplc': float,
              'nsamples': int,
              'range': float,
              'trigger_count': int,
              'trigger_delay': float,
              'trigger_delay_auto': bool,
              'trigger_edge': str,
              'trigger_mode': str,
            }
        """
        match = _info_regex.search(self.connection.query('*LRN?'))
        if not match:
            self.raise_exception(f'invalid regex pattern for {self.alias!r}')
        d = match.groupdict()
        function = DMM.FUNCTIONS[d['FUNCTION']]
        edge = DMM.EDGES[d['TRIGGER_EDGE']]
        return {
            'auto_range': DMM.AUTO[d[f'{function}_RANGE_AUTO']],
            'auto_zero': DMM.AUTO[d[f'{function}_AUTO_ZERO']],
            'function': function,
            'nplc': float(d[f'{function}_NPLC']),
            'nsamples': int(d['NSAMPLES']),
            'range': float(d[f'{function}_RANGE']),
            'trigger_count': int(float(d['TRIGGER_COUNT'])),
            'trigger_delay': float(d['TRIGGER_DELAY']),
            'trigger_delay_auto': d['TRIGGER_DELAY_AUTO'] == '1',
            'trigger_edge': 'FALLING' if edge == 'NEGATIVE' else 'RISING',
            'trigger_mode': DMM.TRIGGERS[d['TRIGGER_SOURCE']],
        }
