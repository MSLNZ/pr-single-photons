"""
Custom Qt widgets.
"""
import logging
import os
import importlib

from msl.equipment import EquipmentRecord
from msl.io import search
from msl.qt import (
    QtWidgets,
    Signal,
)

from ... import (
    logger,
    Register,
)

widgets = []
""":class:`list` of :class:`~photons.utils.Register`: The :class:`QtWidgets.QWidget`\\s that have been registered."""


class BaseWidget(QtWidgets.QWidget):

    window_closing = Signal()

    def __init__(self, connection, *, parent=None, **kwargs):
        """Base class for all Qt widgets.

        Parameters
        ----------
        connection : :class:`~photons.equipment.BaseEquipment`
            The connection to the equipment.
        parent : :class:`QtWidgets.QWidget`, optional
            The parent widget.
        kwargs
            Additional keyword arguments are passed to :class:`QtWidgets.QWidget`.
        """
        super(BaseWidget, self).__init__(parent=parent, **kwargs)
        self.connected_as_link = connection.connected_as_link
        self.connection = connection

        if parent is not None:
            self.gui = parent.parent()  # gui == MainWindow only if the BaseWidget is a docked widget

        if self.connected_as_link:
            self.record = EquipmentRecord(**connection.record_to_json())
            connection.notification_handler = self.notification_handler
        else:
            self.record = connection.record

        self.setWindowTitle(f'{self.record.alias}')

    def notification_handler(self, *args, **kwargs) -> None:
        """Handles notifications emitted by a :class:`~msl.network.service.Service`.

        See :meth:`~msl.network.client.Link.notification_handler` for more details.
        """
        pass

    def closeEvent(self, event) -> None:
        """Overrides :meth:`QtWidgets.QWidget.closeEvent`."""
        self.window_closing.emit()
        super(BaseWidget, self).closeEvent(event)

    @property
    def logger(self) -> logging.Logger:
        """Reference to the package logger."""
        return logger


def widget(manufacturer=None, model=None, flags=0):
    """Use as a decorator to register a QWidget.

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
        widgets.append(Register(manufacturer, model, flags, obj))
        logger.debug('added {} to the widget registry'.format(obj))
        return obj
    return cls


def find_widget(connection, *, parent=None, **kwargs):
    """Find the widget that is used for a connection.

    Parameters
    ----------
    connection : :class:`~photons.equipment.BaseEquipment`
        The connection to the equipment.
    parent : :class:`QtWidgets.QWidget`, optional
        The parent widget.
    kwargs
        Additional keyword arguments are passed to :class:`QtWidgets.QWidget`.

    Returns
    -------
    :class:`~photons.gui.equipment.BaseWidget`
        The widget that corresponds with the `connection`.

    Raises
    ------
    RuntimeError
        If a widget does not exist for the `connection`.
    """
    if connection.connected_as_link:
        record = EquipmentRecord(**connection.record_as_json())
    else:
        record = connection.record

    w = None
    for register in widgets:
        if register.matches(record):
            w = register.cls(connection, parent=parent, **kwargs)
            break

    if w is None:
        raise RuntimeError(f'No widget exists for {record.alias!r}')

    return w


# import all submodules to register all QWidgets
for filename in search(os.path.dirname(__file__), pattern=Register.PATTERN, levels=0):
    importlib.import_module(__name__ + '.' + os.path.basename(filename)[:-3])
