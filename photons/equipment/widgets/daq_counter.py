"""
Widget for a NIDAQ to counts pulse edges.
"""
from msl.qt import CheckBox
from msl.qt import ComboBox
from msl.qt import DoubleSpinBox
from msl.qt import LineEdit
from msl.qt import Qt
from msl.qt import QtCore
from msl.qt import QtGui
from msl.qt import QtWidgets
from msl.qt import Slot
from msl.qt import SpinBox
from msl.qt import Thread
from msl.qt import Worker

from ..base import BaseEquipmentWidget
from ..base import widget
from ..nidaq import NIDAQ
from ...samples import Samples


@widget(model=r'USB-6361')
class DAQCounterWidget(BaseEquipmentWidget):

    def __init__(self,
                 connection: NIDAQ,
                 *,
                 parent: QtWidgets.QWidget = None) -> None:
        """Widget for a NIDAQ to counts pulse edges.

        Args:
            connection: The connection to the NIDAQ.
            parent: The parent widget.
        """
        super().__init__(connection, parent=parent)

        self.counts_lineedit = LineEdit(
            align=Qt.AlignRight,
            read_only=True,
            rescale=True,
            tooltip='The average number of counts per second',
        )

        self.nsamples_spinbox = SpinBox(
            value=20,
            minimum=1,
            tooltip='The number times to repeat edge counting'
        )

        self.duration_spinbox = DoubleSpinBox(
            value=0.1,
            minimum=0.001,
            maximum=9999,
            decimals=3,
            tooltip='The number of seconds to count edges for',
        )

        self.pfi_combobox = ComboBox(
            items=dict((f'PFI{n}', n) for n in range(16)),
            tooltip='The DAQ terminal that the photons counter is connected to',
        )

        self.edge_combobox = ComboBox(
            items=['Rising', 'Falling'],
            tooltip='Count on the rising or on the falling edge',
        )

        self.live_spinbox = SpinBox(
            minimum=0,
            maximum=99999,
            value=0,
            tooltip='The number of milliseconds to wait between live updates',
            value_changed=self.on_live_spinbox_changed,
        )

        self.live_checkbox = CheckBox(
            initial=True,
            tooltip='Enable live update?',
            state_changed=self.on_live_checkbox_changed,
        )

        layout = QtWidgets.QFormLayout()
        layout.addRow('Duration:', self.duration_spinbox)
        layout.addRow('PFI Term:', self.pfi_combobox)
        layout.addRow('Edge:', self.edge_combobox)
        layout.addRow('#Samples:', self.nsamples_spinbox)
        layout.addRow('Counts:', self.counts_lineedit)
        layout.addWidget(self.live_spinbox)
        layout.addWidget(self.live_checkbox)
        self.setLayout(layout)

        if not self.connected_as_link:
            connection.counts_changed.connect(self.on_counts_changed)

        self.thread = CountEdgesThread(self)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_timer_timeout)  # noqa: QTimer.timeout exists
        self.timer.start(self.live_spinbox.value())

    @Slot(Samples)
    def on_counts_changed(self, samples: Samples) -> None:
        """Update the text in the LineEdit."""
        self.counts_lineedit.setText(f'{samples:S}cps')

    @Slot(bool)
    def on_live_checkbox_changed(self, checked: bool) -> None:
        """Start or stop the QTimer."""
        if checked:
            self.timer.start(self.live_spinbox.value())
        else:
            self.timer.stop()

    @Slot(int)
    def on_live_spinbox_changed(self, msec: int) -> None:
        """Change the timeout interval of the QTimer."""
        if self.live_checkbox.isChecked():
            self.timer.stop()
            self.timer.start(msec)

    @Slot()
    def on_timer_timeout(self) -> None:
        """Start the worker thread."""
        if not self.thread.is_running():
            self.thread.start(
                self.connection,
                self.duration_spinbox.value(),
                self.edge_combobox.currentText(),
                self.pfi_combobox.currentData(),
                self.nsamples_spinbox.value(),
            )

    def notification_handler(self, **kwargs) -> None:
        """Handle a notification emitted by the NIDAQ Service."""
        self.on_counts_changed(Samples(**kwargs))

    def stop_timer_and_thread(self) -> None:
        """Stop the QTimer and the QThread."""
        self.live_checkbox.setChecked(False)
        self.timer.stop()
        self.thread.stop()
        self.logger.debug(f'stopped the QTimer and QThread for {self.record.alias!r}')

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Override :meth:`QtWidgets.QWidget.closeEvent` to stop the QTimer and QThread."""
        self.stop_timer_and_thread()
        super().closeEvent(event)


class CountEdgesWorker(Worker):

    def __init__(self,
                 connection: NIDAQ,
                 duration: float,
                 edge: str,
                 pfi: int,
                 nsamples: int) -> None:
        """Count edges in a worker thread."""
        super().__init__()
        self.connection = connection
        self.duration = duration
        self.rising = edge.lower() == 'rising'
        self.pfi = pfi
        self.nsamples = nsamples

    def process(self) -> None:
        self.connection.count_edges(
            self.pfi, self.duration, nsamples=self.nsamples, rising=self.rising)


class CountEdgesThread(Thread):

    def __init__(self, parent: DAQCounterWidget) -> None:
        self.parent = parent
        super().__init__(CountEdgesWorker)

    def error_handler(self, exception, traceback) -> None:
        self.parent.close()
        super().error_handler(exception, traceback)
