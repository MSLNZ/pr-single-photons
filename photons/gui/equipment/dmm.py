"""
Widget for a digital multimeter.
"""
from msl.qt.convert import number_to_si
from msl.qt import (
    QtWidgets,
    QtCore,
    QtGui,
    Qt,
    SpinBox,
    DoubleSpinBox,
    Button,
    Worker,
    Thread,
    prompt,
    application,
)

from . import (
    BaseWidget,
    widget,
)


class FetchWorker(Worker):

    def __init__(self, connection, trigger_mode):
        """Calls :meth:`photons.equipment.dmm.DMM.fetch`"""
        super(FetchWorker, self).__init__()
        self.connection = connection
        self.send_trigger = trigger_mode == 'BUS' or \
            (connection.record_to_json()['model'] == '3458A' and trigger_mode == 'AUTO')

    def process(self):
        if self.send_trigger:
            self.connection.bus_trigger()
        self.connection.fetch(initiate=not self.send_trigger)


@widget(model=r'344*(01|58|60|61|65|70)A')
class DMM(BaseWidget):

    def __init__(self, connection, *, parent=None):
        """Widget for a digital multimeter.

        Parameters
        ----------
        connection
            The connection to the digital multimeter.
        parent : :class:`QtWidgets.QWidget`
            The parent widget.
        """
        super(DMM, self).__init__(connection, parent=parent)

        self.info = {}  # gets updated in update_tooltip()
        self.unit_map = {'CURRENT': 'A', 'VOLTAGE': 'V', 'DCI': 'A', 'DCV': 'V'}

        self.value_lineedit = QtWidgets.QLineEdit()
        self.value_lineedit.setReadOnly(True)
        self.value_lineedit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.value_lineedit.setAlignment(Qt.AlignRight)
        self.update_tooltip()

        self.uncertainty_lineedit = QtWidgets.QLineEdit()
        self.uncertainty_lineedit.setReadOnly(True)
        self.uncertainty_lineedit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.uncertainty_lineedit.setAlignment(Qt.AlignRight)
        self.uncertainty_lineedit.setToolTip('The standard deviation')

        self.config_button = Button(
            icon='shell32|239',
            left_click=self.on_edit_configuration,
            tooltip='Edit the configuration'
        )

        self.font = QtGui.QFont(self.value_lineedit.font())
        self.font_size_spinbox = SpinBox()
        self.font_size_spinbox.setRange(0, 999)
        self.font_size_spinbox.setToolTip('The font size to use to display the value')
        self.font_size_spinbox.valueChanged.connect(self.on_font_size_changed)

        self.live_spinbox = SpinBox()
        self.live_spinbox.setRange(0, 99999)
        self.live_spinbox.setValue(1000)
        self.live_spinbox.setToolTip('The number of milliseconds to wait between live updates')
        self.live_spinbox.valueChanged.connect(self.on_live_spinbox_changed)

        self.live_checkbox = QtWidgets.QCheckBox()
        self.live_checkbox.setChecked(True)
        self.live_checkbox.setToolTip('Enable live update?')
        self.live_checkbox.clicked.connect(self.on_live_checkbox_changed)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.config_button)
        hbox.addSpacerItem(QtWidgets.QSpacerItem(1, 1, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        # hbox.addWidget(self.font_size_spinbox)
        hbox.addWidget(self.live_spinbox)
        hbox.addWidget(self.live_checkbox)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.value_lineedit)
        vbox.addWidget(self.uncertainty_lineedit)
        self.setLayout(vbox)

        if not self.connected_as_link:
            connection.fetched.connect(self.update_lineedits)
            connection.config_changed.connect(self.on_config_changed)

        self.thread = Thread(FetchWorker)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.restart_thread)
        self.timer.start(self.live_spinbox.value())

    def notification_handler(self, *args, **kwargs):
        """Handle a notification emitted by :class:`photons.equipment.dmm.DMM`."""
        if args:
            self.update_lineedits(*args)
        else:
            self.update_tooltip(kwargs)

    def resizeEvent(self, event):
        """Override :class:`QWidget.resizeEvent` to also change the font size."""
        super(DMM, self).resizeEvent(event)
        self.font_size_spinbox.setValue(event.size().width() // 10)

    def closeEvent(self, event):
        """Override :meth:`QWidget.closeEvent` to also stop the Thread and the Timer."""
        self.stop_timer_and_thread()
        super(DMM, self).closeEvent(event)

    def update_tooltip(self, info=None):
        """Update the tooltip of the value QLineEdit."""
        if info is None:
            info = self.connection.info()
        self.info = info
        unit = self.unit_map[self.info['function']]
        if self.info['auto_range'] == 'ON':
            range_ = 'AUTO'
        else:
            scaled, prefix = number_to_si(self.info['range'])
            range_ = f'{scaled:.0f} {prefix}{unit}'
        delay = 'AUTO' if self.info['trigger_delay_auto'] else self.info['trigger_delay']
        function = 'Voltage' if unit == 'V' else 'Current'
        tooltip = f'<html><b>{function}:</b><br>' \
                  f'&nbsp;&nbsp;Range: {range_}<br>' \
                  f'&nbsp;&nbsp;NPLC: {self.info["nplc"]}<br>' \
                  f'&nbsp;&nbsp;# Samples: {self.info["nsamples"]}<br>' \
                  f'&nbsp;&nbsp;Auto Zero: {self.info["auto_zero"]}<br><br>' \
                  f'<b>Trigger:</b><br>' \
                  f'&nbsp;&nbsp;Mode: {self.info["trigger_mode"]}<br>' \
                  f'&nbsp;&nbsp;Edge: {self.info["trigger_edge"]}<br>' \
                  f'&nbsp;&nbsp;# Triggers: {self.info["trigger_count"]}<br>' \
                  f'&nbsp;&nbsp;Delay: {delay}</html>'
        self.value_lineedit.setToolTip(tooltip)

    def on_edit_configuration(self):
        """Slot for the Button clicked signal."""
        was_checked = self.live_checkbox.isChecked()
        if was_checked:
            self.stop_timer_and_thread()
        c = ConfigureDialog(self)
        c.exec()
        if was_checked:
            self.restart_thread_and_timer()

    def on_config_changed(self):
        """Slot for the connection.config_changed signal."""
        self.update_tooltip()

    def on_font_size_changed(self, size):
        """Slot for the font_size_spinbox.valueChanged signal."""
        self.font.setPointSize(size)
        self.value_lineedit.setFont(self.font)
        self.uncertainty_lineedit.setFont(self.font)

    def on_live_checkbox_changed(self, checked):
        """Slot for the live_checkbox.clicked signal."""
        if checked:
            self.timer.start(self.live_spinbox.value())
        else:
            self.timer.stop()

    def on_live_spinbox_changed(self, value):
        """Slot for the live_spinbox.valueChanged signal."""
        if self.live_checkbox.isChecked():
            self.timer.stop()
            self.timer.start(value)

    def update_lineedits(self, average, stdev):
        """Slot for the connection.fetched signal or handles the emitted notification."""
        unit = self.unit_map[self.info['function']]
        scaled, prefix = number_to_si(average)
        self.value_lineedit.setText(f'{scaled:.3f} {prefix}{unit}')
        scaled, prefix = number_to_si(stdev)
        self.uncertainty_lineedit.setText(f'\u00b1 {abs(scaled):.1f} {prefix}{unit}')

    def restart_thread(self):
        """Slot for the QTimer.timeout signal."""
        if not self.thread.is_running():
            self.thread.start(self.connection, self.info['trigger_mode'])

    def stop_timer_and_thread(self):
        """Stop the QTimer and the QThread."""
        self.live_checkbox.setChecked(False)
        self.timer.stop()
        self.thread.stop(milliseconds=max(10, self.live_spinbox.value()))

    def restart_thread_and_timer(self):
        """Restart the Thread and the QTimer."""
        self.live_checkbox.setChecked(True)
        self.restart_thread()
        self.timer.start(self.live_spinbox.value())


class ConfigureDialog(QtWidgets.QDialog):

    def __init__(self, parent):
        """Edit the configuration of the DMM.

        Parameters
        ----------
        parent : :class:`.DMM`
            The parent widget.
        """
        super(ConfigureDialog, self).__init__(parent, Qt.WindowCloseButtonHint)

        self.ask_user = False
        self.info = parent.info.copy()
        self.parent = parent
        self.connection = parent.connection
        self.setWindowTitle(f'Configure {parent.record.alias!r}')

        if parent.connection.connected_as_link:
            # must send the request to the Service by calling the constants
            self.FUNCTIONS = parent.connection.FUNCTIONS()
            self.NPLCS = parent.connection.NPLCS()
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

        self.function_combobox = QtWidgets.QComboBox()
        self.function_combobox.addItems(sorted(set(v for v in self.FUNCTIONS.values())))
        self.function_combobox.setCurrentText(self.FUNCTIONS[self.info['function']])
        self.function_combobox.currentTextChanged.connect(self.on_function_changed)
        self.function_combobox.setToolTip('The function to measure')

        self.range_combobox = QtWidgets.QComboBox()
        self.update_range_combobox()
        self.range_combobox.currentTextChanged.connect(self.set_check_apply)
        self.range_combobox.setToolTip('The function range (not all multimeter\'s will support these ranges)')

        self.nplc_combobox = QtWidgets.QComboBox()
        self.nplc_combobox.addItems([str(v) for v in self.NPLCS.values()])
        self.nplc_combobox.setCurrentText(str(self.NPLCS[self.info['nplc']]))
        self.nplc_combobox.currentTextChanged.connect(self.set_check_apply)
        self.nplc_combobox.setToolTip('The number of power line cycles to integrate over')

        self.nsamples_spinbox = SpinBox()
        self.nsamples_spinbox.setRange(1, int(1e6))
        self.nsamples_spinbox.setValue(self.info['nsamples'])
        self.nsamples_spinbox.valueChanged.connect(self.set_check_apply)
        self.nsamples_spinbox.setToolTip('The number of samples to acquire for each trigger')

        self.auto_zero_combobox = QtWidgets.QComboBox()
        self.auto_zero_combobox.addItems(sorted(set(self.AUTO_ZEROS.values())))
        self.auto_zero_combobox.setCurrentText(self.info['auto_zero'])
        self.auto_zero_combobox.currentTextChanged.connect(self.set_check_apply)
        self.auto_zero_combobox.setToolTip('The auto-zero mode')

        form = QtWidgets.QFormLayout()
        form.addRow('Function:', self.function_combobox)
        form.addRow('Range:', self.range_combobox)
        form.addRow('NPLC:', self.nplc_combobox)
        form.addRow('# Samples:', self.nsamples_spinbox)
        form.addRow('Auto Zero:', self.auto_zero_combobox)
        function_group.setLayout(form)

        trigger_group = QtWidgets.QGroupBox('Trigger Settings')

        self.mode_combobox = QtWidgets.QComboBox()
        self.mode_combobox.addItems(sorted(set(v for v in self.TRIGGERS.values())))
        self.mode_combobox.setCurrentText(self.TRIGGERS[self.info['trigger_mode']])
        self.mode_combobox.currentTextChanged.connect(self.set_check_apply)
        self.mode_combobox.setToolTip('The trigger mode')

        self.edge_combobox = QtWidgets.QComboBox()
        self.edge_combobox.addItems(sorted(set(k for k in self.EDGES.keys())))
        self.edge_combobox.setCurrentText(self.EDGES[self.info['trigger_edge']])
        self.edge_combobox.currentTextChanged.connect(self.set_check_apply)
        self.edge_combobox.setToolTip('The edge to trigger on')

        self.count_spinbox = SpinBox()
        self.count_spinbox.setRange(1, 1e9)
        self.count_spinbox.setValue(self.info['trigger_count'])
        self.count_spinbox.valueChanged.connect(self.set_check_apply)
        self.count_spinbox.setToolTip('The number of triggers that are accepted by the '
                                      'instrument before returning to the "idle" trigger state')

        self.auto_delay_checkbox = QtWidgets.QCheckBox()
        self.auto_delay_checkbox.setCheckable(True)
        self.auto_delay_checkbox.setChecked(self.info['trigger_delay_auto'])
        self.auto_delay_checkbox.clicked.connect(self.auto_delay_changed)
        self.auto_delay_checkbox.setToolTip('Enable the auto-delay feature')

        self.delay_spinbox = DoubleSpinBox()
        self.delay_spinbox.setRange(0, 3600)
        self.delay_spinbox.setValue(self.info['trigger_delay'])
        self.delay_spinbox.setDecimals(6)
        self.delay_spinbox.setEnabled(not self.auto_delay_checkbox.isChecked())
        self.delay_spinbox.setToolTip('The delay, in seconds, between the trigger signal and the first measurement')

        form = QtWidgets.QFormLayout()
        form.addRow('Mode:', self.mode_combobox)
        form.addRow('Edge:', self.edge_combobox)
        form.addRow('# Triggers:', self.count_spinbox)
        form.addRow('Auto delay:', self.auto_delay_checkbox)
        form.addRow('Delay:', self.delay_spinbox)
        trigger_group.setLayout(form)

        self.reset_button = Button(icon=QtWidgets.QStyle.SP_DialogResetButton,
                                   left_click=self.on_reset, tooltip='Reset [*RST]')

        self.clear_button = Button(icon=QtWidgets.QStyle.SP_DialogDiscardButton,
                                   left_click=self.connection.clear, tooltip='Clear [*CLS]')

        self.apply_button = Button(icon=QtWidgets.QStyle.SP_DialogApplyButton,
                                   left_click=self.on_apply_clicked, tooltip='Apply')

        self.cancel_button = Button(icon=QtWidgets.QStyle.SP_DialogCancelButton,
                                    left_click=self.close, tooltip='Cancel')

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
        spacer = QtWidgets.QSpacerItem(1, 1, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        reset_clear_layout.addSpacerItem(spacer)

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

    def update_range_combobox(self):
        """Update the items in range_combobox."""
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

        if self.info['auto_range'] == 'ON':
            self.range_combobox.setCurrentText('AUTO')
        else:
            r = self.info['range']
            for index in range(self.range_combobox.count()):
                if self.range_combobox.itemData(index) >= r:
                    self.range_combobox.setCurrentIndex(index)
                    return
            self.range_combobox.setCurrentText('MAXIMUM')

    def set_check_apply(self, *ignore):
        """A value was changed so notify the user if closing the dialog without applying the changes."""
        self.ask_user = True

    def on_function_changed(self, *ignore):
        """Slot for function_combobox.currentTextChanged signal."""
        self.set_check_apply()
        self.update_range_combobox()

    def auto_delay_changed(self, checked):
        """Slot for auto_delay_checkbox.clicked signal."""
        self.set_check_apply()
        self.delay_spinbox.setEnabled(not checked)

    def on_apply_clicked(self):
        """Slot for self.apply_button click."""
        self.save_settings()

    def save_settings(self):
        """Save the settings to the digital multimeter."""
        application().setOverrideCursor(Qt.WaitCursor)
        self.ask_user = False

        if self.parent.connection.connected_as_link:
            self.stop_parent_timer()

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

        if self.parent.connection.connected_as_link:
            self.restart_parent_timer()

        # close the QDialog
        application().restoreOverrideCursor()
        self.close()

    def on_reset(self):
        """Slot for self.reset_button click."""
        self.connection.reset()
        self.info = self.connection.info()
        self.function_combobox.setCurrentText(self.FUNCTIONS[self.info['function']])
        self.update_range_combobox()
        self.nplc_combobox.setCurrentText(str(self.NPLCS[self.info['nplc']]))
        self.nsamples_spinbox.setValue(self.info['nsamples'])
        self.auto_zero_combobox.setCurrentText(self.info['auto_zero'])
        self.mode_combobox.setCurrentText(self.TRIGGERS[self.info['trigger_mode']])
        self.edge_combobox.setCurrentText(self.EDGES[self.info['trigger_edge']])
        self.count_spinbox.setValue(self.info['trigger_count'])
        self.auto_delay_checkbox.setChecked(self.info['trigger_delay_auto'])

    def closeEvent(self, event):
        """Overrides :meth:`QtWidgets.QDialog.closeEvent`."""
        if self.ask_user:
            if self.original_function != self.function_combobox.currentText() or \
                    self.original_range != self.range_combobox.currentText() or \
                    self.original_nsamples != self.nsamples_spinbox.value() or \
                    self.original_nplc != self.nplc_combobox.currentText() or \
                    self.original_auto_zero != self.auto_zero_combobox.currentText() or \
                    self.original_mode != self.mode_combobox.currentText() or \
                    self.original_edge != self.edge_combobox.currentText() or \
                    self.original_count != self.count_spinbox.value() or \
                    self.original_auto_delay is not self.auto_delay_checkbox.isChecked() or \
                    self.original_delay != self.delay_spinbox.value():
                if prompt.yes_no('You have modified the settings.\n\nApply the changes?', default=False):
                    self.save_settings()
        super(ConfigureDialog, self).closeEvent(event)
