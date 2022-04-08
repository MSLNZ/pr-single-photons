"""
Widget for an OptoSigma SHOT-702 controller.
"""
from msl import qt

from . import (
    BaseWidget,
    widget,
)


@widget(manufacturer=r'OptoSigma', model=r'SHOT-702')
class OptoSigmaSHOT702(BaseWidget):

    def __init__(self, connection, *, parent=None):
        """Widget for an OptoSigma SHOT-702 controller.

        Parameters
        ----------
        connection : :class:`photons.equipment.shot702_controller.OptoSigmaSHOT702`
            The connection to the SHOT-702 controller.
        parent : :class:`QtWidgets.QWidget`
            The parent widget.
        """
        super(OptoSigmaSHOT702, self).__init__(connection, parent=parent)

        self._is_moving = False

        self._timer = qt.QtCore.QTimer()
        self._timer.timeout.connect(self.get_status)

        self.angle_spinbox = qt.DoubleSpinBox()
        self.angle_spinbox.setSuffix(qt.DEGREE)
        self.angle_spinbox.setDecimals(4)  # resolution is 0.0025 degrees
        self.angle_spinbox.setRange(-360, 360)
        self._previous_position, _ = self.connection.status()
        self._previous_angle = self.connection.position_to_degrees(self._previous_position)
        self.angle_spinbox.setToolTip(f'Encoder: {self._previous_position}')
        self.angle_spinbox.setValue(self._previous_angle)
        self.angle_spinbox.editingFinished.connect(self.on_angle_changed)
        if not self.connected_as_link:
            connection.angle_changed.connect(self._timer.start)

        self.home_button = qt.Button(
            icon='ieframe|0',
            left_click=self.on_home,
            tooltip='Home'
        )
        self.settings_button = qt.Button(
            icon='shell32|239',
            left_click=self.on_edit_settings,
            tooltip='Edit the settings'
        )
        self.stop_button = qt.Button(
            icon='wmploc|135',
            left_click=self.on_stop,
            tooltip='Stop moving'
        )

        hbox = qt.QtWidgets.QHBoxLayout()
        hbox.addWidget(self.angle_spinbox)
        hbox.addWidget(self.home_button)
        hbox.addWidget(self.settings_button)
        hbox.addWidget(self.stop_button)
        self.setLayout(hbox)

    def notification_handler(self, position, angle, is_moving) -> None:
        """Handle a notification emitted by
        :class:`~photons.equipment.shot702_controller.OptoSigmaSHOT702`."""
        self.update_angle_spinbox(position, angle)
        self._is_moving = is_moving

    def has_move_started(self) -> bool:
        """Return whether the rotation stage is moving."""
        return self._timer.isActive() or self._is_moving

    def on_angle_changed(self) -> None:
        """Slot for DoubleSpinBox.editingFinished signal."""
        angle = self.angle_spinbox.value()

        # let the displayed value get updated by signals/notifications
        self.angle_spinbox.setValue(self._previous_angle)

        if angle == self._previous_angle or self.has_move_started():
            # ignore that this method gets called when the QDoubleSpinBox loses focus
            return

        self.connection.set_angle(angle, wait=False)

    def on_home(self) -> None:
        """Slot for the self._home_button click signal."""
        if not self.has_move_started():
            self.connection.home(wait=False)
        else:
            qt.prompt.information('Wait for the controller to finish moving')

    def on_stop(self) -> None:
        """Slot for the self._stop_button click signal."""
        self.connection.stop_slowly()

    def on_edit_settings(self) -> None:
        """Slot for the self._settings_button click signal."""
        if not self.has_move_started():
            SettingsDialog(self).exec()
        else:
            qt.prompt.information('Wait for the controller to finish moving')

    def get_status(self) -> None:
        """Slot for the QTimer.timeout signal."""
        position, moving = self.connection.status()
        angle = self.connection.position_to_degrees(position)
        self.update_angle_spinbox(position, angle)
        if not moving:
            self._timer.stop()

    def update_angle_spinbox(self, position, angle) -> None:
        """Update the value and tooltip of self.angle_spinbox."""
        self.angle_spinbox.setValue(angle)
        self.angle_spinbox.setToolTip(f'Encoder: {position}')
        self._previous_angle = angle
        self._previous_position = position


