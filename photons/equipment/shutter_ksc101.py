"""
Communicate with a Thorlabs KSC101 controller to control a shutter.
"""
from msl.equipment import EquipmentRecord
from msl.equipment.resources.thorlabs import KCubeSolenoid
from msl.equipment.resources.thorlabs import enums

from .base import equipment
from .kinesis import KinesisBase
from .shutter import Shutter


@equipment(manufacturer=r'Thorlabs', model=r'KSC101')
class KSC101Shutter(Shutter):

    connection: KCubeSolenoid

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Communicate with a Thorlabs KSC101 controller to control a shutter.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        KinesisBase.build_device_list()
        super().__init__(record, **kwargs)
        self.connection.set_operating_mode(enums.SC_OperatingModes.SC_Manual)

    def is_open(self) -> bool:
        """Query whether the shutter is open (True) or closed (False)."""
        return self.connection.get_operating_state() == enums.SC_OperatingStates.SC_Active

    def open(self) -> None:
        """Open the shutter."""
        self.connection.set_operating_state(enums.SC_OperatingStates.SC_Active)
        self._log_and_emit_opened()

    def close(self) -> None:
        """Close the shutter."""
        self.connection.set_operating_state(enums.SC_OperatingStates.SC_Inactive)
        self._log_and_emit_closed()
