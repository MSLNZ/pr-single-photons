"""
QDialogs for starting a Network Manager or a Service, or,
connecting to a Manager as a Client.
"""
from __future__ import annotations

import os
import re
import subprocess
import typing

from msl.network.database import UsersTable
from msl.network.json import serialize
from msl.qt import Button
from msl.qt import CheckBox
from msl.qt import ComboBox
from msl.qt import LineEdit
from msl.qt import Qt
from msl.qt import QtWidgets
from msl.qt import Slot
from msl.qt import SpinBox
from msl.qt import prompt

from .log import logger
from .services.base import services

if typing.TYPE_CHECKING:
    from .app import MainWindow


class ClientServiceDialog(QtWidgets.QDialog):

    def __init__(self,
                 parent: MainWindow,
                 widget: QtWidgets.QWidget) -> None:
        """Connect to a Manager as either a Client or as a Service.

        Args:
            parent: The parent widget.
            widget: The widget to add to the first row of the QFormLayout.
        """
        super().__init__(parent, Qt.WindowType.WindowCloseButtonHint)

        self.parent = parent

        self.host_lineedit = LineEdit(
            text='localhost',
            tooltip='The IP address or hostname of the computer the '
                    'Manager is running on'
        )

        self.port_spinbox = SpinBox(
            value=1875,
            minimum=1024,
            maximum=49151,
            tooltip='The port that the Manager is running on',
        )

        self.tls_checkbox = CheckBox(
            initial=True,
            tooltip='Whether to use the TLS protocol',
        )

        self.assert_hostname_checkbox = CheckBox(
            initial=True,
            tooltip='Whether to force the hostname of the Manager '
                    'to match the value of host.',
        )

        self.log_level_combobox = ComboBox(
            items=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            initial='INFO',
            tooltip='The logging level to use',
        )

        self.authentication_combobox = ComboBox(
            items=['None', 'Manager Password', 'User login'],
            tooltip='The authentication method to use to connect to the Manager',
        )

        self.timeout_spinbox = SpinBox(
            value=10,
            minimum=1,
            maximum=1000,
            tooltip='The timeout value in seconds',
        )

        self.run_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton,
            left_click=self.on_connect_clicked,
            tooltip='Run',
        )

        self.abort_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton,
            left_click=self.close,
            tooltip='Abort',
        )

        label: str = widget.property('label')

        form = QtWidgets.QFormLayout()
        form.addRow(label, widget)
        form.addRow('Manager Host:', self.host_lineedit)
        form.addRow('Manager Port:', self.port_spinbox)
        form.addRow('Authentication:', self.authentication_combobox)
        if not label.startswith('Client'):
            form.addRow('Log level:', self.log_level_combobox)
        form.addRow('Use TLS?', self.tls_checkbox)
        form.addRow('Assert hostname?', self.assert_hostname_checkbox)
        form.addRow('Timeout:', self.timeout_spinbox)
        box = QtWidgets.QHBoxLayout()
        box.addWidget(self.run_button)
        box.addWidget(self.abort_button)
        form.addRow(box)
        self.setLayout(form)

        self.show()

    def check_hostname(self) -> bool:
        """Check the hostname of the Manager."""
        if not self.host_lineedit.text().strip():
            prompt.critical('You must specify the hostname of the Manager')
            return False
        return True

    @Slot()
    def on_connect_clicked(self) -> None:
        """Connect to a Manager."""
        raise NotImplementedError

    def prompt_authentication(self) -> tuple[str | None, str | None, str | None]:
        """Prompt the user for the authentication credentials (if required).

        Returns:
            The username, the password for username, the password for the Manager.
        """
        username = None
        password = None
        password_manager = None
        auth = self.authentication_combobox.currentText()
        if auth == 'User login':
            username = prompt.text('Enter the username:')
            if username:
                password = prompt.text(
                    f'Enter the password for {username}:',
                    echo=QtWidgets.QLineEdit.EchoMode.Password)
        elif auth == 'Manager Password':
            password_manager = prompt.text(
                'Enter the password of the Manager:',
                echo=QtWidgets.QLineEdit.EchoMode.Password)
        return username, password, password_manager


