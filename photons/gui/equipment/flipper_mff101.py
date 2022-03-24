"""
Widget for a Thorlabs MFF101 flipper.
"""
from msl.qt import QtWidgets

from . import (
    BaseWidget,
    widget,
)


@widget(manufacturer=r'Thorlabs', model=r'MFF101')
class MFF101Flipper(BaseWidget):

    def __init__(self, connection, *, parent=None):
        """Widget for a Thorlabs MFF101 flipper.

        Parameters
        ----------
        connection : :class:`photons.equipment.flipper_mff101.MFF101Flipper`
            The connection to the flipper.
        parent : :class:`QtWidgets.QWidget`, optional
            The parent widget.
        """
        super(MFF101Flipper, self).__init__(connection, parent=parent)

        self._combobox = QtWidgets.QComboBox()
        self._combobox.addItems(list(connection.info().values()))
        self._combobox.setToolTip('The position of the flipper')
        self._combobox.setCurrentIndex(connection.get_position() - 1)
        self._combobox.currentIndexChanged.connect(self.on_index_changed)

        # connect the MotionControlCallback to a slot
        if not connection.connected_as_link:
            connection.thorlabs_signaler.position_changed.connect(self.on_callback)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self._combobox)
        self.setLayout(hbox)

    def notification_handler(self, position) -> None:
        """Handle the notification emitted by a CallbackSignaler for a MotionControlCallback.

        See :mod:`photons.equipment.kinesis`.
        """
        self.on_callback(position)

    def on_index_changed(self, index) -> None:
        """Slot for the QComboBox.currentIndexChanged signal."""
        # undo the index change, let the MotionControlCallback update the index
        self.update_combobox(not index)
        self.connection.set_position(index + 1)

    def on_callback(self, position) -> None:
        """Slot for the MotionControlCallback signal."""
        index = position - 1
        if index < 0:  # the flipper is still moving
            return
        self.update_combobox(index)

    def update_combobox(self, index) -> None:
        """Update the combobox without emitting the currentIndexChanged signal."""
        self._combobox.blockSignals(True)
        self._combobox.setCurrentIndex(index)
        self._combobox.blockSignals(False)
