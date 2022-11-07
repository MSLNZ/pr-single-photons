"""
Thorlabs filter flipper (MFF101 or MFF102).
"""
import time

from msl.equipment import EquipmentRecord
from msl.equipment.resources.thorlabs import FilterFlipper

from .base import equipment
from .kinesis import KinesisBase


@equipment(manufacturer='Thorlabs', model=r'MFF10[1|2]')
class ThorlabsFlipper(KinesisBase):

    connection: FilterFlipper

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Thorlabs filter flipper (MFF101 or MFF102).

        The optical component that is installed in each position can be passed
        in as kwargs (e.g., position_1='ND-4.0', position_2='Empty').

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)

        self._info: dict[int, str] = {
            1: kwargs.get('position_1', 'Position 1'),
            2: kwargs.get('position_2', 'Position 2')
        }

    def info(self) -> dict[int, str]:
        """Returns the information about what is installed in each position.

        For example::

            {1: 'ND-4.0', 2: 'Empty'}
        """
        return self._info

    def get_position(self) -> int:
        """Returns the current position of the flipper.

        The position is either 1 or 2 (but can be 0 during a move).
        """
        return self.connection.get_position()

    def set_position(self, position: int, wait: bool = True) -> None:
        """Set the flipper to the specified position.

        Args:
            position: The position to move to. Must be either 1 or 2.
            wait: Whether to wait for the flipper to finish moving before
                returning to the calling program.
        """
        if position < 1 or position > 2:
            self.raise_exception(
                f'Invalid flipper position {position}. Must be either 1 or 2.'
            )

        self._is_moving = True
        self._start_move_time = time.time()
        self.connection.move_to_position(position)
        self.logger.info(f'move {self.alias!r} to position {position} [{self._info[position]}]')
        if wait:
            self.wait()
