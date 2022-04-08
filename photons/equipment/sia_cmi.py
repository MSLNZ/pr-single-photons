"""
Communicate with a Switched Integrator Amplifier from CMI.
"""
from msl.qt import Signal
from msl.equipment.resources.cmi import sia3

from . import (
    BaseEquipment,
    equipment,
)


@equipment(manufacturer=r'CMI', model=r'SIA3')
class CMISIA3(BaseEquipment):

    Integration = sia3.IntegrationTime

    integration_time_changed = Signal(int)  # IntegrationTime value

    def __init__(self, app, record, *, demo=None):
        """Communicate with a Switched Integrator Amplifier from CMI.

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
        super(CMISIA3, self).__init__(app, record, demo=demo)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes(['integration_time_changed'])

        # Don't know how (or if it is possible) to read the settings from
        # the SIA, therefore we set the gain so that it is in a known state
        self._integration_time = None
        self.set_integration_time(self.Integration.TIME_1m)

    def get_integration_time(self) -> sia3.IntegrationTime:
        """The integration time."""
        return self._integration_time

    def set_integration_time(self, time: int | str) -> None:
        """Set the integration time (i.e., the gain).

        Parameters
        ----------
        time : :class:`~msl.equipment.resources.cmi.sia3.IntegrationTime`
            The integration time. For example,

                * time=sia.IntegrationTime.TIME_100u
                * time='100u'
                * time=6

            are all equivalent.
        """
        self._integration_time = self.connection.convert_to_enum(
            time, self.Integration, prefix='TIME_')

        self.connection.set_integration_time(self._integration_time)

        self.logger.info(f'{self.alias!r} set {self._integration_time!r}')
        self.integration_time_changed.emit(self._integration_time)
        if self.connected_as_link:
            self.emit_notification(self._integration_time)  # to all linked Clients
