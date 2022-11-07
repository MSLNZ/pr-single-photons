"""
Widget for a HRS500M Monochromator from Princeton Instruments.
"""
from msl.qt import Button
from msl.qt import ComboBox
from msl.qt import DoubleSpinBox
from msl.qt import LED
from msl.qt import MICRO
from msl.qt import Qt
from msl.qt import QtWidgets
from msl.qt import Slot
from msl.qt import SpinBox
from msl.qt import Thread
from msl.qt import Worker
from msl.qt import prompt

from ..base import BaseEquipmentWidget
from ..base import widget
from ..hrs_monochromator import HRSMonochromator


class HRSMonochromatorWorker(Worker):

    def __init__(self, method, *args) -> None:
        """Execute the call to the Princeton Instruments DLL in a worker thread."""
        super().__init__()
        self.method = method
        self.args = args

    def process(self) -> None:
        self.method(*self.args)


@widget(manufacturer=r'Princeton Instruments', model=r'HRS500M')
class HRSMonochromatorWidget(BaseEquipmentWidget):

    def __init__(self,
                 connection: HRSMonochromator,
                 *,
                 parent: QtWidgets.QWidget = None) -> None:
        """Widget for a HRS500M Monochromator from Princeton Instruments.

        Args:
            connection: The connection to the monochromator.
            parent: The parent widget.
        """
        super().__init__(connection, parent=parent)

        self._prompt_showing = False

        self._grating_index: int = connection.get_grating_position() - 1
        self._grating_combobox = ComboBox(
            items=[f"Blaze: {v['blaze']}, Density: {v['density']}"
                   for v in connection.grating_info().values()],
            initial=self._grating_index,
            tooltip='The grating that is selected',
            index_changed=self.on_grating_index_changed
        )

        self._filter_index: int = connection.get_filter_position() - 1
        self._filter_combobox = ComboBox(
            items=list(connection.filter_info().values()),
            initial=self._filter_index,
            tooltip='The filter that is selected',
            index_changed=self.on_filter_index_changed,
        )

        self._home_filter_wheel = Button(
            icon='ieframe|0',
            left_click=self.on_home_filter_wheel,
            tooltip='Home the filter wheel',
        )

        self._wavelength_label = QtWidgets.QLabel()
        self._wavelength_label.setToolTip('The wavelength according to the encoder')

        self._wavelength: float = connection.get_wavelength()
        self._wavelength_spinbox = DoubleSpinBox(
            minimum=0,
            maximum=2800,
            decimals=3,
            unit=' nm',
            tooltip='The requested wavelength',
            editing_finished=self.on_wavelength_editing_finished,
        )
        # set the wavelength-spinbox value and the wavelength-label text
        self.on_wavelength_changed(self._wavelength, self._wavelength)

        self._front_entrance_slit_width: int = connection.get_front_entrance_slit_width()
        self._front_entrance_slit_spinbox = SpinBox(
            minimum=10,
            maximum=3000,
            value=self._front_entrance_slit_width,
            unit=f' {MICRO}m',
            tooltip='The width of the front entrance slit',
            editing_finished=self.on_front_entrance_slit_editing_finished,
        )

        self._front_exit_slit_width: int = connection.get_front_exit_slit_width()
        self._front_exit_slit_spinbox = SpinBox(
            minimum=10,
            maximum=3000,
            value=self._front_exit_slit_width,
            unit=f' {MICRO}m',
            tooltip='The width of the front exit slit',
            editing_finished=self.on_front_exit_slit_editing_finished,
        )

        self._home_front_entrance_slit_button = Button(
            icon='ieframe|0',
            left_click=self.on_home_front_entrance_slit,
            tooltip='Home the front entrance slit'
        )

        self._home_front_exit_slit_button = Button(
            icon='ieframe|0',
            left_click=self.on_home_front_exit_slit,
            tooltip='Home the front exit slit',
        )

        self._status_indicator = LED(
            on_color='green',
            clickable=False,
            tooltip='Monochromator busy?'
        )

        if not self.connected_as_link:
            connection.grating_position_changed.connect(self.on_grating_position_changed)
            connection.filter_position_changed.connect(self.on_filter_position_changed)
            connection.wavelength_changed.connect(self.on_wavelength_changed)
            connection.front_entrance_slit_changed.connect(self.on_front_entrance_slit_changed)
            connection.front_exit_slit_changed.connect(self.on_front_exit_slit_changed)

        self.thread = Thread(HRSMonochromatorWorker)
        self.thread.finished.connect(self.on_thread_finished)

        layout = QtWidgets.QFormLayout()
        box1 = QtWidgets.QHBoxLayout()
        box1.addWidget(self._wavelength_spinbox)
        box1.addWidget(self._wavelength_label)
        box1.addWidget(self._status_indicator, stretch=1, alignment=Qt.AlignRight)
        layout.addRow('Wavelength:', box1)
        layout.addRow('Grating:', self._grating_combobox)
        box2 = QtWidgets.QHBoxLayout()
        box2.addWidget(self._filter_combobox)
        box2.addWidget(self._home_filter_wheel)
        layout.addRow('Filter Wheel:', box2)
        box3 = QtWidgets.QHBoxLayout()
        box3.addWidget(self._front_entrance_slit_spinbox)
        box3.addWidget(self._home_front_entrance_slit_button)
        layout.addRow('Entrance slit:', box3)
        box4 = QtWidgets.QHBoxLayout()
        box4.addWidget(self._front_exit_slit_spinbox)
        box4.addWidget(self._home_front_exit_slit_button)
        layout.addRow('Exit slit:', box4)
        self.setLayout(layout)

    @Slot(int)
    def on_grating_index_changed(self, index: int) -> None:
        """Slot for the Grating QComboBox.currentIndexChanged signal.

        Args:
            index: The grating index [0, 1, 2].
        """
        if self.prepare_thread():
            self.thread.start(self.connection.set_grating_position, index + 1)
        else:  # undo the currentIndexChanged signal
            self.on_grating_position_changed(self._grating_index + 1)

    @Slot(int)
    def on_grating_position_changed(self, position: int) -> None:
        """Slot for the HRSMonochromator.grating_position_changed signal.

        Updates the Grating QComboBox without emitting the currentIndexChanged signal.

        Args:
            position: The grating position [1, 2, 3].
        """
        self._grating_index = position - 1
        previous = self._grating_combobox.blockSignals(True)
        self._grating_combobox.setCurrentIndex(self._grating_index)
        self._grating_combobox.blockSignals(previous)

    @Slot(int)
    def on_filter_index_changed(self, index: int) -> None:
        """Slot for the Filter QComboBox.currentIndexChanged signal.

        Args:
            index: The filter index [0, 1, 2, 3, 4, 5].
        """
        if self.prepare_thread():
            self.thread.start(self.connection.set_filter_position, index + 1)
        else:  # undo the currentIndexChanged signal
            self.on_filter_position_changed(self._filter_index + 1)

    @Slot(int)
    def on_filter_position_changed(self, position: int) -> None:
        """Slot for the HRSMonochromator.filter_position_changed signal.

        Updates the Filter QComboBox without emitting the currentIndexChanged signal.

        Args:
            position: The filter position [1, 2, 3, 4, 5, 6].
        """
        self._filter_index = position - 1
        previous = self._filter_combobox.blockSignals(True)
        self._filter_combobox.setCurrentIndex(self._filter_index)
        self._filter_combobox.blockSignals(previous)

    @Slot()
    def on_wavelength_editing_finished(self) -> None:
        """Slot for the Wavelength QDoubleSpinBox.editingFinished signal."""
        value = self._wavelength_spinbox.value()
        if value == self._wavelength:
            # the monochromator is already at that wavelength
            return

        if self.prepare_thread():
            self.thread.start(self.connection.set_wavelength, value)
        else:  # undo the editingFinished signal
            self._wavelength_spinbox.setValue(self._wavelength)

    @Slot(float, float)
    def on_wavelength_changed(self, requested: float, encoder: float) -> None:
        """Slot for the HRSMonochromator.wavelength_changed signal.

        Args:
            requested: The requested wavelength.
            encoder: The wavelength that the encoder indicates that it is at.
        """
        # don't need to blockSignals since the QDoubleSpinBox.valueChanged
        # signal is not connected to any slots
        self._wavelength_spinbox.setValue(requested)
        self._wavelength_label.setText(f'{encoder} nm')
        self._wavelength = requested

    @Slot()
    def on_front_entrance_slit_editing_finished(self) -> None:
        """Slot for the front entrance slit QSpinBox.editingFinished signal."""
        width = self._front_entrance_slit_spinbox.value()
        if width == self._front_entrance_slit_width:
            # the front entrance slit is already at that width
            return

        if self.prepare_thread():
            self.thread.start(self.connection.set_front_entrance_slit_width, width)
        else:  # undo the editingFinished signal
            self._front_entrance_slit_spinbox.setValue(self._front_entrance_slit_width)

    @Slot(int)
    def on_front_entrance_slit_changed(self, width: int) -> None:
        """Slot for the HRSMonochromator.front_entrance_slit_changed signal.

        Args:
            width: The front entrance slit width, in um.
        """
        # don't need to blockSignals since the QSpinBox.valueChanged
        # signal is not connected to any slots
        self._front_entrance_slit_spinbox.setValue(width)
        self._front_entrance_slit_width = width

    @Slot()
    def on_front_exit_slit_editing_finished(self) -> None:
        """Slot for the front exit slit QSpinBox.editingFinished signal."""
        width = self._front_exit_slit_spinbox.value()
        if width == self._front_exit_slit_width:
            # the front exit slit is already at that width
            return

        if self.prepare_thread():
            self.thread.start(self.connection.set_front_exit_slit_width, width)
        else:  # undo the editingFinished signal
            self._front_exit_slit_spinbox.setValue(self._front_exit_slit_width)

    @Slot(int)
    def on_front_exit_slit_changed(self, width: int) -> None:
        """Slot for the HRSMonochromator.front_exit_slit_changed signal.

        Args:
            width: The front exit slit width, in um.
        """
        # don't need to blockSignals since the QSpinBox.valueChanged
        # signal is not connected to any slots
        self._front_exit_slit_spinbox.setValue(width)
        self._front_exit_slit_width = width

    @Slot()
    def on_home_front_entrance_slit(self) -> None:
        """Home the front entrance slit."""
        if self.prepare_thread():
            self.thread.start(self.connection.home_front_entrance_slit)

    @Slot()
    def on_home_front_exit_slit(self) -> None:
        """Home the front exit slit."""
        if self.prepare_thread():
            self.thread.start(self.connection.home_front_exit_slit)

    @Slot()
    def on_home_filter_wheel(self) -> None:
        """Home the filter wheel."""
        if self.prepare_thread():
            self.thread.start(self.connection.home_filter_wheel)

    @Slot()
    def on_thread_finished(self) -> None:
        """Called when the worker thread is finished."""
        self._status_indicator.turn_off()

    def notification_handler(self, *args, **kwargs) -> None:
        """Handle notifications emitted by the HRSMonochromator Service."""
        if 'filter_wheel_position' in kwargs:
            self.on_filter_position_changed(kwargs['filter_wheel_position'])
        elif 'grating_position' in kwargs:
            self.on_grating_position_changed(kwargs['grating_position'])
        elif 'front_entrance_slit_width' in kwargs:
            self.on_front_entrance_slit_changed(kwargs['front_entrance_slit_width'])
        elif 'front_exit_slit_width' in kwargs:
            self.on_front_exit_slit_changed(kwargs['front_exit_slit_width'])
        elif 'wavelength' in kwargs:
            requested = kwargs['wavelength']['requested']
            encoder = kwargs['wavelength']['encoder']
            self.on_wavelength_changed(requested, encoder)
        else:
            self.logger.error(
                f'{self.__class__.__name__!r} has not been configured '
                f'to handle args={args} kwargs={kwargs}'
            )

    def prepare_thread(self) -> bool:
        """Prepare to start a new worker thread.

        Returns:
            Whether a new thread can be started.
        """
        if self.thread.is_running():
            if not self._prompt_showing:
                self._prompt_showing = True
                prompt.warning('Monochromator is busy. Wait. Try again.')
                self._prompt_showing = False
            return False
        self._status_indicator.turn_on()
        return True
