"""
Plugin to determine the gain of a transimpedance amplifier.

Setup
=====
1. A Keithley 6430 sub-femto SourceMeter produces a current.
2. The current (from the IN/OUT HIGH port of the pre-amp) is the input signal to transimpedance amplifier.
3. The output of the transimpedance amplifier is connected to a digital multimeter.
"""
from __future__ import annotations

import re
import time
import typing
from math import isnan
from threading import Event

from msl.qt import Button
from msl.qt import ComboBox
from msl.qt import DoubleSpinBox
from msl.qt import QtWidgets
from msl.qt import Slot
from msl.qt import SpinBox
from msl.qt import Thread
from msl.qt import Worker
from msl.qt import prompt
from msl.qt.convert import number_to_si

from .base import BasePlugin
from .base import plugin
from .. import audio
from ..utils import array_evenly
from ..utils import hhmmss

if typing.TYPE_CHECKING:
    from ..app import MainWindow


@plugin(name='TIA Gain', description='Determine the gain of a transimpedance amplifier')
class TIAGain(BasePlugin):

    def __init__(self, parent: MainWindow, **kwargs) -> None:
        """Plugin to determine the gain of a transimpedance amplifier.

        Args:
            parent: The main window.
            **kwargs: All keyword arguments are passed to super().
        """
        super().__init__(parent, **kwargs)

        self.t0 = 0
        self.abort_event = Event()
        self.thread = Thread(TIAGainWorker)
        self.thread.finished.connect(self.on_worker_finished)

        self._gain_regex = re.compile(r'10(?P<MIN>\d)(?P<MAX>\d)')
        self.gain_spinbox = SpinBox(
            tooltip='Enter the gain [10^gain]',
        )

        records = parent.app.records(model='3458A')
        self.dmm_combobox = ComboBox(
            items=dict((f'{r.manufacturer} {r.model} {r.serial}', r.alias)
                       for r in records),
            tooltip='Select the DMM',
        )

        records = parent.app.records(description='I-V Converter')
        self.tia_combobox = ComboBox(
            items=dict((r.serial, r) for r in records),
            tooltip='Select the transimpedance amplifier',
            text_changed=self.on_tia_changed,
        )
        self.on_tia_changed(self.tia_combobox.currentText())

        default = 0.15
        self.tolerance_spinbox = DoubleSpinBox(
            value=default,
            minimum=0.01,
            decimals=2,
            unit='%',
            tooltip=f'The tolerance of the Keithley 6430 current source. '
                    f'[Default: {default}%]\n'
                    f'The current must be stable to within this '
                    f'tolerance before measuring the voltage.'
        )

        self.step_spinbox = SpinBox(
            minimum=1,
            value=5,
            unit='%',
            tooltip='The step size for each current range',
        )

        self.run_button = Button(
            text='Start',
            icon='ieframe|101',
            left_click=self.on_worker_start,
            tooltip='Run'
        )

        self.abort_button = Button(
            text='Abort',
            icon='shell32|27',
            left_click=self.on_worker_abort,
            tooltip='Abort'
        )

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.abort_button)

        layout = QtWidgets.QFormLayout()
        layout.addRow('DMM:', self.dmm_combobox)
        layout.addRow('TIA:', self.tia_combobox)
        layout.addRow('Gain:', self.gain_spinbox)
        layout.addRow('Tol:', self.tolerance_spinbox)
        layout.addRow('Step:', self.step_spinbox)
        layout.addRow(buttons)
        self.setLayout(layout)

        self.setWindowTitle('TIA Gain')

    @Slot(str)
    def on_tia_changed(self, text: str) -> None:
        """Slot for the TIA changed."""
        m = self._gain_regex.match(text)
        self.gain_spinbox.setRange(int(m['MIN']), int(m['MAX']))

    @Slot()
    def on_worker_abort(self) -> None:
        """Abort the worker thread."""
        if self.thread.is_running():
            self.app.logger.warning('aborting run early')
            self.abort_event.set()
            self.main.status_bar_message.emit(f'Safely aborting {self.windowTitle()}...')
            self.main.show_indeterminate_progress_bar.emit()

    @Slot()
    def on_worker_start(self) -> None:
        """Start acquiring data in the worker thread."""
        if self.thread.is_running():
            prompt.critical('A scan is already running')
            return

        if not prompt.yes_no('Are you certain that the selected transimpedance '
                             'amplifier and gain are correct?', default=False):
            return

        self.abort_event.clear()
        self.main.status_bar_message.emit(f'Running {self.windowTitle()}...')
        self.main.show_indeterminate_progress_bar.emit()
        self.t0 = time.monotonic()
        self.thread.start(self)

    @Slot()
    def on_worker_finished(self) -> None:
        """Called when the worker thread finishes."""
        hms = hhmmss(time.monotonic() - self.t0)
        self.main.status_bar_message.emit(f'{self.windowTitle()} finished [took {hms}]')
        self.main.hide_progress_bar.emit()
        self.app.send_email(subject=f'{self.windowTitle()} finished', body=f'Took {hms}')
        audio.random()


