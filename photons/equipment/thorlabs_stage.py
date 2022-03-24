"""
Communicate with a Thorlabs translational/rotational stage.
"""
import time

from msl import qt

from . import equipment
from .kinesis import KinesisBase


@equipment(manufacturer=r'Thorlabs', model=r'LTS150|LTS300|KDC101|KST101|BSC201')
class ThorlabsStage(KinesisBase):

    def __init__(self, app, record, *, demo=None):
        """Communicate with a Thorlabs translational/rotational stage.

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
        # The load_settings() function has an annoying history of containing bugs
        # We could also use the StepsPerRev, GearboxRatio and Pitch values from the settings
        #       steps_per_rev * gear_box_ratio / pitch
        # but passing these to set_motor_params() has also caused errors in the SDK.
        # Define an "encoder_factor" in ConnectionRecord.properties as a reliable solution.
        # This parameter must be defined before calling super().
        self._encoder_factor = float(record.connection.properties['encoder_factor'])

        super(ThorlabsStage, self).__init__(app, record, demo=demo)

        # access to the values defined in ThorlabsDefaultSettings.xml
        settings = self.connection.settings
        if not settings:
            self.connection.raise_exception(
                'Define a device_name=... parameter '
                'in the properties of the ConnectionRecord'
            )

        self._unit = qt.DEGREE if settings['Units'] == 2 else ' mm'

        self._min_position = settings['MinPos']
        self._max_position = settings['MaxPos']

        self._info = {
            'unit': self._unit,
            'minimum': self._min_position,
            'maximum': self._max_position
        }

        self._channel = record.connection.properties.get('channel')
        if self._channel is None:
            self.connection.enable_channel()
        else:
            self.connection.enable_channel(self._channel)

    def info(self) -> dict:
        """The information about the stage.

        Returns
        -------
        :class:`dict`
            The information about the stage, i.e.::

            {
              'unit': either ' mm' or the unicode value of the degree symbol
              'minimum': the minimum position that the stage can be set to
              'maximum': the maximum position that the stage can be set to
            }

        """
        return self._info

    def home(self, wait: bool = True) -> None:
        """Home the stage.

        Parameters
        ----------
        wait : :class:`bool`, optional
            Whether to wait for the stage to finish homing before returning.
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
        """Get the value of the encoder.

        Returns
        -------
        :class:`int`
            The value of the encoder.
        """
        return self.connection.get_position()

    def get_position(self) -> float:
        """Get the position of the stage (in human units).

        Returns
        -------
        :class:`float`
            The position in mm or degrees.
        """
        return self.to_human(self.get_encoder())

    def set_position(self, position: float, wait: bool = True) -> None:
        """Set the position of the stage (in human units).

        Parameters
        ----------
        position : :class:`float`
            The position in either mm or degrees.
        wait : :class:`bool`, optional
            Whether to wait for the stage to finish moving before returning.
        """
        if position < self._min_position or position > self._max_position:
            self.connection.raise_exception(
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

        Parameters
        ----------
        encoder : :class:`int`
            The value of the encoder.
        ndigits : :class:`int`, optional
            Round the value to `ndigits` precision (see :func:`round` for more details).

        Returns
        -------
        :class:`float`
            The position in either mm or degrees.
        """
        return round(encoder / self._encoder_factor, ndigits)

    def to_encoder(self, position: float) -> int:
        """Convert the position, in human units, to an encoder value.

        Parameters
        ----------
        position : :class:`float`
            The position of the stage in mm or degrees.

        Returns
        -------
        :class:`int`
            The encoder value.
        """
        return round(position * self._encoder_factor)
