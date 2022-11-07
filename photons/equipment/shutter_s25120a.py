"""
Control an electronic shutter controller from Melles Griot.
"""
from msl.equipment import EquipmentRecord

from .base import equipment
from .nidaq import NIDAQ
from .shutter import Shutter


@equipment(manufacturer=r'Melles Griot', model=r'S25120A')
class S25120AShutter(Shutter):

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Control an electronic shutter controller from Melles Griot.

        Uses a NI-DAQ board to output a 0 or 5 volt digital signal.
        The `ConnectionRecord.properties` attribute must contain the
        NI-DAQ port and line value for the digital output signal
        (e.g., port=1; line=1)

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        props = record.connection.properties
        self._daq_port = props.get('port')
        if self._daq_port is None:
            self.raise_exception(
                'You must define the DAQ "port" number '
                'as a ConnectionRecord.properties attribute, e.g. port=1'
            )
        self._daq_line = props.get('line')
        if self._daq_line is None:
            self.raise_exception(
                'You must define the DAQ "line" number '
                'as a ConnectionRecord.properties attribute, e.g., line=1'
            )

        self._daq = NIDAQ(record)
        super().__init__(record, **kwargs)

    def is_open(self) -> bool:
        """Query whether the shutter is open (True) or closed (False)."""
        return self._daq.digital_out_read(self._daq_line, port=self._daq_port)

    def open(self) -> None:
        """Open the shutter."""
        self._daq.digital_out(self._daq_line, True, port=self._daq_port)
        self._log_and_emit_opened()

    def close(self) -> None:
        """Close the shutter."""
        self._daq.digital_out(self._daq_line, False, port=self._daq_port)
        self._log_and_emit_closed()
