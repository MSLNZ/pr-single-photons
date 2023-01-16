"""
Base classes and decorators for equipment.
"""
import re
import threading
from enum import Enum
from typing import Any
from typing import TypeVar

from msl.equipment import EquipmentRecord
from msl.equipment.connection import Connection
from msl.equipment.utils import convert_to_enum
from msl.network import Service
from msl.network.client import Link
from msl.qt import QtCore
from msl.qt import QtGui
from msl.qt import QtWidgets
from msl.qt import Signal

from ..log import logger

E = TypeVar('E', bound=Enum)

ignore_attributes = [name for name in dir(QtCore.QObject) if name[0] != '_']
ignore_attributes.extend([
    'connection', 'convert_to_enum', 'logger', 'maybe_emit_notification',
    'raise_exception', 'running_as_service', 'record', 'timeout'])


# subclass QObject so that Qt Signal's can be emitted
class BaseEquipment(QtCore.QObject, Service):

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Base class for all equipment connections.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments that a subclass requires. Can be
                specified as attributes of an XML element in a configuration
                file (with the tag of the element equal to the alias of `record`).
        """
        QtCore.QObject.__init__(self)
        Service.__init__(
            self,
            name=kwargs.get('name', record.alias),
            max_clients=kwargs.get('max_clients', 1),
            ignore_attributes=ignore_attributes
        )

        self._emit_notifications: bool = bool(kwargs.get('emit_notifications', True))

        self.record: EquipmentRecord = record
        self.alias: str = record.alias
        self.running_as_service: bool = False
        self.connection: Connection = record.connect()

        # redirect QtCore.QObject.disconnect
        self.disconnect = self.connection.disconnect

    def __getattr__(self, item) -> Any:
        """Pass all attributes that do not exist to the connection object."""
        return getattr(self.connection, item)

    def __str__(self) -> str:
        return f'<{self.__class__.__name__} connection={self.connection}>'

    @staticmethod
    def convert_to_enum(
            obj: Any,
            enum: type[E],
            prefix: str = None,
            to_upper: bool = False) -> E:
        """See :func:`~msl.equipment.utils.convert_to_enum` for more details."""
        return convert_to_enum(
            obj, enum, prefix=prefix, to_upper=to_upper, strict=True)

    @property
    def logger(self):
        """Reference to the package logger."""
        return logger

    def maybe_emit_notification(self, *args, **kwargs) -> None:
        """Emit a notification to all Clients that are linked with this Service."""
        if self.notifications_allowed and self.loop_thread_id:
            if threading.get_ident() == self.loop_thread_id:
                self.emit_notification(*args, **kwargs)
            else:
                self.emit_notification_threadsafe(*args, **kwargs)

    @property
    def notifications_allowed(self) -> bool:
        """Returns whether notifications are allowed to be sent to Clients."""
        return self.running_as_service and self._emit_notifications

    def raise_exception(self, message: str | Exception) -> None:
        """Log the message then raise an exception."""
        self.connection.raise_exception(message)

    def record_to_json(self) -> dict:
        """Returns the EquipmentRecord as a JSON-serializable object."""
        return self.record.to_json()

    @property
    def timeout(self) -> float | None:
        """The timeout, in seconds, for read and write operations.

        This property is valid only if the underlying connection is
        :class:`~msl.equipment.connection_message_based.ConnectionMessageBased`.
        """
        return self.connection.timeout  # noqa: AttributueError if not ConnectionMessageBased

    @timeout.setter
    def timeout(self, value: float | None) -> None:
        self.connection.timeout = value


ConnectionClass = Link | BaseEquipment | Connection


class BaseEquipmentWidget(QtWidgets.QWidget):

    closing: QtCore.SignalInstance = Signal()

    def __init__(self,
                 connection: ConnectionClass,
                 *,
                 parent: QtWidgets.QWidget = None,
                 **kwargs) -> None:
        """Base class for all Qt widgets that connect to equipment.

        Args:
            connection: The connection to the equipment.
            parent: The parent widget.
            **kwargs: All keyword arguments are passed to super().
        """
        super().__init__(parent=parent, **kwargs)
        self.connection = connection
        self.connected_as_link: bool = isinstance(connection, Link)
        if self.connected_as_link:
            connection.notification_handler = self.notification_handler
            self.record: EquipmentRecord = EquipmentRecord(**connection.record_to_json())
        else:
            self.record: EquipmentRecord = connection.record

        self.setWindowTitle(f'{self.record.alias}')

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.closeEvent`."""
        self.closing.emit()
        super().closeEvent(event)

    @property
    def logger(self):
        """Reference to the package logger."""
        return logger

    def notification_handler(self, *args, **kwargs) -> None:
        """Override in subclass to handle notifications emitted by a Service."""
        pass


