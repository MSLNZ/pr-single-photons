"""
Widget for a Thorlabs filter flipper (MFF101 or MFF102).
"""
from msl.qt import ComboBox
from msl.qt import QtWidgets
from msl.qt import Slot

from ..base import BaseEquipmentWidget
from ..base import widget
from ..thorlabs_flipper import ThorlabsFlipper


@widget(manufacturer=r'Thorlabs', model=r'MFF10[1|2]')
class ThorlabsFlipperWidget(BaseEquipmentWidget):

    connection: ThorlabsFlipper

    def __init__(self,
                 connection: ThorlabsFlipper,
                 *,
                 parent: QtWidgets.QWidget = None) -> None:
        """Widget for a Thorlabs filter flipper (MFF101 or MFF102).

        Args:
            connection: The connection to the flipper.
            parent: The parent widget.
        """
        super().__init__(connection, parent=parent)

        self._combobox = ComboBox(
            items=list(connection.info().values()),
            initial=connection.get_position() - 1,
            index_changed=self.on_index_changed,
            tooltip='The position of the flipper',
        )

        # connect the MotionControlCallback to a slot
        if not self.connected_as_link:
            connection.signaler.position_changed.connect(self.on_callback)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._combobox)
        self.setLayout(layout)

    def notification_handler(self, info: dict) -> None:
        """Handle the notifications from a MotionControlCallback."""
        self.on_callback(info)

    @Slot(int)
    def on_index_changed(self, index: int) -> None:
        """Slot for the QComboBox.currentIndexChanged signal."""
        self.connection.set_position(index + 1, wait=False)

    @Slot(dict)
    def on_callback(self, info: dict) -> None:
        """Slot for the MotionControlCallback signal."""
        index = info['position'] - 1
        if index < 0:  # the flipper is still moving
            return

        previous = self._combobox.blockSignals(True)
        self._combobox.setCurrentIndex(index)
        self._combobox.blockSignals(previous)