class CreateClient(ClientServiceDialog):

    def __init__(self, parent: MainWindow) -> None:
        """Connect to a Manager as a Client.

        Args:
            parent: The parent widget.
        """
        self.line_edit = LineEdit(
            text='Client',
            tooltip='The name of the Client',
        )
        self.line_edit.setProperty('label', 'Client name:')
        super().__init__(parent, self.line_edit)
        self.setWindowTitle('Create a Client')

    @Slot()
    def on_connect_clicked(self) -> None:
        """Connect to a Manager."""
        if not self.check_hostname():
            return

        name = self.line_edit.text().strip()
        if not name:
            prompt.critical('You must specify the name of the Client')
            return

        username, password, password_manager = self.prompt_authentication()

        self.parent.app.connect_manager(
            name=name,
            host=self.host_lineedit.text().strip(),
            port=self.port_spinbox.value(),
            timeout=self.timeout_spinbox.value(),
            username=username,
            password=password,
            password_manager=password_manager,
            disable_tls=not self.tls_checkbox.isChecked(),
            assert_hostname=self.assert_hostname_checkbox.isChecked()
        )

        # close the QDialog
        self.close()


class StartEquipmentService(ClientServiceDialog):

    def __init__(self, parent: MainWindow) -> None:
        """Start a Service that interfaces with equipment.

        The Service will be running on `localhost`, but the Manager
        can be running on a remote computer.

        Args:
            parent: The parent widget.
        """
        self.combobox = ComboBox(
            items=sorted(parent.app.equipment),
            tooltip='The equipment Service to start (on the local computer)',
        )
        self.combobox.setProperty('label', 'Alias:')
        super().__init__(parent, self.combobox)
        self.setWindowTitle('Start an Equipment Service')

    @Slot()
    def on_connect_clicked(self) -> None:
        """Connect to a Manager."""
        if not self.check_hostname():
            return

        username, password, password_manager = self.prompt_authentication()

        kwargs = {
            'host': self.host_lineedit.text().strip(),
            'port': self.port_spinbox.value(),
            'timeout': self.timeout_spinbox.value(),
            'username': username,
            'password': password,
            'password_manager': password_manager,
            'disable_tls': not self.tls_checkbox.isChecked(),
            'assert_hostname': self.assert_hostname_checkbox.isChecked(),
            'log_level': self.log_level_combobox.currentText(),
        }

        command = [
            'photons',
            self.parent.app.config.path,
            '--alias', self.combobox.currentText(),
            '--kwargs', serialize(kwargs),
        ]

        logger.info('starting equipment Service %r', self.combobox.currentText())
        p = subprocess.Popen(
            command,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env=dict(os.environ, PHOTONS_LOG_LEVEL='INFO')
        )

        # set the value of returncode in order to ignore:
        #   ResourceWarning: subprocess {pid} is still running
        # when p.__del__ is called
        p.returncode = 0

        # close the QDialog
        self.close()


