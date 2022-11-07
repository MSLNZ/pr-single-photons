"""
Base class for equipment that use the Kinesis SDK from Thorlabs.
"""
import time

from msl.equipment import EquipmentRecord
from msl.equipment.exceptions import ThorlabsError
from msl.equipment.resources.thorlabs import MotionControl
from msl.equipment.resources.thorlabs import MotionControlCallback
from msl.qt import QtCore
from msl.qt import Signal

from .base import BaseEquipment
from ..log import logger


class KinesisBase(BaseEquipment):

    connection: MotionControl

    _device_list_built = False

    MOVING_CLOCKWISE = 0x00000010
    MOVING_COUNTERCLOCKWISE = 0x00000020
    JOGGING_CLOCKWISE = 0x00000040
    JOGGING_COUNTERCLOCKWISE = 0x00000080
    HOMING = 0x00000200
    HOMED = 0x00000400
    MOVING = MOVING_CLOCKWISE | MOVING_COUNTERCLOCKWISE | JOGGING_CLOCKWISE | JOGGING_COUNTERCLOCKWISE | HOMING

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Base class for equipment that use the Kinesis SDK from Thorlabs.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        KinesisBase.build_device_list()
        super().__init__(record, **kwargs)

        self._start_move_time: float = 0.0
        self._last_callback_time: float = 0.0
        self._is_moving: bool = False
        self._info: dict = {}

        self.signaler = Signaler(self)
        self._callback = callback(self.signaler)
        self.connection.register_message_callback(self._callback)  # noqa

        self.connection.start_polling(100)  # noqa
        self._poll_seconds = self.connection.polling_duration() * 1e-3  # noqa

        self.ignore_attributes(
            'signaler',
            'build_device_list',
            'MOVING_CLOCKWISE',
            'MOVING_COUNTERCLOCKWISE',
            'JOGGING_CLOCKWISE',
            'JOGGING_COUNTERCLOCKWISE',
            'HOMING',
            'HOMED',
            'MOVING'
        )

    @staticmethod
    def build_device_list() -> None:
        """Builds the Thorlabs device list.

        Only builds the device list once per application instance. This
        function can be called multiple times.
        """
        if KinesisBase._device_list_built:
            return
        logger.debug('calling Thorlabs.MotionControl.build_device_list()')
        MotionControl.build_device_list()
        KinesisBase._device_list_built = True

    def get_position(self) -> int | float:
        """Get the current position of the device."""
        raise NotImplementedError

    def info(self) -> dict:
        """Return information about the device.

        The subclass must populate the dict.
        """
        return self._info

    def is_moving(self, delay: float = 0.2) -> bool:
        """Returns whether the device moving.

        Args:
            delay: The number of seconds to wait before checking whether the
                device is moving. Starting from rest, the motors take time to
                start moving the device and if this method is called too soon
                after requesting the device to move to a new position then the
                callback that checks the moving status might indicate that the
                motors are not currently moving.
        """
        now = time.time()
        if now - self._start_move_time < delay:
            return True

        if self._is_moving and (now - self._last_callback_time > 2 * self._poll_seconds):
            # update the value of self._is_moving since too much time has past
            # since the callback was called
            self.status_bits()

        return self._is_moving

    def set_position(self, position: int | float) -> None:
        """Set the current position of the device."""
        raise NotImplementedError

    def status_bits(self) -> int:
        """Returns the device status bits.

        This method gets called automatically in the registered callback.
        """
        bits = self.connection.get_status_bits()  # noqa
        self._is_moving = bool(bits & KinesisBase.MOVING)
        self._last_callback_time = time.time()
        return bits

    def wait(self, timeout: float = None) -> None:
        """Wait for the device to stop moving.

        Args:
            timeout: The maximum number of seconds to wait.
                Default is to wait forever.
        """
        now = time.time
        t0 = now()
        while True:
            if not self.is_moving():
                return
            if timeout and now() - t0 > timeout:
                self.raise_exception(
                    f'Waiting for {self.alias!r} to finish moving '
                    f'took longer than {timeout} seconds.'
                )
            time.sleep(self._poll_seconds)


class Signaler(QtCore.QObject):
    """Qt Signaler for callbacks that are received from the DLL."""

    # {'position': int | float, 'encoder': int | None, 'homed': bool | None}
    # 'encoder' and 'homed' are only valid for stages (but are always in dict)
    position_changed: QtCore.SignalInstance = Signal(dict)

    def __init__(self, kinesis: KinesisBase) -> None:
        super().__init__()
        self.device: KinesisBase = kinesis

        # don't use hasattr() since a recursion error occurs
        self.is_stage: bool = 'get_encoder' in dir(kinesis)


def callback(signaler: Signaler):
    """Create a callback for the `signaler`."""
    @MotionControlCallback
    def _callback() -> None:
        """Emits the Qt Signal and notifies all linked Clients."""
        device = signaler.device
        # it is important to call status_bits() in the callback
        # because status_bits() updates the value of KinesisBase._is_moving
        device.status_bits()
        if signaler.is_stage:
            encoder = device.get_encoder()
            position = device.to_human(encoder)
            try:
                msg = device.convert_message(*device.get_next_message())
                homed = msg['id'] == 'Homed'
            except ThorlabsError:
                homed = False
        else:
            position = device.get_position()
            encoder = None
            homed = None
        value = {'position': position, 'encoder': encoder, 'homed': homed}
        signaler.position_changed.emit(value)
        device.maybe_emit_notification(value)
    return _callback
