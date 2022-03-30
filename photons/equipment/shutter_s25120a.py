"""
Control an electronic shutter controller from Melles Griot.
"""
from . import equipment
from .shutter import Shutter
from .nidaq import NIDAQ


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
        self._daq_port = record.connection.properties['port']
        if self._daq_port is None:
            raise ValueError(
                'You must define the DAQ "port" number '
                'as a ConnectionRecord.properties attribute, e.g. port=1'
            )
        self._daq_line = record.connection.properties['line']
        if self._daq_line is None:
            raise ValueError(
                'You must define the DAQ "line" number '
                'as a ConnectionRecord.properties attribute, e.g., line=1'
            )
        self._daq = NIDAQ(app, record, demo=demo)
        super(S25120AShutter, self).__init__(app, record, demo=demo)

    def close(self) -> None:
        """Close the shutter."""
        self._daq.digital_out(False, self._daq_line, port=self._daq_port)
        self._log_and_emit_closed()

    def is_open(self) -> bool:
        """Query whether the shutter is open.

        Returns
        -------
        :class:`bool`
            :data:`True` if the shutter is open, :data:`False` otherwise.
        """
        return self._daq.digital_out_read(self._daq_line, port=self._daq_port)

    def open(self) -> None:
        """Open the shutter."""
        self._daq.digital_out(True, self._daq_line, port=self._daq_port)
        self._log_and_emit_opened()
