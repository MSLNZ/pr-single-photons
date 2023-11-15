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
from ..dmm import Auto
from ..dmm import DMM
from ..dmm import Edge
from ..dmm import Function
from ..dmm import Mode
from ..dmm import Settings
from ...plotting import RealTimePlot
from ...samples import Samples


class FetchWorker(Worker):

    def __init__(self, connection: DMM, trigger_mode: Mode) -> None:
        """Fetch samples from the DMM in a worker thread."""
        super().__init__()
        self.connection = connection
        self.send_trigger = trigger_mode == Mode.BUS

    def process(self):
        """Fetch the samples from the DMM."""
        self.connection.initiate()
        if self.send_trigger:
            self.connection.trigger()
        self.connection.fetch()


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
        self.unit_map: dict[str, str] = {'DCI': 'A', 'DCV': 'V'}
        self.samples: Samples = Samples()
        self.settings: Settings = self.get_settings()

        self.value_lineedit = LineEdit(
            align=Qt.AlignRight,
            rescale=True,
            read_only=True,
        )

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

        self.digits_spinbox = SpinBox(
            minimum=1,
            maximum=9,
            value=2,
            tooltip='The number of digits in the uncertainty to retain',
            value_changed=self.on_digits_spinbox_changed,
        )

        self.live_checkbox = CheckBox(
            initial=True,
            state_changed=self.on_live_checkbox_changed,
            tooltip='Live update?',
        )

        box = QtWidgets.QHBoxLayout()
        box.addWidget(self.config_button)
        box.addWidget(self.plot_button)
        box.addSpacerItem(QtWidgets.QSpacerItem(
            1, 1, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum))
        box.addWidget(self.digits_spinbox)
        box.addWidget(self.live_checkbox)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(box)
        layout.addWidget(self.value_lineedit)
        self.setLayout(layout)

        if not self.connected_as_link:
            connection.fetched.connect(self.on_fetched)
            connection.settings_changed.connect(self.on_settings_changed)

        # important to call the configure() method in case it has not been called yet
        connection.configure(
            function=self.settings.function,
            range='AUTO' if self.settings.auto_range else self.settings.range,
            nsamples=self.settings.nsamples,
            nplc=self.settings.nplc,
            auto_zero=self.settings.auto_zero,
            trigger=self.settings.trigger.mode,
            edge=self.settings.trigger.edge,
            ntriggers=self.settings.trigger.count,
            delay=None if self.settings.trigger.auto_delay else self.settings.trigger.delay,
        )

        self.thread = Thread(FetchWorker)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_timer_timeout)  # noqa: QTimer.timeout exists
        self.timer.start()

    def get_settings(self) -> Settings:
        """Get the configuration settings of the DMM."""
        settings = self.connection.settings()
        if self.connected_as_link:
            return Settings(**settings)
        return settings

    @Slot(int)
    def on_digits_spinbox_changed(self, _: int) -> None:
        """Change the number of digits in the uncertainty to retain."""
        self.on_fetched(self.samples)

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
        self.samples = samples
        d = self.digits_spinbox.value()
        unit = self.unit_map[self.settings.function]
        self.value_lineedit.setText(f'{samples:.{d}S} {unit}')

    @Slot(bool)
    def on_live_checkbox_changed(self, checked: bool) -> None:
        """Start or stop the QTimer."""
        if checked:
            self.timer.start()
        else:
            self.timer.stop()

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
    def on_settings_changed(self, settings: Settings) -> None:
        """Slot for the connection.config_changed signal."""
        self.settings = settings
        self.update_tooltip()

    @Slot()
    def on_timer_timeout(self) -> None:
        """Start the worker thread."""
        if not self.thread.is_running():
            self.thread.start(self.connection, self.settings.trigger.mode)

    def notification_handler(self, *args, **kwargs) -> None:
        """Handle a notification emitted by the DMM Service."""
        if len(args) == 3:
            mean, stdev, size = args
            s = Samples(mean=mean, stdev=stdev, size=size)
            self.on_fetched(s)
            if self._plot is not None:
                self._plot.update(s)
        elif len(args) == 1:
            self.settings = Settings(**args[0])
            self.update_tooltip()
        else:
            self.logger.warning(f'Unhandled notification_handler parameters {args=} {kwargs=}')

    def restart_timer_and_thread(self) -> None:
        """Restart the Thread and the QTimer."""
        self.live_checkbox.setChecked(True)
        self.on_timer_timeout()
        self.timer.start()
        self.logger.debug(f'restarted the QTimer and QThread for {self.record.alias!r}')

    def stop_timer_and_thread(self) -> None:
        """Stop the QTimer and the QThread."""
        self.live_checkbox.setChecked(False)
        self.timer.stop()
        self.thread.stop()
        self.logger.debug(f'stopped the QTimer and QThread for {self.record.alias!r}')

    def update_tooltip(self) -> None:
        """Update the tooltip of the 'value' LineEdit."""
        s = self.settings
        unit = self.unit_map[s.function]
        delay = 'AUTO' if s.trigger.auto_delay else s.trigger.delay
        if s.auto_range == Auto.ON:
            range_ = 'AUTO'
        else:
            scaled, prefix = number_to_si(s.range)
            range_ = f'{scaled:.0f} {prefix}{unit}'

        tooltip = f'<html><b>{s.function}:</b><br>' \
                  f'&nbsp;&nbsp;Range: {range_}<br>' \
                  f'&nbsp;&nbsp;NPLC: {s.nplc}<br>' \
                  f'&nbsp;&nbsp;# Samples: {s.nsamples}<br>' \
                  f'&nbsp;&nbsp;Auto Zero: {s.auto_zero}<br><br>' \
                  f'<b>Trigger:</b><br>' \
                  f'&nbsp;&nbsp;Mode: {s.trigger.mode}<br>' \
                  f'&nbsp;&nbsp;Edge: {s.trigger.edge}<br>' \
                  f'&nbsp;&nbsp;# Triggers: {s.trigger.count}<br>' \
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
        self.settings: Settings = parent.settings
        self.connection: DMM = parent.connection

        function_group = QtWidgets.QGroupBox('Function Settings')

        self.function_combobox = ComboBox(
            items=sorted(Function),
            initial=self.settings.function,
            tooltip='The function to measure',
        )

        self.range_line_edit = LineEdit(
            text='AUTO' if self.settings.auto_range == Auto.ON else str(self.settings.range),
            tooltip='The function range as a float or AUTO, MAX, MIN, DEF',
        )

        self.nplc_spinbox = DoubleSpinBox(
            minimum=0.001,
            maximum=100,
            value=self.settings.nplc,
            decimals=3,
            tooltip='The number of power-line cycles to integrate over',
        )

        self.nsamples_spinbox = SpinBox(
            minimum=1,
            maximum=int(1e6),
            value=self.settings.nsamples,
            tooltip='The number of samples to acquire for each trigger event'
        )

        self.auto_zero_combobox = ComboBox(
            items=sorted(Auto),
            initial=self.settings.auto_zero,
            tooltip='The auto-zero mode',
        )

        form = QtWidgets.QFormLayout()
        form.addRow('Function:', self.function_combobox)
        form.addRow('Range:', self.range_line_edit)
        form.addRow('NPLC:', self.nplc_spinbox)
        form.addRow('# Samples:', self.nsamples_spinbox)
        form.addRow('Auto Zero:', self.auto_zero_combobox)
        function_group.setLayout(form)

        trigger_group = QtWidgets.QGroupBox('Trigger Settings')

        self.mode_combobox = ComboBox(
            items=sorted(Mode),
            initial=self.settings.trigger.mode,
            tooltip='The trigger mode'
        )

        self.edge_combobox = ComboBox(
            items=sorted(Edge),
            initial=self.settings.trigger.edge,
            tooltip='The edge to trigger on',
        )

        self.count_spinbox = SpinBox(
            minimum=1,
            maximum=int(1e9),
            value=self.settings.trigger.count,
            tooltip='The number of triggers that are accepted by the instrument '
                    'before returning to the "idle" trigger state'
        )

        self.auto_delay_checkbox = CheckBox(
            initial=self.settings.trigger.auto_delay,
            state_changed=self.auto_delay_changed,
            tooltip='Enable the auto-delay feature',
        )

        self.delay_spinbox = DoubleSpinBox(
            minimum=0,
            maximum=3600,
            value=self.settings.trigger.delay,
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
        self.original_range = self.range_line_edit.text()
        self.original_nsamples = self.nsamples_spinbox.value()
        self.original_nplc = self.nplc_spinbox.value()
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
        self.function_combobox.setCurrentText(self.settings.function)
        self.range_line_edit.setText('AUTO' if self.settings.auto_range == Auto.ON else str(self.settings.range))
        self.nplc_spinbox.setValue(self.settings.nplc)
        self.nsamples_spinbox.setValue(self.settings.nsamples)
        self.auto_zero_combobox.setCurrentText(self.settings.auto_zero)
        self.mode_combobox.setCurrentText(self.settings.trigger.mode)
        self.edge_combobox.setCurrentText(self.settings.trigger.edge)
        self.count_spinbox.setValue(self.settings.trigger.count)
        self.auto_delay_checkbox.setChecked(self.settings.trigger.auto_delay)

    def save_settings(self) -> None:
        """Save the settings to the digital multimeter."""
        try:
            rng = float(self.range_line_edit.text())
        except ValueError:
            rng = self.range_line_edit.text()
        self.connection.configure(
            function=self.function_combobox.currentText(),
            range=rng,
            nsamples=self.nsamples_spinbox.value(),
            nplc=float(self.nplc_spinbox.value()),
            auto_zero=self.auto_zero_combobox.currentText(),
            trigger=self.mode_combobox.currentText(),
            edge=self.edge_combobox.currentText(),
            ntriggers=self.count_spinbox.value(),
            delay=None if self.auto_delay_checkbox.isChecked() else self.delay_spinbox.value()
        )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.closeEvent` and maybe prompt to save."""
        if self.check_if_modified and (
                self.original_function != self.function_combobox.currentText() or
                self.original_range != self.range_line_edit.text() or
                self.original_nsamples != self.nsamples_spinbox.value() or
                self.original_nplc != self.nplc_spinbox.value() or
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
