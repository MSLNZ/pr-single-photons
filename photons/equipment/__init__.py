"""
Custom classes for communicating with equipment.
"""
import importlib
import logging
import os
import weakref

from msl.qt import QtCore
from msl.network import Service
from msl.io import search
from msl.equipment.utils import convert_to_enum

from .. import (
    logger,
    Register,
)

registry = []
""":class:`list` of :class:`~photons.utils.Register`: The equipment classes that have been registered."""


class BaseEquipment(QtCore.QObject, Service):

    def __init__(self, app, record, *, demo=None, name=None, max_clients=1):
        """Base class for all equipment connections.

        Parameters
        ----------
        app : :class:`~photons.app.App`
            The main application entry point.
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment record.
        demo : :class:`bool`, optional
            Whether to simulate a connection to the equipment by opening
            a connection in demo mode.
        name : :class:`str`, optional
            The name of the :class:`~msl.network.service.Service` as it will appear
            on the Network :class:`~msl.network.manager.Manager`. If not specified then
            uses the name of the class.
        max_clients : :class:`int`, optional
            The maximum number of :class:`~msl.network.client.Client`\\s that can be linked
            with this :class:`~msl.network.service.Service`. A value :math:`\\leq` 0 or
            :data:`None` means that there is no limit.
        """
        QtCore.QObject.__init__(self)  # subclass QObject so that Qt signals can be emitted
        Service.__init__(self, name=name if name else record.alias, max_clients=max_clients)
        self.ignore_attributes(['app', 'record', 'connection', 'thorlabs_signaler', 'convert_to_enum', 'logger'])
        self.ignore_attributes(dir(QtCore.QObject))

        self.app = weakref.ref(app)
        """:class:`~photons.app.App`: The main application entry point."""

        self.record = record
        """:class:`~msl.equipment.record_types.EquipmentRecord`: The equipment record."""

        self.alias = record.alias
        """:class:`str`: The alias of the :attr:`.record`"""

        self.connection = record.connect(demo=demo)
        """The :class:`~msl.equipment.connection.Connection` subclass."""

        self.connected_as_link = self._loop is not None
        """:class:`bool`: Whether the connection to the equipment is via a :class:`~msl.network.client.Link`."""

        # redirect QtCore.QObject.disconnect
        self.disconnect = self.connection.disconnect

        self._record_json = self.record.to_json()

    def __str__(self):
        return f'<{self.__class__.__name__} connection={self.connection}>'

    def __getattr__(self, item):
        """Pass all attributes that do not exist to the connection object."""
        return getattr(self.connection, item)

    def emit_notification(self, *args, **kwargs) -> None:
        """Emit a notification to all :class:`~msl.network.client.Client`\\s that
        are :class:`~msl.network.client.Link`\\ed with this :class:`Service`."""
        if self.connected_as_link:
            super(BaseEquipment, self).emit_notification(*args, **kwargs)

    @property
    def logger(self) -> logging.Logger:
        """Reference to the package logger."""
        return logger

    def record_to_json(self) -> dict:
        """Convert the :class:`~msl.equipment.record_types.EquipmentRecord` to be JSON serializable.

        Returns
        -------
        :class:`dict`
            The :class:`~msl.equipment.record_types.EquipmentRecord`.
        """
        return self._record_json

    @property
    def timeout(self):
        """:class:`float` or :data:`None`: The timeout, in seconds, for read and write operations.

        This property is valid if the underlying connection is a
        :class:`~msl.equipment.connection_message_based.ConnectionMessageBased`.
        """
        return self.connection.timeout

    @timeout.setter
    def timeout(self, value):
        self.connection.timeout = value

    @staticmethod
    def convert_to_enum(obj, enum, prefix=None, to_upper=False, strict=True):
        """See :func:`~msl.equipment.utils.convert_to_enum` for more details."""
        return convert_to_enum(obj, enum, prefix=prefix, to_upper=to_upper, strict=strict)


def equipment(manufacturer=None, model=None, flags=0):
    """Use as a decorator to register an equipment-connection class.

    Parameters
    ----------
    manufacturer : :class:`str`, optional
        The name of the manufacturer. Can be a regex pattern.
    model : :class:`str`, optional
        The model number of the equipment. Can be a regex pattern.
    flags : :class:`int`, optional
        The flags to use for the regex pattern.
    """
    def cls(obj):
        registry.append(Register(manufacturer, model, flags, obj))
        logger.debug(f'added {obj} to the equipment registry')
        return obj
    return cls


# import all submodules to register all equipment classes
for filename in search(os.path.dirname(__file__), pattern=Register.PATTERN, levels=0):
    importlib.import_module(__name__ + '.' + os.path.basename(filename)[:-3])
