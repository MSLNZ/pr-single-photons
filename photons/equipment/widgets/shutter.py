"""
Widget for a shutter.
"""
from msl.qt import QtWidgets
from msl.qt import Slot
from msl.qt import ToggleSwitch

from ..base import BaseEquipmentWidget
from ..base import widget
from ..shutter import Shutter


@widget(manufacturer=r'Thorlabs|Melles Griot', model=r'KSC101|S25120A')
class ShutterWidget(BaseEquipmentWidget):

    connection: Shutter

    def __init__(self,
                 connection: Shutter,
                 *,
                 parent: QtWidgets.QWidget = None) -> None:
        """Widget for a shutter.

        Args:
            connection: The connection to the shutter controller.
            parent: The parent widget.
        """
        super().__init__(connection, parent=parent)

        self._switch = ToggleSwitch(
            initial=connection.is_open(),
            toggled=self.on_toggled
        )
        self.update_tooltip()

        if not self.connected_as_link:
            connection.state_changed.connect(self.on_state_changed)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._switch)
        self.setLayout(layout)

    def notification_handler(self, state: bool) -> None:
        """Handle notifications emitted by the Shutter Service."""
        self.on_state_changed(state)

    @Slot(bool)
    def on_toggled(self, state: bool) -> None:
        """Toggle the state of the shutter."""
        if state:
            self.connection.open()
        else:
            self.connection.close()

    @Slot(bool)
    def on_state_changed(self, state: bool) -> None:
        """Update the ToggleSwitch without emitting the signal."""
        previous = self._switch.blockSignals(True)
        self._switch.setChecked(state)
        self._switch.blockSignals(previous)
        self.update_tooltip()

    def update_tooltip(self) -> None:
        """Update the tooltip of the ToggleSwitch."""
        state = 'open' if self._switch.isChecked() else 'closed'
        self._switch.setToolTip(f'The shutter is {state}')
