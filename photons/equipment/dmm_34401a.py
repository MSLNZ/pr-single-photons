"""
Communicate with a Hewlett Packard 34401A digital multimeter.
"""
import re

from msl.equipment.connection_serial import ConnectionSerial

from . import equipment
from .dmm import DMM

# Reduce the number of writes/reads that are needed when calling HP34401A.info().
# The order of the queries in the command and in the regex must be the same.
# The multimeter complains if the length of a query is too long, so break it
# into 2 commands.

_command1 = 'CONFIGURE?;' \
            ':SENSE:CURRENT:RANGE:AUTO?;' \
            ':SENSE:VOLTAGE:RANGE:AUTO?;' \
            ':SENSE:ZERO:AUTO?;' \
            ':SENSE:CURRENT:NPLC?;' \
            ':SENSE:VOLTAGE:NPLC?;'

_command1_regex = re.compile(
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

_command2_regex = re.compile(
    r'(?P<NSAMPLES>\+\d+);'
    r'(?P<TRIGGER_SOURCE>[A-Z]+);'
    r'(?P<TRIGGER_COUNT>\+\d\.\d+E[-+]\d+);'
    r'(?P<TRIGGER_DELAY>\+\d\.\d+E[-+]\d+);'
    r'(?P<TRIGGER_DELAY_AUTO>\d)'
)


@equipment(manufacturer=r'H.*P.*', model=r'34401A')
class HP34401A(DMM):

    def __init__(self, app, record, *, demo=None):
        """Communicate with a Hewlett Packard 34401A digital multimeter.

        Parameters
        ----------
        app : :class:`photons.app.App`
            The main application entry point.
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment record.
        demo : :class:`bool`, optional
            Whether to simulate a connection to the equipment by opening
            a connection in demo mode.
        """
        super(HP34401A, self).__init__(app, record, demo=demo)
        self._rs232 = isinstance(self.connection, ConnectionSerial)
        if self._rs232:
            self.remote_mode()
        self.disconnect = self._disconnect

    def check_errors(self) -> None:
        """Query the multimeter’s error queue.

        If there is an error then raise an exception.
        """
        message = self.connection.query('SYSTEM:ERROR?').rstrip()
        if message != '+0,"No error"':
            self.connection.raise_exception(message)

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
        match1 = _command1_regex.search(self.connection.query(_command1))
        match2 = _command2_regex.search(self.connection.query(_command2))
        if not match1 or not match2:
            self.connection.raise_exception(f'invalid "info" regex pattern for {self.alias!r}')

        d1 = match1.groupdict()
        d2 = match2.groupdict()
        function = self.FUNCTIONS[d1['FUNCTION']]
        return {
            'auto_range': self.AUTO[d1[function+'_RANGE_AUTO']],
            'auto_zero': self.AUTO[d1['AUTO_ZERO']],
            'function': function,
            'nplc': float(d1[function+'_NPLC']),
            'nsamples': int(d2['NSAMPLES']),
            'range': float(d1['RANGE']),
            'trigger_count': int(float(d2['TRIGGER_COUNT'])),
            'trigger_delay': float(d2['TRIGGER_DELAY']),
            'trigger_delay_auto': d2['TRIGGER_DELAY_AUTO'] == '1',
            'trigger_edge': self.EDGES['FALLING'],  # only triggers on the falling edge of an external TTL pulse
            'trigger_mode': self.TRIGGERS[d2['TRIGGER_SOURCE']],
        }

    def bus_trigger(self) -> None:
        """Send a software trigger."""
        self.logger.info(f'software trigger {self.alias!r}')
        if self._rs232:
            self.connection.write('INIT;*TRG;*OPC?')
        else:
            self.connection.write('INIT;*TRG;*OPC')

    def fetch(self, initiate: bool = False) -> tuple:
        if not initiate:
            if self._rs232:
                if not self.connection.read().startswith('1'):
                    self.connection.raise_exception('*OPC? from bus_trigger did not return 1')
        return super().fetch(initiate=initiate)

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
            The edge to trigger on. Must be `'falling'``.
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
        edge = self.EDGES[edge.upper()]
        if edge != 'NEGATIVE':
            self.connection.raise_exception(f'Can only trigger {self.alias!r} on the falling (negative) edge')

        function = self.FUNCTIONS[function.upper()]
        range_ = self.RANGES.get(range, range)
        nplc = self.NPLCS[float(nplc)]
        auto_zero = self.AUTO[auto_zero]
        trigger = self.TRIGGERS[trigger.upper()]
        delay = ':AUTO ON' if delay is None else f' {delay}'  # must include the space before {delay}

        command = f'CONFIGURE:{function} {range_};' \
                  f':{function}:NPLC {nplc};' \
                  f':SENSE:ZERO:AUTO {auto_zero};' \
                  f':SAMPLE:COUNT {nsamples};' \
                  f':TRIGGER:SOURCE {trigger};COUNT {ntriggers};DELAY{delay}'

        self.logger.info(f'configure {self.alias!r} using {command!r}')
        self._send_command_with_opc(command)
        self.check_errors()
        info = self.info()
        self.config_changed.emit(info)
        self.emit_notification(**info)
        return info

    def _disconnect(self) -> None:
        """Set the digital multimeter to be in LOCAL mode and then close the connection."""
        if self._rs232:
            self.local_mode()
        self.connection.disconnect()
