"""
Custom Plugins.
"""
import os
import importlib

from msl.io import search
from msl.qt import (
    QtWidgets,
    Signal,
)

from .. import (
    logger,
    Register,
)

plugins = []
""":class:`list` of :class:`~photons.plugins.Plugin`: The Plugins that have been registered."""


class BasePlugin(QtWidgets.QWidget):

    window_closing = Signal()

    def __init__(self, parent, **kwargs):
        """Base class for all Plugins.

        Parameters
        ----------
        parent : :class:`~photons.gui.MainWindow`
            The main window.
        """
        super(BasePlugin, self).__init__(**kwargs)
        self.gui = parent
        self.app = parent.app
        self.show_plugin = True

    def closeEvent(self, event) -> None:
        """Overrides :meth:`QtWidgets.QWidget.closeEvent`."""
        self.window_closing.emit()
        super(BasePlugin, self).closeEvent(event)


def plugin(name, description):
    """Use as a decorator to register a :class:`~photons.plugins.Plugin` class."""
    def cls(obj):
        plugins.append((obj, name, description))
        logger.debug('added {} to the plugins registry'.format(obj))
        return obj
    return cls


# import all submodules to register all plugin classes
for filename in search(os.path.dirname(__file__), pattern=Register.PATTERN, levels=0):
    importlib.import_module(__name__ + '.' + os.path.basename(filename)[:-3])