class EquipmentMatcher:

    def __init__(self,
                 cls: type[BaseEquipment | BaseEquipmentWidget],
                 manufacturer: str | None,
                 model: str | None,
                 flags: int) -> None:
        """Performs match operations on an :class:`~msl.equipment.record_types.EquipmentRecord`.

        Args:
            cls: The class to associate with the matcher.
                The class must not be instantiated.
            manufacturer: The name of the manufacturer.
                Can be a regex pattern.
            model: The model number of the equipment.
                Can be a regex pattern.
            flags: The flags to use to compile the regex patterns.
        """
        self.cls = cls
        self.manufacturer = re.compile(manufacturer, flags=flags) if manufacturer else None
        self.model = re.compile(model, flags=flags) if model else None

    def matches(self, record: EquipmentRecord) -> bool:
        """Checks if `record` is a match.

        Args:
            record: The equipment record to check if the manufacturer
                and the model number are a match.

        Returns:
            Whether `record` is a match.
        """
        if not (self.manufacturer or self.model):
            return False
        if self.manufacturer and not self.manufacturer.search(record.manufacturer):
            return False
        if self.model and not self.model.search(record.model):
            return False
        return True


DecoratedBaseEquipment = TypeVar('DecoratedBaseEquipment', bound=BaseEquipment)
DecoratedBaseEquipmentWidget = TypeVar('DecoratedBaseEquipmentWidget', bound=BaseEquipmentWidget)


def equipment(*, manufacturer: str = None, model: str = None, flags: int = 0):
    """A decorator to register equipment (for connections).

    Args:
        manufacturer: The name of the manufacturer. Can be a regex pattern.
        model: The model number of the equipment. Can be a regex pattern.
        flags: The flags to use to compile the regex patterns.
    """
    def decorate(cls: type[DecoratedBaseEquipment]) -> type[DecoratedBaseEquipment]:
        if not issubclass(cls, BaseEquipment):
            raise TypeError(f'{cls} is not a subclass of {BaseEquipment}')
        devices.append(EquipmentMatcher(cls, manufacturer, model, flags))
        logger.debug(f'added {cls.__name__!r} to the equipment registry')
        return cls
    return decorate


def widget(*, manufacturer: str = None, model: str = None, flags: int = 0):
    """A decorator to register a widget (for equipment).

    Args:
        manufacturer: The name of the manufacturer. Can be a regex pattern.
        model: The model number of the equipment. Can be a regex pattern.
        flags: The flags to use to compile the regex patterns.
    """
    def decorate(cls: type[DecoratedBaseEquipmentWidget]) -> type[DecoratedBaseEquipmentWidget]:
        if not issubclass(cls, BaseEquipmentWidget):
            raise TypeError(f'{cls} is not a subclass of {BaseEquipmentWidget}')
        widgets.append(EquipmentMatcher(cls, manufacturer, model, flags))
        logger.debug(f'added {cls.__name__!r} to the widget registry')
        return cls
    return decorate


devices: list[EquipmentMatcher] = []
widgets: list[EquipmentMatcher] = []
