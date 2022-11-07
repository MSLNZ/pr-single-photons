"""
Widget for an OptoSigma SHOT-702 controller.
"""
from msl.qt import Button
from msl.qt import DEGREE
from msl.qt import DoubleSpinBox
from msl.qt import Qt
from msl.qt import QtCore
from msl.qt import QtGui
from msl.qt import QtWidgets
from msl.qt import Slot
from msl.qt import SpinBox
from msl.qt import prompt

from ..base import BaseEquipmentWidget
from ..base import widget
from ..shot702_controller import OptoSigmaSHOT702


@widget(manufacturer=r'OptoSigma', model=r'SHOT-702')
class OptoSigmaSHOT702Widget(BaseEquipmentWidget):

    connection: OptoSigmaSHOT702

    def __init__(self,
                 connection: OptoSigmaSHOT702,
                 *,
                 parent: QtWidgets.QWidget = None) -> None:
        """Widget for an OptoSigma SHOT-702 controller.

        Args:
            connection: The connection to the SHOT-702 controller.
            parent: The parent widget.
        """
        super().__init__(connection, parent=parent)

        self._is_moving = False

        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.on_timer_timeout)  # noqa: QTimer.timeout exists

        self._position, _ = self.connection.status()
        self._angle = self.connection.position_to_degrees(self._position)

        self.angle_spinbox = DoubleSpinBox(
            value=self._angle,
            maximum=360,
            minimum=-360,
            decimals=4,  # resolution is 0.0025 degrees
            unit=DEGREE,
            tooltip=f'Encoder: {self._position}',
            editing_finished=self.on_angle_editing_finished
        )

        if not self.connected_as_link:
            connection.angle_changed.connect(self._timer.start)

        self.home_button = Button(
            icon='ieframe|0',
            left_click=self.on_home,
            tooltip='Home'
        )
        self.settings_button = Button(
            icon='shell32|316',
            left_click=self.on_edit_settings,
            tooltip='Edit the settings'
        )
        self.stop_button = Button(
            icon='wmploc|135',
            left_click=self.on_stop,
            tooltip='Stop moving'
        )

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.angle_spinbox)
        layout.addWidget(self.home_button)
        layout.addWidget(self.settings_button)
        layout.addWidget(self.stop_button)
        self.setLayout(layout)

    def has_move_started(self) -> bool:
        """Return whether the rotation stage is moving."""
        return self._timer.isActive() or self._is_moving

    def notification_handler(self, position: int, angle: float, is_moving: bool) -> None:
        """Handle notifications emitted by the OptoSigmaSHOT702 Service."""
        self.update_angle_spinbox(position, angle)
        self._is_moving = is_moving

    @Slot()
    def on_angle_editing_finished(self) -> None:
        """Set the angle of the stage."""
        angle = self.angle_spinbox.value()

        # let the displayed value get updated by signals/notifications
        self.angle_spinbox.setValue(self._angle)

        if angle == self._angle or self.has_move_started():
            return

        self.connection.set_angle(angle, wait=False)

    @Slot()
    def on_edit_settings(self) -> None:
        """Show the Settings Dialog."""
        if not self.has_move_started():
            SettingsDialog(self).exec()
        else:
            prompt.information('Wait for the stage to finish moving')

    @Slot()
    def on_home(self) -> None:
        """Home the stage."""
        if not self.has_move_started():
            self.connection.home(wait=False)
        else:
            prompt.information('Wait for the stage to finish moving')

    @Slot()
    def on_stop(self) -> None:
        """Stop the stage from moving."""
        self.connection.stop_slowly()

    @Slot()
    def on_timer_timeout(self) -> None:
        """Slot for the QTimer timeout signal."""
        position, moving = self.connection.status()
        angle = self.connection.position_to_degrees(position)
        self.update_angle_spinbox(position, angle)
        if not moving:
            self._timer.stop()

    def update_angle_spinbox(self, position: int, angle: float) -> None:
        """Update the value and tooltip Angle spinbox."""
        self.angle_spinbox.setValue(angle)
        self.angle_spinbox.setToolTip(f'Encoder: {position}')
        self._angle = angle
        self._position = position


