"""
Communicate with an OptoSigma SHOT-702 controller.
"""
from time import (
    sleep,
    time,
)
from threading import Thread
from typing import Tuple

from msl.qt import Signal

from . import (
    BaseEquipment,
    equipment,
)


@equipment(manufacturer=r'OptoSigma', model=r'SHOT-702')
class OptoSigmaSHOT702(BaseEquipment):

    NUM_PULSES_PER_360_DEGREES = 144000

    angle_changed = Signal()

    def __init__(self, app, record, *, demo=None):
        """Communicate with an OptoSigma SHOT-702 controller.

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
        super(OptoSigmaSHOT702, self).__init__(app, record, demo=demo)

        self._emitting_thread = None
        self._stop_slowly_requested = False
        self._degrees_per_pulse = 360.0 / float(self.NUM_PULSES_PER_360_DEGREES)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes(['angle_changed'])

        # find out what is attached to each stage -> stage#=model[serial] where # is either 1 or 2
        stage1 = record.connection.properties.get('stage1')
        stage2 = record.connection.properties.get('stage2')

        # determine what stage the continuously-variable filter wheel is attached to
        if stage1 and stage1 == 'OSMS-60-NDU_FCBH-069[10634]':
            self._wheel = 1
        elif stage2 and stage2 == 'OSMS-60-NDU_FCBH-069[10634]':
            self._wheel = 2
        else:
            self.connection.raise_exception(
                f'\nCannot determine which stage the continuously-variable '
                f'filter wheel is attached to. Define a stage#=model[serial] '
                f'in the record.connection.properties, where # is 1 or 2'
            )

        self.stop_slowly()

    @property
    def degrees_per_pulse(self) -> float:
        """:class:`float`: Returns the number of degrees per pulse."""
        return self._degrees_per_pulse

    def degrees_to_position(self, degrees: float) -> int:
        """Convert an angle, in degrees, to an encoder position.

        Parameters
        ----------
        degrees : :class:`float`
            An angle, in degrees.

        Returns
        -------
        :class:`int`
            The corresponding encoder position.
        """
        return round(degrees / self._degrees_per_pulse)

    def get_angle(self) -> float:
        """Get the angle of the filter wheel.

        Returns
        -------
        :class:`float`
            The angle, in degrees.
        """
        position, _ = self.status()
        return self.position_to_degrees(position)

    def get_speed(self) -> Tuple[int, int, int]:
        """Get speed that the stage moves to a new angle.

        Returns
        -------
        :class:`int`
            The minimum speed (in number of pulses per second)
        :class:`int`
            The maximum speed (in number of pulses per second)
        :class:`int`
            The acceleration/deceleration time in ms.
        """
        return self.connection.get_speed()[f'stage{self._wheel}']

    def get_speed_home(self) -> Tuple[int, int, int]:
        """Get speed that the stage moves home.

        Returns
        -------
        :class:`int`
            The minimum speed (in number of pulses per second)
        :class:`int`
            The maximum speed (in number of pulses per second)
        :class:`int`
            The acceleration/deceleration time in ms.
        """
        return self.connection.get_speed_origin()[f'stage{self._wheel}']

    def home(self, *,
             timeout: float = 30,
             wait: bool = True) -> None:
        """Home the continuously-variable filter wheel.

        Parameters
        ----------
        timeout : :class:`float`, optional
            The maximum number of seconds to wait for the wheel to stop moving.
        wait : :class:`bool`, optional
            Whether to wait for the wheel to stop moving.
        """
        self.connection.home(self._wheel)
        self.logger.info(f'home {self.alias!r}')
        self.angle_changed.emit()
        if self.connected_as_link:
            self._start_emitting()
        if wait:
            self._wait(timeout)

    def is_moving(self) -> bool:
        """Returns whether the filter wheel is moving.

        Returns
        -------
        :class:`bool`
            Whether the filter wheel is moving.
        """
        return self.status()[1]

    def position_to_degrees(self, position: int, *, bound: bool = False) -> float:
        """Convert an encoder position to an angle in degrees.

        Parameters
        ----------
        position : :class:`int`
            The encoder position.
        bound : :class:`bool`, optional
            Whether to bound the angle to be between [0, 360) degrees.

        Returns
        -------
        :class:`float`
            The angle in degrees.
        """
        degrees = round(position * self._degrees_per_pulse, 4)
        if bound:
            return round(degrees % 360., 4)
        return degrees

    def set_angle(self,
                  degrees: float, *,
                  timeout: float = 30,
                  wait: bool = True) -> None:
        """Set the angle of the continuously-variable filter wheel.

        Parameters
        ----------
        degrees : :class:`float`
            The angle.
        timeout : :class:`float`, optional
            The maximum number of seconds to wait for the wheel to stop moving.
        wait : :class:`bool`, optional
            Whether to wait for the wheel to stop moving.
        """
        self.connection.move_absolute(self._wheel, self.degrees_to_position(degrees))
        self.logger.info(f'{self.alias!r} set to {degrees} degrees')
        self.angle_changed.emit()
        if self.connected_as_link:
            self._start_emitting()
        if wait:
            self._wait(timeout)

    def set_speed(self, minimum, maximum, acceleration) -> None:
        """Set speed that the stage moves to a new angle.

        According to the manual:
        Max. Driving Speed: 500000 pps -> 1250 deg/s
        Min. Driving Speed: 1 pps -> 0.0025 deg/s
        Acceleration/Deceleration Time: 1 - 1000ms

        Parameters
        ----------
        :class:`int`
            The minimum speed (in number of pulses per second)
        :class:`int`
            The maximum speed (in number of pulses per second)
        :class:`int`
            The acceleration/deceleration time in ms.
        """
        self.connection.set_speed(self._wheel, minimum, maximum, acceleration)
        self.logger.info(f'{self.alias!r} set the move speed settings to '
                         f'minimum={minimum} PPS, maximum={maximum} PPS, '
                         f'acceleration={acceleration} ms')

    def set_speed_home(self, minimum, maximum, acceleration) -> None:
        """Set speed that the stage moves home.

        According to the manual:
        Max. Driving Speed: 500000 pps -> 1250 deg/s
        Min. Driving Speed: 1 pps -> 0.0025 deg/s
        Acceleration/Deceleration Time: 1 - 1000ms

        Parameters
        ----------
        :class:`int`
            The minimum speed (in number of pulses per second)
        :class:`int`
            The maximum speed (in number of pulses per second)
        :class:`int`
            The acceleration/deceleration time in ms.
        """
        self.connection.set_speed_origin(self._wheel, minimum, maximum, acceleration)
        self.logger.info(f'{self.alias!r} set the move home speed settings to '
                         f'minimum={minimum} PPS, maximum={maximum} PPS, '
                         f'acceleration={acceleration} ms')

    def status(self) -> Tuple[int, bool]:
        """Get the status of the continuously-variable filter wheel.

        Returns
        -------
        :class:`int`
            The position of the encoder.
        :class:`bool`
            Whether the stage is moving.
        """
        p1, p2, state, is_moving = self.connection.status()
        position = p1 if self._wheel == 1 else p2
        return position, is_moving

    def stop_slowly(self) -> None:
        """Slowly bring the stage to a stop."""
        if self._emitting_thread is not None:
            self._stop_slowly_requested = True
            self._emitting_thread.join()
        self.connection.stop_slowly(self._wheel)
        self.logger.info(f'stopping {self.alias!r} slowly')

    def _start_emitting(self) -> None:
        """Emit notifications in a separate :class:`~threading.Thread`."""
        self._emitting_thread = Thread(target=self._emit_notification, daemon=True)
        self._emitting_thread.start()

    def _emit_notification(self) -> None:
        """Emit a notification to all linked :class:`~msl.network.client.Client`\\s."""
        position, is_moving = self.status()
        angle = self.position_to_degrees(position)
        if is_moving and not self._stop_slowly_requested:
            self.emit_notification(position, angle, is_moving)
            self._emit_notification()  # re-emit
        else:
            self.emit_notification(position, angle, False)
            self._emitting_thread = None
            self._stop_slowly_requested = False

    def _wait(self, timeout) -> None:
        t0 = time()
        while True:
            _, is_moving = self.status()
            if not is_moving:
                break
            if time() - t0 > timeout:
                raise TimeoutError(
                    f'{self.alias!r} did not finish moving with {timeout} seconds'
                )
            sleep(0.01)
