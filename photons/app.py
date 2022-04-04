"""
Main application entry point.
"""
import logging
import re
import os
import sys
from datetime import datetime

import requests
from msl.equipment import Config
from msl.qt import (
    application,
    excepthook,
    convert,
    QtCore,
    Signal,
    prompt,
)
from msl.network.client import Link
from msl.network import connect
from msl.io import (
    search,
    send_email,
    read,
)
from msl.io.base_io import Root

from .log import logger
from .equipment import registry
from .gui import MainWindow
from .services import services

sys.excepthook = excepthook


class App(QtCore.QObject):

    added_connection = Signal(str)  # the alias
    removed_connection = Signal(str)  # the alias

    def __init__(self, url):
        """Main application entry point.

        Parameters
        ----------
        url : :class:`str`
            The path to the configuration file.
        """
        super(App, self).__init__()
        self._connections = {}  # key: alias; value: EquipmentRecord.connect(), BaseEquipment or Link object
        self._links = {}  # key: Service name; value: Link object
        self._clients = []
        self._cfg = Config(url)
        self._db = self._cfg.database()

    @property
    def config(self):
        """:class:`~msl.equipment.config.Config`: The configuration."""
        return self._cfg

    @property
    def connections(self) -> dict:
        """:class:`dict`: The equipment :class:`~msl.equipment.connection.Connection`s."""
        return self._connections

    @property
    def database(self):
        """:class:`~msl.equipment.database.Database`: The database."""
        return self._db

    @property
    def equipment(self) -> dict:
        """:class:`dict`: The :class:`~msl.equipment.record_types.EquipmentRecord`s that were specified
        as ``<equipment>`` tags in the configuration file."""
        return self._db.equipment

    @property
    def links(self) -> dict:
        """:class:`dict`: The links that have been made with :class:`~msl.network.service.Service`s."""
        return self._links

    @property
    def logger(self) -> logging.Logger:
        """:class:`logging.Logger`: The application logger."""
        return logger

    @property
    def prompt(self) -> prompt:
        """Prompt the user."""
        return prompt

    def gui(self, show=True):
        """Create the main application GUI.

        Parameters
        ----------
        show : :class:`bool`
            Whether to show the :class:`MainWindow` (which blocks until the GUI is
            closed). If :data:`False` then a custom :class:`QtWidgets.QApplication`
            is created and immediately returned.

        Returns
        -------
        :class:`QtWidgets.QApplication`
            The application instance.
        """
        a = application()

        element = self._cfg.root.find('gui')
        if element is not None:
            # NOTE: the 'fusion' style is needed in order to render Sections in a QMenu properly
            a.setStyle(element.get('style', 'windows'))
            family = element.get('font-family', 'MS Shell Dlg 2')
            size = element.get('font-size', 8)
            a.setFont(convert.to_qfont(family, size))
            a.setPalette(MainWindow.create_palette(element.get('theme', '')))

        if not show:
            return a

        m = MainWindow(self)
        m.show()
        a.exec()
        return a

    def connect_equipment(self, *aliases: str, demo=None, strict=True):
        """Connect to equipment.

        The connection is established in the following order:

        1. If a :meth:`link` can be made to the equipment then that gets precedence
        2. If a :class:`~photons.equipment.BaseEquipment` exists then use that class
        3. Use :meth:`~msl.equipment.record_types.EquipmentRecord.connect`

        Parameters
        ----------
        aliases : :class:`str`
            The alias(es) of the EquipmentRecord(s) to connect to. If not specified
            then connect to all equipment in the :attr:`.equipment` dictionary.
        demo : :class:`bool`, optional
            Whether to simulate the connection to the equipment. This value is ignored
            if a :meth:`link` can be established.
        strict : :class:`bool`, optional
            If :data:`False` then log error messages that result from connecting to
            the equipment otherwise raise the exception.

        Returns
        -------
        The new connection classes (can also be an object returned by :meth:`link`).
        """
        if not aliases:
            aliases = self._db.equipment.keys()

        for alias in aliases:
            if alias in self._connections:
                logger.info(f'already connected to {alias!r}')
                continue

            try:
                record = self._db.equipment[alias]
            except KeyError:
                logger.error(f'{alias!r} is an invalid EquipmentRecord alias')
                if strict:
                    raise
                continue

            if record.connection is None:
                logger.warning(f'{alias!r} does not have a ConnectionRecord')
                continue

            # check if a custom-written class exists
            error = False
            for r in registry:
                if r.matches(record):
                    # if a link can be made then that gets precedence
                    link = self.link(alias, strict=False)
                    if link:
                        # pop the link from self._links so that the connection to the
                        # equipment is not in both self._connections and self._links
                        logger.info(f'creating a new connection to {alias!r} via a Link')
                        self._connections[alias] = self._links.pop(alias)
                        self.added_connection.emit(alias)
                        break
                    else:
                        try:
                            logger.info(f'creating a new connection to {alias!r} via a BaseEquipment')
                            self._connections[alias] = r.cls(self, record, demo=demo)
                        except Exception as err:
                            error = True
                            logger.error(f'cannot instantiate {r.cls.__name__!r} -- {err}')
                            if strict:
                                raise
                        else:
                            self.added_connection.emit(alias)
                            break

            if not error and alias not in self._connections:
                try:
                    self._connections[alias] = record.connect(demo=demo)
                except Exception as err:
                    logger.error(f'cannot connect to {alias!r} -- {err}')
                    if strict:
                        raise
                else:
                    logger.info(f'created a new connection to {alias!r} via EquipmentRecord.connect()')
                    self.added_connection.emit(alias)

        new_connections = tuple(self._connections[alias] for alias in aliases if alias in self._connections)
        if len(new_connections) == 1:
            return new_connections[0]
        return new_connections

    def disconnect_equipment(self, *aliases: str) -> None:
        """Disconnect from :class:`~msl.equipment.connection.Connection`\\s.

        Also handles if the connection to the equipment was established via a link to a
        :class:`~msl.network.service.Service`.

        Parameters
        ----------
        aliases : :class:`str`
            The alias(es) of the :class:`~msl.equipment.record_types.EquipmentRecord`\\(s)
            to disconnect from. If not specified then disconnect all
            :class:`~msl.equipment.connection.Connection`\\s.
        """
        if not aliases:
            # create a new list to avoid RuntimeError: dictionary changed size during iteration
            aliases = list(self._connections.keys())

        for alias in aliases:
            if isinstance(self._connections[alias], Link):
                self._connections[alias].unlink()
                logger.info(f'unlinked from {alias!r}')
            else:
                self._connections[alias].disconnect()
                logger.info(f'disconnected from {alias!r}')
            del self._connections[alias]
            self.removed_connection.emit(alias)

    def create_client(self, **kwargs) -> None:
        """Connect to a Network :class:`~msl.network.manager.Manager`.

        All keyword arguments are passed to :func:`~msl.network.client.connect`.
        """
        client = connect(**kwargs)
        self._clients.append(client)
        logger.info(f'created {client!r}')

    def disconnect_clients(self) -> None:
        """Disconnect all :class:`~msl.network.client.Client`\\s."""
        for client in self._clients:
            logger.info(f'disconnected {client!r}')
            client.disconnect()
        self._clients.clear()

    def link(self, *names: str, strict=False):
        """Create links with :class:`~msl.network.service.Service`\\s.

        Parameters
        ----------
        names : :class:`str`
            The name(s) of the Service(s) to link with.
        strict : :class:`bool`, optional
            If :data:`False` then log error messages that result from linking with
            a :class:`~msl.network.service.Service` otherwise raise the exception.

        Returns
        -------
        The new links.
        """
        if not self._clients:
            if strict:
                raise ValueError('No Clients have been created, call create_client(**kwargs)')
            return

        for name in names:
            for client in self._clients:
                if name in client.manager()['services']:
                    try:
                        self._links[name] = client.link(name)
                    except RuntimeError as err:
                        logger.error(f'cannot link with {name!r} -- {err}')
                        if strict:
                            raise

        new_links = tuple(self._links[name] for name in names if name in self._links)
        if len(new_links) == 1:
            return new_links[0]
        return new_links

    def unlink(self, *names: str) -> None:
        """Unlink from :class:`~msl.network.service.Service`\\s.

        Parameters
        ----------
        names
            The name(s) of the :class:`~msl.network.service.Service`\\s to unlink with.
            If not specified then unlink from all :class:`~msl.network.service.Service`\\s.
        """
        if not names:
            # create a new list to avoid getting
            #   RuntimeError: dictionary changed size during iteration
            names = list(self._links.keys())
        for name in names:
            self._links[name].unlink()
            del self._links[name]
            logger.info(f'unlinked from {name!r}')

    def start_equipment_service(self, alias, **kwargs) -> None:
        """Start a :class:`~msl.network.service.Service` that interfaces with equipment.

        This is a blocking call and is meant to be called by the console script
        :func:`~photons.start_service`.

        Parameters
        ----------
        alias : :class:`str`
            The alias of the :class:`~msl.equipment.record_types.EquipmentRecord`
            for the :class:`~photons.equipment.BaseEquipment`
            :class:`~msl.network.service.Service` to start.
        kwargs
            All keyword arguments are passed to :meth:`~msl.network.service.Service.start`.
        """
        record = self._db.equipment.get(alias)
        if record is None:
            raise ValueError(f'No EquipmentRecord exists with the alias {alias!r}')

        service = None
        for r in registry:
            if r.matches(record):
                service = r.cls
                break

        if service is None:
            raise ValueError(f'No service exists for the alias {alias!r}')

        s = service(self, record)
        s.start(**kwargs)

    @staticmethod
    def start_service(name: str, **kwargs) -> None:
        """Start a :class:`~msl.network.service.Service` in :mod:`~photons.services`.

        This is a blocking call and is meant to be called by the console script
        :func:`~photons.start_service`.

        Parameters
        ----------
        name : :class:`str`
            The name of the :class:`~msl.network.service.Service` to start.
        kwargs
            All keyword arguments are passed to :meth:`~msl.network.service.Service.start`.
        """
        service = None
        for s in services:
            if s.__class__.__name__ == name:
                service = s
                break

        if service is None:
            raise ValueError(f'No service exists with the name {name!r}')

        s = service()
        s.start(**kwargs)

    def send_email(self, *to, subject='', body='') -> None:
        """Send an email.

        Requires a ``<smtp>`` element in the XML configuration file with a
        ``<config>`` sub-element which is the path to a SMTP configuration file,
        a ``<from>`` sub-element which is the email address of the person who is
        sending the email and can contain multiple ``<to>`` sub-elements for the
        email addresses that should be emailed.

        Parameters
        ----------
        to : :class:`str`, optional
            Who to send the email(s) to. If not specified then uses the
            ``<to>`` elements in the XML configuration file.
        subject : :class:`str`, optional
            The text to include in the subject field.
        body : :class:`str`, optional
            The text to include in the body of the email.
        """
        element = self.config.find('smtp')
        if element is None:
            raise ValueError('Must create a <smtp> element in the configuration file')
        settings = element.findtext('settings')
        frm = element.findtext('from')
        if to:
            for name in to:
                send_email(name, settings, subject=subject, body=body, frm=frm)
        else:
            for name in element.findall('to'):
                send_email(name.text, settings, subject=subject, body=body, frm=frm)

    def create_writer(self, prefix: str, *, root=None, suffix=None, use_timestamp=True, zero_padding=3):
        """Create a new :class:`~photons.io.PhotonWriter` to save data to.

        The file path has the following structure:

        <root>/<year>/<month>/<day>/<prefix>_<timestamp_OR_run_number_OR_suffix>.<extn>

        Parameters
        ----------
        prefix : :class:`str`
            The prefix of the filename.
        root : :class:`str`, optional
            The root directory where the data is to be saved. If not specified
            then the value is determined from the ``data_root`` element in
            the configuration file.
        suffix : :class:`str`, optional
            If specified then use this suffix instead of using the current
            time or auto-incrementing the run number.
        use_timestamp : :class:`bool`, optional
            If :data:`True` and `suffix` is not specified then use the
            current time as the suffix.
        zero_padding : :class:`int`, optional
            If the `suffix` is not set and not using the current time as the
            suffix then using a run number. The `zero_padding` parameter
            specifies how many leading zeros should be used for the run number.

        Returns
        -------
        :class:`~photons.io.PhotonWriter`
            The writer object.
        """
        if root is None:
            root = self.config.value('data_root')

        if not root:
            raise ValueError(
                'Must create a <data_root> element in the configuration file '
                'or explicitly specify the root when calling this method'
            )

        now = datetime.now()

        # create the sub-folders (use the zero-padded format codes)
        root = os.path.join(root, now.strftime('%Y'), now.strftime('%m'), now.strftime('%d'))
        if not os.path.isdir(root):
            os.makedirs(root)

        if not suffix:
            if use_timestamp:
                suffix = now.strftime('%H%M%S')
            else:
                # find the latest run number in the folder and increment by 1
                n = 0
                for file in search(root, prefix, levels=0):
                    s = re.search(r'_(\d+)\.', file)
                    if s is None:
                        continue
                    n = max(n, 1 + int(s.group(1)))
                suffix = str(n).zfill(zero_padding)

        path = os.path.join(root, prefix + '_' + suffix + '.json')

        # import here to avoid the circular-import error
        from .io import PhotonWriter
        return PhotonWriter(path, app=self)

    @staticmethod
    def plot(file=None, block=True, **kwargs):
        """Show the plot widget.

        Parameters
        ----------
        file : :class:`str` or :class:`~msl.io.base_io.Root`, optional
            A file to read data from. If not specified an emtpy widget is returned.
        block : :class:`bool`, optional
            Whether to block until the application is closed.
        kwargs
            All keyword arguments are passed to :func:`~msl.io.read`.

        Returns
        -------
        :class:`.App`
            The application instance.
        """
        from .gui.plotting import Plot, windows
        if isinstance(file, str):
            root = read(file, **kwargs)
        elif isinstance(file, Root):
            root = file
        else:
            root = None
        app = application()
        p = Plot(root)
        p.show()
        windows.append(p)
        if block:
            app.exec()
        return app

    def lab_monitoring(self, *, timeout=10, alias=None, corrected=True, strict=True) -> dict:
        """Read the temperature, humidity and dewpoint of (an) OMEGA iServer(s).

        Parameters
        ----------
        timeout : :class:`float`, optional
            The maximum number of seconds to wait for a reply from the webapp.
        alias : :class:`str`, optional
            A comma-separated string of iServer aliases. If not specified then
            reads the alias value from the configuration file.
        corrected : :class:`bool`, optional
            Whether to return corrected or uncorrected values.
        strict : :class:`bool`, optional
            Whether to raise an exception if the connection to the webapp cannot be established.

        Returns
        -------
        dict
            The information from the iServer that is measuring the lab environment.
        """
        element = self.config.find('lab_monitoring')
        if element is None:
            raise ValueError('Must create a <lab_monitoring> element in the configuration file')
        url = element.findtext('url')
        if not url:
            raise ValueError('Must create a <url> sub-element in the <lab_monitoring> element')
        if not alias:
            alias = element.findtext('alias')
            if not alias:
                raise ValueError('Must specify the alias(es) of the iServers')

        url = url.rstrip('/')
        logger.debug('requesting the laboratory environment values from the webapp ...')
        try:
            reply = requests.get(f'{url}/now/?alias={alias}&corrected={corrected}', timeout=timeout)
        except requests.exceptions.ConnectTimeout as e:
            logger.error(e)
            if strict:
                raise
            else:
                return {}

        if not reply.ok:
            raise ConnectionError(reply.content.decode())

        data = reply.json()
        for key, value in data.items():
            if value['error']:
                error = value['error']
                alias = value['alias']
                raise OSError(f'{error} [Serial:{key}, Alias:{alias}]')
        logger.info(f'laboratory environment values: {data}')
        return data
