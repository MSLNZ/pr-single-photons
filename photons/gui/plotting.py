import os

import numpy as np
import pyqtgraph as pg
from msl.io import read
from msl.qt import (
    Qt,
    QtWidgets,
    DoubleSpinBox,
    Button,
    convert,
    utils,
    prompt,
)

windows = []


class Plot(QtWidgets.QWidget):

    def __init__(self, root=None):
        """Create a widget for showing 2D data and metadata.

        Parameters
        ----------
        root : :class:`~msl.io.base_io.Root`, optional
            A root object.
        """
        super(Plot, self).__init__()

        self._log_table = None
        self.setAcceptDrops(True)
        self.setWindowTitle('Drag and drop a data file')

        self._root_metadata = Metadata(tooltip='Metadata of the root /')
        self._dset_metadata = Metadata(tooltip='Metadata of the dataset')
        self._meta_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self._meta_splitter.addWidget(self._root_metadata)
        self._meta_splitter.addWidget(self._dset_metadata)

        self._scatter_plot = ScatterPlot(self)

        self._dset_combobox = QtWidgets.QComboBox()
        self._dset_combobox.currentTextChanged.connect(self.on_dataset_changed)

        self._clear_checkbox = QtWidgets.QCheckBox()
        self._clear_checkbox.setToolTip('Auto remove plots')
        self._clear_checkbox.setChecked(True)

        self._screenshot_button = Button(
            icon=convert.to_qicon('imageres|52'),
            icon_size=self._dset_combobox.sizeHint().height()*3//4,
            left_click=self.on_screenshot,
            tooltip='Save screenshot'
        )

        self._clear_button = Button(
            icon=QtWidgets.QStyle.SP_DialogResetButton,
            icon_size=self._dset_combobox.sizeHint().height()*3//4,
            left_click=self.on_clear_plot,
            tooltip='Clear plot'
        )

        hbox = QtWidgets.QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self._dset_combobox)
        hbox.addWidget(self._screenshot_button)
        hbox.addWidget(self._clear_button)
        hbox.addWidget(self._clear_checkbox)

        plot_layout = QtWidgets.QVBoxLayout()
        plot_layout.addLayout(hbox)
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

        geo = utils.screen_geometry(self)
        self.resize(geo.width()//2, geo.height()//2)

        self._root = root
        self._drag_drop_root = None
        if root is not None:
            self.on_new_root()

    def dragEnterEvent(self, event) -> None:
        """Overrides :meth:`QtWidgets.QWidget.dragEnterEvent`."""
        paths = utils.drag_drop_paths(event)
        if paths:
            try:
                self._drag_drop_root = read(paths[0])
                event.accept()
            except IOError:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        """Overrides :meth:`QtWidgets.QWidget.dropEvent`."""
        if self._root is None:
            self._root = self._drag_drop_root
            self.on_new_root()
        else:
            p = Plot(self._drag_drop_root)
            p.show()
            windows.append(p)
        event.accept()

    def on_new_root(self) -> None:
        """A new :class:`~msl.io.base_io.Root` has been dropped."""
        self._dset_combobox.blockSignals(True)
        self._dset_combobox.clear()
        name = ''
        for dset in self._root.datasets():
            if not name and dset.name != '/log':
                name = dset.name
            self._dset_combobox.addItem(dset.name)
        self._dset_combobox.setCurrentText(name)
        self._dset_combobox.blockSignals(False)
        self.on_dataset_changed(name)
        self._root_metadata.add(self._root.metadata)

    def on_dataset_changed(self, name: str) -> None:
        """Slot for the dataset :meth:`QtWidgets.QComboBox.currentTextChanged` signal."""
        dset = self._root[name]
        if dset.name == '/log':
            self._log_table = LogTable(dset, self._root.file)
        else:
            self._scatter_plot.set_dataset(dset)
        self._dset_metadata.add(dset.metadata)
        self._dset_metadata.setToolTip(f'Metadata of {dset.name}')
        self.setWindowTitle(self._root.file)

    def on_clear_plot(self) -> None:
        """Slot for a clear-Button click."""
        self._scatter_plot.clear()

    def on_screenshot(self) -> None:
        """Slot for a screenshot-Button click."""
        start_in = os.path.dirname(self.windowTitle())
        filename = prompt.save(filters='Images (*.png *.jpg *.jpeg *.bmp)', directory=start_in)
        if filename:
            utils.save_image(self, filename)

    def clear_plot(self) -> bool:
        """:class:`bool`: Whether the plots should be cleared."""
        return self._clear_checkbox.isChecked()


class TableDelegate(QtWidgets.QItemDelegate):

    def __init__(self, parent):
        """Allows for a QTableWidgetItem to be selectable while also in read-only mode."""
        super(TableDelegate, self).__init__(parent=parent)

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QLineEdit(parent=parent)
        editor.setFrame(False)
        editor.setReadOnly(True)
        return editor


class Table(QtWidgets.QTableWidget):

    def __init__(self, rows=0, header=None, parent=None, tooltip=None):
        h = header or []
        super(Table, self).__init__(rows, len(h), parent=parent)
        self.setHorizontalHeaderLabels(h)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)
        self.setItemDelegate(TableDelegate(self))
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        if tooltip:
            self.setToolTip(tooltip)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Up or key == Qt.Key_Down or key == Qt.Key_PageUp or key == Qt.Key_PageDown:
            super(Table, self).keyPressEvent(event)
        else:
            event.ignore()

    def resize_vertical_header(self, factor=1.4):
        width = self.fontMetrics().horizontalAdvance(str(self.rowCount()))
        self.verticalHeader().setFixedWidth(int(width*factor))


