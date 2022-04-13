"""
The main window for the GUI.
"""
from msl.qt import (
    QtWidgets,
    QtGui,
    Qt,
    Signal,
    convert,
    prompt,
    application,
)
from msl.qt.utils import (
    screen_geometry,
    drag_drop_paths,
)
from msl.io import read

from .line_edit import LineEdit
from .. import logger
from .equipment import (
    widgets,
    find_widget,
)
from ..plugins import plugins
from .network import (
    StartManager,
    CreateClient,
    StartEquipmentService,
    StartService,
)


class MainWindow(QtWidgets.QMainWindow):

    update_progress_bar = Signal(float)  # a value in the range [0, 100]
    show_indeterminate_progress_bar = Signal()
    hide_progress_bar = Signal()
    status_bar_message = Signal(str)  # the message

    def __init__(self, app, **kwargs):
        """Create the main application widget.

        Parameters
        ----------
        app : :class:`~photons.App`
            The application instance.
        kwargs
            Passed to :class:`~QtWidgets.QMainWindow`.
        """
        super(MainWindow, self).__init__(**kwargs)

        self.app = app
        app.added_connection.connect(self.on_added_connection)
        app.removed_connection.connect(self.on_removed_connection)

        # a list of all the docked widgets that are open
        self._docked_widgets = []

        # a list of all the plugins that are open
        self._plugin_widgets = []

        self.setWindowTitle('Single Photons')

        self.setAcceptDrops(True)
        self._drag_drop_root = None

        self.setCorner(Qt.TopLeftCorner, Qt.TopDockWidgetArea)
        self.setCorner(Qt.TopRightCorner, Qt.RightDockWidgetArea)
        self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.BottomDockWidgetArea)

        # add a progress bar to the status bar
        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setAlignment(Qt.AlignCenter)
        self._progress_bar.setRange(0, 100)
        self.statusBar().addPermanentWidget(self._progress_bar)

        # connect the progress bar and status bar signals/slots
        self.update_progress_bar.connect(self.on_update_progress_bar)
        self.show_indeterminate_progress_bar.connect(self.on_show_indeterminate_progress_bar)
        self.hide_progress_bar.connect(self.on_hide_progress_bar)
        self.status_bar_message.connect(self.on_status_bar_message)
        self.hide_progress_bar.emit()

        menubar = self.menuBar()

        # create the File menubar
        exit_action = QtGui.QAction(convert.to_qicon('shell32|41'), 'Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.setToolTip('Exit application')
        exit_action.triggered.connect(self.closeEvent)

        self.file_menu = menubar.addMenu('File')
        self.file_menu.addAction(exit_action)
        self.file_menu.setToolTipsVisible(True)

        # create the Connections menubar
        self.connection_menu = menubar.addMenu('Connections')
        for alias, record in sorted(self.app.equipment.items()):
            if record.connection is not None:
                action = QtGui.QAction(alias, self)
                action.setStatusTip(f'Connect to {record.manufacturer} {record.model}')
                action.setToolTip(f'{record.manufacturer} {record.model}')
                action.setCheckable(True)
                action.triggered.connect(lambda *args, a=action, r=record: self.on_connect_to_equipment(a, r))
                self.connection_menu.addAction(action)
        self.connection_menu.setToolTipsVisible(True)

        # create the Network menubar
        self.network_menu = menubar.addMenu('Network')
        self.network_menu.setToolTipsVisible(True)

        start_manager_action = QtGui.QAction('Start a Manager', self)
        start_manager_action.setStatusTip('Start a Network Manager')
        start_manager_action.setToolTip('Start a Network Manager')
        start_manager_action.triggered.connect(lambda *args: StartManager(self))
        self.network_menu.addAction(start_manager_action)

        start_service_action = QtGui.QAction('Start a Service', self)
        start_service_action.setStatusTip('Start a service')
        start_service_action.setToolTip('Start a service')
        start_service_action.triggered.connect(lambda *args: StartService(self))
        self.network_menu.addAction(start_service_action)

        start_equip_service_action = QtGui.QAction('Start an Equipment Service', self)
        start_equip_service_action.setStatusTip('Start a service that interfaces with equipment')
        start_equip_service_action.setToolTip('Start a service that interfaces with equipment')
        start_equip_service_action.triggered.connect(lambda *args: StartEquipmentService(self))
        self.network_menu.addAction(start_equip_service_action)

        create_client_action = QtGui.QAction('Create a Client', self)
        create_client_action.setStatusTip('Connect to a Network Manager as a Client')
        create_client_action.setToolTip('Connect to a Network Manager as a Client')
        create_client_action.triggered.connect(lambda *args: CreateClient(self))
        self.network_menu.addAction(create_client_action)

        # create the Widgets menubar
        self.widgets_menu = menubar.addMenu('Widgets')
        for alias, record in sorted(self.app.equipment.items()):
            for w in widgets:
                if w.matches(record):
                    if record.connection is not None:
                        action = QtGui.QAction(alias, self)
                        action.setStatusTip(f'Connect to {record.manufacturer} {record.model}')
                        action.setToolTip(f'{record.manufacturer} {record.model}')
                        action.setCheckable(True)
                        action.triggered.connect(lambda *args, a=action, r=record: self.on_show_widget(a, r))
                        self.widgets_menu.addAction(action)
        self.widgets_menu.setToolTipsVisible(True)

        # create the Plugins menubar
        self.plugin_menu = menubar.addMenu('Plugins')
        for cls, name, description in plugins:
            action = QtGui.QAction(name, self)
            action.setStatusTip(description)
            action.setToolTip(description)
            action.setCheckable(True)
            action.triggered.connect(lambda *args, a=action, c=cls, n=name: self.on_show_plugin(a, c, n))
            self.plugin_menu.addAction(action)
        self.plugin_menu.setToolTipsVisible(True)

        self.resize(screen_geometry().width()//4, self.statusBar().size().height())

    def on_added_connection(self, alias):
        """Slot for the :obj:`~photons.app.App.added_connection` signal."""
        for connection_action in self.connection_menu.actions():
            if connection_action.text() == alias:
                connection_action.setChecked(True)
                break

    def on_removed_connection(self, alias):
        """Slot for the :obj:`~photons.app.App.removed_connection` signal."""
        for connection_action in self.connection_menu.actions():
            if connection_action.text() == alias:
                connection_action.setChecked(False)
                break

    def on_update_progress_bar(self, percentage: float) -> None:
        """Slot the self.update_progress_bar.emit signal.

        Call this method if a process completion rate can be determined.
        Automatically makes the progress bar visible if it isn't already visible.

        Parameters
        ----------
        percentage : :class:`float`
            A value in the range [0, 100] that shows the status of a process.
        """
        if not self._progress_bar.isVisible():
            self._progress_bar.setMaximum(100)
            self._progress_bar.show()
        self._progress_bar.setValue(percentage)

    def on_show_indeterminate_progress_bar(self) -> None:
        """Slot for the self.show_indeterminate_progress_bar signal.

        Call this method if a process completion rate is unknown or if it is
        not necessary to indicate how long the process will take.
        """
        self._progress_bar.setMaximum(0)
        self._progress_bar.show()

    def on_hide_progress_bar(self) -> None:
        """Slot for the self.hide_progress_bar signal.

        Hide the progress bar.
        """
        self._progress_bar.hide()

    def on_status_bar_message(self, message) -> None:
        """Slot for the self.status_bar_message signal.

        Display a message in the status bar.

        Parameters
        ----------
        message : :class:`str`
            The message to display.
        """
        self.statusBar().showMessage(message)

    def on_connect_to_equipment(self, action, record) -> None:
        """Slot -> Connect/Disconnect to/from the equipment.

        Parameters
        ----------
        action : :class:`QtGui.QAction`
            The menu action.
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment equipment_record.
        """
        if action.isChecked():
            self.status_bar_message.emit(f'Connecting to {record.alias!r}...')
            self.show_indeterminate_progress_bar.emit()
            application().processEvents()
            try:
                self.app.connect_equipment(record.alias)
            except:
                action.setChecked(False)
                raise
            finally:
                self.status_bar_message.emit('')
                self.hide_progress_bar.emit()
        else:
            self.app.disconnect_equipment(record.alias)

    def on_show_widget(self, action, record) -> None:
        """Slot -> Show the widget for the equipment record.

        Parameters
        ----------
        action : :class:`QtGui.QAction`
            The menu action.
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment equipment_record.
        """
        if not action.isChecked():
            # if it was unchecked while the widget is visible then we want to re-check
            # the action in the menu and make the widget active
            action.setChecked(True)
            for dock in self._docked_widgets:
                if dock.widget().record is record:
                    dock.setWindowState(Qt.WindowActive)
                    dock.activateWindow()
                    dock.show()
                    break
            return

        for w in widgets:
            if w.matches(record):
                self.status_bar_message.emit(f'Creating widget for {record.alias!r}...')
                self.show_indeterminate_progress_bar.emit()
                application().processEvents()
                try:
                    connection = self.app.connect_equipment(record.alias)
                except:
                    action.setChecked(False)
                    raise
                else:
                    dock = QtWidgets.QDockWidget(self)
                    dock.setAllowedAreas(Qt.AllDockWidgetAreas)
                    widget = w.cls(connection, parent=dock)
                    widget.window_closing.connect(lambda a=action, d=dock: self.on_widget_closed(a, d))
                    dock.setWindowTitle(widget.windowTitle())
                    dock.setWidget(widget)
                    dock.closeEvent = widget.closeEvent
                    dock.topLevelChanged.connect(self.on_dock_top_level_changed)
                    # alternative where to add the dock widget
                    area = Qt.TopDockWidgetArea if len(self._docked_widgets) % 2 else Qt.LeftDockWidgetArea
                    self.addDockWidget(area, dock)
                    self._docked_widgets.append(dock)
                    logger.debug(f'added {widget.__class__.__name__!r} as a docked widget')
                finally:
                    self.status_bar_message.emit('')
                    self.hide_progress_bar.emit()
                return

        prompt.critical(f'There is no widget registered for\n\n{record}')
        action.setChecked(False)

    def on_show_plugin(self, action, plugin, name) -> None:
        """Slot -> Show the Plugin.

        Parameters
        ----------
        action : :class:`QtGui.QAction`
            The menu action.
        plugin : :class:`~photons.plugin.Plugin`
            The Plugin class.
        name : :class:`str`
            The name of the Plugin.
        """
        if not action.isChecked():
            # if it was unchecked while the plugin is visible then we want to re-check
            # the action in the menu and make the widget active
            action.setChecked(True)
            for p in self._plugin_widgets:
                if p is plugin:
                    p.setWindowState(Qt.WindowActive)
                    p.activateWindow()
                    p.show()
                    break
            return

        self.status_bar_message.emit(f'Starting plugin {name!r}...')
        self.show_indeterminate_progress_bar.emit()

        plug = plugin(self)
        self._plugin_widgets.append(plug)
        logger.debug(f'added {plug.__class__.__name__!r} as a plugin widget')
        plug.window_closing.connect(lambda a=action, p=plug: self.on_plugin_closed(a, p))
        if plug.show_plugin:
            plug.show()
        else:
            plug.close()

        self.status_bar_message.emit('')
        self.hide_progress_bar.emit()

    def on_widget_closed(self, action, dock) -> None:
        """Slot -> Called when a widget closes.

        Parameters
        ----------
        action : :class:`QtGui.QAction`
            The menu action.
        dock : :class:`QtWidgets.QDockWidget`
            The docked widget.
        """
        action.setChecked(False)
        self._docked_widgets.remove(dock)
        self.removeDockWidget(dock)
        logger.debug(f'removed {dock.widget().__class__.__name__!r} as a docked widget')

    def on_plugin_closed(self, action, plugin) -> None:
        """Slot -> Called when a Plugin closes.

        Parameters
        ----------
        action : :class:`QtGui.QAction`
            The menu action.
        plugin : :class:`~photons.plugin.Plugin`
            The Plugin class.
        """
        action.setChecked(False)
        self._plugin_widgets.remove(plugin)
        logger.debug(f'removed {plugin.__class__.__name__!r} as a plugin widget')

    def on_dock_top_level_changed(self, is_floating) -> None:
        """Slot -> Show the Minimum, Maximum and Close buttons when a docked widget becomes floating."""
        if is_floating:
            widget = self.sender()
            widget.setWindowFlags(
                Qt.CustomizeWindowHint |
                Qt.Window |
                Qt.WindowMinimizeButtonHint |
                Qt.WindowMaximizeButtonHint |
                Qt.WindowCloseButtonHint
            )
            widget.show()

    @staticmethod
    def create_palette(name: str) -> QtGui.QPalette:
        """Create a :class:`QtGui.QPalette` based on a colour theme.

        Parameters
        ----------
        name : :class:`str`
            The name of the theme.

        Returns
        -------
        :class:`QtGui.QPalette`
            The palette.
        """
        palette = QtGui.QPalette()
        if name == 'dark':
            # taken from https://github.com/Jorgen-VikingGod/Qt-Frameless-Window-DarkStyle
            palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
            palette.setColor(QtGui.QPalette.WindowText, Qt.white)
            palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, QtGui.QColor(127, 127, 127))
            palette.setColor(QtGui.QPalette.Base, QtGui.QColor(42, 42, 42))
            palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(66, 66, 66))
            palette.setColor(QtGui.QPalette.ToolTipBase, Qt.white)
            palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(53, 53, 53))
            palette.setColor(QtGui.QPalette.Text, Qt.white)
            palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, QtGui.QColor(127, 127, 127))
            palette.setColor(QtGui.QPalette.Dark, QtGui.QColor(35, 35, 35))
            palette.setColor(QtGui.QPalette.Shadow, QtGui.QColor(20, 20, 20))
            palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
            palette.setColor(QtGui.QPalette.ButtonText, Qt.white)
            palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, QtGui.QColor(127, 127, 127))
            palette.setColor(QtGui.QPalette.BrightText, Qt.red)
            palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
            palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
            palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Highlight, QtGui.QColor(80, 80, 80))
            palette.setColor(QtGui.QPalette.HighlightedText, Qt.white)
            palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.HighlightedText, QtGui.QColor(127, 127, 127))
        return palette

    def closeEvent(self, event) -> None:
        """Overrides :meth:`QtWidgets.QMainWindow.closeEvent`."""
        if self._docked_widgets:
            if not prompt.yes_no('There are docked widgets. Quit application?'):
                event.ignore()
                return
        if self._plugin_widgets:
            if not prompt.yes_no('There are Plugins open. Quit application?'):
                event.ignore()
                return
        application().quit()

    def dragEnterEvent(self, event) -> None:
        """Overrides :meth:`QtWidgets.QMainWindow.dragEnterEvent`."""
        paths = drag_drop_paths(event)
        if paths:
            try:
                self._drag_drop_root = read(paths[0])
                event.accept()
            except:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        """Overrides :meth:`QtWidgets.QMainWindow.dropEvent`."""
        self.app.plot(file=self._drag_drop_root, block=False)
        event.accept()