class StartManager(QtWidgets.QDialog):

    def __init__(self, parent: MainWindow) -> None:
        """Start a Network Manager on `localhost`.

        Args:
            parent: The parent widget.
        """
        super().__init__(parent, Qt.WindowType.WindowCloseButtonHint)

        self.setWindowTitle('Start a Manager')

        self.port_spinbox = SpinBox(
            value=1875,
            minimum=1024,
            maximum=49151,
            tooltip='The port to use for the Manager'
        )

        self.tls_checkbox = CheckBox(
            initial=True,
            tooltip='Whether to use the TLS protocol',
        )

        self.authentication_combobox = ComboBox(
            items=['None', 'Manager Password', 'User login', 'Hostname'],
            tooltip='The authentication method that a Client/Service must use '
                    'to connect to the Manager',
        )

        self.log_level_combobox = ComboBox(
            items=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            initial='INFO',
            tooltip='The logging level to use',
        )

        self.start_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton,
            left_click=self.on_start_clicked,
            tooltip='Start',
        )

        self.cancel_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton,
            left_click=self.close,
            tooltip='Cancel'
        )

        form = QtWidgets.QFormLayout()
        form.addRow('Port:', self.port_spinbox)
        form.addRow('Authentication:', self.authentication_combobox)
        form.addRow('Log level:', self.log_level_combobox)
        form.addRow('Use TLS?', self.tls_checkbox)
        box = QtWidgets.QHBoxLayout()
        box.addWidget(self.start_button)
        box.addWidget(self.cancel_button)
        form.addRow(box)
        self.setLayout(form)
        self.show()

    @Slot()
    def on_start_clicked(self) -> None:
        """Start a Manager."""
        port = self.port_spinbox.value()
        netstat = ['netstat', '-a', '-n', '-o', '-p', 'TCP']
        stdout = subprocess.run(netstat, capture_output=True).stdout
        match = re.search(r'TCP.*:{}.*LISTENING\s+(\d+)'.format(port),
                          stdout.decode(), flags=re.MULTILINE)
        if match:
            prompt.critical(f'Port {port} is already in use.\n'
                            f'The process ID is {match.group(1)}.')
            return

        command = [
            'msl-network', 'start',
            '--port', str(port),
            '--log-level', self.log_level_combobox.currentText(),
        ]

        if not self.tls_checkbox.isChecked():
            command.append('--disable-tls')

        auth = self.authentication_combobox.currentText()
        if auth == 'Hostname':
            command.append('--auth-hostname')
        elif auth == 'User login':
            if not UsersTable().users():
                prompt.critical(
                    'The users table is empty. You must add at least one user '
                    'to be able to use a user login for authentication.\n\n'
                    'Run the following from the command line for more details:\n\n'
                    'msl-network user --help')
                return
            command.append('--auth-login')
        elif auth == 'Manager Password':
            password = prompt.text('Enter the password of the Manager:',
                                   echo=QtWidgets.QLineEdit.EchoMode.Password)
            if password:
                command.extend(['--auth-password', password])

        logger.info('starting Network Manager')
        p = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)

        # set the value of returncode in order to ignore:
        #   ResourceWarning: subprocess {pid} is still running
        # when p.__del__ is called
        p.returncode = 0

        # close the QDialog
        self.close()


class StartService(ClientServiceDialog):

    def __init__(self, parent: MainWindow) -> None:
        """Start a Service.

        The Service will be running on `localhost`, but the Manager
        can be running on a remote computer.

        Args:
            parent: The parent widget.
        """
        self.options = dict((s.name, s.description) for s in services)
        self.combobox = ComboBox(
            items=sorted(self.options),
            tooltip='The Service to start (on the local computer)',
        )
        self.combobox.setProperty('label', 'Name:')
        super().__init__(parent, self.combobox)
        self.setWindowTitle('Start a Service')

    @Slot()
    def on_connect_clicked(self) -> None:
        """Connect to a Manager."""
        if not self.check_hostname():
            return

        name = self.combobox.currentText()
        if not name:
            prompt.critical('There are no Services registered')
            return

        username, password, password_manager = self.prompt_authentication()

        kwargs = {
            'host': self.host_lineedit.text().strip(),
            'port': self.port_spinbox.value(),
            'timeout': self.timeout_spinbox.value(),
            'username': username,
            'password': password,
            'password_manager': password_manager,
            'disable_tls': not self.tls_checkbox.isChecked(),
            'assert_hostname': self.assert_hostname_checkbox.isChecked(),
            'log_level': self.log_level_combobox.currentText(),
        }

        command = [
            'photons',
            self.parent.app.config.path,
            '--name', name,
            '--kwargs', serialize(kwargs),
        ]

        logger.info('starting Service %r', name)
        p = subprocess.Popen(
            command,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env=dict(os.environ, PHOTONS_LOG_LEVEL='INFO')
        )

        # set the value of returncode in order to ignore:
        #   ResourceWarning: subprocess {pid} is still running
        # when p.__del__ is called
        p.returncode = 0

        # close the QDialog
        self.close()
