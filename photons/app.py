"""
Main application entry point and GUI.
"""
import os
import re
import sys
from datetime import datetime
from functools import partial
from typing import cast

import numpy as np
from msl.equipment import Config
from msl.equipment import EquipmentRecord
from msl.equipment.database import Database
from msl.io import read
from msl.io import search
from msl.io import send_email
from msl.io.base import Root
from msl.network import connect
from msl.network.client import Client
from msl.network.client import Link
from msl.qt import Qt
from msl.qt import QtCore
from msl.qt import QtGui
from msl.qt import QtWidgets
from msl.qt import Signal
from msl.qt import Slot
from msl.qt import application
from msl.qt import convert
from msl.qt import excepthook
from msl.qt import prompt
from msl.qt.convert import to_qfont
from msl.qt.utils import drag_drop_paths
from msl.qt.utils import screen_geometry

from .equipment.base import BaseEquipment
from .equipment.base import BaseEquipmentWidget
from .equipment.base import ConnectionClass
from .equipment.base import devices
from .equipment.base import widgets
from .io import PhotonWriter
from .log import logger
from .network import CreateClient
from .network import StartEquipmentService
from .network import StartManager
from .network import StartService
from .plotting import Plot
from .plugins.base import BasePlugin
from .plugins.base import PluginInfo
from .plugins.base import plugins
from .services.base import services
from .utils import lab_logging

sys.excepthook = excepthook


