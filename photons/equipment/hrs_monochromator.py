"""
HRS500M Monochromator from Princeton Instruments.
"""
from ctypes import ArgumentError

from msl.equipment import EquipmentRecord
from msl.equipment.exceptions import PrincetonInstrumentsError
from msl.equipment.resources import PrincetonInstruments
from msl.qt import QtCore
from msl.qt import Signal

from .base import BaseEquipment
from .base import equipment


@equipment(manufacturer=r'Princeton Instruments', model=r'HRS500M')
class HRSMonochromator(BaseEquipment):

    connection: PrincetonInstruments

    FRONT_ENTRANCE_SLIT = 2
    FRONT_EXIT_SLIT = 3

    grating_position_changed: QtCore.SignalInstance = Signal(int)  # position
    filter_position_changed: QtCore.SignalInstance = Signal(int)  # position
    wavelength_changed: QtCore.SignalInstance = Signal(float, float)  # requested, actual
    front_entrance_slit_changed: QtCore.SignalInstance = Signal(int)  # slit width
    front_exit_slit_changed: QtCore.SignalInstance = Signal(int)  # slit width

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """HRS500M Monochromator from Princeton Instruments.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes(
            'grating_position_changed',
            'filter_position_changed',
            'wavelength_changed',
            'front_entrance_slit_changed',
            'front_exit_slit_changed',
        )

        try:
            self.connection.get_mono_model()
        except ArgumentError:
            raise PrincetonInstrumentsError(
                f'{self.connection!r}\nCannot connect to monochromator') from None

        gratings = record.user_defined.get('gratings')
        if not gratings:
            gratings = {
                position: {
                    'blaze': self.connection.get_mono_grating_blaze(position),
                    'density': f'{self.connection.get_mono_grating_density(position)}/mm',
                }
                for position in [1, 2, 3]
            }
        self._grating_info: dict[int, dict[str, str]] = gratings

        filters = record.user_defined.get('filters')
        if not filters:
            filters = {
                1: 'None (open)',
                2: '320 nm',
                3: '590 nm',
                4: '665 nm',
                5: '715 nm',
                6: 'Blank (closed)',
            }
        self._filter_info: dict[int, str] = filters

    def filter_info(self) -> dict[int, str]:
        """Returns a description of the filters that are installed in each position.

        The keys are the position numbers of each filter.
        """
        return self._filter_info

    def get_filter_position(self) -> int:
        """Returns the filter position, in the range [1, 6]."""
        return self.connection.get_mono_filter_position()

    def get_front_entrance_slit_width(self) -> int:
        """Returns the front entrance slit width (in microns)."""
        return self.connection.get_mono_slit_width(self.FRONT_ENTRANCE_SLIT)

    def get_front_exit_slit_width(self) -> int:
        """Returns the front exit slit width (in microns)."""
        return self.connection.get_mono_slit_width(self.FRONT_EXIT_SLIT)

    def get_grating_position(self) -> int:
        """Returns the current grating position. Either 1, 2 or 3."""
        return self.connection.get_mono_grating()

    def get_wavelength(self) -> float:
        """Returns the current wavelength (in nm)."""
        return self.connection.get_mono_wavelength_nm()

    def grating_info(self) -> dict[int, dict[str, str]]:
        """Returns the density and blaze values for each grating.

        The keys are the position numbers of each grating.
        """
        return self._grating_info

    def home_filter_wheel(self) -> int:
        """Home the filter wheel.

        Returns:
            The filter wheel position after homing.
        """
        self.connection.mono_filter_home()
        self.logger.info(f'home the filter wheel of {self.alias!r}')
        position = self.get_filter_position()
        self.filter_position_changed.emit(position)
        self.maybe_emit_notification(filter_wheel_position=position)
        return position

    def home_front_entrance_slit(self) -> int:
        """Home the front entrance slit.

        Returns:
            The slit width (in microns) after homing.
        """
        self.connection.mono_slit_home(self.FRONT_ENTRANCE_SLIT)
        self.logger.info(f'home the front entrance slit of {self.alias!r}')
        width = self.get_front_entrance_slit_width()
        self.front_entrance_slit_changed.emit(width)
        self.maybe_emit_notification(front_entrance_slit_width=width)
        return width

    def home_front_exit_slit(self) -> int:
        """Home the front exit slit.

        Returns:
            The slit width (in microns) after homing.
        """
        self.connection.mono_slit_home(self.FRONT_EXIT_SLIT)
        self.logger.info(f'home the front exit slit of {self.alias!r}')
        width = self.get_front_exit_slit_width()
        self.front_exit_slit_changed.emit(width)
        self.maybe_emit_notification(front_exit_slit_width=width)
        return width

    def set_filter_position(self, position: int) -> int:
        """Set the filter wheel position.

        Args:
            position: The filter wheel position, in the range [1, 6].

        Returns:
            The actual filter wheel position after it has finished moving.
        """
        if position < 1 or position > 6:
            self.raise_exception(f'Invalid {self.alias!r} filter position {position}. '
                                 f'Must be in the range [1, 6].')
        pos = int(position)
        self.connection.set_mono_filter_position(pos)
        actual = self.get_filter_position()
        assert actual == pos
        self.logger.info(f'set {self.alias!r} filter position to {pos} [{self._filter_info[pos]}]')
        self.filter_position_changed.emit(actual)
        self.maybe_emit_notification(filter_wheel_position=actual)
        return actual

    def set_front_entrance_slit_width(self, um: int) -> int:
        """Set the front entrance slit width.

        Args:
            um: The slit width (in microns).

        Returns:
            The actual slit width (in microns) after it has finished moving.
        """
        width = int(um)
        self._set_slit_width(self.FRONT_ENTRANCE_SLIT, width)
        actual = self.get_front_entrance_slit_width()
        assert actual == width
        self.front_entrance_slit_changed.emit(actual)
        self.maybe_emit_notification(front_entrance_slit_width=actual)
        return actual

    def set_front_exit_slit_width(self, um: int) -> int:
        """Set the front exit slit width.

        Args:
            um: The slit width (in microns).

        Returns:
            The actual slit width (in microns) after it has finished moving.
        """
        width = int(um)
        self._set_slit_width(self.FRONT_EXIT_SLIT, width)
        actual = self.get_front_exit_slit_width()
        assert actual == width
        self.front_exit_slit_changed.emit(actual)
        self.maybe_emit_notification(front_exit_slit_width=actual)
        return actual

    def set_grating_position(self, position: int) -> int:
        """Set the grating position.

        Args:
            position: The grating position. Either 1, 2 or 3.

        Returns:
            The actual grating position after it has finished moving.
        """
        if position < 1 or position > 3:
            self.raise_exception(f'Invalid {self.alias!r} grating position {position}. '
                                 f'Must be either 1, 2 or 3.')
        pos = int(position)
        self.connection.set_mono_grating(pos)
        actual = self.get_grating_position()
        assert actual == pos
        self.logger.info(f'set {self.alias!r} grating to position {pos} [{self._grating_info[pos]}]')
        self.grating_position_changed.emit(actual)
        self.maybe_emit_notification(grating_position=actual)
        return actual

    def set_wavelength(self, nm: float) -> float:
        """Set the wavelength.

        Args:
            nm: The wavelength (in nm).

        Returns:
            The actual wavelength (in nm) after it has finished moving.
        """
        if nm < -2800 or nm > 2800:
            self.raise_exception(f'Invalid {self.alias!r} wavelength of {nm} nm. '
                                 f'Must be in the range [-2800, 2800].')
        requested = round(nm, 3)
        self.connection.set_mono_wavelength_nm(requested)
        encoder = self.get_wavelength()
        self.logger.info(f'set {self.alias!r} wavelength to {requested} nm [encoder={encoder} nm]')
        self.wavelength_changed.emit(requested, encoder)
        self.maybe_emit_notification(wavelength={'requested': requested, 'encoder': encoder})
        return encoder

    def _set_slit_width(self, port: int, um: int) -> None:
        if um < 10 or um > 3000:
            self.raise_exception(f'Invalid {self.alias!r} slit width of {um}. '
                                 f'Must be in the range [10, 3000].')
        self.connection.set_mono_slit_width(port, um)
        text = 'entrance' if port == self.FRONT_ENTRANCE_SLIT else 'exit'
        self.logger.info(f'set {self.alias!r} front {text} slit width to {um} microns')