class TIAGainWorker(Worker):

    def __init__(self, parent: TIAGain) -> None:
        super().__init__()
        self.plugin = parent

    def process(self):
        app = self.plugin.app
        update_progress_bar = self.plugin.main.update_progress_bar
        status_bar_message = self.plugin.main.status_bar_message
        abort_event = self.plugin.abort_event
        dmm_alias = self.plugin.dmm_combobox.currentData()
        tia_serial = self.plugin.tia_combobox.currentText()
        gain = self.plugin.gain_spinbox.value()
        tol = self.plugin.tolerance_spinbox.value() / 100.
        step = self.plugin.step_spinbox.value() / 100.
        factor = 10**(1-gain)
        decimals = gain + 3

        # determine the suffix to use in the filename
        scan = ''
        suffix = f'{tia_serial}_1e{gain}'
        while True:
            try:
                writer = app.create_writer('tia_gain', suffix=f'{suffix}{scan}')
            except FileExistsError as e:
                s = re.search(r'_scan(?P<scan>\d+)\.', str(e))
                n = 2 if s is None else int(s['scan']) + 1
                scan = f'_scan{n}'
            else:
                break

        tia_record = self.plugin.tia_combobox.currentData()
        if not tia_record.alias:
            tia_record.alias = 'amplifier'
        dmm, femto = app.connect_equipment(dmm_alias, 'femtoamp')
        writer.add_equipment(dmm, femto, tia_record)
        writer.add_metadata(
            comment=f'I-V converter: {tia_serial}, Gain: 10^{gain}',
            current_unit='Amps',
            voltage_unit='Volts',
        )

        values = [(factor, 10), (factor*0.1, 10), (factor*0.01, 1)]
        loop = 0
        update_progress_bar.emit(0)
        for i, (max_amps, dmm_range) in enumerate(values, start=1):
            if abort_event.is_set():
                break

            currents = array_evenly(
                -max_amps, max_amps, round(step*max_amps, decimals),
                decimals=decimals
            )

            # The Keithley 6430 is a bit slower to read the output current than the DMM is,
            # so read less samples than the DMM does so that each device acquires
            # samples during approximately the same time interval
            dmm_settings = dmm.configure(nsamples=10, range=dmm_range)

            femto.disable_output()
            femto_settings = femto.configure_source(nsamples=6, range=max_amps, cmpl=0.1)
            femto.enable_output()

            # The Keysight 3458A supports a command to read the internal temperature.
            # If a different DMM is being used then the temperature command may not be available.
            try:
                metadata = {
                    'dmm_temperature': dmm.temperature(),
                    'temperature_unit': 'Celsius',
                }
            except AttributeError:
                metadata = {}

            metadata.update(
                current_configuration=femto_settings,
                voltage_configuration=dmm_settings,
            )

            value, si_prefix = number_to_si(max_amps, unicode=False)
            name = f'{value:.0f} {si_prefix}A'
            writer.initialize('set_current', 'current', 'current_stdev', 'voltage', 'voltage_stdev',
                              size=currents.size, name=name, **metadata)

            total = float(currents.size) * len(values)
            app.logger.info(f'currents={currents.tolist()}')
            for current in currents:
                if abort_event.is_set():
                    break
                value, si_prefix = number_to_si(current)
                status_bar_message.emit(f'Current at {value:.1f} {si_prefix}A [{i} of {len(values)}]')
                femto.set_output_level(current, wait=True, tol=tol)
                nan_index = 0
                while True:
                    # On very rare occasions the HP 3458A would return one sample
                    # (out of the N samples that were requested) that is 1e+38
                    # causing a NaN to be written to the file. Keep fetching samples
                    # until only finite values are returned from the DMM.
                    femto.bus_trigger()
                    dmm.bus_trigger()
                    dmm_samples = dmm.fetch()
                    femto_samples = femto.fetch()
                    if not isnan(dmm_samples.mean) or abort_event.is_set():
                        break
                    msg = f'Received {nan_index} NaN(s) from the DMM'
                    status_bar_message.emit(msg)
                    app.logger.warning(msg)
                    nan_index += 1
                writer.append(current, *femto_samples, *dmm_samples)
                loop += 1
                update_progress_bar.emit(100. * loop / total)

        femto.disable_output()
        writer.write()