class App(QtCore.QObject):

    added_connection: QtCore.SignalInstance = Signal(str)  # the alias
    removed_connection: QtCore.SignalInstance = Signal(str)  # the alias

    def __init__(self, config: str = None) -> None:
        """Main application entry point.

        Args:
            config: The path to a configuration file.
                If not specified then uses ``~/photons.xml``.
        """
        super().__init__()
        if not config:
            config = os.path.expanduser('~/photons.xml')
        self._connections: dict[str, ConnectionClass] = {}
        self._links: dict[str, Link] = {}
        self._clients: list[Client] = []
        self._cfg: Config = Config(config)
        self._db: Database = self._cfg.database()

    def add_lab_logging_metadata(self, writer: PhotonWriter) -> None:
        """Add the current temperature and humidity of an OMEGA iServer to the writer.

        All parameters are read from the configuration file.
        """
        element = self.config.find('lab_logging')
        if element is None:
            raise ValueError('Must create a <lab_logging> element '
                             'in the configuration file')

        root_url = element.attrib.get('root_url')
        if root_url is None:
            raise ValueError('Must add a "root_url" attribute to <lab_logging>')

        alias = element.attrib.get('alias')
        if alias is None:
            raise ValueError('Must add an "alias" attribute to <lab_logging>')

        info = lab_logging(root_url, alias, strict=False)
        if not info:
            return

        serial, data = next(iter(info.items()))
        writer.add_metadata(
            lab_temperature=round(data['temperature'], 4),
            lab_humidity=round(data['humidity'], 4),
            lab_iServer_serial=serial,
        )

    @property
    def config(self) -> Config:
        """The configuration object."""
        return self._cfg

    def connect_equipment(self, *args: str) -> ConnectionClass | tuple[ConnectionClass, ...]:
        """Connect to equipment.

        The connection to each equipment is attempted in the following order:

            1. If a Link can be established then that gets precedence
            2. If a BaseEquipment exists then use it
            3. Use EquipmentRecord.connect()

        Args:
            *args: The alias(es) of the EquipmentRecord(s) or the name(s)
                of Services to Link with to establish the connection.

        Returns:
            The connection(s).
        """
        if not args:
            raise ValueError('You must specify at least one EquipmentRecord '
                             'alias or Service name')

        if self._clients:
            self.link(*args, strict=False)

        for arg in args:
            if arg in self.connections:
                logger.info(f'already connected to {arg!r}')
                continue

            # first, see if a Link can be established
            if arg in self.links:
                logger.info(f'created a connection to {arg!r} via a Link')
                # TODO should it be popped so that the object is not in both
                #  self.connections and self.links?
                self.connections[arg] = self.links.pop(arg)
                self.added_connection.emit(arg)
                continue

            # next, try to connect via a registered BaseEquipment
            record = self.equipment[arg]
            for device in devices:
                if device.matches(record):
                    logger.info(f'creating a connection to {arg!r} via {device.cls}')
                    kwargs = self.config.attrib(record.alias)
                    self.connections[arg] = device.cls(record, **kwargs)
                    self.added_connection.emit(arg)
                    break

            # finally, try EquipmentRecord.connect()
            if arg not in self.connections:
                logger.info(f'creating a new connection to {arg!r} via '
                            f'EquipmentRecord.connect()')
                self.connections[arg] = record.connect()
                self.added_connection.emit(arg)

        if len(args) == 1:
            return self.connections[args[0]]
        return tuple(self.connections[arg] for arg in args)

    def connect_manager(self, **kwargs) -> None:
        """Connect to a :class:`~msl.network.manager.Manager`.

        All keyword arguments are passed to :func:`~msl.network.client.connect`.
        """
        client: Client = connect(**kwargs)
        self._clients.append(client)
        logger.info(f'created {client!r}')

    @property
    def connections(self):
        """The connections to equipment."""
        return self._connections

    def create_writer(self,
                      prefix: str,
                      *,
                      root: str = None,
                      suffix: str = None,
                      use_timestamp: bool = True,
                      zero_padding: int = 3) -> PhotonWriter:
        """Create a new PhotonWriter to save data to.

        The file path has the following structure:

        <root>/<year>/<month>/<day>/<prefix>_<suffix | timestamp | run_number>.json

        Args:
            prefix: The prefix of the filename.
            root: The root directory where the data is saved. If not specified
                then the value is determined from the <data_root> element in
                the configuration file.
            suffix: If specified, use this value as the suffix. The
                `use_timestamp` and `zero_padding` parameters are ignored.
            use_timestamp: If True and `suffix` is not specified then use the
                current time as the suffix.
            zero_padding: If `use_timestamp` is False and `suffix` is not specified
                then use an auto-incremented run number as the suffix. The
                `zero_padding` value specifies how many leading zeros should be
                padded to the run number.

        Returns:
            The writer object.
        """
        if root is None:
            root = self.config.value('data_root')

        if not root:
            raise ValueError(
                'Must create a <data_root> element in the configuration file '
                'or explicitly specify the root when calling this method'
            )

        # create the sub-folders (use the zero-padded format codes)
        now = datetime.now()
        root = os.path.join(root, now.strftime('%Y'), now.strftime('%m'), now.strftime('%d'))
        if not os.path.isdir(root):
            os.makedirs(root)

        if not suffix:
            if use_timestamp:
                suffix = now.strftime('%H%M%S')
            else:
                # find the latest run number in the folder and increment by 1
                n = 0
                for file in search(root, pattern=prefix, levels=0):
                    s = re.search(r'_(?P<run>\d+)\.', file)
                    if s is None:
                        continue
                    n = max(n, 1 + int(s['run']))
                suffix = str(n).zfill(zero_padding)

        path = os.path.join(root, f'{prefix}_{suffix}.json')
        writer = PhotonWriter(path, log_size=1000)
        self.add_lab_logging_metadata(writer)
        return writer

    @property
    def database(self) -> Database:
        """The database object."""
        return self._db

    def disconnect_equipment(self, *args: str) -> None:
        """Disconnect from equipment.

        Also handles if the connection to the equipment was established via a Link.

        Args:
            *args: The alias(es) of the EquipmentRecord(s) or the name(s)
                of Services to disconnect from. If not specified then
                disconnect from all connections.
        """
        if not args:
            # create a new list to avoid getting
            #   RuntimeError: dictionary changed size during iteration
            args = list(self.connections.keys())

        for arg in args:
            if arg not in self.connections:
                logger.warning(f'{arg!r} is not an active connection')
                continue

            if isinstance(self.connections[arg], Link):
                self.connections[arg].unlink()
                logger.info(f'unlinked from {arg!r}')
            else:
                self.connections[arg].disconnect()
                logger.info(f'disconnected from {arg!r}')

            del self.connections[arg]
            self.removed_connection.emit(arg)

    def disconnect_managers(self) -> None:
        """Disconnect from all :class:`~msl.network.manager.Manager`\\s."""
        for client in self._clients:
            logger.info(f'disconnecting {client!r}')
            client.disconnect()
        self._clients.clear()

    @property
    def equipment(self) -> dict[str, EquipmentRecord]:
        """The equipment record`s that were specified in the configuration file."""
        return self._db.equipment

    def link(self,
             *names: str,
             timeout: float = 10,
             strict: bool = True) -> Link | tuple[Link, ...]:
        """Create links with :class:`~msl.network.service.Service`\\s.

        You must have first connected to a :class:`~msl.network.manager.Manager`
        (see :meth:`.connect_manager`).

        A Link is established with the first Service that was found with the
        appropriate name.

        Args:
            names: The name(s) of the Service(s) to link with.
            timeout: The maximum number of seconds to wait when sending a
                request to a Manager.
            strict: Whether to raise an error if the Service does not exist.

        Returns:
            The link(s).
        """
        if not names:
            raise ValueError('You must specify at least one name')

        if not self._clients:
            raise RuntimeError('You must connect to at least one Manager')

        options: list[tuple[Client, list[str]]] = []
        for client in self._clients:
            ids = client.identities(timeout=timeout)
            if ids['services']:
                options.append((client, list(ids['services'])))

        for name in names:
            if name in self.links:
                logger.info(f'already linked with {name!r}')
                continue

            for client, service_names in options:
                if name in service_names:
                    logger.info(f'linking with {name!r}')
                    self.links[name] = client.link(name, timeout=timeout)
                    break

            if strict and name not in self.links:
                raise ValueError(f'Cannot link with {name!r} (no Service exists)')

        if len(names) == 1:
            try:
                return self.links[names[0]]
            except KeyError:
                if strict:
                    raise

        # if strict=False then it is possible that not all requested Links exist
        return tuple(self.links[name] for name in names if name in self.links)

    @property
    def links(self) -> dict[str, Link]:
        """The Links that have been made to Services."""
        return self._links

    @property
    def logger(self):
        """The application logger."""
        return logger

    @staticmethod
    def plot(data: str | Root | np.ndarray | list | tuple = None,
             block: bool = True,
             **kwargs) -> QtWidgets.QApplication:
        """Show the Plot widget.

        Args:
            data: The data to initially plot. If a string then a file path.
                If not specified then an emtpy Plot is returned.
            block: Whether to block until all Plots are closed.
            **kwargs: If `data` is a filename then all keyword arguments
                are passed to :func:`~msl.io.read`. Otherwise, ignored.

        Returns:
            The application instance.
        """
        if isinstance(data, str):
            root = read(data, **kwargs)
        elif isinstance(data, Root):
            root = data
        elif isinstance(data, (np.ndarray, list, tuple)):
            root = Root('ndarray')
            root.create_dataset('data', data=data)
        else:
            root = None

        app = application()
        p = Plot(root)
        p.show()
        if block:
            app.exec()
        return app

    @property
    def prompt(self):
        """Prompt the user (see :mod:`msl.qt.prompt`)."""
        return prompt

    def records(self, *aliases: str, **kwargs) -> list[EquipmentRecord]:
        """Returns the equipment records.

        Args:
            *aliases: The alias(es) of the equipment records that are
                specified in the configuration file.
            **kwargs: Find all equipment records that match the specified
                search criteria (e.g., manufacturer, model, description).
                See :meth:`msl.equipment.database.Database.records` for more
                details.

        Examples:

            .. invisible-code-block:
               >>> from photons import App
               >>> app = App()

            >>> app.records('dmm-3458a', 'shutter', manufacturer='Keithley')

        """
        if aliases:
            records = [v for k, v in self.equipment.items() if k in aliases]
        else:
            records = []
        if kwargs:
            records.extend(self._db.records(**kwargs))
        return records

    def run(self, show: bool = True) -> QtWidgets.QApplication:
        """Run the main application.

        To override the default style, font and palette theme that is used for the
        QApplication you can create an <app> XML element in the configuration file
        with the following (optional) attributes:

        <app style="windows" font_family="arial" font_size="12" theme="dark"/>

        For possible themes, see :meth:`MainWindow.create_palette`.

        Args:
            show: After the application is created, either return immediately or
                instantiate and show the GUI (which blocks until the GUI is closed).

        Returns:
            The application instance.
        """
        a = application()

        element = self.config.find('app')
        if element is not None:
            style = element.attrib.get('style', 'Fusion')
            family = element.attrib.get('font_family', 'Segoe UI')
            size = element.attrib.get('font_size', '8')
            theme = element.attrib.get('theme', 'dark')
            a.setStyle(style)
            a.setFont(to_qfont(family, size))
            a.setPalette(MainWindow.create_palette(theme))

        if not show:
            return a

        m = MainWindow(self)
        m.show()
        a.exec()
        return a

    def send_email(self,
                   *to: str,
                   subject: str = None,
                   body: str = None) -> None:
        """Send an email.

        Requires a <smtp> element in the XML configuration file with a
        <settings> sub-element which is the path to an SMTP configuration file,
        a <from> sub-element which is the email address of the person who is
        sending the email and can contain multiple <to> sub-elements for the
        email addresses that should be emailed. For example,

        .. code-block:: xml

            <smtp>
                <settings>path/to/SMTP/setting.txt</settings>
                <from>max.planck</from>
                <!-- The following are optional -->
                <to>neils.bohr</to>
                <to>marie.curie</to>
            </smtp>

        Args:
            to: Who to send the email to. If not specified then uses the
                <to> elements in the configuration file.
            subject: The text to include in the subject field.
            body: The text to include in the body of the email. The text can be
                enclosed in ``<html></html>`` tags to use HTML elements to format
                the message.
        """
        element = self.config.find('smtp')
        if element is None:
            raise ValueError('Must create an <smtp> element in the configuration file')

        config = element.findtext('config')
        if config is None:
            raise ValueError('Must create a <config> sub-element to '
                             '<smtp> in the configuration file')

        sender = element.findtext('from')
        if sender is None:
            raise ValueError('Must create a <from> sub-element to '
                             '<smtp> in the configuration file')

        recipients = to if to else [name.text for name in element.findall('to')]
        send_email(config, recipients, sender=sender, subject=subject, body=body)

    def start_equipment_service(self, alias: str, **kwargs) -> None:
        """Start a :class:`~msl.network.service.Service` that interfaces with equipment.

        This is a blocking call. It is meant to be invoked by the console script.

        Args:
            alias: The alias of an EquipmentRecord.
            **kwargs: Keyword arguments.
        """
        record = self.equipment.get(alias)
        if record is None:
            raise ValueError(f'No EquipmentRecord exists with the alias {alias!r}')

        service: type[BaseEquipment] | None = None
        for device in devices:
            if device.matches(record):
                service = device.cls
                break

        if service is None:
            raise ValueError(f'No Service exists for the alias {alias!r}')

        s = service(record, **self.config.attrib(record.alias))
        s.running_as_service = True
        s.set_logging_level(kwargs.pop('log_level'))
        s.start(**kwargs)

    @staticmethod
    def start_service(name: str, **kwargs) -> None:
        """Start a registered Service.

        This is a blocking call. It is meant to be invoked by the console script.

        Args:
            name: The name of the Service to start.
            **kwargs: Keyword arguments.
        """
        cls = None
        for service in services:
            if service.name == name:
                cls = service.cls
                break

        if cls is None:
            raise ValueError(f'No Service exists with the name {name!r}')

        s = cls()
        if s.name != name:
            logger.warning(
                f'Service name {s.name!r} != registered name {name!r}\n\n'
                f'To avoid seeing this warning, you should do one of the following for {cls}\n\n'
                f'1. use super().__init__(name={name!r})\n'
                f'2. use @service(name={s.name!r})\n'
                f'3. do not use a name with super() nor @service() [uses the class name instead]\n')

        s.set_logging_level(kwargs.pop('log_level'))
        s.start(**kwargs)

    def unlink(self, *names: str) -> None:
        """Unlink from :class:`~msl.network.service.Service`\\s.

        Args:
            names: The name(s) of the Services to unlink with.
                If not specified then unlink from all Services.
        """
        if not names:
            # create a new list to avoid getting
            #   RuntimeError: dictionary changed size during iteration
            names = list(self.links.keys())

        for name in names:
            if name not in self.links:
                logger.warning(f'{name!r} is not an activate Link')
                continue

            self.links[name].unlink()
            del self.links[name]
            logger.info(f'unlinked from {name!r}')


