"""
Dialogs for starting a Network :class:`~msl.network.manager.Manager`,
starting a :class:`~msl.network.service.Service` or connecting to a
:class:`~msl.network.manager.Manager` as a :class:`~msl.network.client.Client`.
"""
import re
import os
import sys
import logging
import subprocess

from msl.network.database import UsersTable
from msl.network.json import serialize
from msl.qt import (
    Qt,
    QtWidgets,
    SpinBox,
    Button,
    prompt,
)


class StartManager(QtWidgets.QDialog):

    def __init__(self, parent):
        """Start a Network :class:`~msl.network.manager.Manager`.

        The :class:`~msl.network.manager.Manager` will be running on `localhost`.

        Parameters
        ----------
        parent : :class:`QtWidgets.QWidget`
            The parent widget.
        """
        super(StartManager, self).__init__(parent, Qt.WindowCloseButtonHint)

        self.setWindowTitle('Start a Manager')

        self.port_spinbox = SpinBox(
            value=1875,
            minimum=1024,
            maximum=49151,
            tooltip='The port to use for the Manager'
        )

        self.tls_checkbox = QtWidgets.QCheckBox()
        self.tls_checkbox.setToolTip('Whether to use the TLS protocol')
        self.tls_checkbox.setChecked(True)

        self.authentication_combobox = QtWidgets.QComboBox()
        self.authentication_combobox.addItems(
            ['None', 'Manager Password', 'User login', 'Hostname'])
        self.authentication_combobox.setToolTip(
            'The authentication method that a Client/Service must '
            'use to connect to the Manager')

        self.debug_checkbox = QtWidgets.QCheckBox()
        self.debug_checkbox.setToolTip('Allow DEBUG messages to be visible')

        self.start_button = Button(
            icon=QtWidgets.QStyle.SP_DialogApplyButton,
            left_click=self.on_start_clicked,
            tooltip='Start')

        self.cancel_button = Button(
            icon=QtWidgets.QStyle.SP_DialogCancelButton,
            left_click=self.close,
            tooltip='Cancel')

        form = QtWidgets.QFormLayout()
        form.addRow('Port:', self.port_spinbox)
        form.addRow('Authentication:', self.authentication_combobox)
        form.addRow('Use TLS?', self.tls_checkbox)
        form.addRow('Debug mode?', self.debug_checkbox)
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.start_button)
        hbox.addWidget(self.cancel_button)
        form.addRow(hbox)
        self.setLayout(form)

        self.show()

    def on_start_clicked(self):
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
            os.path.join(os.path.dirname(sys.executable), 'Scripts', 'msl-network'),
            'start',
            '--port', str(port)
        ]

        if not self.tls_checkbox.isChecked():
            command.append('--disable-tls')

        if self.debug_checkbox.isChecked():
            command.append('--debug')

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
                                   echo=QtWidgets.QLineEdit.Password)
            if password:
                command.extend(['--auth-password', password])

        p = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)

        # set the value of the returncode in order to ignore:
        #   ResourceWarning: subprocess {pid} is still running
        # when p.__del__ is called
        p.returncode = 0

        # close the QDialog
        self.close()


class ClientServiceDialog(QtWidgets.QDialog):

    def __init__(self, parent, widget):
        """Connect to a :class:`~msl.network.manager.Manager` as either a
        :class:`~msl.network.client.Client` or as a :class:`~msl.network.service.Service`.

        Parameters
        ----------
        parent : :class:`QtWidgets.QWidget`
            The parent widget.
        widget : :class:`QtWidgets.QWidget`
            The widget to add to the first row of the :class:`QtWidgets.QFormLayout`.
        """
        super(ClientServiceDialog, self).__init__(parent, Qt.WindowCloseButtonHint)

        self.parent = parent

        self.host_lineedit = QtWidgets.QLineEdit()
        self.host_lineedit.setText('localhost')
        self.host_lineedit.setToolTip('The IP address or hostname of the '
                                      'computer the Manager is running on')

        self.port_spinbox = SpinBox(
            value=1875,
            minimum=1024,
            maximum=49151,
            tooltip='The port that the Manager is running on')

        self.tls_checkbox = QtWidgets.QCheckBox()
        self.tls_checkbox.setToolTip('Whether to use the TLS protocol')
        self.tls_checkbox.setChecked(True)

        self.assert_hostname_checkbox = QtWidgets.QCheckBox()
        self.assert_hostname_checkbox.setChecked(True)
        self.assert_hostname_checkbox.setToolTip(
            'Whether to force the hostname of the Manager to '
            'match the value of host.')

        self.authentication_combobox = QtWidgets.QComboBox()
        self.authentication_combobox.addItems(['None', 'Manager Password', 'User login'])
        self.authentication_combobox.setToolTip(
            'The authentication method that a Client/Service must '
            'use to connect to the Manager')

        self.timeout_spinbox = SpinBox(
            value=10,
            minimum=1,
            maximum=1000,
            tooltip='The timeout value in seconds')

        self.run_button = Button(
            icon=QtWidgets.QStyle.SP_DialogApplyButton,
            left_click=self.on_connect_clicked,
            tooltip='Run')

        self.abort_button = Button(
            icon=QtWidgets.QStyle.SP_DialogCancelButton,
            left_click=self.close,
            tooltip='Abort')

        form = QtWidgets.QFormLayout()
        form.addRow(widget.label_text, widget)
        form.addRow('Host:', self.host_lineedit)
        form.addRow('Port:', self.port_spinbox)
        form.addRow('Authentication:', self.authentication_combobox)
        form.addRow('Use TLS?', self.tls_checkbox)
        form.addRow('Assert hostname?', self.assert_hostname_checkbox)
        form.addRow('Timeout:', self.timeout_spinbox)
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.run_button)
        hbox.addWidget(self.abort_button)
        form.addRow(hbox)
        self.setLayout(form)

        self.show()

    def check_hostname(self) -> bool:
        if not self.host_lineedit.text().strip():
            prompt.critical('You must specify the hostname')
            return False
        return True

    def prompt_authentication(self):
        """Prompt the user for the authentication values (if necessary).

        Returns
        -------
        :class:`str` or :data:`None`
            The username.
        :class:`str` or :data:`None`
            The password of username.
        :class:`str` or :data:`None`
            The password of the Manager.
        """
        username = None
        password = None
        password_manager = None
        auth = self.authentication_combobox.currentText()
        if auth == 'User login':
            username = prompt.text('Enter the username:')
            if not username:
                return
            password = prompt.text(f'Enter the password for {username}:',
                                   echo=QtWidgets.QLineEdit.Password)
            if not password:
                return
        elif auth == 'Manager Password':
            password_manager = prompt.text('Enter the password of the Manager:',
                                           echo=QtWidgets.QLineEdit.Password)
            if not password_manager:
                return
        return username, password, password_manager


