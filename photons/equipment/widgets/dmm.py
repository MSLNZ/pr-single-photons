"""
Widget for a digital multimeter.
"""
from msl.qt import Button
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
from msl.qt import prompt
from msl.qt.convert import number_to_si

from ..base import BaseEquipmentWidget
from ..base import widget
from ..dmm import DMM
from ...plotting import RealTimePlot
from ...samples import Samples


class FetchWorker(Worker):

    def __init__(self, connection: DMM, trigger_mode: str) -> None:
        """Fetch samples from the DMM in a worker thread."""
        super().__init__()
        self.connection = connection
        self.send_trigger = trigger_mode == 'BUS' or \
            (trigger_mode == 'AUTO' and connection.record_to_json()['model'] == '3458A')

    def process(self):
        """Fetch the samples from the DMM."""
        if self.send_trigger:
            self.connection.bus_trigger()
        self.connection.fetch(initiate=not self.send_trigger)


@widget(model=r'344?(01|58|60|61|65|70)A')
class DMMWidget(BaseEquipmentWidget):

    def __init__(self,
                 connection: DMM,
                 *,
                 parent: QtWidgets.QWidget = None) -> None:
        """Widget for a digital multimeter.

        Args:
            connection: The connection to the digital multimeter.
            parent: The parent widget.
        """
        super().__init__(connection, parent=parent)

        self.settings: dict[str, ...] = {}  # gets updated in update_tooltip()
        self.unit_map: dict[str, str] = {
            'CURRENT': 'A',
            'VOLTAGE': 'V',
            'DCI': 'A',
            'DCV': 'V'
        }

        self.value_lineedit = LineEdit(
            align=Qt.AlignRight,
            rescale=True,
            read_only=True,
        )
        self.update_tooltip()

        self.config_button = Button(
            icon='shell32|316',
            left_click=self.on_edit_configuration,
            tooltip='Edit the configuration'
        )

        self._plot = None
        self.plot_button = Button(
            icon='imageres|144',
            left_click=self.on_show_plot,
            tooltip='Plot the data. Re-clicking clears the plot.'
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
            state_changed=self.on_live_checkbox_changed,
            tooltip='Enable live update?',
        )

        box = QtWidgets.QHBoxLayout()
        box.addWidget(self.config_button)
        box.addWidget(self.plot_button)
        box.addSpacerItem(QtWidgets.QSpacerItem(
            1, 1, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum))
        box.addWidget(self.live_spinbox)
        box.addWidget(self.live_checkbox)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(box)
        layout.addWidget(self.value_lineedit)
        self.setLayout(layout)

        if not self.connected_as_link:
            connection.fetched.connect(self.on_fetched)
            connection.settings_changed.connect(self.on_settings_changed)

        self.thread = Thread(FetchWorker)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_timer_timeout)  # noqa: QTimer.timeout exists
        self.timer.start(self.live_spinbox.value())

    @Slot()
    def on_edit_configuration(self) -> None:
        """Show the QDialog to edit the configuration settings of the DMM."""
        was_checked = self.live_checkbox.isChecked()
        if was_checked:
            self.stop_timer_and_thread()
        c = ConfigureDialog(self)
        c.exec()
        if was_checked:
            self.restart_timer_and_thread()

    @Slot(Samples)
    def on_fetched(self, samples: Samples) -> None:
        """Samples were fetched."""
        unit = self.unit_map[self.settings['function']]
        self.value_lineedit.setText(f'{samples:.4S} {unit}')

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
    def on_show_plot(self) -> None:
        """Show the RealTimePlot widget."""
        if self._plot is not None:
            self._plot.close()

        if self.connected_as_link:
            signaler = None
        else:
            signaler = self.connection.fetched

        self._plot = RealTimePlot(signaler=signaler, title=self.record.alias)
        self._plot.show()
        self._plot.closing.connect(self._plot_closing)

    def _plot_closing(self) -> None:
        """The plot widget is closing."""
        self._plot = None

    @Slot(dict)
    def on_settings_changed(self, settings: dict) -> None:
        """Slot for the connection.config_changed signal."""
        self.update_tooltip(settings=settings)

    @Slot()
    def on_timer_timeout(self) -> None:
        """Start the worker thread."""
        if not self.thread.is_running():
            self.thread.start(self.connection, self.settings['trigger_mode'])

    def notification_handler(self, *args, **kwargs) -> None:
        """Handle a notification emitted by the DMM Service."""
        if args:
            mean, stdev, size = args
            s = Samples(mean=mean, stdev=stdev, size=size)
            self.on_fetched(s)
            if self._plot is not None:
                self._plot.update(s)
        else:
            self.update_tooltip(kwargs)

    def restart_timer_and_thread(self) -> None:
        """Restart the Thread and the QTimer."""
        self.live_checkbox.setChecked(True)
        self.on_timer_timeout()
        self.timer.start(self.live_spinbox.value())
        self.logger.debug(f'restarted the QTimer and QThread for {self.record.alias!r}')

    def stop_timer_and_thread(self) -> None:
        """Stop the QTimer and the QThread."""
        self.live_checkbox.setChecked(False)
        self.timer.stop()
        self.thread.stop()
        self.logger.debug(f'stopped the QTimer and QThread for {self.record.alias!r}')

    def update_tooltip(self, settings: dict[str, ...] = None) -> None:
        """Update the tooltip of the 'value' LineEdit."""
        if settings is None:
            settings = self.connection.settings()
        self.settings = settings

        unit = self.unit_map[settings['function']]
        function = 'Voltage' if unit == 'V' else 'Current'
        delay = 'AUTO' if settings['trigger_delay_auto'] else settings['trigger_delay']
        if settings['auto_range'] == 'ON':
            range_ = 'AUTO'
        else:
            scaled, prefix = number_to_si(settings['range'])
            range_ = f'{scaled:.0f} {prefix}{unit}'

        tooltip = f'<html><b>{function}:</b><br>' \
                  f'&nbsp;&nbsp;Range: {range_}<br>' \
                  f'&nbsp;&nbsp;NPLC: {settings["nplc"]}<br>' \
                  f'&nbsp;&nbsp;# Samples: {settings["nsamples"]}<br>' \
                  f'&nbsp;&nbsp;Auto Zero: {settings["auto_zero"]}<br><br>' \
                  f'<b>Trigger:</b><br>' \
                  f'&nbsp;&nbsp;Mode: {settings["trigger_mode"]}<br>' \
                  f'&nbsp;&nbsp;Edge: {settings["trigger_edge"]}<br>' \
                  f'&nbsp;&nbsp;# Triggers: {settings["trigger_count"]}<br>' \
                  f'&nbsp;&nbsp;Delay: {delay}</html>'
        self.value_lineedit.setToolTip(tooltip)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Override :meth:`QtWidgets.QWidget.closeEvent` to stop the QTimer and QThread."""
        self.stop_timer_and_thread()
        if self._plot is not None:
            self._plot.close()
        super().closeEvent(event)


class ConfigureDialog(QtWidgets.QDialog):

    def __init__(self, parent: DMMWidget) -> None:
        """Edit the configuration of the DMM."""
        super().__init__(parent, Qt.WindowCloseButtonHint)

        self.parent = parent
        self.check_if_modified = True
        self.settings: dict = parent.settings.copy()
        self.connection: DMM = parent.connection

        if parent.connected_as_link:
            # must send the request to the Service by calling the constants
            self.FUNCTIONS = parent.connection.FUNCTIONS()
            self.NPLCS = dict((float(k), v) for k, v in parent.connection.NPLCS().items())
            self.AUTO_ZEROS = parent.connection.AUTO()
            self.TRIGGERS = parent.connection.TRIGGERS()
            self.EDGES = parent.connection.EDGES()
            self.RANGES = parent.connection.RANGES()
        else:
            self.FUNCTIONS = parent.connection.FUNCTIONS
            self.NPLCS = parent.connection.NPLCS
            self.AUTO_ZEROS = parent.connection.AUTO
            self.TRIGGERS = parent.connection.TRIGGERS
            self.EDGES = parent.connection.EDGES
            self.RANGES = parent.connection.RANGES

        function_group = QtWidgets.QGroupBox('Function Settings')

        self.function_combobox = ComboBox(
            items=sorted(set(v for v in self.FUNCTIONS.values())),
            initial=self.FUNCTIONS[self.settings['function']],
            text_changed=self.on_function_changed,
            tooltip='The function to measure',
        )

        self.range_combobox = ComboBox(
            tooltip='The function range (not all multimeter\'s will support these ranges)',
        )
        self.update_range_combobox()

        self.nplc_combobox = ComboBox(
            items=[str(v) for v in self.NPLCS.values()],
            initial=str(self.NPLCS[self.settings['nplc']]),
            tooltip='The number of power-line cycles to integrate over',
        )

        self.nsamples_spinbox = SpinBox(
            minimum=1,
            maximum=int(1e6),
            value=self.settings['nsamples'],
            tooltip='The number of samples to acquire for each trigger event'
        )

        self.auto_zero_combobox = ComboBox(
            items=sorted(set(self.AUTO_ZEROS.values())),
            initial=self.settings['auto_zero'],
            tooltip='The auto-zero mode',
        )

        form = QtWidgets.QFormLayout()
        form.addRow('Function:', self.function_combobox)
        form.addRow('Range:', self.range_combobox)
        form.addRow('NPLC:', self.nplc_combobox)
        form.addRow('# Samples:', self.nsamples_spinbox)
        form.addRow('Auto Zero:', self.auto_zero_combobox)
        function_group.setLayout(form)

        trigger_group = QtWidgets.QGroupBox('Trigger Settings')

        self.mode_combobox = ComboBox(
            items=sorted(set(v for v in self.TRIGGERS.values())),
            initial=self.TRIGGERS[self.settings['trigger_mode']],
            tooltip='The trigger mode'
        )

        self.edge_combobox = ComboBox(
            items=sorted(set(k for k in self.EDGES)),
            initial=self.EDGES[self.settings['trigger_edge']],
            tooltip='The edge to trigger on',
        )

        self.count_spinbox = SpinBox(
            minimum=1,
            maximum=int(1e9),
            value=self.settings['trigger_count'],
            tooltip='The number of triggers that are accepted by the instrument '
                    'before returning to the "idle" trigger state'
        )

        self.auto_delay_checkbox = CheckBox(
            initial=self.settings['trigger_delay_auto'],
            state_changed=self.auto_delay_changed,
            tooltip='Enable the auto-delay feature',
        )

        self.delay_spinbox = DoubleSpinBox(
            minimum=0,
            maximum=3600,
            value=self.settings['trigger_delay'],
            decimals=6,
            tooltip='The delay, in seconds, between the trigger signal '
                    'and the first measurement'
        )
        self.delay_spinbox.setEnabled(not self.auto_delay_checkbox.isChecked())

        form = QtWidgets.QFormLayout()
        form.addRow('Mode:', self.mode_combobox)
        form.addRow('Edge:', self.edge_combobox)
        form.addRow('# Triggers:', self.count_spinbox)
        form.addRow('Auto delay:', self.auto_delay_checkbox)
        form.addRow('Delay:', self.delay_spinbox)
        trigger_group.setLayout(form)

        self.reset_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogResetButton,
            left_click=self.on_reset,
            tooltip='Send the Reset [*RST] command'
        )

        self.clear_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogDiscardButton,
            left_click=self.connection.clear,
            tooltip='Send the Clear [*CLS] command'
        )

        self.apply_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton,
            left_click=self.on_apply_clicked,
            tooltip='Apply'
        )

        self.cancel_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton,
            left_click=self.close,
            tooltip='Cancel'
        )

        self.original_function = self.function_combobox.currentText()
        self.original_range = self.range_combobox.currentText()
        self.original_nsamples = self.nsamples_spinbox.value()
        self.original_nplc = self.nplc_combobox.currentText()
        self.original_auto_zero = self.auto_zero_combobox.currentText()
        self.original_mode = self.mode_combobox.currentText()
        self.original_edge = self.edge_combobox.currentText()
        self.original_count = self.count_spinbox.value()
        self.original_auto_delay = self.auto_delay_checkbox.isChecked()
        self.original_delay = self.delay_spinbox.value()

        reset_clear_layout = QtWidgets.QHBoxLayout()
        reset_clear_layout.addWidget(self.clear_button)
        reset_clear_layout.addWidget(self.reset_button)
        reset_clear_layout.addSpacerItem(QtWidgets.QSpacerItem(
            1, 1, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum))

        group_layout = QtWidgets.QHBoxLayout()
        group_layout.addWidget(function_group)
        group_layout.addWidget(trigger_group)

        apply_cancel_layout = QtWidgets.QHBoxLayout()
        apply_cancel_layout.addWidget(self.apply_button)
        apply_cancel_layout.addWidget(self.cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(reset_clear_layout)
        layout.addLayout(group_layout)
        layout.addLayout(apply_cancel_layout)
        self.setLayout(layout)
        self.setWindowTitle(f'Configure {parent.record.alias!r}')

    @Slot(str)
    def on_function_changed(self, function: str) -> None:
        """The Function ComboBox value changed."""
        self.update_range_combobox(function)

    @Slot(bool)
    def auto_delay_changed(self, checked: bool) -> None:
        """The Trigger auto-delay CheckBox was clicked."""
        self.delay_spinbox.setEnabled(not checked)

    @Slot()
    def on_apply_clicked(self) -> None:
        """The Apply button was clicked."""
        self.save_settings()
        self.check_if_modified = False
        self.close()

    @Slot()
    def on_reset(self) -> None:
        """Send the ``*RST`` command to the digital multimeter."""
        self.connection.reset()
        self.settings = self.connection.settings()
        self.function_combobox.setCurrentText(self.FUNCTIONS[self.settings['function']])
        self.update_range_combobox()
        self.nplc_combobox.setCurrentText(str(self.NPLCS[self.settings['nplc']]))
        self.nsamples_spinbox.setValue(self.settings['nsamples'])
        self.auto_zero_combobox.setCurrentText(self.settings['auto_zero'])
        self.mode_combobox.setCurrentText(self.TRIGGERS[self.settings['trigger_mode']])
        self.edge_combobox.setCurrentText(self.EDGES[self.settings['trigger_edge']])
        self.count_spinbox.setValue(self.settings['trigger_count'])
        self.auto_delay_checkbox.setChecked(self.settings['trigger_delay_auto'])

    def save_settings(self) -> None:
        """Save the settings to the digital multimeter."""
        self.connection.configure(
            function=self.function_combobox.currentText(),
            range=self.range_combobox.currentText(),
            nsamples=self.nsamples_spinbox.value(),
            nplc=float(self.nplc_combobox.currentText()),
            auto_zero=self.auto_zero_combobox.currentText(),
            trigger=self.mode_combobox.currentText(),
            edge=self.edge_combobox.currentText(),
            ntriggers=self.count_spinbox.value(),
            delay=None if self.auto_delay_checkbox.isChecked() else self.delay_spinbox.value()
        )

    def update_range_combobox(self, function: str = None) -> None:
        """Update the items in Range QComboBox.

        Args:
            function: The current text in the Function QComboBox.
        """
        if function is None:
            function = self.function_combobox.currentText()
        self.range_combobox.clear()
        str_values = []  # don't want to have AUTO, MAX, MIN, DEF added multiple times
        for k, v in self.RANGES.items():
            if isinstance(v, str) and v not in str_values:
                str_values.append(v)
                self.range_combobox.addItem(v, userData=-1)
            elif isinstance(k, float):
                continue
            elif function in ['CURRENT', 'DCI'] and k.endswith('A') and not k.endswith('uA'):
                self.range_combobox.addItem(k, userData=v)
            elif function in ['VOLTAGE', 'DCV'] and k.endswith('V'):
                self.range_combobox.addItem(k, userData=v)

        if self.settings['auto_range'] == 'ON':
            self.range_combobox.setCurrentText('AUTO')
        else:
            r = self.settings['range']
            for index in range(self.range_combobox.count()):
                if self.range_combobox.itemData(index) >= r:
                    self.range_combobox.setCurrentIndex(index)
                    return
            self.range_combobox.setCurrentText('MAXIMUM')

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.closeEvent` and maybe prompt to save."""
        if self.check_if_modified and (
                self.original_function != self.function_combobox.currentText() or
                self.original_range != self.range_combobox.currentText() or
                self.original_nsamples != self.nsamples_spinbox.value() or
                self.original_nplc != self.nplc_combobox.currentText() or
                self.original_auto_zero != self.auto_zero_combobox.currentText() or
                self.original_mode != self.mode_combobox.currentText() or
                self.original_edge != self.edge_combobox.currentText() or
                self.original_count != self.count_spinbox.value() or
                self.original_auto_delay is not self.auto_delay_checkbox.isChecked() or
                self.original_delay != self.delay_spinbox.value()):
            if prompt.yes_no('You have modified the settings.\n\n'
                             'Apply the changes?', default=False):
                self.save_settings()
        super().closeEvent(event)
