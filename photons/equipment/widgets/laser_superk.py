"""
Widget for a SuperK Fianium laser from NKT Photonics.
"""
import queue

from msl.equipment.exceptions import NKTError
from msl.qt import ComboBox
from msl.qt import DoubleSpinBox
from msl.qt import QtCore
from msl.qt import QtGui
from msl.qt import QtWidgets
from msl.qt import Signal
from msl.qt import Slot
from msl.qt import Thread
from msl.qt import ToggleSwitch
from msl.qt import Worker

from ..base import BaseEquipmentWidget
from ..base import widget
from ..laser_superk import SuperK


class Watchdog(Worker):

    emission_changed: QtCore.SignalInstance = Signal(bool)
    level_changed: QtCore.SignalInstance = Signal(float)
    mode_changed: QtCore.SignalInstance = Signal(int)

    def __init__(self, connection: SuperK, qu: queue.Queue) -> None:
        """Handle NKTDLL callbacks."""
        super().__init__()
        self.connection = connection
        self.queue = qu

    def process(self) -> None:
        from time import sleep
        while True:
            status = self.queue.get()
            if not status:
                break
            try:
                match status['data']:
                    case 40000 | 10000:  # emission changed
                        sleep(0.5)
                        state = self.connection.is_emission_on()
                        self.emission_changed.emit(state)
                    case 2000:  # mode changed
                        sleep(0.5)
                        mode = self.connection.get_operating_mode()
                        self.mode_changed.emit(mode)
                        state = self.connection.is_emission_on()
                        self.emission_changed.emit(state)
                    case 200 | 100000:  # level changed
                        sleep(0.5)
                        level = self.connection.get_current_level()
                        self.level_changed.emit(level)
            except NKTError as e:
                self.connection.logger.warning(e)


@widget(manufacturer=r'^NKT')
class SuperKWidget(BaseEquipmentWidget):

    connection: SuperK

    def __init__(self,
                 connection: SuperK,
                 *,
                 parent: QtWidgets.QWidget = None) -> None:
        """Widget for a SuperK Fianium laser from NKT Photonics.

        Args:
            connection: The connection to the laser.
            parent: The parent widget.
        """
        super().__init__(connection, parent=parent)

        # the NKT callbacks are not that reliable
        # that is why the front panel gets locked (if the laser supports it)
        self.queue = queue.Queue()
        self.watchdog = Thread(Watchdog)
        self.watchdog.worker_connect(Watchdog.level_changed, self.on_level_changed)
        self.watchdog.worker_connect(Watchdog.emission_changed, self.on_emission_changed)
        self.watchdog.worker_connect(Watchdog.mode_changed, self.update_mode)
        self.watchdog.start(connection, self.queue)

        self._operating_modes = connection.get_operating_modes()

        self.mode_combobox = ComboBox(
            items=self._operating_modes,
            tooltip='The operating mode',
            text_changed=self.on_mode_changed,
        )
        self.update_mode(connection.get_operating_mode())

        self._level = self.connection.get_current_level()
        self.level_spinbox = DoubleSpinBox(
            value=self._level,
            minimum=0,
            maximum=100,
            decimals=1,
            unit=' %',
            tooltip='The level of the operating mode',
            editing_finished=self.on_level_editing_finished,
        )

        self.emission_switch = ToggleSwitch(
            initial=connection.is_emission_on(),
            toggled=self.connection.emission,
            tooltip='Turn the laser emission on or off',
        )

        # link the DLL callback(s) and the Qt Signal to the Slots
        if not self.connected_as_link:
            connection.signaler.device_status_changed.connect(self.on_device_status_changed)
            connection.level_changed.connect(self.on_level_changed)
            connection.emission_changed.connect(self.on_emission_changed)

        # create the layout
        box = QtWidgets.QHBoxLayout()
        box.addWidget(self.mode_combobox)
        box.addWidget(self.level_spinbox)
        layout = QtWidgets.QFormLayout()
        layout.addRow('Mode:', box)
        layout.addRow('Emission:', self.emission_switch)
        self.setLayout(layout)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Stop the Watchdog thread and close the Widget."""
        self.queue.put_nowait(None)
        self.watchdog.stop()
        super().closeEvent(event)

    def notification_handler(self, *args, **kwargs) -> None:
        """Handle notifications emitted by the SuperK Service."""
        if 'level' in kwargs:
            self.on_level_changed(kwargs['level'])
        elif 'mode' in kwargs:
            self.update_mode(kwargs['mode'])
        elif 'emission' in kwargs:
            self.on_emission_changed(kwargs['emission'])
        else:
            self.logger.error(
                f'{self.__class__.__name__!r} has not been configured '
                f'to handle args={args} kwargs={kwargs}'
            )

    @Slot(str)
    def on_mode_changed(self, text: str) -> None:
        """Change the operating mode."""
        mode = self._operating_modes[text]
        self.connection.set_operating_mode(mode)

    @Slot()
    def on_level_editing_finished(self) -> None:
        """Set the level when the DoubleSpinBox loses focus."""
        level = self.level_spinbox.value()
        if level == self._level:
            return
        self.connection.set_current_level(level)

    @Slot(float)
    def on_level_changed(self, level: float) -> None:
        """Update the value of the DoubleSpinBox without emitting the signal."""
        previous = self.level_spinbox.blockSignals(True)
        self.level_spinbox.setValue(level)
        self.level_spinbox.blockSignals(previous)
        self._level = level

    @Slot(dict)
    def on_device_status_changed(self, status: dict) -> None:
        """Called by the DeviceStatusCallback from the DLL."""
        self.queue.put_nowait(status)

    @Slot(bool)
    def on_emission_changed(self, state: bool) -> None:
        """Update the ToggleSwitch without emitting the signal."""
        previous = self.emission_switch.blockSignals(True)
        self.emission_switch.setChecked(state)
        self.emission_switch.blockSignals(previous)

    def update_mode(self, mode: int) -> None:
        """Update the ComboBox without emitting the signal."""
        for name, value in self._operating_modes.items():
            if value == mode:
                previous = self.mode_combobox.blockSignals(True)
                self.mode_combobox.setCurrentText(name)
                self.mode_combobox.blockSignals(previous)
                break
