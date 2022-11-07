"""
Widget for a Keithley 6430 sub-femtoAmp SourceMeter.
"""
from msl.qt import ComboBox
from msl.qt import DoubleSpinBox
from msl.qt import QtWidgets
from msl.qt import Slot
from msl.qt import ToggleSwitch

from ..base import BaseEquipmentWidget
from ..base import widget
from ..keithley_6430 import Keithley6430


@widget(manufacturer=r'Keithley', model=r'6430')
class Keithley6430Widget(BaseEquipmentWidget):

    connection: Keithley6430

    def __init__(self,
                 connection: Keithley6430,
                 *,
                 parent: QtWidgets.QWidget = None) -> None:
        """Widget for a Keithley 6430 sub-femtoAmp SourceMeter.

        Args:
            connection: The connection to the SourceMeter.
            parent: The parent widget.
        """
        super().__init__(connection, parent=parent)

        if not self.connected_as_link:
            # connection.settings_changed.connect()
            connection.source_settings_changed.connect(self.on_source_settings_changed)

        source_group = QtWidgets.QGroupBox('Source')

        vbox = QtWidgets.QVBoxLayout()
        self._toggle = ToggleSwitch(
            initial=connection.is_output_enabled(),
            toggled=connection.enable_output,
            tooltip='Turn the Source output on or off'
        )
        vbox.addWidget(self._toggle)

        # TODO create the following widgets for the Source subsystem
        #  nsamples: int = 10
        #  auto_zero: bool | int | str = True
        #  trigger: str = 'bus'
        #  delay: float = 0.0
        #  mode: str = 'fixed'
        #  cmpl: float = 0.01
        #  cmpl_range: float = 0.21

        self._function_combobox = ComboBox(
            items=['Current', 'Voltage'],
            text_changed=self.on_function_text_changed,
        )
        vbox.addWidget(self._function_combobox)

        self._range_spinbox = DoubleSpinBox(
            minimum=-0.105,
            maximum=0.105,
            step=0.01,
            decimals=3,
            unit='A',
            use_si_prefix=True,
            editing_finished=self.on_configure_source,
        )

        # update the initial values in the widgets
        self.on_source_settings_changed(connection.settings_source())

        form = QtWidgets.QFormLayout()
        form.addRow('Output:', self._range_spinbox)
        vbox.addLayout(form)

        source_group.setLayout(vbox)
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(source_group)
        self.setLayout(layout)

    @Slot(str)
    def on_function_text_changed(self, text: str) -> None:
        """Slot for the Function QComboBox.currentTextChanged signal."""
        suffix = 'A' if text == 'Current' else 'V'
        self._range_spinbox.setSuffix(suffix)
        self._configure_source()

    @Slot(dict)
    def on_source_settings_changed(self, settings: dict) -> None:
        """Slot for the Keithley6430.source_settings_changed signal."""
        previous = self._function_combobox.blockSignals(True)
        self._function_combobox.setCurrentText(settings['function'].title())
        self._function_combobox.blockSignals(previous)
        self._range_spinbox.setValue(settings['range'])

    @Slot()
    def on_configure_source(self) -> None:
        """Slot to configure the Source subsystem."""
        self.connection.configure_source(
            function=self._function_combobox.currentText(),
            range=self._range_spinbox.value(),
            nsamples=10,
            auto_zero=True,
            trigger='bus',
            delay=0.0,
            mode='fixed',
            cmpl=0.01,
            cmpl_range=0.21
        )
