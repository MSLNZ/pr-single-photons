"""
Communicate with a Keysight 344(60|61|65|70)A digital multimeter.
"""
import re

from . import equipment
from .dmm import DMM

_info_regex = re.compile(
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
    """Communicate with a Keysight 344(60|61|65|70)A digital multimeter."""

    def check_errors(self) -> None:
        """Query the multimeter’s error queue.

        If there is an error then raise an exception.
        """
        message = self.connection.query('SYSTEM:ERROR:NEXT?').rstrip()
        if message != '+0,"No error"':
            self.connection.raise_exception(message)

    def info(self) -> dict:
        """Get the configuration information of the digital multimeter.

        Returns
        -------
        :class:`dict`
            The configuration, in the form::

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
            self.connection.raise_exception(f'invalid info regex pattern for {self.alias!r}')
        d = match.groupdict()
        function = self.FUNCTIONS[d['FUNCTION']]
        edge = self.EDGES[d['TRIGGER_EDGE']]
        return {
            'auto_range': self.AUTO[d[function+'_RANGE_AUTO']],
            'auto_zero': self.AUTO[d[function+'_AUTO_ZERO']],
            'function': function,
            'nplc': float(d[function+'_NPLC']),
            'nsamples': int(d['NSAMPLES']),
            'range': float(d[function+'_RANGE']),
            'trigger_count': int(float(d['TRIGGER_COUNT'])),
            'trigger_delay': float(d['TRIGGER_DELAY']),
            'trigger_delay_auto': d['TRIGGER_DELAY_AUTO'] == '1',
            'trigger_edge': 'FALLING' if edge == 'NEGATIVE' else 'RISING',
            'trigger_mode': self.TRIGGERS[d['TRIGGER_SOURCE']],
        }

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
            The auto-zero mode. Can be any key in :attr:`.DMM.AUTO`.
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
        function = self.FUNCTIONS[function.upper()]
        range_ = self.RANGES.get(range, range)
        nplc = self.NPLCS[float(nplc)]
        auto_zero = self.AUTO[auto_zero]
        trigger = self.TRIGGERS[trigger.upper()]
        edge = self.EDGES[edge.upper()]
        delay = ':AUTO ON' if delay is None else f' {delay}'  # must include the space before {delay}

        command = f'CONFIGURE:{function} {range_};' \
                  f':{function}:NPLC {nplc};ZERO:AUTO {auto_zero};' \
                  f':SAMPLE:COUNT {nsamples};' \
                  f':TRIGGER:SOURCE {trigger};SLOPE {edge};COUNT {ntriggers};DELAY{delay}'

        self.logger.info(f'configure {self.alias!r} using {command!r}')
        self._send_command_with_opc(command)
        self.check_errors()
        info = self.info()
        self.config_changed.emit(info)
        self.emit_notification(**info)
        return info