class CreateClient(ClientServiceDialog):

    def __init__(self, parent):
        """Connect to a :class:`~msl.network.manager.Manager` as a
        :class:`~msl.network.client.Client`.

        Parameters
        ----------
        parent : :class:`QtWidgets.QWidget`
            The parent widget.
        """
        self.name_lineedit = QtWidgets.QLineEdit()
        self.name_lineedit.setText('Client')
        self.name_lineedit.setToolTip('The name of the Client')
        self.name_lineedit.label_text = 'Client name:'
        super(CreateClient, self).__init__(parent, self.name_lineedit)
        self.setWindowTitle('Create a Client')

    def on_connect_clicked(self) -> None:
        if not self.check_hostname():
            return

        name = self.name_lineedit.text().strip()
        if not name:
            prompt.critical('You must specify the name of the Client')
            return

        auth = self.prompt_authentication()
        if auth is None:
            return

        username, password, password_manager = auth

        self.parent.app.create_client(
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

    def __init__(self, parent):
        """Start a :class:`~msl.network.service.Service` that interfaces with equipment.

        The :class:`~msl.network.service.Service` will be running on `localhost` but
        the :class:`~msl.network.manager.Manager` can be a remote computer.

        Parameters
        ----------
        parent : :class:`QtWidgets.QWidget`
            The parent widget.
        """
        self.alias_combobox = QtWidgets.QComboBox()
        self.alias_combobox.addItems(sorted(parent.app.equipment.keys()))
        self.alias_combobox.setToolTip('The service to start (on the local computer)')
        self.alias_combobox.label_text = 'Alias:'
        super(StartEquipmentService, self).__init__(parent, self.alias_combobox)
        self.setWindowTitle('Start an Equipment Service')

    def on_connect_clicked(self) -> None:
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
            'assert_hostname': self.assert_hostname_checkbox.isChecked()
        }

        command = [
            'start-service',
            self.parent.app.config.path,
            '--alias', self.alias_combobox.currentText(),
            '--kwargs', serialize(kwargs),
        ]

        p = subprocess.Popen(
            command,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env=dict(os.environ, PHOTON_LOG_LEVEL=str(logging.INFO))  # PHOTON_LOG_LEVEL -> see log.py module
        )

        # set the value of the returncode in order to ignore:
        #   ResourceWarning: subprocess {pid} is still running
        # when p.__del__ is called
        p.returncode = 0

        # close the QDialog
        self.close()


class StartService(ClientServiceDialog):

    def __init__(self, parent):
        """Start a :class:`~msl.network.service.Service`.

        The :class:`~msl.network.service.Service` will be running on `localhost` but
        the :class:`~msl.network.manager.Manager` can be a remote computer.

        Parameters
        ----------
        parent : :class:`QtWidgets.QWidget`
            The parent widget.
        """
        self.name_lineedit = QtWidgets.QLineEdit()
        self.name_lineedit.setToolTip('The service to start (on the local computer)')
        self.name_lineedit.label_text = 'Name:'
        super(StartService, self).__init__(parent, self.name_lineedit)
        self.setWindowTitle('Start a Service')

    def on_connect_clicked(self) -> None:
        if not self.check_hostname():
            return

        name = self.name_lineedit.text().strip()
        if not name:
            prompt.critical('You must specify the name of a Service to start')
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
            'assert_hostname': self.assert_hostname_checkbox.isChecked()
        }

        command = [
            'start-service',
            self.parent.app.config.path,
            '--name', name,
            '--kwargs', serialize(kwargs),
        ]

        p = subprocess.Popen(
            command,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env=dict(os.environ, PHOTON_LOG_LEVEL=str(logging.INFO))  # PHOTON_LOG_LEVEL -> see log.py module
        )

        # set the value of the returncode in order to ignore:
        #   ResourceWarning: subprocess {pid} is still running
        # when p.__del__ is called
        p.returncode = 0

        # close the QDialog
        self.close()
