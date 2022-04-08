"""
Widget for a Switched Integrator Amplifier from CMI.
"""
import re

from msl import qt

from . import (
    BaseWidget,
    widget,
)

_gain_regex = re.compile(r'TIME_(?P<value>\d+)(?P<unit>\w)*')


@widget(manufacturer=r'CMI', model=r'SIA3')
class CMISIA3(BaseWidget):

    def __init__(self, connection, *, parent=None):
        """Widget for a Switched Integrator Amplifier from CMI.

        Parameters
        ----------
        connection : :class:`photons.equipment.sia_cmi.CMISIA3`
            The connection to the amplifier.
        parent : :class:`QtWidgets.QWidget`
            The parent widget.
        """
        super(CMISIA3, self).__init__(connection, parent=parent)

        index = None

        self.gain_combobox = qt.QtWidgets.QComboBox()
        self.gain_combobox.setToolTip('SIA integration time')
        int_time = connection.get_integration_time()
        for i, (key, value) in enumerate(connection.Integration.__members__.items()):
            d = _gain_regex.search(key).groupdict()
            if not d['unit']:
                text = f'{d["value"]} s'
            elif d['unit'] == 'u':
                text = f'{d["value"]} {qt.MICRO}s'
            else:
                text = f'{d["value"]} {d["unit"]}s'
            if value == int_time:
                index = i
            self.gain_combobox.addItem(text, userData=value)

        if index is None:
            raise ValueError(f'Cannot determine the QComboBox index for {self.__class__.__name__}')
        self.gain_combobox.setCurrentIndex(index)
        self.gain_combobox.currentIndexChanged.connect(self.on_gain_changed)

        if not connection.connected_as_link:
            connection.integration_time_changed.connect(self.on_update_gain)

        form = qt.QtWidgets.QFormLayout()
        form.addRow('Integration time:', self.gain_combobox)
        self.setLayout(form)

    def notification_handler(self, integration_time) -> None:
        """Handle a notification from :class:`photons.equipment.cmi_sia3.CMISIA3`."""
        self.on_update_gain(integration_time)

    def on_gain_changed(self, index) -> None:
        """Slot for the gain_combobox.currentIndexChanged signal."""
        self.connection.set_integration_time(self.gain_combobox.itemData(index))

    def on_update_gain(self, value) -> None:
        """Slot for the connection.integration_time_changed signal.

        Update the gain_combobox without emitting the signal.
        """
        self.gain_combobox.blockSignals(True)
        for index in range(self.gain_combobox.count()):
            if self.gain_combobox.itemData(index) == value:
                self.gain_combobox.setCurrentIndex(index)
                break
        self.gain_combobox.blockSignals(False)
