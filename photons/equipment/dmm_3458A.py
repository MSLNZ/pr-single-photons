"""
Communicate with a Keysight 3458A digital multimeter.
"""
from . import equipment
from .dmm import DMM


@equipment(manufacturer=r'Keysight', model=r'3458A')
class Keysight3458A(DMM):

    FUNCTIONS = {
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

    TRIGGERS = {
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

    def __init__(self, app, record, *, demo=None):
        """Communicate with a Keysight 3458A digital multimeter.

        Parameters
        ----------
        app : :class:`photons.App`
            The main application entry point.
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment record.
        demo : :class:`bool`, optional
            Whether to simulate a connection to the equipment by opening
            a connection in demo mode.
        """
        super(Keysight3458A, self).__init__(app, record, demo=demo)
        self._trigger_count = 1
        self._nreadings = 1

    def reset(self) -> None:
        """Resets instrument to factory default state."""
        self.logger.info(f'reset {self.alias!r}')
        self.connection.write('RESET')

    def clear(self) -> None:
        """Clears the event registers in all register groups and the error queue."""
        self.logger.info(f'clear {self.alias!r}')
        self.connection.write('CLEAR')

    def check_errors(self) -> None:
        """Query the multimeter’s error queue.

        If there is an error then raise an exception.
        """
        message = self.connection.query('ERRSTR?').rstrip()
        if not message == '0,"NO ERROR"':
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
        # seems like one must send each query individually
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
            'trigger_edge': self.EDGES['FALLING'],  # only triggers on the falling edge of an external TTL pulse
            'trigger_mode': Keysight3458A.TRIGGERS[int(query('TRIG?'))],
        }

    def bus_trigger(self) -> None:
        """Send a software trigger."""
        self.logger.info(f'software trigger {self.alias!r}')
        self.connection.write(f'TRIG AUTO;MEM FIFO;TARM SGL,{self._trigger_count};MEM OFF')

    def configure(self, *, function='dcv', range=10, nsamples=10, nplc=10, auto_zero=True,
                  trigger='bus', edge='falling', ntriggers=1, delay=None) -> dict:
        """Configure the digital multimeter.

        Parameters
        ----------
        function : :class:`str`, optional
            The function to measure. Can be any key in :class:`.Keysight3458A.FUNCTIONS` (case insensitive).
        range : :class:`float` or :class:`str`, optional
            The range to use for the measurement. Can be any key in :attr:`.DMM.RANGES`.
        nsamples : :class:`int`, optional
            The number of samples to acquire after receiving a trigger.
        nplc : :class:`float`, optional
            The number of power line cycles.
        auto_zero : :class:`bool` or :class:`str`, optional
            The auto-zero mode. Can be any key in :attr:`.DMM.AUTO`.
        trigger : :class:`str`, optional
            The trigger mode. Can be any key in :attr:`.Keysight3458A.TRIGGERS` (case insensitive).
        edge : :class:`str` or :attr:`.DMM.TriggerEdge`, optional
           The edge to trigger on. Must be `'falling'``.
        ntriggers : :class:`int`, optional
            The number of triggers that are accepted by the digital multimeter
            before returning to the *wait-for-trigger* state.
        delay : :class:`float` or :data:`None`, optional
            The trigger delay in seconds. If :data:`None` then set the delay to 0.

        Returns
        -------
        :class:`dict`
            The result of :meth:`.info` after the settings have been written.
        """
        edge = self.EDGES[edge.upper()]
        if edge != 'NEGATIVE':
            self.connection.raise_exception(f'Can only trigger {self.alias!r} on the falling (negative) edge')

        if nsamples < 1 or nsamples > 16777215:
            self.connection.raise_exception(f'Invalid number of samples, {nsamples}, for {self.alias!r}. '
                                            f'Must be between [1, 16777215]')

        if ntriggers < 1:
            self.connection.raise_exception(f'Invalid number of triggers, {ntriggers}, for {self.alias!r}')

        function = Keysight3458A.FUNCTIONS[function.upper()]
        range_ = DMM.RANGES.get(range, range)
        nplc = float(nplc)
        auto_zero = DMM.AUTO[auto_zero]
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
        info = self.info()
        self.config_changed.emit(info)
        self.emit_notification(**info)
        return info

    def fetch(self, initiate=False) -> tuple:
        """Fetch the samples.

        Parameters
        ----------
        initiate : :class:`bool`
            Whether to call :meth:`Keysight3458A.bus_trigger` before fetching the samples.
            # Whether to send the ``'TARM HOLD'`` command before fetching the samples.

        Returns
        -------
        :class:`float`
           The average value.
        :class:`float`
           The standard deviation.
        """
        if initiate:
            self.bus_trigger()
            # self.logger.info(f'send TARM HOLD to {self.alias!r}')
            # self.connection.write('TARM HOLD')
        samples = self.connection.query(f'RMEM 1,{self._nreadings},1').rstrip().split(',')
        # had issues getting the wrong number of readings after a software trigger
        # make sure that those issues have been fixed
        if len(samples) != self._nreadings:
            self.connection.raise_exception(f'Expected {self._nreadings} values, '
                                            f'got {len(samples)} for {self.alias!r}')
        return self._average_and_emit(samples)

    def temperature(self) -> float:
        """Get the temperature of the digital multimeter.

        Returns
        -------
        :class:`float`
            The temperature.
        """
        return float(self.connection.query('TEMP?'))
