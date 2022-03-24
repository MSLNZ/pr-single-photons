"""
Base class for a shutter.
"""
from msl.qt import Signal

from . import BaseEquipment


class Shutter(BaseEquipment):

    state_changed = Signal(bool)  # True: shutter is open, False: shutter is closed

    def __init__(self, app, record, *, demo=None):
        """Base class for a shutter.

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
        super(Shutter, self).__init__(app, record, demo=demo)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes(['state_changed'])

        # the shutter that is attached to the controller, shutter=model[serial]
        self.shutter_name = record.connection.properties.get('shutter')

        self.close()

    def close(self) -> None:
        """Close the shutter."""
        raise NotImplementedError

    def open(self) -> None:
        """Open the shutter."""
        raise NotImplementedError

    def is_open(self) -> bool:
        """Query whether the shutter is open."""
        raise NotImplementedError

    def _log_and_emit_opened(self):
        self.logger.info(f'open the shutter {self.shutter_name!r}')
        self.state_changed.emit(True)
        self.emit_notification(True)  # to all linked clients

    def _log_and_emit_closed(self):
        self.logger.info(f'close the shutter {self.shutter_name!r}')
        self.state_changed.emit(False)
        self.emit_notification(False)  # to all linked clients
