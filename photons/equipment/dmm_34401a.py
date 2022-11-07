"""
Hewlett Packard 34401A digital multimeter.
"""
import re

from msl.equipment import EquipmentRecord
from msl.equipment.connection_serial import ConnectionSerial

from .base import equipment
from .dmm import DMM
from ..samples import Samples

# Reduce the number of writes/reads that are needed when calling
# HP34401A.settings(). The order of the queries in the command and in the regex
# must be the same. The multimeter complains if the length of a query is too
# long, so break it up in 2 commands.

_command1 = 'CONFIGURE?;' \
            ':SENSE:CURRENT:RANGE:AUTO?;' \
            ':SENSE:VOLTAGE:RANGE:AUTO?;' \
            ':SENSE:ZERO:AUTO?;' \
            ':SENSE:CURRENT:NPLC?;' \
            ':SENSE:VOLTAGE:NPLC?;'

_command1_regex: re.Pattern[str] = re.compile(
    r'(?P<FUNCTION>[A-Z]+)\s(?P<RANGE>(\+\d\.\d+E[-+]\d+)),.*;'
    r'(?P<CURRENT_RANGE_AUTO>\d);'
    r'(?P<VOLTAGE_RANGE_AUTO>\d);'
    r'(?P<AUTO_ZERO>\d);'
    r'(?P<CURRENT_NPLC>\+\d\.\d+E[-+]\d+);'
    r'(?P<VOLTAGE_NPLC>\+\d\.\d+E[-+]\d+)'
)

_command2 = 'SAMPLE:COUNT?;' \
            ':TRIGGER:SOURCE?;' \
            ':TRIGGER:COUNT?;' \
            ':TRIGGER:DELAY?;' \
            ':TRIGGER:DELAY:AUTO?;'

_command2_regex: re.Pattern[str] = re.compile(
    r'(?P<NSAMPLES>\+\d+);'
    r'(?P<TRIGGER_SOURCE>[A-Z]+);'
    r'(?P<TRIGGER_COUNT>\+\d\.\d+E[-+]\d+);'
    r'(?P<TRIGGER_DELAY>\+\d\.\d+E[-+]\d+);'
    r'(?P<TRIGGER_DELAY_AUTO>\d)'
)


@equipment(manufacturer=r'H.*P.*', model=r'34401A')
class HP34401A(DMM):

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Hewlett Packard 34401A digital multimeter.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)
        self._rs232: bool = isinstance(self.connection, ConnectionSerial)
        if self._rs232:
            self.remote_mode()
        self.disconnect = self._disconnect

    def bus_trigger(self) -> None:
        """Send a software trigger to the digital multimeter."""
        self.logger.info(f'software trigger {self.alias!r}')
        if self._rs232:
            self.connection.write('INIT;*TRG;*OPC?')
        else:
            self.connection.write('INIT;*TRG;*OPC')

    def check_errors(self) -> None:
        """Query the error queue of the digital multimeter.

        If there is an error then raise an exception.
        """
        message = self.connection.query('SYSTEM:ERROR?').rstrip()
        if message != '+0,"No error"':
            self.raise_exception(message)

    def configure(self,
                  *,
                  function: str = 'voltage',
                  range: float | str = 10,  # noqa: Shadows built-in name 'range'
                  nsamples: int = 10,
                  nplc: float = 10,
                  auto_zero: bool | str = True,
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
        edge = DMM.EDGES[edge.upper()]
        if edge != 'NEGATIVE':
            self.raise_exception(f'Can only trigger {self.alias!r} on '
                                 f'the falling (negative) edge')

        function = DMM.FUNCTIONS[function.upper()]
        range_ = DMM.RANGES.get(range, range)
        nplc = DMM.NPLCS[float(nplc)]
        auto_zero = DMM.AUTO[auto_zero]
        trigger = DMM.TRIGGERS[trigger.upper()]
        delay = ':AUTO ON' if delay is None else f' {delay}'  # must include a space before {delay}

        command = f'CONFIGURE:{function} {range_};' \
                  f':{function}:NPLC {nplc};' \
                  f':SENSE:ZERO:AUTO {auto_zero};' \
                  f':SAMPLE:COUNT {nsamples};' \
                  f':TRIGGER:SOURCE {trigger};COUNT {ntriggers};DELAY{delay}'

        self.logger.info(f'configure {self.alias!r} using {command!r}')
        self._send_command_with_opc(command)
        self.check_errors()
        settings = self.settings()
        self.settings_changed.emit(settings)
        self.maybe_emit_notification(**settings)
        return settings

    def fetch(self, initiate: bool = False) -> Samples:
        """Fetch the samples.

        Args:
            initiate: Whether to send INIT before FETCH?.
        """
        if not initiate and self._rs232:
            if not self.connection.read().startswith('1'):
                self.raise_exception('*OPC? from bus_trigger did not return 1')
        return super().fetch(initiate=initiate)

    def local_mode(self) -> None:
        """Set the multimeter to be in LOCAL mode for the RS-232 interface.

        All keys on the front panel are fully functional.
        """
        if not self._rs232:
            self.logger.warning(f'setting {self.alias!r} to LOCAL mode is '
                                f'only valid for the RS-232 interface')
            return

        self.logger.info(f'set {self.alias!r} to LOCAL mode')
        self._send_command_with_opc('SYSTEM:LOCAL')

    def remote_mode(self) -> None:
        """Set the multimeter to be in REMOTE mode for the RS-232 interface.

        All keys on the front panel, except the LOCAL key, are disabled.
        """
        if not self._rs232:
            self.logger.warning(f'setting {self.alias!r} to REMOTE mode is '
                                f'only valid for the RS-232 interface')
            return

        self.logger.info(f'set {self.alias!r} to REMOTE mode')
        self._send_command_with_opc('SYSTEM:REMOTE')

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
        match1 = _command1_regex.search(self.connection.query(_command1))
        match2 = _command2_regex.search(self.connection.query(_command2))
        if not match1 or not match2:
            self.raise_exception(f'invalid regex pattern for {self.alias!r}')

        d1 = match1.groupdict()
        d2 = match2.groupdict()
        function = DMM.FUNCTIONS[d1['FUNCTION']]
        return {
            'auto_range': DMM.AUTO[d1[f'{function}_RANGE_AUTO']],
            'auto_zero': DMM.AUTO[d1['AUTO_ZERO']],
            'function': function,
            'nplc': float(d1[f'{function}_NPLC']),
            'nsamples': int(d2['NSAMPLES']),
            'range': float(d1['RANGE']),
            'trigger_count': int(float(d2['TRIGGER_COUNT'])),
            'trigger_delay': float(d2['TRIGGER_DELAY']),
            'trigger_delay_auto': d2['TRIGGER_DELAY_AUTO'] == '1',
            'trigger_edge': 'FALLING',  # only triggers on the falling edge of an external TTL pulse
            'trigger_mode': DMM.TRIGGERS[d2['TRIGGER_SOURCE']],
        }

    def _disconnect(self) -> None:
        """Set the digital multimeter to be in LOCAL mode and then close the connection."""
        if self._rs232:
            self.local_mode()
        self.connection.disconnect()
