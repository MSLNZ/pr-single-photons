"""
Plugin that is just a widget with a black background.
"""
from . import (
    plugin,
    BasePlugin,
)


@plugin(name='Black Screen', description='Make the desktop screen black')
class BlackScreen(BasePlugin):

    def __init__(self, parent):
        """Make the desktop screen black.

        Parameters
        ----------
        parent : :class:`QtWidgets.QWidget`
            The parent widget.
        """
        super(BlackScreen, self).__init__(parent)
        self.setWindowTitle('Click anywhere or press any key to enable full screen')
        self.setStyleSheet('background-color:black')
        self.showNormal()

    def toggle(self) -> None:
        """Toggle between full screen and normal display."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def mousePressEvent(self, event) -> None:
        """Overrides :meth:`QtWidgets.QtWidget.mousePressEvent`."""
        self.toggle()
        super(BlackScreen, self).mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        """Overrides :meth:`QtWidgets.QtWidget.keyPressEvent`."""
        self.toggle()
        super(BlackScreen, self).keyPressEvent(event)
