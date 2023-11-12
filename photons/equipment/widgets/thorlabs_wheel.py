"""
Widget for a Thorlabs filter wheel FW212C.
"""
from msl.qt import ComboBox
from msl.qt import QtWidgets
from msl.qt import Slot

from ..base import BaseEquipmentWidget
from ..base import widget
from ..thorlabs_wheel import ThorlabsWheel


@widget(manufacturer=r'Thorlabs', model=r'FW212C')
class ThorlabsWheelWidget(BaseEquipmentWidget):

    connection: ThorlabsWheel

    def __init__(self,
                 connection: ThorlabsWheel,
                 *,
                 parent: QtWidgets.QWidget = None) -> None:
        """Widget for a Thorlabs filter wheel FW212C.

        :param connection: The connection to the filter wheel.
        :param parent: The parent widget.
        """
        super().__init__(connection, parent=parent)

        self._combobox = ComboBox(
            items=list(f'OD: {v}' if v is not None else '' for v in connection.filter_info().values()),
            initial=connection.get_position() - 1,
            index_changed=self.on_index_changed,
            tooltip='The position of the filter wheel',
        )

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._combobox)
        self.setLayout(layout)

    @Slot(int)
    def on_index_changed(self, index: int) -> None:
        """Slot for the QComboBox.currentIndexChanged signal."""
        self.connection.set_position(index + 1)
