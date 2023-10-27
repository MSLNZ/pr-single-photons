"""
Perform a 3D spatial scan of a photodetector.
"""
from __future__ import annotations

import typing
from threading import Event
from time import monotonic
from time import perf_counter

import numpy as np
from msl.equipment.utils import convert_to_primitive
from msl.qt import Button
from msl.qt import CheckBox
from msl.qt import DoubleSpinBox
from msl.qt import Qt
from msl.qt import QtCore
from msl.qt import QtGui
from msl.qt import QtWidgets
from msl.qt import Slot
from msl.qt import SpinBox
from msl.qt import Thread
from msl.qt import Worker
from msl.qt import prompt

from .base import BasePlugin
from .base import plugin
from .. import audio
from ..equipment import DMM
from ..equipment.widgets import DAQCounterWidget
from ..samples import Samples
from ..utils import array_central
from ..utils import array_photodiode_centre
from ..utils import hhmmss

if typing.TYPE_CHECKING:
    from ..app import MainWindow


@plugin(name='Spatial Scan', description='Perform a 3D spatial scan of a detector')
class SpatialScan(BasePlugin):

    def __init__(self, parent: MainWindow, **kwargs) -> None:
        """Perform a 3D spatial scan of a photodetector.

        Args:
            parent: The main window.
            **kwargs: All keyword arguments are passed to super().
        """
        super().__init__(parent, **kwargs)
        self.abort_event = Event()
        self.monitor_widget = None
        self.detector_widget = None
        self.comment = ''
        self.filename_suffix = ''
        self.x_values = np.empty(0)
        self.y_values = np.empty(0)
        self.z_values = np.empty(0)
        self.t0 = 0

        self.thread = Thread(SpatialScanWorker)
        self.thread.finished.connect(self.on_worker_finished)

        #
        # Create the widgets
        #

        # the root element in the configuration file
        root = self.app.config.find(self.__class__.__name__)
        if root is None:
            prompt.critical(f'You must create a <{self.__class__.__name__}> '
                            f'element in the configuration file')
            self.show_plugin = False
            return

        # determine the equipment that the DUT is connected to
        detectors = {el.text: el for el in root.findall('detector')}
        if not detectors:
            prompt.critical(f'You must create at least one <detector> '
                            f'sub-element to <{root.tag}>')
            self.show_plugin = False
            return
        elif len(detectors) == 1:
            alias = list(detectors)[0]
        else:
            alias = prompt.item(
                'Select the device that the DUT is connected to',
                list(detectors)
            )
            if alias is None:
                self.show_plugin = False
                return

        self.detector = self.app.connect_equipment(alias)
        self.is_detector_dmm = isinstance(self.detector, DMM)
        if self.is_detector_dmm:
            self.detector.configure(
                **{k: convert_to_primitive(v)
                   for k, v in detectors[alias].attrib.items()}
            )
        self.detector_widget = self.find_widget(self.detector, parent=self)

        element = root.find('x')
        alias, width, step = 'stage-x', 10, 1
        if element is not None:
            alias = element.text
            width = float(element.attrib.get('width', width))
            step = float(element.attrib.get('step', step))
        self.x_stage = self.app.connect_equipment(alias)
        self.x_widget = self.find_widget(self.x_stage, parent=self)
        info = self.x_stage.info()
        self.x_width_spinbox = DoubleSpinBox(
            value=width,
            minimum=0,
            maximum=info['maximum'],
            decimals=3,
            tooltip='The total width to scan in the X direction',
            unit=info['unit'],
        )
        self.x_step_spinbox = DoubleSpinBox(
            value=step,
            minimum=0,
            maximum=info['maximum'],
            decimals=3,
            tooltip='The step size in the X direction',
            unit=info['unit'],
        )
        self.x_randomize_checkbox = CheckBox(
            initial=False,
            tooltip='Randomize the X values?',
        )

        element = root.find('y')
        alias, width, step = 'stage-y', 10, 1
        if element is not None:
            alias = element.text
            width = float(element.attrib.get('width', width))
            step = float(element.attrib.get('step', step))
        self.y_stage = self.app.connect_equipment(alias)
        self.y_widget = self.find_widget(self.y_stage, parent=self)
        info = self.y_stage.info()
        self.y_width_spinbox = DoubleSpinBox(
            value=width,
            minimum=0,
            maximum=info['maximum'],
            decimals=3,
            tooltip='The total height to scan in the Y direction',
            unit=info['unit'],
        )
        self.y_step_spinbox = DoubleSpinBox(
            value=step,
            minimum=0,
            maximum=info['maximum'],
            decimals=3,
            tooltip='The step size in the Y direction',
            unit=info['unit'],
        )
        self.y_randomize_checkbox = CheckBox(
            initial=False,
            tooltip='Randomize the Y values?',
        )

        element = root.find('z')
        alias, width, step = 'stage-z', 10, 1
        if element is not None:
            alias = element.text
            width = float(element.attrib.get('width', width))
            step = float(element.attrib.get('step', step))
        self.z_stage = self.app.connect_equipment(alias)
        self.z_widget = self.find_widget(self.z_stage, parent=self)
        info = self.z_stage.info()
        self.z_width_spinbox = DoubleSpinBox(
            value=width,
            minimum=0,
            maximum=info['maximum'],
            decimals=3,
            tooltip='The total depth to scan in the Z direction',
            unit=info['unit'],
        )
        self.z_step_spinbox = DoubleSpinBox(
            value=step,
            minimum=0,
            maximum=info['maximum'],
            decimals=3,
            tooltip='The step size in the Z direction',
            unit=info['unit'],
        )
        self.z_randomize_checkbox = CheckBox(
            initial=False,
            tooltip='Randomize the Z values?',
        )

        element = root.find('monitor')
        if element is None:
            prompt.critical(f'Add a <monitor> sub-element to <{root.tag}>')
            self.show_plugin = False
            return
        self.monitor = self.app.connect_equipment(element.text.strip())
        self.monitor.configure(**{k: convert_to_primitive(v) for k, v in element.attrib.items()})
        self.monitor_widget = self.find_widget(self.monitor, parent=self)

        self.shutter = self.app.connect_equipment(root.findtext('shutter', 'shutter'))
        self.shutter_widget = self.find_widget(self.shutter, parent=self)

        self.delay_spinbox = DoubleSpinBox(
            value=2,
            decimals=1,
            tooltip='The number of seconds to wait after moving the translation stages',
            unit=' s',
        )

        self.nrepeats_spinbox = SpinBox(
            value=1,
            tooltip='The number of times to repeat the scan',
        )

        self.run_button = Button(
            text='Start',
            icon='ieframe|101',
            left_click=self.on_worker_start,
            tooltip='Run (CTRL+R)'
        )

        self.abort_button = Button(
            text='Abort',
            icon='shell32|27',
            left_click=self.on_worker_abort,
            tooltip='Abort (CTRL+A)'
        )

        #
        # Create the layout
        #

        spacer = 1, 1, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum

        layout = QtWidgets.QVBoxLayout()

        box_x = QtWidgets.QHBoxLayout()
        box_x.addWidget(QtWidgets.QLabel('X:'))
        box_x.addWidget(self.x_widget)
        box_x.addWidget(self.x_width_spinbox)
        box_x.addWidget(self.x_step_spinbox)
        box_x.addWidget(self.x_randomize_checkbox)
        box_x.addSpacerItem(QtWidgets.QSpacerItem(*spacer))
        layout.addLayout(box_x)

        box_y = QtWidgets.QHBoxLayout()
        box_y.addWidget(QtWidgets.QLabel('Y:'))
        box_y.addWidget(self.y_widget)
        box_y.addWidget(self.y_width_spinbox)
        box_y.addWidget(self.y_step_spinbox)
        box_y.addWidget(self.y_randomize_checkbox)
        box_y.addSpacerItem(QtWidgets.QSpacerItem(*spacer))
        layout.addLayout(box_y)

        box_z = QtWidgets.QHBoxLayout()
        box_z.addWidget(QtWidgets.QLabel('Z:'))
        box_z.addWidget(self.z_widget)
        box_z.addWidget(self.z_width_spinbox)
        box_z.addWidget(self.z_step_spinbox)
        box_z.addWidget(self.z_randomize_checkbox)
        box_z.addSpacerItem(QtWidgets.QSpacerItem(*spacer))
        layout.addLayout(box_z)

        box1 = QtWidgets.QHBoxLayout()
        box1.addWidget(QtWidgets.QLabel('Mon:'))
        box1.addWidget(self.monitor_widget)
        box1.addWidget(QtWidgets.QLabel('Det:'))
        box1.addWidget(self.detector_widget)
        layout.addLayout(box1)

        box2 = QtWidgets.QHBoxLayout()
        box2.addWidget(QtWidgets.QLabel('Shutter:'))
        box2.addWidget(self.shutter_widget)
        box2.addWidget(QtWidgets.QLabel('Delay:'))
        box2.addWidget(self.delay_spinbox)
        box2.addWidget(QtWidgets.QLabel('#Repeats:'))
        box2.addWidget(self.nrepeats_spinbox)
        box2.addSpacerItem(QtWidgets.QSpacerItem(*spacer))
        layout.addLayout(box2)

        box3 = QtWidgets.QHBoxLayout()
        box3.addWidget(self.run_button)
        box3.addWidget(self.abort_button)
        layout.addLayout(box3)
        self.setLayout(layout)
        self.setWindowTitle('3D Spatial Scan')

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.closeEvent`."""
        if self.thread.is_running():
            prompt.critical('Scan running. Click Abort to stop it.')
            event.ignore()
            return
        self.stop_monitor_and_detector_timer_and_thread()
        super().closeEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.keyReleaseEvent`."""
        if event.modifiers() == Qt.ControlModifier:
            key = event.key()
            if key == Qt.Key_R:
                self.on_worker_start()
            elif key == Qt.Key_A:
                self.on_worker_abort()
        super().keyReleaseEvent(event)

    @Slot()
    def on_worker_abort(self) -> None:
        """Abort the worker thread."""
        if self.thread.is_running():
            self.app.logger.warning('aborting scan early')
            self.abort_event.set()
            self.main.status_bar_message.emit(f'Safely aborting {self.windowTitle()}...')
            self.main.show_indeterminate_progress_bar.emit()

    @Slot()
    def on_worker_finished(self) -> None:
        """Called when the worker thread finishes."""
        hms = hhmmss(monotonic() - self.t0)
        self.main.status_bar_message.emit(f'{self.windowTitle()} finished [took {hms}]')
        self.main.hide_progress_bar.emit()
        self.app.send_email(subject=f'{self.windowTitle()} finished', body=f'Took {hms}')
        try:
            audio.random()
        except RuntimeError as e:  # can occur if using Remote Desktop
            self.app.logger.warning(f'{e.__class__.__name__}: {e}')

    @Slot()
    def on_worker_start(self) -> None:
        """Start acquiring data in the worker thread."""
        if self.thread.is_running():
            prompt.critical('A scan is already running')
            return

        self.abort_event.clear()
        self.stop_monitor_and_detector_timer_and_thread()

        if prompt.yes_no('Are you finding the centre of a photodiode?', default=False):
            array = array_photodiode_centre
        else:
            array = array_central

        self.x_values = array(
            centre=self.x_stage.get_position(),
            width=self.x_width_spinbox.value(),
            step=self.x_step_spinbox.value(),
            randomize=self.x_randomize_checkbox.isChecked(),
        )
        self.y_values = array(
            centre=self.y_stage.get_position(),
            width=self.y_width_spinbox.value(),
            step=self.y_step_spinbox.value(),
            randomize=self.y_randomize_checkbox.isChecked(),
        )
        self.z_values = array(
            centre=self.z_stage.get_position(),
            width=self.z_width_spinbox.value(),
            step=self.z_step_spinbox.value(),
            randomize=self.z_randomize_checkbox.isChecked(),
        )

        self.comment = prompt.comments(
            even_row_color=Qt.lightGray,
            odd_row_color=Qt.darkGray
        )

        self.filename_suffix = prompt.text('<i>Optional</i>: Specify a suffix for the filename')
        if not prompt.yes_no('Start spatial scan?'):
            return
        self.main.status_bar_message.emit(f'Running {self.windowTitle()}...')
        self.t0 = monotonic()
        self.thread.start(self)

    def stop_monitor_and_detector_timer_and_thread(self) -> None:
        """Stop the timers/threads for the monitor/detector connection."""
        if self.monitor_widget is not None:
            self.monitor_widget.stop_timer_and_thread()  # noqa: DMM and NIDAQ widgets have stop_timer_and_thread()
        if self.detector_widget is not None:
            self.detector_widget.stop_timer_and_thread()  # noqa: DMM and NIDAQ widgets have stop_timer_and_thread()


class SpatialScanWorker(Worker):

    def __init__(self, parent: SpatialScan) -> None:
        super().__init__()
        self.plugin = parent
        self.is_detector_dmm = parent.is_detector_dmm
        self.update_progress_bar = parent.main.update_progress_bar
        self.status_bar_message = parent.main.status_bar_message
        self.logger = parent.app.logger
        self.delay = parent.delay_spinbox.value()
        self.delay_ms = int(self.delay * 1e3)
        self.monitor = typing.cast(DMM, parent.monitor)
        self.detector = parent.detector
        self.shutter = parent.shutter

        self.detector_settings = {}
        if self.is_detector_dmm:
            self.detector_settings = self.detector.settings()

        if not parent.is_detector_dmm:
            widget = typing.cast(DAQCounterWidget, parent.detector_widget)
            self.count_edges_kwargs = {
                'pfi': widget.pfi_combobox.currentData(),
                'duration': widget.duration_spinbox.value(),
                'nsamples': widget.nsamples_spinbox.value(),
                'rising': widget.edge_combobox.currentText().lower() == 'rising',
            }

    def acquire(self) -> tuple[Samples, Samples]:
        """Acquire the monitor and detector samples.

        Returns:
            (monitor samples, detector samples)
        """
        self.monitor.initiate()
        if self.is_detector_dmm:
            self.detector.initiate()
        # read DUT before monitor since DUT could be connected to a counter or the SIA from CMI
        dut = self.read_dut()
        mon = self.monitor.fetch()
        return mon, dut

    def acquire_dark(self) -> dict[str, float]:
        """Take a dark measurement."""
        self.status_bar_message.emit('Taking a dark measurement...')
        self.logger.info('Taking a dark measurement...')
        self.shutter.close()
        QtCore.QThread.msleep(self.delay_ms)
        mon, dut = self.acquire()
        return {
            'mon_ave': mon.mean,
            'mon_stdev': mon.stdev,
            'dut_ave': dut.mean,
            'dut_stdev': dut.stdev,
        }

    def process(self) -> None:
        """Run the spatial scan."""
        app = self.plugin.app
        x_values = self.plugin.x_values
        y_values = self.plugin.y_values
        z_values = self.plugin.z_values
        x_stage = self.plugin.x_stage
        y_stage = self.plugin.y_stage
        z_stage = self.plugin.z_stage

        x_original = x_stage.get_position()
        y_original = y_stage.get_position()
        z_original = z_stage.get_position()

        prefix = app.config.value(
            f'{self.plugin.__class__.__name__}/filename_prefix',
            'spatial_scan'
        )
        writer = app.create_writer(prefix, suffix=self.plugin.filename_suffix)
        writer.add_equipment(
            self.monitor, self.detector, self.shutter,
            x_stage, y_stage, z_stage
        )
        writer.add_metadata(
            comment=self.plugin.comment,
            delay=self.delay,
            delay_unit='seconds',
            detector_info=self.detector_settings,
            monitor_info=self.monitor.settings().to_json(),
            x_start=x_original,
            x_step=round(float(x_values[1] - x_values[0]), 4) if len(x_values) > 1 else 0.0,
            x_stop=np.max(x_values),
            x_unit=x_stage.info()['unit'].strip(),
            y_start=y_original,
            y_step=round(float(y_values[1] - y_values[0]), 4) if len(y_values) > 1 else 0.0,
            y_stop=np.max(y_values),
            y_unit=y_stage.info()['unit'].strip(),
            z_start=z_original,
            z_step=round(float(z_values[1] - z_values[0]), 4) if len(z_values) > 1 else 0.0,
            z_stop=np.max(z_values),
            z_unit=z_stage.info()['unit'].strip()
        )

        self.logger.info('START')
        self.logger.info(f'X values: {np.array_str(x_values, max_line_width=1024)}')
        self.logger.info(f'Y values: {np.array_str(y_values, max_line_width=1024)}')
        self.logger.info(f'Z values: {np.array_str(z_values, max_line_width=1024)}')

        abort: Event = self.plugin.abort_event
        total: int = x_values.size * y_values.size * z_values.size
        n_repeats: int = self.plugin.nrepeats_spinbox.value()
        for irepeat in range(n_repeats):
            if abort.is_set():
                break

            iteration = 0
            writer.initialize(
                'x', 'y', 'z', 'mon', 'mon_stdev', 'dut', 'dut_stdev',
                name=f'spatial_scan_{irepeat+1}',
                size=total,
                dark_before=self.acquire_dark(),
            )

            # ZYX loop
            self.shutter.open()
            QtCore.QThread.msleep(self.delay_ms)
            self.status_bar_message.emit('Start loop...')
            self.logger.info('Start loop...')
            for z_val in z_values:
                if abort.is_set():
                    break
                z_stage.set_position(z_val, wait=False)
                for y_val in y_values:
                    if abort.is_set():
                        break
                    y_stage.set_position(y_val, wait=False)
                    for x_val in x_values:
                        if abort.is_set():
                            break
                        x_stage.set_position(x_val, wait=False)
                        t0 = perf_counter()
                        while x_stage.is_moving() or y_stage.is_moving() or z_stage.is_moving():
                            QtCore.QThread.msleep(100)
                            if perf_counter() - t0 > 30:
                                break

                        x = round(x_stage.get_position(), 3)
                        y = round(y_stage.get_position(), 3)
                        z = round(z_stage.get_position(), 3)
                        self.logger.info(f'stages at x={x:.4f}, y={y:.4f}, z={z:.4f}')
                        self.status_bar_message.emit(f'x={x}, y={y}, z={z} [{irepeat+1} of {n_repeats}]')

                        self.logger.info(f'waiting for {self.delay} seconds ...')
                        QtCore.QThread.msleep(self.delay_ms)
                        mon, dut = self.acquire()
                        writer.append(x, y, z, mon.mean, mon.stdev, dut.mean, dut.stdev)
                        iteration += 1
                        self.update_progress_bar.emit(100 * iteration / total)

            writer.update_metadata(dark_after=self.acquire_dark())
            x_stage.set_position(x_original, wait=False)
            y_stage.set_position(y_original, wait=False)
            z_stage.set_position(z_original, wait=False)

        writer.write()

    def read_dut(self) -> Samples:
        """Read the samples for the device-under-test."""
        if self.is_detector_dmm:
            return self.detector.fetch()
        else:
            return self.detector.count_edges(**self.count_edges_kwargs)
