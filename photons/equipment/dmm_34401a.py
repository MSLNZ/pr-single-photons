"""
Hewlett Packard 34401A digital multimeter.
"""
import re
import warnings

from msl.equipment import EquipmentRecord
from msl.equipment.constants import Interface

from .base import equipment
from .dmm import DMM
from .dmm import Settings
from .dmm import Trigger
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
    r'(?P<DCI_AUTO_RANGE>\d);'
    r'(?P<DCV_AUTO_RANGE>\d);'
    r'(?P<AUTO_ZERO>\d);'
    r'(?P<DCI_NPLC>\+\d\.\d+E[-+]\d+);'
    r'(?P<DCV_NPLC>\+\d\.\d+E[-+]\d+)'
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
    r'(?P<TRIGGER_AUTO_DELAY>\d)'
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
        self._trigger_cmd: str = 'updated in configure()'
        self._zero_once_cmd: str = 'ZERO:AUTO ONCE'
        self._prologix: bool = self.record.connection.address.startswith('Prologix')
        self._gpib: bool = record.connection.interface == Interface.GPIB
        self._rs232: bool = record.connection.interface == Interface.SERIAL
        if self._rs232:
            self.connection.serial.dtrdsr = True  # noqa: connection has serial attribute
            self.remote_mode()

    def abort(self) -> None:
        """Abort a measurement in progress."""
        # Only the self._pyvisa case is working reliably with GPIB-USB-HS+ adapter
        self.logger.info(f'abort measurement {self.alias!r}')
        if self._rs232:
            # From the HP 34401A manual "DTR/DSR Handshake Protocol" (Chapter 4, page 152):
            #   For the <Ctrl-C> character to be recognized reliably by the multimeter
            #   while it holds DTR FALSE, the controller must first set DSR FALSE.
            # PySerial does not allow for the DSR pin to be set, it is a read-only attribute.
            self.connection.serial.dtr = True  # noqa: connection has serial attribute
            self.connection.write(b'\x03')  # Ctrl-C ASCII character
        elif self._gpib:
            self.connection.clear()  # noqa: ConnectionGPIB has a clear() method
        elif self._prologix:
            self.connection.write(b'++clr')
        else:
            self.raise_exception(f'abort() not handled for {self.alias!r}')

    def check_errors(self) -> None:
        """Query the error queue.

        Raises an exception if there is an error.
        """
        message = self.connection.query('SYSTEM:ERROR?')
        if not message.startswith('+0,'):
            self.raise_exception(message)

    def configure(self,
                  *,
                  function: DMM.Function | str = DMM.Function.DCV,
                  range: DMM.Range | str | float = 10,  # noqa: Shadows built-in name 'range'
                  nsamples: int = 10,
                  nplc: float = 10,
                  auto_zero: DMM.Auto | bool | int | str = DMM.Auto.ON,
                  trigger: DMM.Mode | str = DMM.Mode.IMMEDIATE,
                  edge: DMM.Edge | str = DMM.Edge.FALLING,
                  ntriggers: int = 1,
                  delay: float = None) -> Settings:
        """Configure the digital multimeter.

        Args:
            function: The measurement function.
            range: The range to use for the measurement.
            nsamples: The number of samples to acquire after a trigger event.
            nplc: The number of power-line cycles.
            auto_zero: The auto-zero mode.
            trigger: The trigger mode.
            edge: The edge to trigger on.
            ntriggers: The number of triggers that are accepted before
                returning to the wait-for-trigger state.
            delay: The number of seconds to wait after a trigger event before
                acquiring samples. If None, then the auto-delay
                feature is enabled where the digital multimeter automatically
                determines the delay based on the function, range and NPLC.

        Returns:
            The result of :meth:`.settings` after applying the configuration.
        """
        auto_zero = self.Auto(auto_zero)
        delay = ':AUTO ON' if delay is None else f' {delay}'

        readings = nsamples * ntriggers
        if readings > 512:
            self.raise_exception(
                f'Invalid number of samples, {readings}, for '
                f'{self.alias!r}. Must be <= 512')

        trigger = self.Mode(trigger)
        self._initiate_cmd = 'INITIATE'
        self._trigger_cmd = '*TRG'
        if self._rs232:
            if trigger in (self.Mode.IMMEDIATE, self.Mode.EXTERNAL):
                self._initiate_cmd += ';*OPC?'
            elif trigger == self.Mode.BUS:
                self._trigger_cmd += ';*OPC?'

        if not self._gpib and trigger == self.Mode.EXTERNAL:
            warnings.warn(f'Trigger {trigger} is only reliable with '
                          f'the GPIB-USB-HS+ adaptor.',
                          stacklevel=2)

        function = self.Function(function)
        if function == self.Function.DCV:
            function = 'VOLTAGE:DC'
        elif function == self.Function.DCI:
            function = 'CURRENT:DC'
        else:
            self.raise_exception(f'Unhandled function {function!r}')

        edge = self.Edge(edge)
        if edge != self.Edge.FALLING:
            self.raise_exception(f'Can only trigger {self.alias!r} on '
                                 f'the falling (negative) edge')

        range_ = self._get_range(range)

        return self._configure(
            f':CONFIGURE:{function} {range_};'
            f':SENSE:{function}:NPLC {nplc};'
            f':SENSE:ZERO:AUTO {auto_zero};'
            f':SAMPLE:COUNT {nsamples};'
            f':TRIGGER:SOURCE {trigger};COUNT {ntriggers};DELAY{delay};'
        )

    def disconnect_equipment(self) -> None:
        """Set the digital multimeter to be in LOCAL mode and then close the connection."""
        self.local_mode()
        super().disconnect_equipment()

    def fetch(self, initiate: bool = False) -> Samples:
        """Fetch the samples.

        Args:
            initiate: Whether to call :meth:`.initiate` before fetching the data.
        """
        if initiate:
            self.initiate()

        if self._rs232:
            self.logger.info(f'fetch {self.alias!r} | waiting for *OPC? reply...')
            assert self.connection.read().startswith('1')
        else:
            self.logger.info(f'fetch {self.alias!r}')

        samples = self.connection.query('FETCH?')
        return self._average_and_emit(samples)

    def local_mode(self) -> None:
        """Set the multimeter to be in LOCAL mode for the RS-232 interface.

        All keys on the front panel are fully functional.
        """
        self.logger.info(f'set {self.alias!r} to LOCAL mode')
        if self._rs232:
            self._send_command_with_opc('SYSTEM:LOCAL')
        elif self._gpib:
            self.connection.local()  # noqa: ConnectionGPIB has a local() method
        elif self._prologix:
            self.connection.write(b'++loc')
        else:
            self.logger.warning(f'setting {self.alias!r} to LOCAL mode has '
                                f'not been implemented')

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

    def settings(self) -> Settings:
        """Returns the configuration settings of the digital multimeter."""
        match1 = _command1_regex.search(self.connection.query(_command1))
        match2 = _command2_regex.search(self.connection.query(_command2))
        if not match1 or not match2:
            self.raise_exception(f'invalid regex pattern for {self.alias!r}')
        function = self.Function(match1['FUNCTION'])
        return Settings(
            auto_range=match1[f'{function}_AUTO_RANGE'],
            auto_zero=match1['AUTO_ZERO'],
            function=function,
            nplc=match1[f'{function}_NPLC'],
            nsamples=match2['NSAMPLES'],
            range=match1['RANGE'],
            trigger=Trigger(
                auto_delay=match2['TRIGGER_AUTO_DELAY'] == '1',
                count=match2['TRIGGER_COUNT'],
                delay=match2['TRIGGER_DELAY'],
                edge=self.Edge.FALLING,
                mode=match2['TRIGGER_SOURCE'],
            )
        )
