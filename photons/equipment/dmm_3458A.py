"""
Keysight 3458A digital multimeter.
"""
import warnings
from time import sleep

from msl.equipment import EquipmentRecord
from msl.equipment.constants import Interface

from .base import equipment
from .dmm import DMM
from .dmm import Settings
from .dmm import Trigger
from ..samples import Samples


@equipment(manufacturer=r'Keysight|Hewlett Packard|Agilent', model=r'3458A')
class Keysight3458A(DMM):

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Keysight 3458A digital multimeter.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        self._ntriggers: int = 1
        self._nreadings: int = 1
        self._trigger_mode: DMM.Mode = DMM.Mode.IMMEDIATE
        self._prologix: bool = record.connection.address.startswith('Prologix')
        self._gpib: bool = record.connection.interface == Interface.GPIB
        self._check_revision: bool = True

        super().__init__(record, **kwargs)

        # these must come after super()
        self.connection.read_termination = '\r\n'
        self._trigger_cmd: str = 'MEM FIFO;TARM SGL'

    def abort(self) -> None:
        """Abort a measurement in progress."""
        self.logger.info(f'abort measurement {self.alias!r} | calls clear()')
        self.clear()

    def check_errors(self) -> None:
        """Query the error queue.

        Raises an exception if there is an error.
        """
        message = self.connection.query('ERRSTR?')
        if not message.startswith('0,'):
            self.raise_exception(message)

    def clear(self) -> None:
        """Clears the event registers in all register groups and the error queue."""
        self.logger.info(f'clear {self.alias!r}')
        if self._prologix:
            self.connection.write(b'++clr')
        elif self._gpib:
            self.connection.clear()   # noqa: ConnectionGPIB has a clear() method
        else:
            self.raise_exception(f'{self.alias!r} clear() has not been implemented yet')

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
                acquiring samples. A value of :data:`None` is equivalent to zero.

        Returns:
            The result of :meth:`.settings` after applying the configuration.
        """
        edge = self.Edge(edge)
        if edge != self.Edge.FALLING:
            self.raise_exception(f'Can only trigger {self.alias!r} on '
                                 f'the falling (negative) edge')

        range_ = self._get_range(range)

        self._ntriggers = ntriggers
        self._nreadings = nsamples * ntriggers

        if self._nreadings > 16777215:
            self.raise_exception(
                f'Invalid number of samples, {self._nreadings}, for '
                f'{self.alias!r}. Must be between <= 16777215')

        # TARM  -> AUTO, EXT, HOLD,              SGL, SYN
        # TRIG  -> AUTO, EXT, HOLD, LEVEL, LINE, SGL, SYN
        # NRDGS -> AUTO, EXT,     , LEVEL, LINE       SYN, TIMER
        mode = self.Mode(trigger)
        trig_event = 'AUTO'
        if mode == self.Mode.IMMEDIATE:
            self._initiate_cmd = f'MEM FIFO;TARM SGL,{ntriggers};MEM OFF'
        elif mode == self.Mode.BUS:
            self._initiate_cmd = 'TARM HOLD'
        elif mode == self.Mode.EXTERNAL:
            trig_event = 'EXT'
            if self._check_revision:
                self._check_revision = False
                rev = tuple(map(int, self.connection.query('REV?').split(',')))
                if rev < (9, 2):
                    warnings.warn(f'Trigger {mode} works with firmware revision '
                                  f'(9, 2), but revision (6, 2) does not work. '
                                  f'The revision for {self.alias!r} is {rev}.',
                                  stacklevel=2)

            self._initiate_cmd = f'MEM FIFO;TARM SGL,{ntriggers};MEM OFF'
            if self._prologix:
                warnings.warn(f'Trigger {mode} is not reliable when using '
                              f'the Prologix GPIB-ENET adapter. May get a '
                              f'ConnectionResetError.',
                              stacklevel=2)

        if self._gpib:
            # Turning the INBUF ON/OFF is required because the GPIB write()
            # method waits for the count() return value. Therefore, when
            # self.initiate() or self.trigger() is called, it blocks until a
            # timeout error is raised or until count() receives a return value.
            #
            # Used the NI GPIB-USB-HS+ adapter to communicate with the DMM
            # to determine this caveat.
            buff = 'INBUF ON;INBUF OFF;'
            self._initiate_cmd = buff + self._initiate_cmd
            self._trigger_cmd = buff + self._trigger_cmd

        self._trigger_mode = mode

        function = self.Function(function)
        fixedz = 'ON' if function in ['DCV', 'OHM', 'OHMF'] else 'OFF'

        return self._configure(
            f'TARM HOLD;'
            f'TRIG {trig_event};'
            f'MEM FIFO;'
            f'FUNC {function},{range_};'
            f'NPLC {nplc};'
            f'AZERO {self.Auto(auto_zero)};'
            f'NRDGS {nsamples},AUTO;'
            f'DELAY {delay or 0};'
            f'LFREQ LINE;'
            f'FIXEDZ {fixedz};'
            f'NDIG 8;',
            opc=False,
        )

    def fetch(self, initiate: bool = False) -> Samples:
        """Fetch the samples.

        Args:
            initiate: Whether to call :meth:`.initiate` before fetching the samples.
        """
        if initiate:
            self.initiate()
        self.logger.info(f'fetch {self.alias!r}')

        if self._gpib:
            while True:
                try:
                    # From the "Using the Input Buffer" section of the manual (page 75):
                    #   When using the input buffer, it may be necessary to know when all
                    #   buffered commands have been executed. The multimeter provides this
                    #   information by setting bit 4 (0b00010000 = 16) in the status register
                    val = self.connection.serial_poll()  # noqa: ConnectionGPIB has serial_poll()
                    if val & 16:
                        break
                except TypeError:  # serial_poll() received an empty reply
                    pass
                else:
                    sleep(0.1)

        # From the RMEM documentation on page 230 of manual:
        #   The multimeter assigns a number to each reading in reading memory. The most
        #   recent reading is assigned the lowest number (1) and the oldest reading has the
        #   highest number. Numbers are always assigned in this manner regardless of
        #   whether you're using the FIFO or LIFO mode.
        # This means that samples is an array of [latest reading, ..., first reading]
        samples = self.connection.query(f'RMEM 1,{self._nreadings},1')
        # Want FIFO, so reverse to be [first reading, ..., latest reading]
        s = samples.split(',')[::-1]
        return self._average_and_emit(s)

    def reset(self) -> None:
        """Resets the digital multimeter to the factory default state."""
        self.logger.info(f'reset {self.alias!r}')
        self.connection.write('RESET;TARM HOLD;')

    def settings(self) -> Settings:
        """Returns the configuration settings of the digital multimeter."""
        # must send each query individually
        def query(command):
            return self.connection.query(command).rstrip()

        function, range_ = query('FUNC?').split(',')
        if function == '1':
            function = self.Function.DCV
        elif function == '6':
            function = self.Function.DCI
        else:
            self.raise_exception(f'Unhandled function {function}')

        samples_per_trigger, event = query('NRDGS?').split(',')
        return Settings(
            auto_range=query('ARANGE?'),
            auto_zero=query('AZERO?'),
            function=function,
            nplc=query('NPLC?'),
            nsamples=samples_per_trigger,
            range=range_,
            trigger=Trigger(
                auto_delay=False,  # not available
                count=self._ntriggers,  # TARM? returns "number_arms" in SGL mode only
                delay=query('DELAY?'),
                edge=self.Edge.FALLING,
                mode=self._trigger_mode,
            )
        )

    def temperature(self) -> float:
        """Returns the temperature (in Celsius) of the digital multimeter."""
        return float(self.connection.query('TEMP?'))

    def zero(self) -> None:
        """Reset the zero value.

        When the multimeter is configured with `auto_zero` set to OFF, the
        multimeter may gradually drift out of specification. To minimize the
        drift, you may call this method to take a new zero measurement.
        """
        self.logger.info(f'auto zero {self.alias!r}')
        self.connection.write('AZERO ONCE')
        self.check_errors()
