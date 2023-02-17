"""
Switched Integrator Amplifier from CMI.
"""
from msl.equipment import EquipmentRecord
from msl.equipment.resources.cmi import SIA3
from msl.qt import QtCore
from msl.qt import Signal

from .base import BaseEquipment
from .base import equipment


@equipment(manufacturer=r'CMI', model=r'SIA3')
class SIA3CMI(BaseEquipment):

    connection: SIA3

    Integration = SIA3.GAIN

    integration_time_changed: QtCore.SignalInstance = Signal(SIA3.GAIN)

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Switched Integrator Amplifier from CMI.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes('integration_time_changed')

        # Don't know how (or if it is possible) to read the settings from
        # the SIA, therefore we set the gain so that it is in a known state
        self._integration_time: SIA3.IntegrationTime | None = None
        self.set_integration_time(self.Integration.TIME_1m)

        self._numeric = {
            SIA3.GAIN.TIME_50u: 50e-6,
            SIA3.GAIN.TIME_100u: 100e-6,
            SIA3.GAIN.TIME_1m: 1e-3,
            SIA3.GAIN.TIME_10m: 10e-3,
            SIA3.GAIN.TIME_20m: 20e-3,
            SIA3.GAIN.TIME_100m: 100e-3,
            SIA3.GAIN.TIME_200m: 200e-3,
            SIA3.GAIN.TIME_500m: 500e-3,
            SIA3.GAIN.TIME_1: 1.0,
            SIA3.GAIN.TIME_2: 2.0,
        }

    def get_integration_time(self, as_enum: bool = False) -> SIA3.GAIN | float:
        """Get the integration time.

        Args:
            as_enum: Whether to return the value as an
                :class:`~msl.equipment.resources.cmi.sia3.IntegrationTime`
                enum value or as a numeric value in seconds.

        Returns:
            The integration time.
        """
        if as_enum:
            return self._integration_time
        return self._numeric[self._integration_time]

    def set_integration_time(self, time: int | str) -> None:
        """Set the integration time (i.e., the gain).

        For example::

            time=sia.Integration.TIME_100u
            time='100u'
            time='100us'
            time=6

        are all equivalent.

        Args:
            time: The integration time.
        """
        if isinstance(time, str):
            time = time.rstrip('s')
        self._integration_time = self.connection.convert_to_enum(
            time, self.Integration, prefix='TIME_')

        self.connection.set_integration_time(self._integration_time)

        self.logger.info(f'{self.alias!r} set {self._integration_time!r}')
        self.integration_time_changed.emit(self._integration_time)
        self.maybe_emit_notification(self._integration_time)
