"""
Keithley DMM6500 digital multimeter.
"""
import re
from dataclasses import dataclass

import numpy as np
from msl.equipment import EquipmentRecord

from .base import equipment
from .dmm import DMM
from .dmm import Settings
from .dmm import Trigger
from ..samples import Samples

_block_regex: re.Pattern[str] = re.compile(
    r'(NOP|EVENT_(?P<EVENT>[A-Z]+)).+'
    r'DELAY: (?P<DELAY>\d+\.\d+).+'
    r'COUNT: (?P<NSAMPLES>\d+).+'
    r'VALUE: (?P<NTRIGGERS>\d+)',
    flags=re.DOTALL
)


@dataclass(eq=False, order=False)
class Channel:
    """The settings for a scanner channel."""
    number: int
    function: DMM.Function
    range: float | DMM.Range
    nplc: float
    auto_zero: DMM.Auto

    def copy(self, number: int) -> 'Channel':
        """Create a copy of this Channel for a new Channel"""
        return Channel(number=number,
                       function=self.function,
                       range=self.range,
                       nplc=self.nplc,
                       auto_zero=self.auto_zero)


@equipment(manufacturer=r'Keithley', model=r'DMM6500')
class Keithley6500(DMM):

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Keithley DMM6500 digital multimeter.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)
        self._trace_name: str = 'defbuffer1'
        self._trace_length: int = 0
        self._channel_length: int = 0
        self._trigger_cmd: str = 'updated in configure()'
        self._zero_once_cmd: str = 'AZERO:ONCE'

    def _fetch(self, initiate: bool) -> np.ndarray:
        if initiate:
            self.initiate()
        self.logger.info(f'fetch {self.alias!r}')
        command = f':TRACE:DATA? 1, {self._trace_length}, "{self._trace_name}"'
        return self.connection.query(command, fmt='ieee', dtype='<d')

    def check_errors(self) -> None:
        """Query the error queue.

        Raises an exception if there is an error.
        """
        message = self.connection.query(':SYSTEM:ERROR:NEXT?')
        if not message.startswith('0,'):
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

        This method requires the FRONT terminals to be selected.

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
        if not self.connection.query(':ROUTE:TERMINALS?').startswith('FRON'):
            self.raise_exception('FRONT terminals are not enabled')

        function = self.Function(function)
        if function == self.Function.DCV:
            function = 'VOLTAGE:DC'
        elif function == self.Function.DCI:
            function = 'CURRENT:DC'
        else:
            self.raise_exception(f'Unhandled function {function!r}')

        range_ = self._get_range(range)
        if range_ == self.Range.AUTO:
            range_cmd = ':AUTO ON'
        else:
            range_cmd = f' {range_}'

        auto_zero = self.Auto(auto_zero)
        if auto_zero == self.Auto.ONCE:
            auto_zero = self.Auto.OFF
            self.zero()

        mode, event = self.Mode(trigger), None
        self._initiate_cmd = 'INITIATE;*WAI'
        if mode == self.Mode.IMMEDIATE:
            event = 'NOP 2'
        elif mode == self.Mode.BUS:
            event = 'WAIT 2, COMMAND, ENTER'
            self._initiate_cmd = 'INITIATE'
        elif mode == self.Mode.EXTERNAL:
            event = 'WAIT 2, EXTERNAL, ENTER'
        else:
            self.raise_exception(f'Unhandled trigger mode {mode!r}')

        settings = self._configure(
            f':FORMAT REAL;'
            f':SENSE:FUNCTION "{function}";'
            f':{function}:NPLC {nplc};'
            f':{function}:RANGE{range_cmd};'
            f':{function}:AZERO {auto_zero};'
            f':TRACE:CLEAR;'
            f':TRACE:POINTS {max(10, nsamples * ntriggers)}, "{self._trace_name}";'
            f':TRIGGER:LOAD "EMPTY";'
            f':TRIGGER:EXTERNAL:IN:EDGE {self.Edge(edge)};'
            f':TRIGGER:BLOCK:BUFFER:CLEAR 1, "{self._trace_name}";'
            f':TRIGGER:BLOCK:{event};'
            f':TRIGGER:BLOCK:DELAY:CONSTANT 3, {delay or 0};'
            f':TRIGGER:BLOCK:MDIGITIZE 4, "{self._trace_name}", {nsamples};'
            f':TRIGGER:BLOCK:BRANCH:COUNTER 5, {ntriggers}, 2;'
        )
        self._trace_length = settings.nsamples * settings.trigger.count
        self._trigger_cmd = '*TRG;*WAI'
        return settings

    def configure_scanner(self,
                          *channels: Channel | int,
                          nsamples: int = 10,
                          trigger: DMM.Mode | str = DMM.Mode.IMMEDIATE,
                          edge: DMM.Edge | str = DMM.Edge.FALLING,
                          ntriggers: int = 1,
                          delay: float = None) -> dict[str, Settings]:
        """Configure the scanner card.

        The channels are sampled in an interleaved manner.

        Args:
            *channels: The channel configuration. If an :class:`int`, then
                :meth:`.create_scanner_channel` is called with the `channel`
                value as the `number` parameter.
            nsamples: The number of samples to acquire for each channel.
            trigger: The trigger mode.
                If using bus or external trigger mode, after one trigger event is
                received there will be one sample acquired from one channel. To
                acquire all data, there must be ``len(channels) * nsamples``
                trigger events.
            edge: The edge to trigger on.
            ntriggers: Must be equal to 1.
            delay: The number of seconds to wait after a trigger event before
                acquiring samples.

        Returns:
            The configuration settings for the scanner channels
        """
        if not channels:
            raise ValueError('Must specify the scanner channels to read')

        if ntriggers != 1:
            raise ValueError('ntriggers != 1')

        if not self.connection.query(':ROUTE:TERMINALS?').startswith('REAR'):
            self.raise_exception('REAR terminals are not enabled')

        self._channel_length = len(channels)
        self._trace_length = nsamples * self._channel_length

        sense = []
        ch_numbers = []
        function = ''
        for c in channels:
            if isinstance(c, int):
                c = self.create_scanner_channel(c)
            ch_numbers.append(str(c.number))
            if c.function == self.Function.DCV:
                function = 'VOLTAGE:DC'
            elif c.function == self.Function.DCI:
                function = 'CURRENT:DC'
            else:
                self.raise_exception(f'Unhandled function {c.function!r}')
            if c.range == self.Range.AUTO:
                range_cmd = ':AUTO ON'
            else:
                range_cmd = f' {c.range}'
            if c.auto_zero == self.Auto.ONCE:
                c.auto_zero = self.Auto.OFF
                self.zero()
            sense.append(
                f':SENSE:FUNCTION "{function}", (@{c.number});'
                f':{function}:NPLC {c.nplc}, (@{c.number});'
                f':{function}:RANGE{range_cmd}, (@{c.number});'
                f':{function}:AZERO {c.auto_zero}, (@{c.number});')
        sense_cmd = ''.join(sense)

        stimulus = self.Mode(trigger)
        self._initiate_cmd = 'INITIATE;*WAI'
        self._trigger_cmd = '*TRG;*WAI'
        if stimulus == self.Mode.IMMEDIATE:
            stimulus = 'NONE'
        elif stimulus == self.Mode.BUS:
            stimulus = 'COMMAND'
            self._initiate_cmd = 'INITIATE'
            self._trigger_cmd = '*TRG'
        elif stimulus == self.Mode.EXTERNAL:
            pass
        else:
            self.raise_exception(f'Trigger {stimulus!r} is not implemented')

        command = (f':FORMAT REAL;'
                   f'{sense_cmd}'
                   f':TRACE:CLEAR;'
                   f':TRACE:POINTS {max(10, self._trace_length)}, "{self._trace_name}";'
                   f':ROUTE:SCAN:CREATE (@{",".join(ch_numbers)});'
                   f':ROUTE:SCAN:COUNT:SCAN {nsamples};'
                   f':ROUTE:SCAN:MEASURE:INTERVAL {delay or 0};'
                   f':ROUTE:SCAN:MEASURE:STIMULUS {stimulus};'
                   f':TRIGGER:EXTERNAL:IN:EDGE {self.Edge(edge)};')

        self.logger.info(f'configure {self.alias!r} using {command!r}')
        self._send_command_with_opc(command)
        self.check_errors()
        settings = self.settings_scanner()
        self.settings_changed.emit(settings)
        self.maybe_emit_notification(settings)
        return settings

    def create_scanner_channel(self,
                               number: int,
                               *,
                               function: DMM.Function | str = DMM.Function.DCV,
                               range: DMM.Range | str | float = 10,  # noqa: Shadows built-in name 'range'
                               nplc: float = 10,
                               auto_zero: DMM.Auto | bool | int | str = DMM.Auto.ON) -> Channel:
        """Create a scanner channel.

        A scanner channel may be passed to :meth:`.configure_scanner`.

        Args:
            number: The scanner channel number.
            function: The measurement function.
            range: The range to use for the measurement.
            nplc: The number of power-line cycles.
            auto_zero: The auto-zero mode.

        Returns:
            The scanner channel settings.
        """
        return Channel(number=int(number),
                       function=DMM.Function(function),
                       range=self._get_range(range),
                       nplc=float(nplc),
                       auto_zero=DMM.Auto(auto_zero))

    def fetch(self, initiate: bool = False) -> Samples:
        """Fetch the samples.

        Args:
            initiate: Whether to call :meth:`.initiate` before fetching the data.
        """
        samples = self._fetch(initiate)
        return self._average_and_emit(samples)

    def fetch_scanner(self, initiate: bool = False) -> list[Samples]:
        """Fetch the scanner samples.

        Args:
            initiate: Whether to call :meth:`.initiate` before fetching the data.
        """
        samples = self._fetch(initiate)
        return [self._average_and_emit(samples[i::self._channel_length])
                for i in range(self._channel_length)]

    def settings(self) -> Settings:
        """Returns the configuration settings of the digital multimeter."""
        function = self.connection.query(':SENSE:FUNCTION?').rstrip()
        reply = self.connection.query(
            f':SENSE:{function}:NPLC?;'
            f':SENSE:{function}:RANGE?;'
            f':SENSE:{function}:AZERO?;'
            f':SENSE:{function}:RANGE:AUTO?;'
            f':TRIGGER:EXTERNAL:IN:EDGE?;'
            f':TRIGGER:BLOCK:LIST?;')
        nplc, range_, azero, arange, edge, block = reply.split(';')
        match = _block_regex.search(block)
        if not match:
            self.raise_exception(f'Invalid regex pattern to parse:\n\n{block}')
        return Settings(
            auto_range=arange,
            auto_zero=azero,
            function=function,
            nplc=nplc,
            nsamples=match['NSAMPLES'],
            range=range_,
            trigger=Trigger(
                auto_delay=False,
                count=match['NTRIGGERS'],
                delay=match['DELAY'],
                edge=edge,
                mode=match['EVENT'],
            )
        )

    def settings_scanner(self) -> dict[str, Settings]:
        """Returns the scanner configuration settings of the digital multimeter.

        Returns:
            A dictionary of settings for each channel.
        """
        reply = self.connection.query(':TRIGGER:EXTERNAL:IN:EDGE?;'
                                      ':ROUTE:SCAN:CREATE?;'
                                      ':ROUTE:SCAN:MEASURE:STIMULUS?;'
                                      ':ROUTE:SCAN:COUNT:SCAN?;'
                                      ':ROUTE:SCAN:MEASURE:INTERVAL?;')
        edge, create, mode, nsamples, delay = reply.split(';')

        channels = []
        for c in create.lstrip('(@').rstrip(')').split(','):
            if ':' in c:
                a, b = map(int, c.split(':'))
                channels.extend(range(a, b+1))
            else:
                channels.append(int(c))

        trigger = Trigger(auto_delay=False,
                          count=1,
                          delay=delay,
                          edge=edge,
                          mode=mode)

        settings = {}

        for c in channels:
            function = self.connection.query(f':SENSE:FUNCTION? (@{c})').rstrip()
            reply = self.connection.query(
                f':SENSE:{function}:NPLC? (@{c});'
                f':SENSE:{function}:RANGE? (@{c});'
                f':SENSE:{function}:AZERO? (@{c});'
                f':SENSE:{function}:RANGE:AUTO? (@{c});')
            nplc, range_, azero, arange = reply.rstrip().split(';')
            settings[f'ch{c}'] = Settings(
                auto_range=arange,
                auto_zero=azero,
                function=function,
                nplc=nplc,
                nsamples=nsamples,
                range=range_,
                trigger=trigger
            )

        return settings
