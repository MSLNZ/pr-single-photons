"""
OptoSigma SHOT-702 controller.
"""
import re
import time
from threading import Thread

from msl.equipment import EquipmentRecord
from msl.equipment.exceptions import OptoSigmaError
from msl.equipment.resources.optosigma import SHOT702
from msl.qt import QtCore
from msl.qt import Signal

from .base import BaseEquipment
from .base import equipment


@equipment(manufacturer=r'OptoSigma', model=r'SHOT-702', flags=re.ASCII)
class OptoSigmaSHOT702(BaseEquipment):

    connection: SHOT702

    NUM_PULSES_PER_360_DEGREES = 144000

    angle_changed: QtCore.SignalInstance = Signal()

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """OptoSigma SHOT-702 controller.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)

        self._emitting_thread: Thread | None = None
        self._stop_slowly_requested: bool = False
        self._degrees_per_pulse: float = 360.0 / float(self.NUM_PULSES_PER_360_DEGREES)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes('angle_changed')

        # find out what is attached to each stage -> stage#=model[serial] where # is either 1 or 2
        stage1 = record.connection.properties.get('stage1')
        stage2 = record.connection.properties.get('stage2')

        # determine what stage the continuously-variable filter wheel is attached to
        if stage1 and stage1 == 'OSMS-60-NDU_FCBH-069[10634]':
            self._wheel = 1
        elif stage2 and stage2 == 'OSMS-60-NDU_FCBH-069[10634]':
            self._wheel = 2
        else:
            self.raise_exception(
                f'\nCannot determine which stage the continuously-variable '
                f'filter wheel is attached to. Define a stage#=model[serial] '
                f'in the record.connection.properties, where # is 1 or 2'
            )

        # Sometimes the controller sends data in an unexpected format.
        # The try-except block is an attempt to clear the controller's buffer.
        # Using PySerial's read_all() method clears the buffer for the OS, not the controller.
        try:
            self.stop_slowly()
        except OptoSigmaError:
            self.stop_slowly()

    @property
    def degrees_per_pulse(self) -> float:
        """Returns the number of degrees per pulse."""
        return self._degrees_per_pulse

    def degrees_to_position(self, degrees: float) -> int:
        """Convert an angle, in degrees, to an encoder position.

        Args:
            degrees: An angle, in degrees.

        Returns:
            The corresponding encoder position.
        """
        return round(degrees / self._degrees_per_pulse)

    def get_angle(self) -> float:
        """Returns the angle (in degrees) of the filter wheel."""
        position, _ = self.status()
        return self.position_to_degrees(position)

    def get_speed(self) -> tuple[int, int, int]:
        """Get speed that the stage moves to a new angle.

        Returns:
            The minimum speed (in number of pulses per second),
                the maximum speed (in number of pulses per second)
                and the acceleration/deceleration time in ms.
        """
        return self.connection.get_speed()[f'stage{self._wheel}']

    def get_speed_home(self) -> tuple[int, int, int]:
        """Get speed that the stage moves home.

        Returns:
            The minimum speed (in number of pulses per second),
                the maximum speed (in number of pulses per second),
                and the acceleration/deceleration time in ms.
        """
        return self.connection.get_speed_origin()[f'stage{self._wheel}']

    def home(self,
             *,
             wait: bool = True,
             timeout: float = 300) -> None:
        """Home the continuously-variable filter wheel.

        Args:
            wait: Whether to wait for the wheel to stop moving.
            timeout: The maximum number of seconds to wait for the wheel to
                stop moving.
        """
        self.connection.home(self._wheel)
        self.logger.info(f'home {self.alias!r}')
        self.angle_changed.emit()
        self._maybe_start_emitting()
        if wait:
            self._wait(timeout)

    def is_moving(self) -> bool:
        """Returns whether the filter wheel is moving."""
        return self.status()[1]

    def position_to_degrees(self, position: int, *, bound: bool = False) -> float:
        """Convert an encoder position to an angle in degrees.

        Args:
            position: The encoder position.
            bound: Whether to bound the angle to be between [0, 360) degrees.

        Returns:
            The angle in degrees.
        """
        degrees = round(position * self._degrees_per_pulse, 4)
        if bound:
            return round(degrees % 360., 4)
        return degrees

    def set_angle(self,
                  degrees: float,
                  *,
                  wait: bool = True,
                  timeout: float = 300) -> None:
        """Set the angle of the continuously-variable filter wheel.

        Args:
            degrees: The angle, in degrees.
            wait: Whether to wait for the wheel to stop moving.
            timeout: The maximum number of seconds to wait for the wheel to
                stop moving.
        """
        self.connection.move_absolute(self._wheel, self.degrees_to_position(degrees))
        self.logger.info(f'{self.alias!r} set to {degrees} degrees')
        self.angle_changed.emit()
        self._maybe_start_emitting()
        if wait:
            self._wait(timeout)

    def set_speed(self, minimum: int, maximum: int, acceleration: int) -> None:
        """Set speed that the stage moves to a new angle.

        According to the manual::

            Max. Driving Speed: 500000 pps -> 1250 deg/s
            Min. Driving Speed: 1 pps -> 0.0025 deg/s
            Acceleration/Deceleration Time: 1 - 1000ms

        Args:
            minimum: The minimum speed (in number of pulses per second).
            maximum: The maximum speed (in number of pulses per second).
            acceleration: The acceleration/deceleration time in ms.
        """
        self.connection.set_speed(self._wheel, minimum, maximum, acceleration)
        self.logger.info(f'{self.alias!r} set the move speed settings to '
                         f'minimum={minimum} PPS, maximum={maximum} PPS, '
                         f'acceleration={acceleration} ms')

    def set_speed_home(self, minimum: int, maximum: int, acceleration: int) -> None:
        """Set speed that the stage moves home.

        According to the manual::

            Max. Driving Speed: 500000 pps -> 1250 deg/s
            Min. Driving Speed: 1 pps -> 0.0025 deg/s
            Acceleration/Deceleration Time: 1 - 1000ms

        Args:
            minimum: The minimum speed (in number of pulses per second).
            maximum: The maximum speed (in number of pulses per second).
            acceleration: The acceleration/deceleration time in ms.
        """
        self.connection.set_speed_origin(self._wheel, minimum, maximum, acceleration)
        self.logger.info(f'{self.alias!r} set the move home speed settings to '
                         f'minimum={minimum} PPS, maximum={maximum} PPS, '
                         f'acceleration={acceleration} ms')

    def status(self) -> tuple[int, bool]:
        """Get the status of the continuously-variable filter wheel.

        Returns:
            The position of the encoder and whether the stage is moving.
        """
        p1, p2, state, is_moving = self.connection.status()
        position = p1 if self._wheel == 1 else p2
        return position, is_moving

    def stop_slowly(self) -> None:
        """Slowly bring the stage to a stop."""
        if self._emitting_thread is not None:
            self._stop_slowly_requested = True
            self._emitting_thread.join()
            self._emitting_thread = None
            self._stop_slowly_requested = False
        self.connection.stop_slowly(self._wheel)
        self.logger.info(f'stopping {self.alias!r} slowly')

    def _maybe_start_emitting(self) -> None:
        """Emit notifications in a separate Thread."""
        if self.notifications_allowed:
            self._emitting_thread = Thread(target=self._notify_clients, daemon=True)
            self._emitting_thread.start()

    def _notify_clients(self) -> None:
        """Emit a notification to all linked Clients."""
        position, is_moving = self.status()
        angle = self.position_to_degrees(position)
        if is_moving and not self._stop_slowly_requested:
            self.maybe_emit_notification(position, angle, is_moving)
            self._notify_clients()  # re-emit
        else:
            self.maybe_emit_notification(position, angle, False)

    def _wait(self, timeout: float) -> None:
        now = time.time
        sleep = time.sleep
        t0 = now()
        while True:
            _, is_moving = self.status()
            if not is_moving:
                break
            if now() - t0 > timeout:
                raise TimeoutError(
                    f'{self.alias!r} did not finish moving within {timeout} seconds'
                )
            sleep(0.01)