class SettingsDialog(QtWidgets.QDialog):

    def __init__(self, parent: OptoSigmaSHOT702Widget) -> None:
        """Edit the rotation rate and the acceleration settings.

        Args:
            parent: The parent widget.
        """
        super().__init__(parent, Qt.WindowCloseButtonHint)

        self.check_if_modified = True
        self.connection = parent.connection
        self.setWindowTitle(f'{parent.record.manufacturer} {parent.record.model}')

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
        if parent.connected_as_link:
            self.deg_per_pulse = parent.connection.degrees_per_pulse()  # noqa
        else:
            self.deg_per_pulse = parent.connection.degrees_per_pulse
        self.move_max_original = move_max_pps * self.deg_per_pulse
        self.home_max_original = home_max_pps * self.deg_per_pulse

        self.move_acc_original = move_acc_ms
        self.home_acc_original = home_acc_ms

        self.jog_original = parent.angle_spinbox.singleStep()

        self.jog_spinbox = DoubleSpinBox(
            value=self.jog_original,
            minimum=0,
            maximum=360,
            step=0.1,
            unit=DEGREE,
            tooltip='The jog size',
        )

        self.move_max_spinbox = DoubleSpinBox(
            value=self.move_max_original,
            minimum=0.0025,
            maximum=1250,
            unit=f'{DEGREE}/s',
            tooltip='The maximum rotation rate when moving',
        )

        self.home_max_spinbox = DoubleSpinBox(
            value=self.home_max_original,
            minimum=0.0025,
            maximum=1250,
            unit=f'{DEGREE}/s',
            tooltip='The maximum rotation rate when homing',
        )

        self.move_acc_spinbox = SpinBox(
            value=self.move_acc_original,
            minimum=1,
            maximum=1000,
            unit=' ms',
            tooltip='The acceleration/deceleration time when moving',
        )

        self.home_acc_spinbox = SpinBox(
            value=self.home_acc_original,
            minimum=1,
            maximum=1000,
            unit=' ms',
            tooltip='The acceleration/deceleration time when homing',
        )

        self.apply_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton,
            left_click=self.on_apply_clicked,
            tooltip='Apply'
        )

        self.cancel_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton,
            left_click=self.close,
            tooltip='Cancel'
        )

        form = QtWidgets.QFormLayout()
        box1 = QtWidgets.QHBoxLayout()
        box1.addWidget(self.move_max_spinbox)
        box1.addWidget(self.move_acc_spinbox)
        form.addRow('Moving: ', box1)
        box2 = QtWidgets.QHBoxLayout()
        box2.addWidget(self.home_max_spinbox)
        box2.addWidget(self.home_acc_spinbox)
        form.addRow('Homing: ', box2)
        form.addRow('Jog: ', self.jog_spinbox)
        box3 = QtWidgets.QHBoxLayout()
        box3.addWidget(self.apply_button)
        box3.addWidget(self.cancel_button)
        form.addRow(box3)
        self.setLayout(form)
        self.show()

    @Slot()
    def on_apply_clicked(self) -> None:
        """The Apply button was clicked."""
        self.save_settings()
        self.check_if_modified = False
        self.close()

    def save_settings(self) -> None:
        """Save the settings to the controller."""
        self.parent().angle_spinbox.setSingleStep(self.jog_spinbox.value())

        # convert to pulses per second
        move_max = round(self.move_max_spinbox.value() / self.deg_per_pulse)
        move_min = move_max // 10
        home_max = round(self.home_max_spinbox.value() / self.deg_per_pulse)
        home_min = home_max // 10

        self.connection.set_speed(move_min, move_max, self.move_acc_spinbox.value())
        self.connection.set_speed_home(home_min, home_max, self.home_acc_spinbox.value())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.closeEvent`."""
        if self.check_if_modified and (
                self.move_max_spinbox.value() != self.move_max_original or
                self.home_max_spinbox.value() != self.home_max_original or
                self.move_acc_spinbox.value() != self.move_acc_original or
                self.home_acc_spinbox.value() != self.home_acc_original or
                self.jog_spinbox.value() != self.jog_original):
            if prompt.yes_no(
                    'You have modified the settings.\n\n'
                    'Apply the changes?',
                    default=False):
                self.save_settings()
        super().closeEvent(event)
