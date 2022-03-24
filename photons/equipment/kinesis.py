"""
Custom implementations for the Thorlabs Kinesis SDK.
"""
import time
from typing import Union

from msl.qt import (
    QtCore,
    Signal,
)
from msl.equipment.resources.thorlabs import (
    MotionControl,
    MotionControlCallback,
)

from . import BaseEquipment
from .. import logger

_build_device_list = True


def build_device_list():
    """
    Builds the Thorlabs device list (only once per application instance).
    """
    global _build_device_list
    if _build_device_list:
        logger.debug('calling Thorlabs.MotionControl.build_device_list()')
        MotionControl.build_device_list()
        _build_device_list = False


def prepare_kinesis(base_equipment):
    """Prepare the Kinesis SDK.

    Builds the device list (only once per application instance) and creates
    the objects necessary to handle callbacks from the SDK.

    Parameters
    ----------
    base_equipment : :class:`~photons.equipment.BaseEquipment`
        The equipment subclass.

    Returns
    -------
    :class:`tuple`
        The Qt signaler and the MotionControlCallback function.
    """
    @MotionControlCallback
    def callback():
        device = signaler.service
        if signaler.is_stage:
            # it is important to call status_bits() in the callback
            # because status_bits() updates the value of KinesisBase._is_moving
            device.status_bits()
            try:
                msg = device.convert_message(*device.get_next_message())
            except:
                msg = {'id': ''}
            encoder = device.get_encoder()
            value = [device.to_human(encoder), encoder, msg['id'] == 'Homed']
        else:
            value = device.get_position()
        signaler.position_changed.emit(value)  # emit the Qt signal
        device.emit_notification(value)  # notify all linked Clients

    class CallbackSignaler(QtCore.QObject):
        """Signal for the MotionControlCallback in the DLL."""

        # either an int (flipper) or a list (stage)
        position_changed = Signal(object)

        def __init__(self, service):
            super(CallbackSignaler, self).__init__()
            self.service = service

            # don't use hasattr() since a recursion error occurs
            self.is_stage = 'get_encoder' in dir(service)

    build_device_list()
    signaler = CallbackSignaler(base_equipment)
    return signaler, callback


class KinesisBase(BaseEquipment):
    MOVING_CLOCKWISE = 0x00000010
    MOVING_COUNTERCLOCKWISE = 0x00000020
    JOGGING_CLOCKWISE = 0x00000040
    JOGGING_COUNTERCLOCKWISE = 0x00000080
    HOMING = 0x00000200
    HOMED = 0x00000400
    MOVING = MOVING_CLOCKWISE | MOVING_COUNTERCLOCKWISE | JOGGING_CLOCKWISE | JOGGING_COUNTERCLOCKWISE | HOMING

    def __init__(self, app, record, *, demo=None):
        """Base class for equipment that uses the Kinesis SDK from Thorlabs.

        Parameters
        ----------
        app : :class:`photons.App`
            The main application entry point.
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment record.
        demo : :class:`bool`, optional
            Whether to simulate a connection to the equipment by opening
            a connection in demo mode.
        """
        # must put this before calling super() which calls record.connect() because prepare_kinesis()
        # calls MotionControl.build_device_list() which must be done before connecting to the device
        self.thorlabs_signaler, self._thorlabs_callback = prepare_kinesis(self)

        # define self._encoder_factor before calling super() to avoid getting an
        # AttributeError that sometimes occurs when starting the BaseEquipment as a Service
        super(KinesisBase, self).__init__(app, record, demo=demo)

        self._start_move_time = 0
        self._last_callback_time = 0
        self._is_moving = False
        self._info = {}

        self.connection.start_polling(100)
        self._poll_seconds = self.connection.polling_duration() * 1e-3

        self.connection.register_message_callback(self._thorlabs_callback)

        # not sure why, but this delay is needed to avoid getting a TypeError during
        # the Manager.check_identity() query when starting the BaseEquipment as a Service
        time.sleep(0.02)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes(['thorlabs_signaler'])

    def info(self) -> dict:
        """Return a :class:`dict` about the relevant information about the device."""
        return self._info

    def get_position(self) -> Union[int, float]:
        """Get the current position of the device."""
        raise NotImplementedError

    def set_position(self, position: Union[int, float]):
        """Set the current position of the device."""
        raise NotImplementedError

    def is_moving(self, delay: float = 0.2) -> bool:
        """Check whether the device moving.

        Parameters
        ----------
        delay : :class:`float`, optional
            The number of seconds to pass before checking whether the device is
            moving. Starting from rest, the motors can take some time to start
            moving and if this method is called too oon after setting the device
            to a new position the callback that checks the moving status might
            indicate that the motors are not currently moving.

        Returns
        -------
        :class:`bool`
            Whether the device is moving.
        """
        now = time.time()
        if now - self._start_move_time < delay:
            return True

        if self._is_moving and (now - self._last_callback_time > 2 * self._poll_seconds):
            # update the value of self._is_moving since too much time has past
            self.status_bits()

        return self._is_moving

    def wait(self, timeout: float = None) -> None:
        """Wait for the device to stop moving.

        Parameters
        ----------
        timeout : :class:`float`, optional
            The maximum number of seconds to wait.
        """
        now = time.time
        sleep = time.sleep
        t0 = now()
        while True:
            if not self.is_moving():
                return
            if timeout and now() - t0 > timeout:
                self.connection.raise_exception(
                    f'Waiting for {self.alias!r} to finish moving '
                    f'took longer than {timeout} seconds.'
                )
            sleep(self._poll_seconds)

    def status_bits(self) -> int:
        """Get the device status bits.

        This method gets called automatically in the callback
        (see :meth:`~photons.equipment.kinesis.prepare_kinesis.callback`).

        Returns
        -------
        :class:`int`
            The status bits.
        """
        bits = self.connection.get_status_bits()
        self._is_moving = bool(bits & KinesisBase.MOVING)
        self._last_callback_time = time.time()
        return bits
