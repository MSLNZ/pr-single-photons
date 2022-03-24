"""
Communicate with a Thorlabs MFF101 flipper.
"""
import time

from . import equipment
from .kinesis import KinesisBase


@equipment(manufacturer=r'Thorlabs', model=r'MFF101')
class MFF101Flipper(KinesisBase):

    def __init__(self, app, record, *, demo=None):
        """Communicate with a Thorlabs MFF101 flipper.

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
        super(MFF101Flipper, self).__init__(app, record, demo=demo)

        default = {1: 'Position 1', 2: 'Position 2'}
        info = app.config.root.find(record.alias)
        if info is not None:
            self._info = {1: info.get('position-1', default[1]), 2: info.get('position-2', default[2])}
        else:
            self._info = default

    def info(self) -> dict:
        """Return the information about what is installed in each position.

        Returns
        -------
        :class:`dict`
            The information about what is installed in each position, e.g.,::

            {1: 'ND-4.0', 2: 'ND-2.0'}

        """
        return self._info

    def get_position(self) -> int:
        """The position of the flipper.

        Returns
        -------
        :class:`int`
            The position, 1 or 2 (can be 0 during a move).
        """
        return self.connection.get_position()

    def set_position(self, position: int, wait: bool = True) -> None:
        """Set the flipper to the specified position.

        Parameters
        ----------
        position : :class:`int`
            The position. Must be either 1 or 2.
        wait : :class:`bool`, optional
            Whether to wait for the flipper to finish moving before returning.
        """
        if position < 1 or position > 2:
            self.connection.raise_exception(
                f'Invalid flipper position {position}. Must be either 1 or 2.'
            )

        self._is_moving = True
        self._start_move_time = time.time()
        self.connection.move_to_position(position)
        self.logger.info(f'move {self.alias!r} to position {position} [{self._info[position]}]')
        if wait:
            self.wait()
