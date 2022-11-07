"""
Communicate with a Thorlabs translation/rotation stage.
"""
import time

from msl.equipment import EquipmentRecord
from msl.equipment.resources.thorlabs import BenchtopStepperMotor
from msl.equipment.resources.thorlabs import IntegratedStepperMotors
from msl.qt import DEGREE

from .base import equipment
from .kinesis import KinesisBase


@equipment(manufacturer=r'Thorlabs', model=r'BSC201|K10CR1|KDC101|KST101|LTS150|LTS300')
class ThorlabsStage(KinesisBase):

    connection: IntegratedStepperMotors | BenchtopStepperMotor

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Communicate with a Thorlabs translation/rotation stage.

        The `ConnectionRecord.properties` attribute must contain the
        "encoder_factor" to convert the encoder position to real-world units.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        # The load_settings() function has an annoying history of containing bugs
        # We could also use the StepsPerRev, GearboxRatio and Pitch values from the settings
        #       steps_per_rev * gear_box_ratio / pitch
        # but passing these to set_motor_params() has also caused errors in the SDK.
        # Define an "encoder_factor" in ConnectionRecord.properties as a reliable solution.
        # This parameter must be defined before calling super().
        self._encoder_factor: float = record.connection.properties.get('encoder_factor')
        if self._encoder_factor is None:
            self.raise_exception(
                'Cannot determine the encoder factor.\n'
                'Define an encoder_factor=float parameter '
                'in the properties of the ConnectionRecord'
            )

        super().__init__(record, **kwargs)

        # access to the values defined in ThorlabsDefaultSettings.xml
        settings = self.connection.settings
        if not settings:
            self.raise_exception(
                'Define a device_name="..." parameter '
                'in the properties of the ConnectionRecord'
            )

        self._unit: str = DEGREE if settings['Units'] == 2 else ' mm'
        self._min_position: float = settings['MinPos']
        self._max_position: float = settings['MaxPos']

        self._info: dict[str, float | str] = {
            'unit': self._unit,
            'minimum': self._min_position,
            'maximum': self._max_position
        }

        self._channel = record.connection.properties.get('channel')
        if self._channel is None:
            self.connection.enable_channel()
        else:
            self.connection.enable_channel(self._channel)

    def info(self) -> dict[str, float | str]:
        """Returns the information about the stage.

        For example::

            {
              'unit': str, either ' mm' or the unicode value of the degree symbol
              'minimum': float, the minimum position that the stage can be set to
              'maximum': float, the maximum position that the stage can be set to
            }
        """
        return self._info

    def home(self, wait: bool = True) -> None:
        """Home the stage.

        Args:
            wait: Whether to wait for the stage to finish homing before
                returning to the calling program.
        """
        self._is_moving = True
        self._start_move_time = time.time()
        if self._channel is None:
            self.connection.home()
        else:
            self.connection.home(self._channel)
        self.logger.info(f'homing {self.alias!r}')
        if wait:
            self.wait()

    def stop(self) -> None:
        """Stop moving immediately."""
        if self._channel is None:
            self.connection.stop_immediate()
        else:
            self.connection.stop_immediate(self._channel)
        self.logger.info(f'stop moving {self.alias!r}')

    def get_encoder(self) -> int:
        """Returns the value of the encoder."""
        return self.connection.get_position()

    def get_position(self) -> float:
        """Returns the position of the stage (in mm or degrees)."""
        return self.to_human(self.get_encoder())

    def set_position(self, position: float, wait: bool = True) -> None:
        """Set the position of the stage (in mm or degrees).

        Args:
            position: The position, in mm or degrees.
            wait: Whether to wait for the stage to finish moving before
                returning to the calling program.
        """
        if position < self._min_position or position > self._max_position:
            self.raise_exception(
                f'Invalid {self.alias!r} position of {position}{self._unit}. '
                f'Must be in the range [{self._min_position}, {self._min_position}].'
            )

        encoder = self.to_encoder(position)
        self._is_moving = True
        self._start_move_time = time.time()
        self.connection.move_to_position(encoder)
        self.logger.info(f'set {self.alias!r} to {position}{self._unit} [encoder: {encoder}]')
        if wait:
            self.wait()

    def to_human(self, encoder: int, ndigits: int = 4) -> float:
        """Convert the encoder value to human units.

        Args:
            encoder: The value of the encoder.
            ndigits: Round the value to `ndigits` precision
                (see :func:`round` for more details).

        Returns:
            The position (in mm or degrees).
        """
        return round(encoder / self._encoder_factor, ndigits)

    def to_encoder(self, position: float) -> int:
        """Convert the position (in mm or degrees) to an encoder value.

        Args:
            position: The position of the stage (in mm or degrees).

        Returns:
            The encoder value.
        """
        return round(position * self._encoder_factor)
