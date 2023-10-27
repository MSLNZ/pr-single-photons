"""
Visualise data from the Spatial Scan plugin.
"""
import os
import re
import sys
from queue import Queue
from typing import Callable
from xml.etree.ElementTree import ElementTree

import numpy as np
import pyqtgraph as pg
from msl.io import read
from msl.qt import LineEdit
from msl.qt import Qt
from msl.qt import QtCore
from msl.qt import QtGui
from msl.qt import QtWidgets
from msl.qt import Signal
from msl.qt import Slot
from msl.qt import Thread
from msl.qt import Worker
from msl.qt import application
from msl.qt import convert
from msl.qt import excepthook
from msl.qt import prompt
from msl.qt import utils

from photons.log import logger
from photons.nlf import SuperGaussian
from photons.utils import std_relative


class FitQueue(Queue):

    def clear_put(self, x: np.ndarray, y: np.ndarray, typ: str, clear: bool) -> None:
        """Maybe clear the queue and put the latest x, y data to fit."""
        if clear:
            self.queue.clear()
        self.put_nowait((x, y, typ))


class FitWorker(Worker):

    result = Signal(dict)

    def __init__(self, queue: Queue) -> None:
        super().__init__()
        self.queue: Queue = queue
        self.super_gaussian = SuperGaussian()

    def process(self) -> None:
        while True:
            x, y, typ = self.queue.get()
            if x.size == 0:
                break
            try:
                result = self.super_gaussian.fit(x, y)
            except OSError as e:
                logger.warning(e)
                continue
            x_fit = np.linspace(x[0], x[-1], num=100)
            y_fit = self.super_gaussian.evaluate(x_fit, result)
            self.result.emit({
                'type': typ,
                'x': x,
                'y': y,
                'x_fit': x_fit,
                'y_fit': y_fit,
                'params': result.params
            })


class FitThread(Thread):

    def __init__(self) -> None:
        super().__init__(FitWorker)


