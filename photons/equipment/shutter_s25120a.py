"""
Control an electronic shutter controller from Melles Griot.
"""
from nidaqmx import Task
from nidaqmx.constants import LineGrouping

from .shutter import Shutter
from . import equipment


@equipment(manufacturer=r'Melles Griot', model=r'S25120A')
class S25120AShutter(Shutter):

    def __init__(self, app, record, *, demo=None):
        """Control an electronic shutter controller from Melles Griot.

        Uses a NI-DAQ board to output a 0 or 5 volt digital signal.

        Parameters
        ----------
        app : :class:`~photons.app.App`
            The main application entry point.
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment record.
        demo : :class:`bool`, optional
            Whether to simulate a connection to the equipment by opening
            a connection in demo mode.
        """
        self._is_open = None

        # the parent class calls close() so self._lines must be defined before calling super()
        dev = record.connection.address
        port = record.connection.properties['port']
        line = record.connection.properties['line']
        self._lines = f'{dev}/port{port}/line{line}'

        super(S25120AShutter, self).__init__(app, record, demo=demo)

    def close(self) -> None:
        """Close the shutter."""
        self._digital_out(False)
        self._log_and_emit_closed()

    def open(self) -> None:
        """Open the shutter."""
        self._digital_out(True)
        self._log_and_emit_opened()

    def is_open(self) -> bool:
        """Query whether the shutter is open.

        Returns
        -------
        :class:`bool`
            :data:`True` if the shutter is open, :data:`False` otherwise.
        """
        return self._is_open

    def _digital_out(self, state: bool) -> None:
        """Create the Task to either output 0 or 5 volts from a digital channel.

        Parameters
        ----------
        state : :class:`bool`
            Whether to open (:data:`True`) or close (:data:`False`) the shutter.
        """
        with Task() as task:
            task.do_channels.add_do_chan(self._lines, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
            task.write(state)
            self._is_open = task.read()
