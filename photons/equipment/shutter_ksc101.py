"""
Communicate with a Thorlabs KSC101 controller to control a shutter.
"""
from msl.equipment.resources.thorlabs.kinesis.enums import (
    SC_OperatingModes,
    SC_OperatingStates,
)

from . import equipment
from .shutter import Shutter
from .kinesis import build_device_list


@equipment(manufacturer=r'Thorlabs', model=r'KSC101')
class KSC101Shutter(Shutter):

    def __init__(self, app, record, *, demo=None):
        """Communicate with a Thorlabs KSC101 controller to control a shutter.

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
        build_device_list()
        super(KSC101Shutter, self).__init__(app, record, demo=demo)
        self.connection.set_operating_mode(SC_OperatingModes.SC_Manual)

    def is_open(self) -> bool:
        """Query whether the shutter is open.

        Returns
        -------
        :class:`bool`
            :data:`True` if the shutter is open, :data:`False` otherwise.
        """
        return self.connection.get_operating_state() == SC_OperatingStates.SC_Active

    def open(self) -> None:
        """Open the shutter."""
        self.connection.set_operating_state(SC_OperatingStates.SC_Active)
        self._log_and_emit_opened()

    def close(self) -> None:
        """Close the shutter."""
        self.connection.set_operating_state(SC_OperatingStates.SC_Inactive)
        self._log_and_emit_closed()