class Main(QtWidgets.QWidget):

    def __init__(self, file: str = None) -> None:
        """Main widget."""
        super().__init__()
        self.setAcceptDrops(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.black)
        self.setPalette(p)

        self.data = {}
        self.filename = file
        self.max_signal = 1.0
        self.x_unique = np.empty(0)
        self.dx = 0
        self.y_unique = np.empty(0)
        self.dy = 0
        self.z_value = None
        self.x_pos = -1
        self.y_pos = -1
        self.clear_fit_queue = True

        self.fit_params_x = None
        self.fit_params_y = None
        self.fit_queue = FitQueue()
        self.fit_thread = FitThread()
        self.fit_thread.start(self.fit_queue)
        self.fit_thread.worker_connect(FitWorker.result, self.plot_x_or_y)

        self.win = pg.GraphicsLayoutWidget()
        self.win.scene().contextMenu = None  # remove 'Export...'

        self.view_box = pg.ViewBox(border='w', invertY=True, lockAspect=True, enableMouse=False)
        self.canvas = pg.ImageItem()
        self.view_box.addItem(self.canvas)
        self.view_box.menu = CanvasMenu(self)
        self.win.addItem(self.view_box, row=0, col=0, rowspan=2)  # noqa: row, col, rowspan are valid kwargs
        self.view_box.scene().sigMouseMoved.connect(self.on_mouse_moved)

        self.x_line = pg.InfiniteLine(angle=90, movable=True)
        self.x_line.sigPositionChanged.connect(self.update_x_plot)
        self.view_box.addItem(self.x_line)

        self.y_line = pg.InfiniteLine(angle=0, movable=True)
        self.y_line.sigPositionChanged.connect(self.update_y_plot)
        self.view_box.addItem(self.y_line)

        self.rect_roi = pg.RectROI((0, 0), (1, 1), pen='r', maxBounds=self.canvas.boundingRect(),
                                   scaleSnap=True, translateSnap=True, invertible=True)
        self.rect_roi.sigRegionChanged.connect(self.on_roi_changed)
        self.view_box.addItem(self.rect_roi)

        self.x_plot = self.win.addPlot(row=0, col=1)
        self.x_plot.ctrlMenu = None  # remove 'Plot Options'
        self.x_plot.vb.menu = PlotMenu(self, self.save_xplot_as_csv, self.x_plot)
        self.x_plot.showGrid(x=True, y=True)

        self.y_plot = self.win.addPlot(row=1, col=1)
        self.y_plot.ctrlMenu = None  # remove 'Plot Options'
        self.y_plot.vb.menu = PlotMenu(self, self.save_yplot_as_csv, self.y_plot)
        self.y_plot.showGrid(x=True, y=True)

        self.x_region = pg.LinearRegionItem()
        self.x_region.sigRegionChanged.connect(self.update_x_title)
        self.x_region.setZValue(-10)

        self.y_region = pg.LinearRegionItem()
        self.y_region.sigRegionChanged.connect(self.update_y_title)
        self.y_region.setZValue(-10)

        self.x_fit = pg.PlotDataItem(pen='r')
        self.y_fit = pg.PlotDataItem(pen='r')

        self.z_slider = QtWidgets.QSlider(orientation=Qt.Horizontal)
        self.z_slider.setSingleStep(1)
        self.z_slider.valueChanged.connect(self.on_z_change)  # noqa: valueChanged is a valid attribute

        self.canvas_lut = pg.HistogramLUTWidget()
        self.canvas_lut.setImageItem(self.canvas)
        self.canvas_lut.gradient.loadPreset('flame')
        self.canvas_lut.vb.menu = QtWidgets.QMenu()  # clear the Menu
        self.canvas_lut.scene().contextMenu = None  # remove 'Export...'

        self.max_label = QtWidgets.QLabel(self)
        self.max_label.setStyleSheet('color: white;')
        self.pos_label = QtWidgets.QLabel(self)
        self.pos_label.setStyleSheet('color: white;')
        self.roi_label = LineEdit(
            read_only=True,
            parent=self,
        )
        self.roi_label.setStyleSheet('color: white; background: black; border: 1px')

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.canvas_lut)
        hbox.addWidget(self.win)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.z_slider)

        label_layout = QtWidgets.QHBoxLayout()
        label_layout.addWidget(self.max_label)
        label_layout.addStretch(1)
        label_layout.addWidget(self.pos_label)
        label_layout.addStretch(1)
        label_layout.addWidget(self.roi_label)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(label_layout)
        layout.addLayout(vbox)
        self.setLayout(layout)

        if file:
            self.load_data(file)
            self.dropEvent()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.dragEnterEvent`."""
        paths = utils.drag_drop_paths(event)
        try:
            self.load_data(paths[0])
        except Exception as e:
            prompt.critical(e)
            event.ignore()
        else:
            self.filename = paths[0]
            event.accept()

    def dropEvent(self, event: QtGui.QDropEvent = None) -> None:
        """Overrides :meth:`QtWidgets.QWidget.dropEvent`."""
        if event is not None:
            event.accept()

        z_value, array = self.data[self.z_slider.value()]

        # temporarily disable updating the titles for a region change
        # since the signal gets called before the data is added to the plots
        # after a new drag 'n drop event occurs
        self.x_region.blockSignals(True)
        self.y_region.blockSignals(True)

        self.x_unique = np.unique(array['x'])
        self.y_unique = np.unique(array['y'])

        self.dx = self.x_unique[1] - self.x_unique[0]
        self.dy = self.y_unique[1] - self.y_unique[0]

        # update x_region based on the Y values
        y_ave = np.average(self.y_unique)
        y_max = np.amax(self.y_unique)
        y_min = np.amin(self.y_unique)
        region = self.x_region.getRegion()
        if region == (0, 1) or region[0] < y_min or region[1] > y_max:
            dy = 0.125 * (y_max - y_min)
            self.x_region.setRegion((y_ave - dy, y_ave + dy))

        # update y_region based on the X values
        x_ave = np.average(self.x_unique)
        x_max = np.amax(self.x_unique)
        x_min = np.amin(self.x_unique)
        region = self.y_region.getRegion()
        if region == (0, 1) or region[0] < x_min or region[1] > x_max:
            dx = 0.125 * (x_max - x_min)
            self.y_region.setRegion((x_ave - dx, x_ave + dx))

        i_max = np.argmax(array['signal'])
        self.max_signal = 1.0  # array['signal'][i_max]
        image = np.reshape(array['signal'] / self.max_signal, (self.y_unique.size, self.x_unique.size))

        self.canvas.setImage(image.T)
        self.rect_roi.maxBounds = self.canvas.boundingRect()

        self.update_x_plot()
        self.update_y_plot()

        x_max, y_max = array['x'][i_max], array['y'][i_max]
        if self.max_signal > 1e3:
            value, si = convert.number_to_si(self.max_signal)
        else:
            value, si = self.max_signal, ''
        self.max_label.setText(f'Maximum={value:.3f}{si} @ X={x_max:.3f}, Y={y_max:.3f}')

        self.setWindowTitle(f'Spatial Scan || {self.filename}')
        self.on_roi_changed()

        # re-enable the signals since the x and y plots now have the updated data
        self.x_region.blockSignals(False)
        self.y_region.blockSignals(False)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.fit_queue.clear_put(np.empty(0), np.empty(0), '', True)
        self.fit_thread.stop()
        super().closeEvent(event)

    def on_z_change(self, value: int) -> None:
        """Handle when the Z slider changes."""
        self.x_pos = -1
        self.y_pos = -1
        self.z_slider.setToolTip(f'Z={self.data[value][0]} mm')
        self.clear_fit_queue = False
        self.dropEvent()
        self.clear_fit_queue = True

    def on_roi_changed(self, *ignore) -> None: # noqa
        """Handle when the RectROI changes."""
        if self.canvas.image is None:
            return
        array = self.rect_roi.getArrayRegion(self.canvas.image, self.canvas)
        rsd = f'{std_relative(array.flatten()):.3%}'
        diff = np.amax(array) - np.amin(array)
        width, height = array.shape
        mm_x = self.dx * width
        mm_y = self.dy * height
        html = f'ROI {mm_x:g} x {mm_y:g} mm, &sigma;<sub>rel</sub>={rsd}, max-min={diff}'
        text = QtGui.QTextDocument()
        text.setHtml(html)
        self.roi_label.setText(text.toPlainText())
        self.roi_label.adjustSize()
        fm = self.fontMetrics()
        self.roi_label.setFixedSize(fm.horizontalAdvance(html)+8, fm.height())

    def on_mouse_moved(self, point: QtCore.QPointF) -> None:
        """Handle a mouse-moved event."""
        p = self.view_box.mapSceneToView(point)
        if self.filename and self.canvas.image is not None and \
                (0 <= p.x() < self.canvas.width()) and (0 <= p.y() < self.canvas.height()):
            ix, iy = int(p.x()), int(p.y())
            try:
                x = self.x_unique[ix]
                y = self.y_unique[iy]
                z = self.data[self.z_slider.value()][0]
                v = self.canvas.image[ix, iy]
                self.pos_label.setText(f'({x:.3f}, {y:.3f}, {z:.3f}) = {v:.6f}')
            except IndexError:
                self.pos_label.setText('')
        else:
            self.pos_label.setText('')

    def load_data(self, path: str) -> None:
        self.data.clear()
        if path.endswith('.xml'):
            # KRISS format
            urn = '{urn:schemas-microsoft-com:office:spreadsheet}'
            root = ElementTree().parse(path)
            table = root.find(f'.//{urn}Worksheet[@{urn}Name="Log"]/{urn}Table')
            data = [tuple(val.text for val in element.findall(f'.//{urn}Cell/{urn}Data'))
                    for element in table if element.tag.endswith('Row')]
            dtype = [('timestamp', 'S23'), ('x', '<f8'), ('y', '<f8'),
                     ('signal', '<f8'), ('std', '<f8'), ('navg', '<f8')]
            # each Z position is in a separate file, so read the value from the filename
            found = re.search(r'at(?P<z>[\d.]+)', path)
            z = 0 if found is None else float(found['z'])
            self.data[0] = (z, np.asarray(data[1:], dtype=dtype))
            self.z_slider.setMaximum(0)
        elif path.endswith('.json'):
            # MSL format
            root = read(path)
            datasets = [dset.name for dset in root.datasets() if dset.name.startswith('/spatial_scan')]
            if len(datasets) > 1:
                scan = root[prompt.item('Select a dataset', items=datasets)]
            else:
                scan = root[datasets[0]]
            # dark_mon = (scan.metadata.dark_before.mon_ave + scan.metadata.dark_after.mon_ave) * 0.5
            dark_dut = (scan.metadata.dark_before.dut_ave + scan.metadata.dark_after.dut_ave) * 0.5
            signal = (scan.dut - dark_dut)  # / (scan.mon - dark_mon)
            x = np.around(scan.x, decimals=3)
            y = np.around(scan.y, decimals=3)
            z = np.around(scan.z, decimals=3)
            z_unique = np.unique(z)
            for i, z_val in enumerate(z_unique):
                indices = z == z_val
                self.data[i] = (
                    z_val, np.asarray(
                        [items for items in zip(x[indices], y[indices], signal[indices])],
                        dtype=[('x', '<f8'), ('y', '<f8'), ('signal', '<f8')])
                )
            self.z_slider.setMaximum(len(z_unique)-1)

    def update_x_plot(self) -> None:
        if self.canvas.image is None:
            return

        x = int(self.x_line.getXPos())
        if self.x_pos == x:
            return

        if 0 <= x < self.canvas.image.shape[0]:
            self.x_pos = x
            self.fit_queue.clear_put(self.y_unique, self.canvas.image[x, :],
                                     'x', self.clear_fit_queue)
        else:
            self.xclear()

    @Slot(dict)
    def plot_x_or_y(self, result: dict) -> None:
        if result['type'] == 'x':
            self.xclear()
            self.x_fit.setData(result['x_fit'], result['y_fit'])
            self.x_plot.plot(result['x'], result['y'])
            self.x_plot.addItem(self.x_region)
            self.x_plot.addItem(self.x_fit)
            self.x_plot.vb.autoRange()
            self.fit_params_x = result['params']
            self.update_x_title()
        else:
            self.yclear()
            self.y_fit.setData(result['x_fit'], result['y_fit'])
            self.y_plot.plot(result['x'], result['y'])
            self.y_plot.addItem(self.y_region)
            self.y_plot.addItem(self.y_fit)
            self.y_plot.vb.autoRange()
            self.fit_params_y = result['params']
            self.update_y_title()

    def update_y_plot(self) -> None:
        if self.canvas.image is None:
            return

        y = int(self.y_line.getYPos())
        if self.y_pos == y:
            return

        if 0 <= y < self.canvas.image.shape[1]:
            self.y_pos = y
            self.fit_queue.clear_put(self.x_unique, self.canvas.image[:, y],
                                     'y', self.clear_fit_queue)
        else:
            self.yclear()

    def xclear(self) -> None:
        self.x_plot.setTitle('')
        self.x_plot.clear()

    def yclear(self) -> None:
        self.y_plot.setTitle('')
        self.y_plot.clear()

    def update_x_title(self) -> None:
        if not self.x_plot.dataItems:
            return

        mu = self.fit_params_x['mu'].value
        sigma = self.fit_params_x['sigma'].value
        x = self.x_unique[self.x_pos]
        y1, y2 = self.x_region.getRegion()
        signal = self.x_plot.dataItems[0].yData
        array = signal[(self.y_unique >= y1) & (self.y_unique <= y2)]
        rsd = f'{std_relative(array):.3%}'
        yc, yd = 0.5*(y1+y2), y2-y1
        self.x_plot.setTitle(
            f'<html>X={x:.3f}, Fit<sub>&mu;</sub>={mu:.3f}, Fit<sub>&sigma;</sub>={sigma:.3f}, '
            f'Y<sub>centre</sub>={yc:.3f}, &Delta;Y={yd:.3f}, &sigma;<sub>rel</sub>={rsd}</html>'
        )

    def update_y_title(self) -> None:
        if not self.y_plot.dataItems:
            return

        mu = self.fit_params_y['mu'].value
        sigma = self.fit_params_y['sigma'].value
        y = self.y_unique[self.y_pos]
        x1, x2 = self.y_region.getRegion()
        signal = self.y_plot.dataItems[0].yData
        array = signal[(self.x_unique >= x1) & (self.x_unique <= x2)]
        rsd = f'{std_relative(array):.3%}'
        xc, xd = 0.5*(x1+x2), x2-x1
        self.y_plot.setTitle(
            f'<html>Y={y:.3f}, Fit<sub>&mu;</sub>={mu:.3f}, Fit<sub>&sigma;</sub>={sigma:.3f}, '
            f'X<sub>centre</sub>={xc:.3f}, &Delta;X={xd:.3f}, &sigma;<sub>rel</sub>={rsd}</html>'
        )

    def save_canvas_as_csv(self) -> None:
        if not self.filename:
            prompt.warning('No data to save')
            return

        filename = os.path.splitext(self.filename)[0] + '.csv'
        with open(filename, mode='wt') as fp:
            fp.write(f'scale factor,{self.max_signal}\n')
            fp.write('X/Y,' + ','.join(f'{x:.3f}' for x in self.x_unique) + '\n')
            for y, row in zip(self.y_unique, self.canvas.image.T):
                fp.write(f'{y:.3f},' + ','.join(f'{v:.6f}' for v in row) + '\n')

        prompt.information(f'Saved image data to\n{filename}')

    def save_as_jpeg(self) -> None:
        if not self.filename:
            prompt.warning('A file has not been loaded yet')
        else:
            filename = os.path.splitext(self.filename)[0] + '.jpeg'
            self.grab().toImage().save(filename)
            prompt.information(f'Saved image to\n{filename}')

    def save_xplot_as_csv(self) -> None:
        if not self.x_plot.items:
            prompt.warning('No data to save')
        else:
            x = re.search(r'X=(\d+\.\d+),', self.x_plot.titleLabel.text).group(1)
            self.save_plot_as_csv('X', x, self.x_plot.items[0].getData())

    def save_yplot_as_csv(self) -> None:
        if not self.y_plot.items:
            prompt.warning('No data to save')
        else:
            y = re.search(r'Y=(\d+\.\d+),', self.y_plot.titleLabel.text).group(1)
            self.save_plot_as_csv('Y', y, self.y_plot.items[0].getData())

    def save_plot_as_csv(self, axis, value, data):
        print(axis, value, data)
        filename = os.path.splitext(self.filename)[0] + f'_{axis}={value}mm.csv'
        xy = 'X' if axis == 'Y' else 'Y'
        positions, signals = data
        with open(filename, mode='wt') as fp:
            fp.write(f'scale factor,{self.max_signal}\n')
            fp.write(f'{axis}[mm],{value}\n')
            fp.write(f'{xy}[mm],normalized\n')
            for p, s in zip(positions, signals):
                fp.write(f'{p},{s}\n')
        prompt.information(f'Saved data to\n{filename}')


class CanvasMenu(QtWidgets.QMenu):

    def __init__(self, parent: Main) -> None:
        super().__init__(parent)

        csv = QtGui.QAction('Save 2D plot as CSV', self)
        csv.triggered.connect(parent.save_canvas_as_csv)  # noqa: QAction.triggered exists
        self.addAction(csv)

        jpeg = QtGui.QAction('Save Window as JPEG', self)
        jpeg.triggered.connect(parent.save_as_jpeg)  # noqa: QAction.triggered exists
        self.addAction(jpeg)


class PlotMenu(QtWidgets.QMenu):

    def __init__(self,
                 parent: Main,
                 csv_callback: Callable[[], None],
                 plot_item: pg.PlotItem) -> None:
        super().__init__(parent)

        reset = QtGui.QAction('Reset view', self)
        reset.triggered.connect(plot_item.vb.autoRange)  # noqa: QAction.triggered exists
        self.addAction(reset)

        self.addSeparator()

        csv = QtGui.QAction('Save plot as CSV', self)
        csv.triggered.connect(csv_callback)  # noqa: QAction.triggered exists
        self.addAction(csv)

        jpeg = QtGui.QAction('Save Window as JPEG', self)
        jpeg.triggered.connect(parent.save_as_jpeg)  # noqa: QAction.triggered exists
        self.addAction(jpeg)


if __name__ == '__main__':
    # shows all unhandled exceptions in a popup window
    sys.excepthook = excepthook

    app = application()
    main = Main()
    main.setWindowTitle('Spatial Scan')
    geo = app.primaryScreen().availableGeometry()
    main.resize(geo.width()*0.6, geo.height()*0.5)
    main.show()
    sys.exit(app.exec())
