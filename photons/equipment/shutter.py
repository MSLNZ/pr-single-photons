"""
Base class for a shutter.
"""
from msl.equipment import EquipmentRecord
from msl.qt import QtCore
from msl.qt import Signal

from .base import BaseEquipment


class Shutter(BaseEquipment):

    # True: shutter is open, False: shutter is closed
    state_changed: QtCore.SignalInstance = Signal(bool)

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Base class for a shutter.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes('state_changed')

        # the shutter that is attached to the controller
        # use the following format in ConnectionRecord.properties shutter=model[serial]
        self.shutter_name = record.connection.properties.get('shutter')
        if self.shutter_name is None:
            self.raise_exception(
                'Cannot determine the name of the shutter.\n'
                'Define a shutter=model[serial] parameter '
                'in the properties of the ConnectionRecord'
            )

    def is_open(self) -> bool:
        """Query whether the shutter is open (True) or closed (False)."""
        raise NotImplementedError

    def open(self) -> None:
        """Open the shutter."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the shutter."""
        raise NotImplementedError

    def _log_and_emit_opened(self):
        self.logger.info(f'open the shutter {self.shutter_name!r}')
        self.state_changed.emit(True)
        self.maybe_emit_notification(True)

    def _log_and_emit_closed(self):
        self.logger.info(f'close the shutter {self.shutter_name!r}')
        self.state_changed.emit(False)
        self.maybe_emit_notification(False)
