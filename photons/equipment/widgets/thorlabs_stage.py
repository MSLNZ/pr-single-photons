"""
Widget for a Thorlabs translational/rotational stage.
"""
from msl.qt import Button
from msl.qt import DoubleSpinBox
from msl.qt import Qt
from msl.qt import QtGui
from msl.qt import QtWidgets
from msl.qt import Slot
from msl.qt import prompt

from ..base import BaseEquipmentWidget
from ..base import widget
from ..thorlabs_stage import ThorlabsStage


@widget(manufacturer=r'Thorlabs', model=r'BSC201|K10CR1|KDC101|KST101|LTS150|LTS300')
class ThorlabsStageWidget(BaseEquipmentWidget):

    connection: ThorlabsStage

    def __init__(self,
                 connection: ThorlabsStage,
                 *,
                 parent: QtWidgets.QWidget = None) -> None:
        """Widget for a Thorlabs translational/rotational stage.

        Args:
            connection: The connection to the stage controller.
            parent: The parent widget.
        """
        super().__init__(connection, parent=parent)

        self.info = connection.info()
        unit = self.info['unit']
        self.min_position = self.info['minimum']
        self.max_position = self.info['maximum']

        encoder = connection.get_encoder()
        self._position = connection.to_human(encoder)

        self.position_spinbox = DoubleSpinBox(
            value=self._position,
            minimum=min(self._position, self.min_position),
            maximum=self.max_position,
            unit=unit,
            decimals=3,
            tooltip=f'Encoder: {encoder}',
            editing_finished=self.on_editing_finished,
        )

        # connect the MotionControlCallback to a slot
        if not self.connected_as_link:
            connection.signaler.position_changed.connect(self.on_callback)

        self.home_button = Button(
            icon='ieframe|0',
            left_click=self.on_home,
            tooltip='Home'
        )
        self.stop_button = Button(
            icon='wmploc|135',
            left_click=self.on_stop,
            tooltip='Stop moving'
        )
        self.settings_button = Button(
            icon='shell32|316',
            left_click=self.on_edit_settings,
            tooltip='Edit the settings'
        )

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.position_spinbox)
        layout.addWidget(self.home_button)
        layout.addWidget(self.settings_button)
        layout.addWidget(self.stop_button)
        self.setLayout(layout)

        self.setWindowTitle(f'{self.record.alias} || {self.max_position}{unit}')

    def notification_handler(self, info: dict) -> None:
        """Handle the notifications from a MotionControlCallback."""
        self.on_callback(info)

    @Slot(dict)
    def on_callback(self, info: dict) -> None:
        """Slot for the MotionControlCallback."""
        self._position = info['position']
        self.position_spinbox.setValue(self._position)
        self.position_spinbox.setToolTip(f'Encoder: {info["encoder"]}')
        if info['homed']:
            # undo that negative values were allowed in self.on_home()
            self.position_spinbox.setMinimum(self.min_position)

    @Slot()
    def on_edit_settings(self) -> None:
        """Slot for the self.settings_button click."""
        Settings(self).exec()

    @Slot()
    def on_editing_finished(self) -> None:
        """Slot for the DoubleSpinBox.editingFinished signal."""
        if self.connection.is_moving():
            # if the spinbox looses focus while it is moving then
            # the editingFinished signal should be ignored
            return

        position = self.position_spinbox.value()

        # ignore that this method gets called when the spinbox loses focus
        if position == self._position:
            return

        # Makes the value in the spinbox less "jumpy", otherwise, the final
        # position value is initially displayed in the spinbox.
        # The self.on_callback() slot will update the value of the spinbox.
        self.position_spinbox.setValue(self._position)

        self.connection.set_position(position, wait=False)

    @Slot()
    def on_home(self) -> None:
        """Home the stage."""
        # temporarily allow negative values to be displayed when homing
        self.position_spinbox.setMinimum(-self.max_position - 5)
        self.connection.home(wait=False)

    @Slot()
    def on_stop(self) -> None:
        """Stop the stage from moving."""
        self.connection.stop()


class Settings(QtWidgets.QDialog):

    def __init__(self, parent: ThorlabsStageWidget) -> None:
        """Edit the jog step size."""
        super().__init__(parent, Qt.WindowCloseButtonHint)

        self.parent = parent
        self.check_if_modified = True

        self.jog_original = parent.position_spinbox.singleStep()

        self.jog_spinbox = DoubleSpinBox(
            value=self.jog_original,
            minimum=0.001,
            maximum=parent.position_spinbox.maximum(),
            unit=parent.position_spinbox.suffix(),
            decimals=3,
            tooltip='The jog step size',
        )

        self.apply_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton,
            left_click=self.on_apply,
            tooltip='Apply'
        )

        self.cancel_button = Button(
            icon=QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton,
            left_click=self.close,
            tooltip='Cancel'
        )

        box = QtWidgets.QHBoxLayout()
        box.addWidget(self.apply_button)
        box.addWidget(self.cancel_button)
        form = QtWidgets.QFormLayout()
        form.addRow('Jog size: ', self.jog_spinbox)
        form.addRow(box)
        self.setLayout(form)
        self.setWindowTitle(f'{parent.record.manufacturer} {parent.record.model}')
        self.show()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Overrides :meth:`QtWidgets.QWidget.closeEvent` and maybe prompt to save."""
        if self.check_if_modified and self.jog_spinbox.value() != self.jog_original:
            if prompt.yes_no('You have modified the settings.\n\n'
                             'Apply the changes?', default=False):
                self.save_settings()
        super().closeEvent(event)

    @Slot()
    def on_apply(self) -> None:
        """Apply the settings."""
        self.save_settings()
        self.check_if_modified = False
        self.close()

    def save_settings(self) -> None:
        """Save the step size to the DoubleSpinBox."""
        self.parent.position_spinbox.setSingleStep(self.jog_spinbox.value())