class SettingsDialog(qt.QtWidgets.QDialog):

    def __init__(self, parent):
        """Edit the rotation rate and the acceleration settings.

        Parameters
        ----------
        parent : :class:`.OptoSigmaSHOT702`
            The parent widget.
        """
        super(SettingsDialog, self).__init__(parent, qt.Qt.WindowCloseButtonHint)

        self.connection = parent.connection
        self.setWindowTitle(f'{parent.record.manufacturer} {parent.record.model}')

        self.ask_user = False

        # the min/max values are pulses per second
        # the acceleration is in milliseconds
        move_min_pps, move_max_pps, move_acc_ms = parent.connection.get_speed()
        home_min_pps, home_max_pps, home_acc_ms = parent.connection.get_speed_home()

        # the travel per pulse should be (1.0, 1.0)
        travel1, travel2 = parent.connection.get_travel_per_pulse()
        if travel1 != 1.0 or travel2 != 1.0:
            raise ValueError(f'Unexpected travel-per-pulse values '
                             f'{(travel1, travel2)} is not (1.0, 1.0)')

        # According to the manual
        # Max. Driving Speed: 500000 pps -> 1250 deg/s
        # Min. Driving Speed: 1 pps -> 0.0025 deg/s
        # Acceleration/Deceleration Time: 1 - 1000ms

        # convert to degrees per second
        self.deg_per_pulse = parent.connection.degrees_per_pulse
        self.move_max_original = move_max_pps * self.deg_per_pulse
        self.home_max_original = home_max_pps * self.deg_per_pulse

        self.move_acc_original = move_acc_ms
        self.home_acc_original = home_acc_ms

        self.jog_spinbox = qt.DoubleSpinBox(step=0.1)
        self.jog_spinbox.setSuffix(qt.DEGREE)
        self.jog_spinbox.setRange(0, 360)
        self.jog_spinbox.setValue(parent.angle_spinbox.singleStep())
        self.jog_spinbox.setToolTip('The jog size')
        self.jog_spinbox.valueChanged.connect(self.set_check_apply)

        self.move_max_spinbox = qt.DoubleSpinBox()
        self.move_max_spinbox.setSuffix(f'{qt.DEGREE}/s')
        self.move_max_spinbox.setRange(0.0025, 1250)
        self.move_max_spinbox.setValue(self.move_max_original)
        self.move_max_spinbox.setToolTip('The maximum rotation rate when moving')
        self.move_max_spinbox.valueChanged.connect(self.set_check_apply)

        self.home_max_spinbox = qt.DoubleSpinBox()
        self.home_max_spinbox.setSuffix(f'{qt.DEGREE}/s')
        self.home_max_spinbox.setRange(0.0025, 1250)
        self.home_max_spinbox.setValue(self.home_max_original)
        self.home_max_spinbox.setToolTip('The maximum rotation rate when homing')
        self.home_max_spinbox.valueChanged.connect(self.set_check_apply)

        self.move_acc_spinbox = qt.SpinBox()
        self.move_acc_spinbox.setSuffix(' ms')
        self.move_acc_spinbox.setRange(1, 1000)
        self.move_acc_spinbox.setValue(self.move_acc_original)
        self.move_acc_spinbox.setToolTip('The amount of time to accelerate/decelerate when moving')
        self.move_acc_spinbox.valueChanged.connect(self.set_check_apply)

        self.home_acc_spinbox = qt.SpinBox()
        self.home_acc_spinbox.setSuffix(' ms')
        self.home_acc_spinbox.setRange(1, 1000)
        self.home_acc_spinbox.setValue(self.home_acc_original)
        self.home_acc_spinbox.setToolTip('The amount of time to accelerate/decelerate when homing')
        self.home_acc_spinbox.valueChanged.connect(self.set_check_apply)

        self.apply_button = qt.Button(
            icon=qt.QtWidgets.QStyle.SP_DialogApplyButton,
            left_click=self.on_apply_clicked,
            tooltip='Apply'
        )

        self.cancel_button = qt.Button(
            icon=qt.QtWidgets.QStyle.SP_DialogCancelButton,
            left_click=self.close,
            tooltip='Cancel'
        )

        form = qt.QtWidgets.QFormLayout()
        hbox = qt.QtWidgets.QHBoxLayout()
        hbox.addWidget(self.move_max_spinbox)
        hbox.addWidget(self.move_acc_spinbox)
        form.addRow('Moving: ', hbox)
        hbox = qt.QtWidgets.QHBoxLayout()
        hbox.addWidget(self.home_max_spinbox)
        hbox.addWidget(self.home_acc_spinbox)
        form.addRow('Homing: ', hbox)
        form.addRow('Jog: ', self.jog_spinbox)
        hbox = qt.QtWidgets.QHBoxLayout()
        hbox.addWidget(self.apply_button)
        hbox.addWidget(self.cancel_button)
        form.addRow(hbox)
        self.setLayout(form)
        self.show()

    def on_apply_clicked(self) -> None:
        """Slot for self.apply_button click."""
        self.save_settings()

    def set_check_apply(self) -> None:
        """A value was changed so notify the user if closing the
        dialog without applying the changes."""
        self.ask_user = True

    def save_settings(self) -> None:
        """Save the settings to the controller."""
        self.ask_user = False

        self.parent().angle_spinbox.setSingleStep(self.jog_spinbox.value())

        move_max = self.move_max_spinbox.value()
        move_acc = self.move_acc_spinbox.value()
        home_max = self.home_max_spinbox.value()
        home_acc = self.home_acc_spinbox.value()

        # convert to pulses per second
        move_max = round(move_max / self.deg_per_pulse)
        move_min = move_max // 10
        home_max = round(home_max / self.deg_per_pulse)
        home_min = home_max // 10

        self.connection.set_speed(move_min, move_max, move_acc)
        self.connection.set_speed_home(home_min, home_max, home_acc)

        # close the QDialog
        self.close()

    def closeEvent(self, event) -> None:
        """Overrides :meth:`QtWidgets.QDialog.closeEvent`."""
        if self.ask_user:
            if self.move_max_spinbox.value() != self.move_max_original or \
                    self.home_max_spinbox.value() != self.home_max_original or \
                    self.move_acc_spinbox.value() != self.move_acc_original or \
                    self.home_acc_spinbox.value() != self.home_acc_original:
                if qt.prompt.yes_no(
                        'You have modified the settings.\n\n'
                        'Apply the changes?',
                        default=False):
                    self.save_settings()
        super(SettingsDialog, self).closeEvent(event)