class Metadata(Table):

    def __init__(self, parent=None, tooltip=None):
        super(Metadata, self).__init__(header=('name', 'value'), parent=parent, tooltip=tooltip)

    def add(self, metadata):
        self.setSortingEnabled(False)
        self.setRowCount(len(metadata))
        for i, (key, value) in enumerate(metadata.items()):
            self.setItem(i, 0, QtWidgets.QTableWidgetItem(key))
            self.setItem(i, 1, QtWidgets.QTableWidgetItem(str(value)))
        self.resizeColumnsToContents()
        self.setSortingEnabled(True)
        self.resize_vertical_header()


class LogTable(Table):

    def __init__(self, log_dataset, title):
        super(LogTable, self).__init__(rows=log_dataset.size, header=log_dataset.dtype.names)
        colors = {
            'NOTSET': convert.to_qcolor('white'),
            'DEBUG': convert.to_qcolor('lightslategrey'),
            'INFO': convert.to_qcolor('black'),
            'WARNING': convert.to_qcolor('darkgoldenrod'),
            'ERROR': convert.to_qcolor('darkred'),
            'CRITICAL': convert.to_qcolor('red')
        }
        self.setWindowTitle(title)
        for row, values in enumerate(log_dataset):
            color = colors[values['levelname'] or 'NOTSET']
            for col, val in enumerate(values):
                item = QtWidgets.QTableWidgetItem(val)
                item.setForeground(color)
                self.setItem(row, col, item)
        self.resizeColumnsToContents()
        self.setSortingEnabled(True)
        geo = utils.screen_geometry(self)
        self.resize(geo.width()//4, geo.height()//4)
        self.resize_vertical_header()
        self.show()


class ScatterPlot(QtWidgets.QWidget):

    def __init__(self, parent):
        """A scatter-plot widget.

        Parameters
        ----------
        parent : :class:`.Plot`
            The main plotting widget.
        """
        super(ScatterPlot, self).__init__(parent=parent)
        self._dataset = None
        self._parent = parent

        self._plot_widget = pg.PlotWidget(parent=self)
        self._plot_widget.addLegend()

        self._x_combobox = QtWidgets.QComboBox()
        self._x_combobox.currentTextChanged.connect(self.redraw)
        self._x_combobox.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self._y_combobox = QtWidgets.QComboBox()
        self._y_combobox.currentTextChanged.connect(self.redraw)
        self._y_combobox.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)

        self._x_scaling = DoubleSpinBox(
            value=1, maximum=1e20, use_si_prefix=True, tooltip='X scaling factor'
        )
        self._x_scaling.editingFinished.connect(self.redraw)

        self._y_scaling = DoubleSpinBox(
            value=1, maximum=1e20, use_si_prefix=True, tooltip='Y scaling factor'
        )
        self._y_scaling.editingFinished.connect(self.redraw)

        self._y_minimum = DoubleSpinBox(
            value=0, maximum=1e20, decimals=2, use_si_prefix=True, tooltip='Minimum value'
        )
        self._y_minimum.setDisabled(True)
        self._y_minimum.editingFinished.connect(self.redraw)

        self._y_maximum = DoubleSpinBox(
            value=1, maximum=1e20, decimals=2, use_si_prefix=True, tooltip='Maximum value'
        )
        self._y_maximum.setDisabled(True)
        self._y_maximum.editingFinished.connect(self.redraw)

        self._y_range_checkbox = QtWidgets.QCheckBox()
        self._y_range_checkbox.setChecked(False)
        self._y_range_checkbox.setToolTip('Enable the min/max filter')
        self._y_range_checkbox.stateChanged.connect(self.on_y_range_combobox_clicked)

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

    def clear(self):
        """Clear all plots."""
        self._plot_widget.clear()

    def set_dataset(self, dataset):
        self._dataset = dataset
        x_text, y_text = self._x_combobox.currentText(), self._y_combobox.currentText()
        self._x_combobox.clear()
        self._y_combobox.clear()
        if dataset.dtype.fields is not None:
            names = [name for name, typ in dataset.dtype.fields.items() if typ[0].kind in 'iuf']
        else:
            names = []
        self._x_combobox.blockSignals(True)
        self._x_combobox.addItems(names)
        if x_text in names:
            self._x_combobox.setCurrentText(x_text)
        self._x_combobox.blockSignals(False)
        self._y_combobox.blockSignals(True)
        self._y_combobox.addItems(names)
        if y_text in names:
            self._y_combobox.setCurrentText(y_text)
        self._y_combobox.blockSignals(False)
        self.redraw()

    def redraw(self, *ignore):
        x_text, y_text = self._x_combobox.currentText(), self._y_combobox.currentText()
        if not x_text or not y_text:
            return

        x = self._dataset[x_text] * self._x_scaling.value()
        y = self._dataset[y_text] * self._y_scaling.value()

        if self._y_range_checkbox.isChecked():
            indices = np.logical_and(self._y_minimum.value() <= y, y <= self._y_maximum.value())
            x = x[indices]
            y = y[indices]

        if self._parent.clear_plot():
            self.clear()

        n = len(self._plot_widget.listDataItems())
        item = self._plot_widget.plot(
            x=x, y=y, pen=n, symbolBrush=n, symbol='o',
            antialias=True, name=self._dataset.name,
        )
        item.scatter.opts['hoverable'] = True
        item.scatter.opts['tip'] = ScatterPlot.on_hover

        if not self._y_range_checkbox.isChecked():
            xrange, yrange = self._plot_widget.getPlotItem().viewRange()
            self._y_minimum.setValue(yrange[0])
            self._y_maximum.setValue(yrange[1])

    @staticmethod
    def on_hover(x=None, y=None, data=None):
        if data is None:
            return f'x={x}\ny={y}'
        return f'x={x}\ny={y}\ndata={data}'

    def on_y_range_combobox_clicked(self, state):
        enabled = bool(state)
        self._y_minimum.setEnabled(enabled)
        self._y_maximum.setEnabled(enabled)
        self.redraw()
