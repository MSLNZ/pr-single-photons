"""
Widget for a Thorlabs translational/rotational stage.
"""
from msl.qt import (
    prompt,
    Qt,
    QtWidgets,
    DoubleSpinBox,
    Button,
)

from . import (
    BaseWidget,
    widget,
)


@widget(manufacturer=r'Thorlabs', model=r'LTS150|LTS300|KDC101|KST101|BSC201')
class ThorlabsStage(BaseWidget):

    def __init__(self, connection, *, parent=None):
        """Widget for a Thorlabs translational/rotational stage.

        Parameters
        ----------
        connection
            The connection to the stage controller.
        parent : :class:`QtWidgets.QWidget`
            The parent widget.
        """
        super(ThorlabsStage, self).__init__(connection, parent=parent)

        self.info = connection.info()
        unit = self.info['unit']
        self.min_position = self.info['minimum']
        self.max_position = self.info['maximum']

        encoder = connection.get_encoder()
        self._previous_position_mm = connection.to_human(encoder)

        self.setWindowTitle(f'{self.record.alias} || {self.max_position}{unit}')

        self.position_spinbox = DoubleSpinBox()
        self.position_spinbox.setSuffix(unit)
        self.position_spinbox.setDecimals(3)
        self.position_spinbox.setRange(min(self._previous_position_mm, self.min_position), self.max_position)
        self.position_spinbox.setValue(self._previous_position_mm)
        self.position_spinbox.setToolTip(f'Encoder: {encoder}')
        self.position_spinbox.editingFinished.connect(self.on_position_changed)

        # connect the MotionControlCallback to a slot
        if not connection.connected_as_link:
            connection.thorlabs_signaler.position_changed.connect(self.on_callback)

        self.home_button = Button(
            icon='ieframe|0',
            left_click=self.on_home,
            tooltip='Home')
        self.stop_button = Button(
            icon='wmploc|135',
            left_click=self.on_stop,
            tooltip='Stop moving')
        self.settings_button = Button(
            icon='shell32|239',
            left_click=self.on_edit_settings,
            tooltip='Edit the settings')

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.position_spinbox)
        hbox.addWidget(self.home_button)
        hbox.addWidget(self.settings_button)
        hbox.addWidget(self.stop_button)
        self.setLayout(hbox)

    def notification_handler(self, values):
        """Handle the notification emitted by a CallbackSignaler for a MotionControlCallback.

        See :mod:`photons.equipment.kinesis`.
        """
        self.on_callback(values)

    def on_position_changed(self):
        """Slot for the DoubleSpinBox.editingFinished signal."""
        if self.connection.is_moving():
            # if the DoubleSpinBox looses focus while it is moving then
            # the editingFinished signal should be ignored
            return

        position = self.position_spinbox.value()

        # makes the value in the spinbox less "jumpy" since the callback will update the spinbox
        # otherwise the final position value is initially displayed in the spinbox
        self.position_spinbox.setValue(self._previous_position_mm)

        # ignore that this method gets called when the DoubleSpinBox loses focus
        if position == self._previous_position_mm:
            return

        self.connection.set_position(position, wait=False)

    def on_home(self):
        """Slot for the self.home_button click."""
        # temporarily allow negative values to be displayed when homing
        self.position_spinbox.setMinimum(-self.max_position - 5)
        self.connection.home(wait=False)

    def on_stop(self):
        """Slot for the self.stop_button click."""
        self.connection.stop()

    def on_edit_settings(self):
        """Slot for the self.settings_button click."""
        Settings(self).exec()

    def on_callback(self, values):
        """Slot for the MotionControlCallback."""
        position, encoder, homed = values
        self.position_spinbox.setValue(position)
        self.position_spinbox.setToolTip(f'Encoder: {encoder}')
        self._previous_position_mm = position
        if homed:  # then undo that negative values were allowed in self.on_home()
            self.position_spinbox.setMinimum(self.min_position)


class Settings(QtWidgets.QDialog):

    def __init__(self, parent):
        """Edit the rotation rate and the acceleration settings.

        Parameters
        ----------
        parent : :class:`.ThorlabsStage`
            The parent widget.
        """
        super(Settings, self).__init__(parent, Qt.WindowCloseButtonHint)

        self.parent = parent
        self.setWindowTitle(f'{parent.record.manufacturer} {parent.record.model}')

        self.ask_user = False

        self.jog_spinbox = DoubleSpinBox()
        self.jog_spinbox.setSuffix(parent.position_spinbox.suffix())
        self.jog_spinbox.setRange(0.001, parent.position_spinbox.maximum())
        self.jog_spinbox.setDecimals(3)
        self.jog_original = parent.position_spinbox.singleStep()
        self.jog_spinbox.setValue(self.jog_original)
        self.jog_spinbox.setToolTip('The jog size')
        self.jog_spinbox.valueChanged.connect(self.set_check_apply)

        self.apply_button = Button(icon=QtWidgets.QStyle.SP_DialogApplyButton,
                                   left_click=self.on_apply_clicked, tooltip='Apply')

        self.cancel_button = Button(icon=QtWidgets.QStyle.SP_DialogCancelButton,
                                    left_click=self.close, tooltip='Cancel')

        form = QtWidgets.QFormLayout()
        form.addRow('Jog size: ', self.jog_spinbox)
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.apply_button)
        hbox.addWidget(self.cancel_button)
        form.addRow(hbox)
        self.setLayout(form)
        self.show()

    def on_apply_clicked(self):
        """Slot for self.apply_button click."""
        self.save_settings()

    def set_check_apply(self):
        """A value was changed so notify the user if closing the dialog without applying the changes."""
        self.ask_user = True

    def save_settings(self):
        """Save the settings to the controller."""
        self.ask_user = False
        self.parent.position_spinbox.setSingleStep(self.jog_spinbox.value())

        # close the QDialog
        self.close()

    def closeEvent(self, event):
        """Overrides :meth:`QtWidgets.QDialog.closeEvent`."""
        if self.ask_user and self.jog_spinbox.value() != self.jog_original:
            if prompt.yes_no('You have modified the settings.\n\nApply the changes?', default=False):
                self.save_settings()
        super(Settings, self).closeEvent(event)
