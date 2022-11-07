"""
Plugin that is just a widget with a black background.
"""
from __future__ import annotations

import typing

from msl.qt import QtGui

from .base import BasePlugin
from .base import plugin

if typing.TYPE_CHECKING:
    from ..app import MainWindow


@plugin(name='Black Screen', description='Make the desktop screen black')
class BlackScreen(BasePlugin):

    def __init__(self, parent: MainWindow, **kwargs) -> None:
        """Make the desktop screen black.

        Args:
            parent: The main window.
            **kwargs: All keyword arguments are passed to super().
        """
        super().__init__(parent, **kwargs)
        self.setWindowTitle('Click anywhere or press any key to enable full screen')
        self.setStyleSheet('background-color:black')
        self.showNormal()

    def toggle(self) -> None:
        """Toggle between full screen and normal display."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.mousePressEvent`."""
        self.toggle()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.keyPressEvent`."""
        self.toggle()
        super().keyPressEvent(event)
