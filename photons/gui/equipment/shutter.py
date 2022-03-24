"""
Widget for a shutter.
"""
from msl.qt import (
    QtWidgets,
    ToggleSwitch,
)

from . import (
    BaseWidget,
    widget,
)


@widget(manufacturer=r'Thorlabs|Melles Griot', model=r'KSC101|S25120A')
class Shutter(BaseWidget):

    def __init__(self, connection, *, parent=None):
        """Widget for a shutter.

        Parameters
        ----------
        connection : :class:`~photons.equipment.shutter.Shutter`
            The connection to the shutter controller.
        parent : :class:`QtWidgets.QWidget`
            The parent widget.
        """
        super(Shutter, self).__init__(connection, parent=parent)

        self._switch = ToggleSwitch()
        is_open = connection.is_open()
        self._switch.setChecked(is_open)
        self._switch.toggled.connect(self.on_state_changed)
        self.update_tooltip(is_open)

        if not connection.connected_as_link:
            connection.state_changed.connect(self.update_switch_display)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self._switch)
        self.setLayout(hbox)

    def notification_handler(self, state: bool) -> None:
        """Handle the notification emitted by a CallbackSignaler for a MotionControlCallback.

        See :mod:`photons.equipment.kinesis`.
        """
        self.update_switch_display(state)

    def on_state_changed(self, state: bool) -> None:
        """Slot for the ToggleSwitch."""
        if state:
            self.connection.open()
        else:
            self.connection.close()
        self.update_tooltip(state)

    def update_switch_display(self, state: bool) -> None:
        """Slot for the connection.state_changed signal.

        Update the ToggleSwitch without emitting the signal.
        """
        self._switch.blockSignals(True)
        self._switch.setChecked(state)
        self._switch.blockSignals(False)
        self.update_tooltip(state)

    def update_tooltip(self, is_open: bool) -> None:
        """Update the tooltip of the ToggleSwitch.

        Parameters
        ----------
        is_open : :class:`bool`
             :data:`True` if the shutter is open, :data:`False` otherwise.
        """
        state = 'open' if is_open else 'closed'
        self._switch.setToolTip(f'The shutter is {state}')
