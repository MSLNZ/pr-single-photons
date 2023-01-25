"""
Keysight 3458A digital multimeter.
"""
from msl.equipment import EquipmentRecord

from .base import equipment
from .dmm import DMM
from ..samples import Samples


@equipment(manufacturer=r'Keysight|Hewlett Packard|Agilent', model=r'3458A')
class Keysight3458A(DMM):

    FUNCTIONS: dict[int | str, str] = {
        1: 'DCV',
        'DCV': 'DCV',
        'VOLT': 'DCV',
        'VOLTAGE': 'DCV',
        2: 'ACV',
        'ACV': 'ACV',
        3: 'ACDCV',
        'ACDCV': 'ACDCV',
        4: 'OHM',
        'OHM': 'OHM',
        5: 'OHMF',
        'OHMF': 'OHMF',
        6: 'DCI',
        'DCI': 'DCI',
        'CURR': 'DCI',
        'CURRENT': 'DCI',
        7: 'ACI',
        'ACI': 'ACI',
        8: 'ACDCI',
        'ACDCI': 'ACDCI',
        9: 'FREQ',
        'FREQ': 'FREQ',
        10: 'PER',
        'PER': 'PER',
        11: 'DSAC',
        'DSAC': 'DSAC',
        12: 'DSDC',
        'DSDC': 'DSDC',
        13: 'SSAC',
        'SSAC': 'SSAC',
        14: 'SSDC',
        'SSDC': 'SSDC',
    }

    TRIGGERS: dict[int | str, str] = {
        1: 'AUTO',
        'AUTO': 'AUTO',
        'IMM': 'AUTO',
        'IMMEDIATE': 'AUTO',
        2: 'EXT',  # only on the falling edge
        'EXT': 'EXT',
        'EXTERNAL': 'EXT',
        3: 'SGL',  # Triggers once (upon receipt of TRIG SGL) then reverts to TRIG HOLD
        'SGL': 'SGL',
        4: 'HOLD',
        'HOLD': 'HOLD',
        'BUS': 'HOLD',
        5: 'SYN',
        'SYN': 'SYN',
        7: 'LEVEL',
        'LEVEL': 'LEVEL',
        8: 'LINE',
        'LINE': 'LINE',
        'INT': 'LINE',
        'INTERNAL': 'LINE',
    }

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Keysight 3458A digital multimeter.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)
        self._trigger_count: int = 1
        self._nreadings: int = 1

    def bus_trigger(self) -> None:
        """Send a software trigger to the digital multimeter."""
        self.logger.info(f'software trigger {self.alias!r}')
        self.connection.write(f'TRIG AUTO;MEM FIFO;TARM SGL,{self._trigger_count};MEM OFF')

    def check_errors(self) -> None:
        """Query the error queue of the digital multimeter.

        If there is an error then raise an exception.
        """
        message = self.connection.query('ERRSTR?').lstrip()
        if not message.startswith('0,'):
            self.raise_exception(message)

    def clear(self) -> None:
        """Clears the event registers in all register groups and the error queue."""
        self.logger.info(f'clear {self.alias!r}')
        self.connection.write('CLEAR')

    def configure(self,
                  *,
                  function: int | str = 'voltage',
                  range: float | str = 10,  # noqa: Shadows built-in name 'range'
                  nsamples: int = 10,
                  nplc: float = 10,
                  auto_zero: bool | int | str = True,
                  trigger: int | str = 'bus',
                  edge: str = 'falling',
                  ntriggers: int = 1,
                  delay: float = None) -> dict[str, ...]:
        """Configure the digital multimeter.

        Args:
            function: The function to measure.
                Can be any key in :attr:`Keysight3458A.FUNCTIONS` (case insensitive).
            range: The range to use for the measurement.
                Can be any key in :attr:`.DMM.RANGES`.
            nsamples: The number of samples to acquire after a trigger event.
            nplc: The number of power-line cycles.
            auto_zero: The auto-zero mode.
                Can be any key in :attr:`.DMM.AUTO`.
            trigger: The trigger mode.
                Can be any key in :attr:`Keysight3458A.TRIGGERS` (case insensitive).
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

        if nsamples < 1 or nsamples > 16777215:
            self.raise_exception(f'Invalid number of samples, {nsamples}, for '
                                 f'{self.alias!r}. Must be between [1, 16777215]')

        if ntriggers < 1:
            self.raise_exception(f'Invalid number of triggers, '
                                 f'{ntriggers}, for {self.alias!r}')

        range_ = DMM.RANGES.get(range, range)
        nplc = float(nplc)
        auto_zero = DMM.AUTO[auto_zero]
        if isinstance(function, str):
            function = Keysight3458A.FUNCTIONS[function.upper()]
        if isinstance(trigger, str):
            trigger = Keysight3458A.TRIGGERS[trigger.upper()]
        if delay is None:
            delay = 0.0

        # TARM  -> AUTO, EXT, HOLD,              SGL, SYN
        # TRIG  -> AUTO, EXT, HOLD, LEVEL, LINE, SGL, SYN
        # NRDGS -> AUTO, EXT,     , LEVEL, LINE       SYN, TIMER

        self._trigger_count = ntriggers
        self._nreadings = nsamples * ntriggers
        tarm_event = 'AUTO' if trigger in ['LEVEL', 'LINE'] else trigger
        nrdgs_event = 'AUTO' if trigger in ['SGL', 'HOLD'] else trigger

        command = f'FUNC {function},{range_};' \
                  f'NPLC {nplc};' \
                  f'AZERO {auto_zero};' \
                  f'NRDGS {nsamples},{nrdgs_event};' \
                  f'DELAY {delay};' \
                  f'TRIG {trigger};' \
                  f'TARM {tarm_event};' \
                  f'LFREQ LINE;' \
                  f'MEM FIFO;'

        if function in ['DCV', 'OHM', 'OHMF']:
            command += 'FIXEDZ ON;'

        self.logger.info(f'configure {self.alias!r} using {command!r}')
        self.connection.write(command)
        self.check_errors()
        settings = self.settings()
        self.settings_changed.emit(settings)
        self.maybe_emit_notification(**settings)
        return settings

    def fetch(self, initiate: bool = False) -> Samples:
        """Fetch the samples.

        Args:
            initiate: Whether to call :meth:`.bus_trigger` before fetching the samples.
        """
        if initiate:
            self.bus_trigger()
        samples = self.connection.query(f'RMEM 1,{self._nreadings},1')
        return self._average_and_emit(samples)

    def reset(self) -> None:
        """Resets the digital multimeter to the factory default state."""
        self.logger.info(f'reset {self.alias!r}')
        self.connection.write('RESET')

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
        # must send each query individually
        def query(command):
            return self.connection.query(command).rstrip()

        function, range_ = query('FUNC?').split(',')
        samples_per_trigger, event = query('NRDGS?').split(',')
        return {
            'auto_range': DMM.AUTO[query('ARANGE?')],
            'auto_zero': DMM.AUTO[query('AZERO?')],
            'function': Keysight3458A.FUNCTIONS[int(function)],
            'nplc': float(query('NPLC?')),
            'nsamples': int(samples_per_trigger),
            'range': float(range_),
            'trigger_count': self._trigger_count,  # unfortunately TARM? does not return the "number_arms" value
            'trigger_delay': float(query('DELAY?')),
            'trigger_delay_auto': False,  # not available
            'trigger_edge': 'FALLING',  # only triggers on the falling edge of an external TTL pulse
            'trigger_mode': Keysight3458A.TRIGGERS[int(query('TRIG?'))],
        }

    def temperature(self) -> float:
        """Returns the temperature (in Celsius) of the digital multimeter."""
        return float(self.connection.query('TEMP?'))
