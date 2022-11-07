"""
Widget for a Switched Integrator Amplifier from CMI.
"""
import re

from msl.qt import ComboBox
from msl.qt import MICRO
from msl.qt import QtWidgets
from msl.qt import Slot

from ..base import BaseEquipmentWidget
from ..base import widget
from ..sia_cmi import SIA3CMI

_gain_regex = re.compile(r'TIME_(?P<value>\d+)(?P<unit>[um]?)')


@widget(manufacturer=r'CMI', model=r'SIA3')
class SIA3CMIWidget(BaseEquipmentWidget):

    connection: SIA3CMI

    def __init__(self,
                 connection: SIA3CMI,
                 *,
                 parent: QtWidgets.QWidget = None) -> None:
        """Widget for a Switched Integrator Amplifier from CMI.

        Args:
            connection: The connection to the amplifier.
            parent: The parent widget.
        """
        super().__init__(connection, parent=parent)

        index = None
        int_time = connection.get_integration_time()
        items = {}
        for i, (key, value) in enumerate(SIA3CMI.Integration.__members__.items()):
            if value == int_time:
                index = i

            d = _gain_regex.search(key).groupdict()
            if not d['unit']:
                text = f'{d["value"]} s'
            elif d['unit'] == 'u':
                text = f'{d["value"]} {MICRO}s'
            else:
                text = f'{d["value"]} {d["unit"]}s'
            items[text] = value

        if index is None:
            raise ValueError(f'Cannot determine the QComboBox index for '
                             f'{self.__class__.__name__!r}')

        self.gain_combobox = ComboBox(
            items=items,
            initial=index,
            tooltip='SIA integration time',
            index_changed=self.on_index_changed,
        )

        if not self.connected_as_link:
            connection.integration_time_changed.connect(self.on_integration_time_changed)

        form = QtWidgets.QFormLayout()
        form.addRow('Integration time:', self.gain_combobox)
        self.setLayout(form)

    def notification_handler(self, integration_time: int) -> None:
        """Handle notifications from the SIA3CMI Service."""
        self.on_integration_time_changed(integration_time)

    @Slot(int)
    def on_index_changed(self, index: int) -> None:
        """Set the integration time."""
        self.connection.set_integration_time(index + 5)

    @Slot(int)
    def on_integration_time_changed(self, value: int) -> None:
        """Update the combobox without emitting the signal."""
        previous = self.gain_combobox.blockSignals(True)
        for index in range(self.gain_combobox.count()):
            if self.gain_combobox.itemData(index) == value:
                self.gain_combobox.setCurrentIndex(index)
                break
        self.gain_combobox.blockSignals(previous)
