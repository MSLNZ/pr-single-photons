"""
Plot widget.
"""
import os
from datetime import datetime
from math import isfinite
from time import monotonic
from typing import Callable
from typing import Sequence

import numpy as np
import pyqtgraph as pg
from msl.io import Root
from msl.io import read
from msl.io.dataset import Dataset
from msl.io.metadata import Metadata
from msl.qt import Button
from msl.qt import CheckBox
from msl.qt import ComboBox
from msl.qt import DoubleSpinBox
from msl.qt import Qt
from msl.qt import QtCore
from msl.qt import QtGui
from msl.qt import QtWidgets
from msl.qt import Signal
from msl.qt import Slot
from msl.qt import convert
from msl.qt import prompt
from msl.qt import utils

from .samples import Samples


class BaseTable(QtWidgets.QTableWidget):

    def __init__(self,
                 rows: int = 0,
                 header: Sequence[str] = None,
                 parent: QtWidgets.QWidget = None,
                 tooltip: str = None) -> None:
        """Custom table that has text-selectable, read-only cells."""
        h = header or []
        super().__init__(rows, len(h), parent=parent)
        self.setHorizontalHeaderLabels(h)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)
        self.setItemDelegate(BaseTableDelegate(self))
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        if tooltip:
            self.setToolTip(tooltip)

    def resize_row_column(self, factor: float = 1.5) -> None:
        """Resize the width of the row-indicator column (the first column)."""
        width = max(10, self.fontMetrics().horizontalAdvance(str(self.rowCount())))
        self.verticalHeader().setFixedWidth(int(width*factor))


class BaseTableDelegate(QtWidgets.QItemDelegate):

    def __init__(self, parent: BaseTable) -> None:
        """Allows for a table cell to be selectable and read only."""
        super().__init__(parent=parent)

    def createEditor(self,
                     parent: QtWidgets.QWidget,
                     option: QtWidgets.QStyleOptionViewItem,
                     index: QtCore.QModelIndex) -> QtWidgets.QLineEdit:
        """Overrides :meth:`QtWidgets.QAbstractItemDelegate.createEditor`."""
        editor = QtWidgets.QLineEdit(parent=parent)
        editor.setFrame(False)
        editor.setReadOnly(True)
        return editor


