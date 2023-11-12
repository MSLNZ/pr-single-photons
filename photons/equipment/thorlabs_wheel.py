"""
Communicate with a Thorlabs filter wheel FW212C.
"""
from msl.equipment import EquipmentRecord
from msl.equipment.resources.thorlabs import FilterWheelXX2C

from .base import BaseEquipment
from .base import equipment


@equipment(manufacturer=r'Thorlabs', model=r'FW212C')
class ThorlabsWheel(BaseEquipment):

    connection: FilterWheelXX2C

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Communicate with a Thorlabs fiter wheel FW212C.

        :param record: The equipment record.
        :param kwargs: The keyword arguments can be specified as attributes of
            an XML element in a configuration file (with the tag of the element
            equal to the alias of `record`). For example,
            <wheel-12 p1="None" p2="0.1" ... />
        """
        super().__init__(record, **kwargs)

        self._max_position = self.connection.get_position_count()
        self.connection.set_speed_mode(1)  # SLOW=0, FAST=1

        if not kwargs:
            filters = {
                1: None,  # empty
                2: 0.1,
                3: 0.2,
                4: 0.3,
                5: 0.4,
                6: 0.5,
                7: 0.6,
                8: 1.0,
                9: 1.3,
                10: 2.0,
                11: 3.0,
                12: 4.0,
            }
        else:
            # key (position number), value (optical density)
            filters = dict((int(k[1:]), v) for k, v in kwargs.items())

        if len(filters) != self._max_position:
            raise ValueError(f'A dict of {self._max_position} ND filters are required, '
                             f'got {filters}')

        self._info: dict[int, float | None] = filters

    def filter_info(self) -> dict[int, float | None]:
        """Get the optical densities of all ND filters at each position.

        The position number is the key and the OD is the value.
        """
        return self._info

    def get_position(self) -> int:
        """Get the current position."""
        return self.connection.get_position()

    def set_position(self, position: int) -> int:
        """Set the position number of the ND filter wheel.

        :param position: The position number. The first position is 1 (not 0).
        :return: The position of the ND filter wheel after it has moved.
        """
        if not (1 <= position <= self._max_position):
            raise ValueError(
                f'Invalid position {position}. Must be between [1, {self._max_position}]'
            )

        self.logger.info(f'move {self.alias!r} to position {position} [OD: {self._info[position]}]')
        self.connection.set_position(position)
        self.maybe_emit_notification(alias=self.alias, position=position)
        return self.get_position()
