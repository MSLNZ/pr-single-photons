"""
Plugin that helps to select an icon.
"""
from __future__ import annotations

import typing

from .base import BasePlugin
from .base import plugin

if typing.TYPE_CHECKING:
    from ..app import MainWindow


@plugin(name='Browse Icons', description='Find an icon to use')
class BrowseIcons(BasePlugin):

    def __init__(self, parent: MainWindow, **kwargs) -> None:
        """Find an icon to use.

        Args:
            parent: The main window.
            **kwargs: All keyword arguments are passed to super().
        """
        super().__init__(parent, **kwargs)
        self.show_plugin = False

        from msl.examples.qt import ShowStandardIcons
        ShowStandardIcons()