class LogTable(BaseTable):

    COLORS: dict[str, QtGui.QColor] = {
        'NOTSET': convert.to_qcolor('white'),
        'DEBUG': convert.to_qcolor('lightslategrey'),
        'INFO': convert.to_qcolor('black'),
        'WARNING': convert.to_qcolor('darkgoldenrod'),
        'ERROR': convert.to_qcolor('darkred'),
        'CRITICAL': convert.to_qcolor('red')
    }

    def __init__(self, log_dataset: Dataset, title: str) -> None:
        """Display the logging records in a table."""
        super().__init__(rows=log_dataset.size, header=log_dataset.dtype.names)
        for i, row in enumerate(log_dataset):
            color = LogTable.COLORS[row['levelname'] or 'NOTSET']
            for j, text in enumerate(row):
                item = QtWidgets.QTableWidgetItem(text)
                item.setForeground(color)
                self.setItem(i, j, item)
        self.setWindowTitle(title)
        self.resizeColumnsToContents()
        self.setSortingEnabled(True)
        geo = utils.screen_geometry(self)
        self.resize(geo.width()//4, geo.height()//4)
        self.resize_row_column()
        self.show()


class MetadataTable(BaseTable):

    def __init__(self, tooltip: str = None) -> None:
        """Display metadata in a table."""
        super().__init__(header=('name', 'value'), tooltip=tooltip)

    def add(self, metadata: Metadata) -> None:
        """Add a row to the table."""
        self.setSortingEnabled(False)
        self.setRowCount(len(metadata))
        for i, (key, value) in enumerate(metadata.items()):
            self.setItem(i, 0, QtWidgets.QTableWidgetItem(key))
            self.setItem(i, 1, QtWidgets.QTableWidgetItem(str(value)))
        self.resizeColumnsToContents()
        self.setSortingEnabled(True)
        self.resize_row_column()


class Plot(QtWidgets.QWidget):

    def __init__(self,
                 root: Root = None,
                 parent: QtWidgets.QWidget = None,
                 **kwargs) -> None:
        """A widget for plotting 2D data and displaying metadata.

        Args:
            root: A Root object.
            parent: The parent widget.
            **kwargs: All keyword arguments are passed to super().
        """
        super().__init__(parent=parent, **kwargs)

        self._log_table: LogTable | None = None
        self._root_metadata = MetadataTable(tooltip='Metadata of the root /')
        self._dset_metadata = MetadataTable(tooltip='Metadata of the dataset')
        self._meta_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self._meta_splitter.addWidget(self._root_metadata)
        self._meta_splitter.addWidget(self._dset_metadata)

        self._scatter_plot = ScatterPlot(self)

        self._dset_combobox = ComboBox(
            tooltip='Select a Dataset',
            text_changed=self.on_dataset_changed,
        )

        self._clear_checkbox = CheckBox(
            initial=True,
            tooltip='Auto remove plots',
        )

        self._screenshot_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DesktopIcon,
            icon_size=self._dset_combobox.sizeHint().height()*3//4,
            left_click=self.on_screenshot,
            tooltip='Save screenshot'
        )

        self._clear_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogResetButton,
            icon_size=self._dset_combobox.sizeHint().height()*3//4,
            left_click=self.on_clear_plot,
            tooltip='Clear plot'
        )

        self._replot_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_BrowserReload,
            icon_size=self._dset_combobox.sizeHint().height()*3//4,
            left_click=self.on_replot,
            tooltip='Replot'
        )

        box = QtWidgets.QHBoxLayout()
        box.addStretch()
        box.addWidget(self._dset_combobox)
        box.addWidget(self._replot_button)
        box.addWidget(self._screenshot_button)
        box.addWidget(self._clear_button)
        box.addWidget(self._clear_checkbox)

        plot_layout = QtWidgets.QVBoxLayout()
        plot_layout.addLayout(box)
        plot_layout.addWidget(self._scatter_plot)

        self._plot_widget = QtWidgets.QWidget()
        self._plot_widget.setLayout(plot_layout)

        self._main_splitter = QtWidgets.QSplitter()
        self._main_splitter.addWidget(self._plot_widget)
        self._main_splitter.addWidget(self._meta_splitter)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 0)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._main_splitter)
        self.setLayout(layout)

        self.setAcceptDrops(True)
        self.setWindowTitle('Drag and drop a data file')

        geo = utils.screen_geometry(self)
        self.resize(geo.width()//2, geo.height()//2)

        self._root: Root = root
        self._drag_drop_root = None
        if root is not None:
            self.new_root()

        plots.append(self)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.dragEnterEvent`."""
        paths = utils.drag_drop_paths(event)
        if paths:
            try:
                self._drag_drop_root = read(paths[0])
                event.accept()
            except OSError:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.dropEvent`."""
        if self._root is None:
            # the Plot is currently empty
            self._root = self._drag_drop_root
            self.new_root()
        else:
            p = Plot(self._drag_drop_root)
            p.show()
        event.accept()

    def new_root(self) -> None:
        """A new :class:`~msl.io.base.Root` has been dropped."""
        previous = self._dset_combobox.blockSignals(True)
        self._dset_combobox.clear()
        name = ''
        for dset in self._root.datasets():
            if not name and dset.name != '/log':
                name = dset.name
            self._dset_combobox.addItem(dset.name)
        self._dset_combobox.setCurrentText(name)
        self._dset_combobox.blockSignals(previous)
        self.on_dataset_changed(name)
        self._root_metadata.add(self._root.metadata)

    @Slot()
    def on_clear_plot(self) -> None:
        """Clear the scatter plot."""
        self._scatter_plot.clear()

    @Slot(str)
    def on_dataset_changed(self, name: str) -> None:
        """A new dataset was selected."""
        dset: Dataset = self._root[name]
        if dset.name == '/log':
            self._log_table = LogTable(dset, self._root.file)
        else:
            self._scatter_plot.set_dataset(dset)
        self._dset_metadata.add(dset.metadata)
        self._dset_metadata.setToolTip(f'Metadata of {dset.name}')
        self.setWindowTitle(self._root.file)

    @Slot()
    def on_replot(self) -> None:
        """Replot the currently-selected data."""
        self._scatter_plot.redraw()

    @Slot()
    def on_screenshot(self) -> None:
        """Save a screenshot of the Plot widget."""
        filename = prompt.save(
            filters='Images (*.png *.jpg *.jpeg *.bmp)',
            directory=os.path.dirname(self.windowTitle()),
        )
        if filename:
            utils.save_image(self, filename)

    def should_clear_plot(self) -> bool:
        """Whether the plots should be cleared."""
        return self._clear_checkbox.isChecked()


class ScatterPlot(QtWidgets.QWidget):

    def __init__(self, parent: Plot) -> None:
        """A scatter-plot for a 2D dataset."""
        super().__init__(parent=parent)
        self._dataset = None
        self._parent = parent

        self._plot_widget = pg.PlotWidget(parent=self)
        self._plot_widget.addLegend()

        self._x_combobox = ComboBox(text_changed=self.redraw)
        self._x_combobox.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._y_combobox = ComboBox(text_changed=self.redraw)
        self._y_combobox.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)

        self._x_scaling = DoubleSpinBox(
            value=1,
            maximum=1e20,
            use_si_prefix=True,
            tooltip='X scaling factor',
            editing_finished=self.redraw,
        )

        self._y_scaling = DoubleSpinBox(
            value=1,
            minimum=-1e20,
            maximum=1e20,
            use_si_prefix=True,
            tooltip='Y scaling factor',
            editing_finished=self.redraw,
        )

        self._y_minimum = DoubleSpinBox(
            value=0,
            minimum=-1e20,
            maximum=1e20,
            decimals=2,
            use_si_prefix=True,
            tooltip='Minimum value',
            editing_finished=self.redraw,
        )
        self._y_minimum.setDisabled(True)

        self._y_maximum = DoubleSpinBox(
            value=1,
            minimum=-1e20,
            maximum=1e20,
            decimals=2,
            use_si_prefix=True,
            tooltip='Maximum value',
            editing_finished=self.redraw,
        )
        self._y_maximum.setDisabled(True)

        self._y_range_checkbox = CheckBox(
            initial=False,
            tooltip='Enable the min/max filter',
            state_changed=self.on_y_range_checkbox_clicked,
        )

        y_range_layout = QtWidgets.QHBoxLayout()
        y_range_layout.addWidget(self._y_minimum)
        y_range_layout.addWidget(self._y_maximum)
        y_range_layout.addWidget(self._y_range_checkbox)

        y_layout = QtWidgets.QVBoxLayout()
        y_layout.addWidget(self._y_combobox)
        y_layout.addWidget(self._y_scaling)
        y_layout.addLayout(y_range_layout)
        y_layout.addStretch()

        x_layout = QtWidgets.QHBoxLayout()
        x_layout.addStretch()
        x_layout.addWidget(self._x_combobox)
        x_layout.addWidget(self._x_scaling)

        layout = QtWidgets.QGridLayout()
        layout.addLayout(y_layout, 0, 0)
        layout.addWidget(self._plot_widget, 0, 1)
        layout.addLayout(x_layout, 1, 1)
        layout.setColumnStretch(1, 1)
        self.setLayout(layout)

    def clear(self) -> None:
        """Clear all plots."""
        self._plot_widget.clear()

    @staticmethod
    def hovering(x_text: str) -> Callable[[float, float, float | None], str]:
        """Callback function for a mouse hover."""
        def hover(x: float, y: float, data: float = None) -> str:
            assert data is None  # only plotting 2D data
            if x_text == 'timestamp':
                return f'x={datetime.fromtimestamp(x)}\ny={y:.6g}'
            else:
                return f'x={x:.6g}\ny={y:.6g}'
        return hover

    @Slot(int)
    def on_y_range_checkbox_clicked(self, state: int) -> None:
        """Enable or disable the min-max widgets for the Y axis."""
        enabled = state == Qt.Checked
        self._y_minimum.setEnabled(enabled)
        self._y_maximum.setEnabled(enabled)
        self.redraw()

    @Slot(str)
    def redraw(self, ignore: str = None) -> None:  # noqa: Parameter 'ignore' value is not used
        """Redraw the plot."""
        if self._dataset is None or self._dataset.size == 0:
            return

        x_text = self._x_combobox.currentText()
        y_text = self._y_combobox.currentText()

        if x_text and y_text:
            x = self._dataset[x_text].copy()
            y = self._dataset[y_text].copy()
        elif self._dataset.ndim == 1:
            x = np.arange(self._dataset.size, dtype=float)
            y = self._dataset
        elif self._dataset.shape[0] == 2:
            x = self._dataset[0, :]
            y = self._dataset[1, :]
        elif self._dataset.shape[1] == 2:
            x = self._dataset[:, 0]
            y = self._dataset[:, 1]
        else:
            raise ValueError(f'Invalid Dataset with shape {self._dataset.shape}')

        y_min = y.min()
        y_max = y.max()

        if x_text == 'timestamp':
            iso = datetime.fromisoformat
            x = np.asarray([iso(s).timestamp() for s in x])
            self._plot_widget.setAxisItems({'bottom': pg.DateAxisItem(orientation='bottom')})
        else:
            self._plot_widget.setAxisItems({'bottom': pg.AxisItem(orientation='bottom')})  # reset

        # Do not use "x *= " and "y *= " to avoid getting an error like:
        #   Cannot cast ufunc 'multiply' output from dtype('float64') to
        #   dtype('uint64') with casting rule 'same_kind'
        x = x * self._x_scaling.value()
        y = y * self._y_scaling.value()

        if self._y_range_checkbox.isChecked():
            indices = np.logical_and(self._y_minimum.value() <= y,
                                     y <= self._y_maximum.value())
            x = x[indices]
            y = y[indices]

        if self._parent.should_clear_plot():
            self.clear()

        legend_name = self._dataset.name
        if y_text:
            legend_name += f' [{y_text}]'

        n = len(self._plot_widget.listDataItems())
        item = self._plot_widget.plot(
            x=x, y=y, pen=n, symbolBrush=n, symbol='o',
            antialias=True, name=legend_name,
        )
        item.scatter.opts['hoverable'] = True
        item.scatter.opts['tip'] = ScatterPlot.hovering(x_text)

        if not self._y_range_checkbox.isChecked():
            self._y_minimum.setValue(y_min)
            self._y_maximum.setValue(y_max)

    def set_dataset(self, dataset: Dataset) -> None:
        """A different dataset was selected in the combobox."""
        self._dataset = dataset
        x_text = self._x_combobox.currentText()
        y_text = self._y_combobox.currentText()

        x_previous = self._x_combobox.blockSignals(True)
        y_previous = self._y_combobox.blockSignals(True)

        self._x_combobox.clear()
        self._y_combobox.clear()
        if dataset.dtype.fields is not None:
            names = [name for name, typ in dataset.dtype.fields.items()
                     if typ[0].kind in 'iuf']
            if 'timestamp' in dataset.dtype.fields:
                self._x_combobox.addItem('timestamp')
        else:
            names = []

        self._x_combobox.addItems(names)
        if x_text in names:
            self._x_combobox.setCurrentText(x_text)

        self._y_combobox.addItems(names)
        if y_text in names:
            self._y_combobox.setCurrentText(y_text)

        self._x_combobox.blockSignals(x_previous)
        self._y_combobox.blockSignals(y_previous)
        self.redraw()


class RealTimePlot(QtWidgets.QWidget):

    closing: QtCore.SignalInstance = Signal()
    """Emitted when the widget closes."""

    def __init__(self,
                 *,
                 error_options: dict = None,
                 plot_options: dict = None,
                 signaler: QtCore.SignalInstance = None,
                 size: int = 10000,
                 title: str = None) -> None:
        """Plot data in real time.

        Args:
            error_options: Options passed to :class:`~pyqtgraph.ErrorBarItem`.
                If not specified, default options are used.
            plot_options: Options passed to :class:`~pyqtgraph.PlotItem`.
                If not specified, default options are used.
            signaler: The Qt signal that emits :class:`~photons.samples.Samples`.
            size: The maximum number of data points that can be shown. When the
                number of data points exceeds this value the latest data point
                is shown and the oldest data point is removed.
            title: The text to display in the titlebar of the widget.
        """
        super().__init__()
        self._signaler = signaler
        if signaler is not None:
            signaler.connect(self.update)

        if not error_options:
            error_options = {'beam': 0.5, 'pen': pg.mkPen(color='#bdb76b', width=2)}

        if not plot_options:
            plot_options = {'symbol': 'o', 'pen': pg.mkPen(color=0.8, width=2)}

        self._index = -1
        self._x0 = monotonic()
        self._x = np.empty(size)
        self._y = np.empty(size)
        self._dy = np.empty(size)

        self._widget = pg.PlotWidget(self)
        self._error = pg.ErrorBarItem(**error_options)
        self._plot = self._widget.plot(**plot_options)
        self._widget.addItem(self._error)
        self._widget.setLabel('bottom', 'Time [s]')

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.resize(300, 300)
        self.setWindowTitle(title or self.__class__.__name__)

    def clear(self) -> None:
        """Clear the plot."""
        self._index = -1
        self._x0 = monotonic()
        self._x[:] = 0
        self._y[:] = 0
        self._dy[:] = 0
        empty = np.empty(0)
        self._plot.setData(x=empty, y=empty)
        self._error.setData(x=empty, y=empty, top=empty, bottom=empty)
        self._error.setVisible(False)

    @Slot(Samples)
    def update(self, samples: Samples) -> None:
        """Update the plot.

        If a `signaler` is specified when this class is instantiated, this method
        `(slot)` is called automatically when the `signaler` emits the `samples`.

        Args:
            samples: The data to add to the plot. The standard deviation of the
                mean is used as the error bar.
        """
        self._index += 1
        if self._index == self._x.size:
            self._x = np.roll(self._x, -1)
            self._y = np.roll(self._y, -1)
            self._dy = np.roll(self._dy, -1)
            self._index -= 1

        i = self._index
        self._x[i] = monotonic() - self._x0
        self._y[i] = samples.mean
        self._dy[i] = samples.stdom

        i += 1
        x = self._x[:i]
        y = self._y[:i]
        dy = self._dy[:i]

        # need at least 2 data points to connect the points with a line
        if i > 1:
            self._plot.setData(x=x, y=y)
            if isfinite(samples.stdom):
                self._error.setData(x=x, y=y, top=dy, bottom=dy)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.closeEvent`.

        Disconnect from the `signaler` (if one was specified), removes items
        from the plot and emits the :attr:`.closing` signal.
        """
        if self._signaler is not None:
            self._signaler.disconnect(self.update)
        self._widget.close()
        self.closing.emit()
        super().closeEvent(event)


plots: list[Plot] = []