class MainWindow(QtWidgets.QMainWindow):

    hide_progress_bar: QtCore.SignalInstance = Signal()
    """Hide the progress bar."""

    show_indeterminate_progress_bar: QtCore.SignalInstance = Signal()
    """Show an indeterminate progress bar."""

    status_bar_message: QtCore.SignalInstance = Signal(str)
    """The message (text) to display in the status bar."""

    update_progress_bar: QtCore.SignalInstance = Signal(int)
    """Update the progress bar with a value in the range [0, 100]."""

    def __init__(self, app: App, **kwargs) -> None:
        """Main application window.

        Args:
            app: The application instance.
            **kwargs: All keyword argument are passed to super().
        """
        super().__init__(**kwargs)

        self.app = app
        app.added_connection.connect(self.on_added_connection)
        app.removed_connection.connect(self.on_removed_connection)

        # a list of all the docked widgets that are open
        self._docked_widgets: list[QtWidgets.QDockWidget] = []

        # a list of all the plugins that are open
        self._plugin_widgets: list[BasePlugin] = []

        self.setWindowTitle('Photons')

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
        exit_action.triggered.connect(lambda: application().quit())  # noqa: QAction.triggered exists

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
                action.setData(record)
                action.triggered.connect(partial(self.on_connections_triggered, action))  # noqa: QAction.triggered exists
                self.connection_menu.addAction(action)
        self.connection_menu.setToolTipsVisible(True)

        # create the Network menubar
        self.network_menu = menubar.addMenu('Network')
        self.network_menu.setToolTipsVisible(True)

        start_manager_action = QtGui.QAction('Start a Manager', self)
        start_manager_action.setStatusTip('Start a Network Manager')
        start_manager_action.setToolTip('Start a Network Manager')
        start_manager_action.triggered.connect(partial(StartManager, self))  # noqa: QAction.triggered exists
        self.network_menu.addAction(start_manager_action)

        start_service_action = QtGui.QAction('Start a Service', self)
        start_service_action.setStatusTip('Start a service')
        start_service_action.setToolTip('Start a service')
        start_service_action.triggered.connect(partial(StartService, self))  # noqa: QAction.triggered exists
        self.network_menu.addAction(start_service_action)

        start_equip_service_action = QtGui.QAction('Start an Equipment Service', self)
        start_equip_service_action.setStatusTip('Start a service that interfaces with equipment')
        start_equip_service_action.setToolTip('Start a service that interfaces with equipment')
        start_equip_service_action.triggered.connect(partial(StartEquipmentService, self))  # noqa: QAction.triggered exists
        self.network_menu.addAction(start_equip_service_action)

        create_client_action = QtGui.QAction('Create a Client', self)
        create_client_action.setStatusTip('Connect to a Network Manager as a Client')
        create_client_action.setToolTip('Connect to a Network Manager as a Client')
        create_client_action.triggered.connect(partial(CreateClient, self))  # noqa: QAction.triggered exists
        self.network_menu.addAction(create_client_action)

        # create the Widgets menubar
        self.widgets_menu = menubar.addMenu('Widgets')
        for alias, record in sorted(self.app.equipment.items()):
            for w in widgets:
                if w.matches(record):
                    if record.connection is not None:
                        action = QtGui.QAction(alias, self)
                        action.setStatusTip(f'Interface with {record.manufacturer} {record.model}')
                        action.setToolTip(f'{record.manufacturer} {record.model}')
                        action.setCheckable(True)
                        action.setData(record)
                        action.triggered.connect(partial(self.on_widgets_triggered, action))  # noqa: QAction.triggered exists
                        self.widgets_menu.addAction(action)
        self.widgets_menu.setToolTipsVisible(True)

        # create the Plugins menubar
        self.plugin_menu = menubar.addMenu('Plugins')
        for p in plugins:
            action = QtGui.QAction(p.name, self)
            action.setStatusTip(p.description)
            action.setToolTip(p.description)
            action.setCheckable(True)
            action.setData(p)
            action.triggered.connect(partial(self.on_plugins_triggered, action))  # noqa: QAction.triggered exists
            self.plugin_menu.addAction(action)
        self.plugin_menu.setToolTipsVisible(True)

        self.resize(screen_geometry().width()//4, self.statusBar().size().height())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.closeEvent`."""
        if self._docked_widgets:
            if not prompt.yes_no('There are docked widgets. Quit application?'):
                event.ignore()
                return
        if self._plugin_widgets:
            if not prompt.yes_no('There are Plugins open. Quit application?'):
                event.ignore()
                return
        for w in self._docked_widgets:
            w.close()
        for w in self._plugin_widgets:
            w.close()
        super().closeEvent(event)
        application().quit()

    @staticmethod
    def create_palette(name: str) -> QtGui.QPalette:
        """Create and return a QPalette based on a colour theme.

        Args:
            name: The name of the theme. Currently only supports "dark".
        """
        palette = QtGui.QPalette()
        name_lower = name.lower()
        if name_lower == 'dark':
            # taken from https://github.com/Jorgen-VikingGod/Qt-Frameless-Window-DarkStyle
            cg = QtGui.QPalette.ColorGroup
            cr = QtGui.QPalette.ColorRole
            palette.setColor(cr.Window, QtGui.QColor(53, 53, 53))
            palette.setColor(cr.WindowText, Qt.white)
            palette.setColor(cg.Disabled, cr.WindowText, QtGui.QColor(127, 127, 127))
            palette.setColor(cr.Base, QtGui.QColor(42, 42, 42))
            palette.setColor(cr.AlternateBase, QtGui.QColor(66, 66, 66))
            palette.setColor(cr.ToolTipBase, Qt.white)
            palette.setColor(cr.ToolTipText, QtGui.QColor(53, 53, 53))
            palette.setColor(cr.Text, Qt.white)
            palette.setColor(cg.Disabled, cr.Text, QtGui.QColor(127, 127, 127))
            palette.setColor(cr.Dark, QtGui.QColor(35, 35, 35))
            palette.setColor(cr.Shadow, QtGui.QColor(20, 20, 20))
            palette.setColor(cr.Button, QtGui.QColor(53, 53, 53))
            palette.setColor(cr.ButtonText, Qt.white)
            palette.setColor(cg.Disabled, cr.ButtonText, QtGui.QColor(127, 127, 127))
            palette.setColor(cr.BrightText, Qt.red)
            palette.setColor(cr.Link, QtGui.QColor(42, 130, 218))
            palette.setColor(cr.Highlight, QtGui.QColor(42, 130, 218))
            palette.setColor(cg.Disabled, cr.Highlight, QtGui.QColor(80, 80, 80))
            palette.setColor(cr.HighlightedText, Qt.white)
            palette.setColor(cg.Disabled, cr.HighlightedText, QtGui.QColor(127, 127, 127))
        return palette

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.dragEnterEvent`."""
        paths = drag_drop_paths(event)
        if paths:
            try:
                self._drag_drop_root = read(paths[0])
                event.accept()
            except:  # noqa: Too broad exception clause (PEP8: E722)
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.dropEvent`."""
        App.plot(self._drag_drop_root, block=False)
        event.accept()

    @staticmethod
    def find_widget(connection: ConnectionClass,
                    *,
                    parent: QtWidgets.QWidget = None,
                    **kwargs) -> BaseEquipmentWidget:
        """Returns the widget that is used for the equipment.

        Args:
            connection: The connection to the equipment.
            parent: The parent widget to use for the BaseEquipmentWidget.
            **kwargs: All additional keyword arguments are passed to super()
                for the BaseEquipmentWidget.

        Raises:
            RuntimeError: If a widget does not exist for the `connection`.
        """
        if isinstance(connection, Link):
            record = EquipmentRecord(**connection.record_as_json())
        else:
            record = connection.record

        for widget in widgets:
            if widget.matches(record):
                return widget.cls(connection, parent=parent, **kwargs)

        raise RuntimeError(f'No widget exists for {record.alias!r}')

    @Slot(str)
    def on_added_connection(self, alias: str) -> None:
        """Add a checkmark to a QAction in the Connections QMenu."""
        for action in self.connection_menu.actions():
            if action.text() == alias:
                action.setChecked(True)
                break

    @Slot(QtGui.QAction)
    def on_connections_triggered(self, action: QtGui.QAction) -> None:
        """A QAction in the Connections QMenu was triggered."""
        if action.isChecked():
            prefix = f'Connecting to'
            fcn = self.app.connect_equipment
        else:
            prefix = f'Disconnecting from'
            fcn = self.app.disconnect_equipment

        record: EquipmentRecord = action.data()
        self.status_bar_message.emit(f'{prefix} {record.alias!r}...')
        self.show_indeterminate_progress_bar.emit()
        application().processEvents()
        try:
            fcn(record.alias)
        except:  # noqa: Too broad exception clause (PEP8: E722)
            action.setChecked(not action.isChecked())
            raise
        finally:
            self.status_bar_message.emit('')
            self.hide_progress_bar.emit()

    @Slot(QtWidgets.QDockWidget, bool)
    def on_dock_top_level_changed(self, widget: QtWidgets.QDockWidget, is_floating: bool) -> None:
        """Show the Minimum, Maximum and Close buttons when a docked widget becomes floating."""
        if is_floating:
            widget.setWindowFlags(
                Qt.CustomizeWindowHint |
                Qt.Window |
                Qt.WindowMinimizeButtonHint |
                Qt.WindowMaximizeButtonHint |
                Qt.WindowCloseButtonHint
            )
            widget.show()

    @Slot()
    def on_hide_progress_bar(self) -> None:
        """Hide the progress bar."""
        self._progress_bar.hide()

    @Slot(QtGui.QAction, BasePlugin)
    def on_plugin_closed(self,
                         action: QtGui.QAction,
                         plugin: BasePlugin) -> None:
        """Called when a Plugin closes."""
        action.setChecked(False)
        self._plugin_widgets.remove(plugin)
        logger.debug(f'removed {plugin.__class__.__name__!r} as a plugin widget')

    @Slot(QtGui.QAction)
    def on_plugins_triggered(self, action: QtGui.QAction) -> None:
        """A QAction in the Plugins QMenu was triggered."""
        plugin: PluginInfo = action.data()
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

        self.status_bar_message.emit(f'Starting plugin {plugin.name!r}...')
        self.show_indeterminate_progress_bar.emit()

        cls = plugin.cls(self)
        self._plugin_widgets.append(cls)
        logger.debug(f'added {cls.__class__.__name__!r} as a plugin widget')
        cls.closing.connect(partial(self.on_plugin_closed, action, cls))
        if cls.show_plugin:
            cls.show()
            cls.after_show()
        else:
            cls.close()

        self.status_bar_message.emit('')
        self.hide_progress_bar.emit()

    @Slot(str)
    def on_removed_connection(self, alias: str) -> None:
        """Remove a checkmark from a QAction in the Connections QMenu."""
        for action in self.connection_menu.actions():
            if action.text() == alias:
                action.setChecked(False)
                break

    @Slot()
    def on_show_indeterminate_progress_bar(self) -> None:
        """Show an indeterminate progress bar.

        Call this method if a process completion rate is unknown or if it is
        not necessary to indicate how long the process will take.
        """
        self._progress_bar.setMaximum(0)
        self._progress_bar.show()

    @Slot(str)
    def on_status_bar_message(self, message: str) -> None:
        """Display a message in the QStatusBar."""
        self.statusBar().showMessage(message)

    @Slot(int)
    def on_update_progress_bar(self, percentage: int | float) -> None:
        """Update the value of the progress bar.

        Call this method if a process completion rate can be determined.
        Automatically shows the progress bar if it is hidden.

        Args:
            percentage: A value in the range [0, 100]. The value gets
                rounded to the nearest integer.
        """
        if not self._progress_bar.isVisible() or self._progress_bar.maximum() == 0:
            self._progress_bar.setMaximum(100)
            self._progress_bar.show()
        self._progress_bar.setValue(round(percentage))

    @Slot(QtGui.QAction, QtWidgets.QDockWidget)
    def on_widget_closed(self,
                         action: QtGui.QAction,
                         widget: QtWidgets.QDockWidget) -> None:
        """Called when a docked widget closes."""
        action.setChecked(False)
        self._docked_widgets.remove(widget)
        self.removeDockWidget(widget)
        logger.debug(f'removed {widget.widget().__class__.__name__!r} as a docked widget')

    @Slot(QtGui.QAction)
    def on_widgets_triggered(self, action: QtGui.QAction) -> None:
        """A QAction in the Widgets QMenu was triggered."""
        record: EquipmentRecord = action.data()

        if not action.isChecked():
            # if it was unchecked while the widget is visible then recheck
            # the action in the menu and make the widget active
            action.setChecked(True)
            for docked in self._docked_widgets:
                widget = cast(BaseEquipmentWidget, docked.widget())
                if widget.record is record:
                    docked.setWindowState(Qt.WindowActive)
                    docked.activateWindow()
                    docked.show()
                    break
            return

        for w in widgets:
            if w.matches(record):
                self.status_bar_message.emit(f'Creating widget for {record.alias!r}...')
                self.show_indeterminate_progress_bar.emit()
                application().processEvents()
                try:
                    connection = self.app.connect_equipment(record.alias)
                except:  # noqa: Too broad exception clause (PEP8: E722)
                    action.setChecked(False)
                    raise
                else:
                    dock = QtWidgets.QDockWidget(self)
                    dock.setAllowedAreas(Qt.AllDockWidgetAreas)
                    # Must call addDockWidget and append before the widget is
                    # instantiated in case the widget emits the closing signal
                    # in __init__ (if, for example, an error was raised)
                    self.addDockWidget(Qt.LeftDockWidgetArea, dock)
                    self._docked_widgets.append(dock)
                    widget: BaseEquipmentWidget = w.cls(connection, parent=self)
                    widget.closing.connect(partial(self.on_widget_closed, action, dock))
                    dock.setWindowTitle(widget.windowTitle())
                    dock.setWidget(widget)
                    dock.closeEvent = widget.closeEvent
                    dock.topLevelChanged.connect(partial(self.on_dock_top_level_changed, dock))  # noqa: QDockWidget.topLevelChanged exists
                    logger.debug(f'added {widget.__class__.__name__!r} as a docked widget')
                finally:
                    self.status_bar_message.emit('')
                    self.hide_progress_bar.emit()
                return

        prompt.critical(f'There is no widget registered for\n\n{record}')
        action.setChecked(False)
