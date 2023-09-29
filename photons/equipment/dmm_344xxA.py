"""
Keysight 344(60|61|65|70)A digital multimeter.
"""
import re

from msl.equipment import EquipmentRecord

from .base import equipment
from .dmm import DMM
from .dmm import Samples
from .dmm import Settings
from .dmm import Trigger

_info_regex: re.Pattern[str] = re.compile(
    r':FUNC "(?P<FUNCTION>[A-Z]+)".*'
    r':TRIG:SOUR (?P<TRIGGER_SOURCE>[A-Z]+).*'
    r':TRIG:COUN (?P<TRIGGER_COUNT>\+\d\.\d+E[-+]\d+).*'
    r':TRIG:DEL (?P<TRIGGER_DELAY>\+\d\.\d+E[-+]\d+).*'
    r':TRIG:DEL:AUTO (?P<TRIGGER_AUTO_DELAY>\d).*'
    r':TRIG:SLOP (?P<TRIGGER_EDGE>[A-Z]+).*'
    r':SAMP:COUN \+(?P<NSAMPLES>\d+).*'
    r':CURR:NPLC (?P<DCI_NPLC>\+\d\.\d+E[-+]\d+).*'
    r':CURR:RANG (?P<DCI_RANGE>\+\d\.\d+E[-+]\d+).*'
    r':CURR:RANG:AUTO (?P<DCI_AUTO_RANGE>\d).*'
    r':CURR:ZERO:AUTO (?P<DCI_AUTO_ZERO>\d).*'
    r':VOLT:NPLC (?P<DCV_NPLC>\+\d\.\d+E[-+]\d+).*'
    r':VOLT:RANG (?P<DCV_RANGE>\+\d\.\d+E[-+]\d+).*'
    r':VOLT:RANG:AUTO (?P<DCV_AUTO_RANGE>\d).*'
    r':VOLT:ZERO:AUTO (?P<DCV_AUTO_ZERO>\d).*'
)


@equipment(manufacturer=r'Keysight', model=r'344(60|61|65|70)A')
class Keysight344XXA(DMM):

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Keysight 344(60|61|65|70)A digital multimeter.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        if record.model in ('34465A', '34470A'):
            # these models support the ":FORMAT:DATA REAL" command
            self._fetch_kwargs = {'fmt': 'ieee', 'dtype': '>d'}
        else:
            self._fetch_kwargs = {}

        super().__init__(record, **kwargs)

        # these must come after super()
        self._initiate_cmd: str = 'INITIATE'
        self._trigger_cmd: str = '*TRG'

    def check_errors(self) -> None:
        """Query the error queue.

        Raises an exception if there is an error.
        """
        message = self.connection.query(':SYSTEM:ERROR:NEXT?')
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
        trigger = self.Mode(trigger)
        delay = ':AUTO ON' if delay is None else f' {delay}'
        range_ = self._get_range(range)

        function = self.Function(function)
        if function == self.Function.DCV:
            function = 'VOLTAGE:DC'
        elif function == self.Function.DCI:
            function = 'CURRENT:DC'
        else:
            self.raise_exception(f'Unhandled function {function!r}')

        self._zero_once_cmd = f'{function}:ZERO:AUTO ONCE'

        edge = self.Edge(edge)
        if edge == self.Edge.RISING:
            edge = 'POSITIVE'
        elif edge == self.Edge.FALLING:
            edge = 'NEGATIVE'
        else:
            self.raise_exception(f'Unsupported trigger edge {edge!r}')

        fmt = ':FORMAT:DATA REAL;' if self._fetch_kwargs else ''

        return self._configure(
            f':CONFIGURE:{function} {range_};'
            f':SENSE:{function}:NPLC {nplc};'
            f':SENSE:{function}:ZERO:AUTO {auto_zero};'
            f':SAMPLE:COUNT {nsamples};'
            f':TRIGGER:SOURCE {trigger};SLOPE {edge};COUNT {ntriggers};DELAY{delay};'
            f'{fmt}'
        )

    def fetch(self, initiate: bool = False) -> Samples:
        """Fetch the samples.

        Args:
            initiate: Whether to call :meth:`.initiate` before fetching the data.
        """
        if initiate:
            self.initiate()
        self.logger.info(f'fetch {self.alias!r}')
        samples = self.connection.query('FETCH?', **self._fetch_kwargs)
        return self._average_and_emit(samples)

    def settings(self) -> Settings:
        """Returns the configuration settings of the digital multimeter."""
        match = _info_regex.search(self.connection.query('*LRN?'))
        if not match:
            self.raise_exception(f'invalid regex pattern for {self.alias!r}')
        function = self.Function(match['FUNCTION'])
        return Settings(
            auto_range=match[f'{function}_AUTO_RANGE'],
            auto_zero=match[f'{function}_AUTO_ZERO'],
            function=function,
            nplc=match[f'{function}_NPLC'],
            nsamples=match['NSAMPLES'],
            range=match[f'{function}_RANGE'],
            trigger=Trigger(
                auto_delay=match['TRIGGER_AUTO_DELAY'] == '1',
                count=match['TRIGGER_COUNT'],
                delay=match['TRIGGER_DELAY'],
                edge=match['TRIGGER_EDGE'],
                mode=match['TRIGGER_SOURCE'],
            )
        )
