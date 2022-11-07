"""
Base class for Plugins.
"""
from __future__ import annotations

import typing
from dataclasses import dataclass

from msl.qt import QtCore
from msl.qt import QtGui
from msl.qt import QtWidgets
from msl.qt import Signal

from ..log import logger

if typing.TYPE_CHECKING:
    from ..app import MainWindow


class BasePlugin(QtWidgets.QWidget):

    closing: QtCore.SignalInstance = Signal()

    def __init__(self, main: MainWindow, **kwargs) -> None:
        """Base class for all Plugins.

        Args:
            main: The main window.
            **kwargs: All keyword arguments are passed to super().
        """
        super().__init__(**kwargs)  # the subclass should pass parent to super()
        self.main = main
        self.app = main.app
        self.update_progress_bar = main.update_progress_bar
        self.status_bar_message = main.status_bar_message
        self.find_widget = main.find_widget
        self.show_plugin = True

    def after_show(self) -> None:
        """Override in subclass. Called immediately after show()."""
        pass

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.closeEvent`."""
        self.closing.emit()
        super().closeEvent(event)


@dataclass(frozen=True)
class PluginInfo:
    cls: type[BasePlugin]
    name: str
    description: str


def plugin(*, name: str, description: str):
    """A decorator to register a Plugin.

    Args:
        name: A name to associate with the Plugin.
        description: A short description about the Plugin.
    """
    def decorate(cls: type[DecoratedBasePlugin]) -> type[DecoratedBasePlugin]:
        if not issubclass(cls, BasePlugin):
            raise TypeError(f'{cls} is not a subclass of {BasePlugin}')
        plugins.append(PluginInfo(cls=cls, name=name, description=description))
        logger.debug(f'added {cls.__name__!r} to the plugins registry')
        return cls
    return decorate


DecoratedBasePlugin = typing.TypeVar('DecoratedBasePlugin', bound=BasePlugin)

plugins: list[PluginInfo] = []
