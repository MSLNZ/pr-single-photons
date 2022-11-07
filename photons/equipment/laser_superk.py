"""
SuperK Fianium laser from NKT Photonics.
"""
from binascii import hexlify
from ctypes import c_ubyte
from enum import IntEnum
from math import nan
from time import sleep

from msl.equipment import EquipmentRecord
from msl.equipment.resources import NKT
from msl.qt import QtCore
from msl.qt import Signal

from .base import BaseEquipment
from .base import equipment
from ..log import logger


class ID60(IntEnum):
    """Register IDs for "SK Fianium" (Module type 0x0060)."""
    INLET_TEMPERATURE = 0x11
    EMISSION = 0x30
    MODE = 0x31
    INTERLOCK = 0x32
    PULSE_PICKER_RATIO = 0x34
    WATCHDOG_INTERVAL = 0x36
    POWER_LEVEL = 0x37
    CURRENT_LEVEL = 0x38
    NIM_DELAY = 0x39
    SERIAL_NUMBER = 0x65
    STATUS_BITS = 0x66
    SYSTEM_TYPE = 0x6B
    USER_TEXT = 0x6C


class ID88(IntEnum):
    """Register IDs for "SuperK G3 Mainboard" (Module type 0x0088)."""
    INLET_TEMPERATURE = 0x11
    EMISSION = 0x30
    MODE = 0x31
    INTERLOCK = 0x32
    DATETIME = 0x33
    PULSE_PICKER_RATIO = 0x34
    WATCHDOG_INTERVAL = 0x36
    CURRENT_LEVEL = 0x37
    PULSE_PICKER_NIM_DELAY = 0x39
    MAINBOARD_NIM_DELAY = 0x3A
    USER_CONFIG = 0x3B
    MAX_PULSE_PICKER_RATIO = 0x3D
    STATUS_BITS = 0x66
    ERROR_CODE = 0x67
    USER_TEXT = 0x8D


class ID61(IntEnum):
    """Register IDs for "SuperK Front panel" (Module type 0x61)."""
    PANEL_LOCK = 0x3D
    DISPLAY_TEXT = 0x72
    ERROR_FLASH = 0x8D


class ID89(IntEnum):
    """Register IDs for "SuperK G3 Front Panel" (Module type 0x0089).

    According to the NKT engineers, there are no front-panel registers available.
    This means that the PANEL_LOCK, DISPLAY_TEXT and ERROR_FLASH do not exist.
    """


class OperatingModes(IntEnum):
    """The operating modes for a SuperK Fianium laser."""
    CONSTANT_CURRENT = 0
    CONSTANT_POWER = 1
    MODULATED_CURRENT = 2
    MODULATED_POWER = 3
    POWER_LOCK = 4


@equipment(manufacturer=r'^NKT', model=r'F?S473')
class SuperK(BaseEquipment):

    _callbacks_registered = False

    connection: NKT

    OperatingModes = OperatingModes

    DEVICE_ID = 0x0F
    FRONT_PANEL_ID = 0x01
    MODULE_TYPE_0x60 = 0x60
    MODULE_TYPE_0x88 = 0x88

    # the DeviceStatusCallback is not reliable when changing the level manually
    # on the front panel, this is one reason why the front panel gets locked
    # when communication is established
    level_changed: QtCore.SignalInstance = Signal(float)  # level value

    emission_changed: QtCore.SignalInstance = Signal(bool)  # on/off state

    mode_changed: QtCore.SignalInstance = Signal(int)  # the mode value

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """SuperK Fianium laser from NKT Photonics.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)

        # suppress the warning that the following attributes cannot be made
        # available when starting the BaseEquipment as a Service
        self.ignore_attributes('level_changed', 'emission_changed', 'signaler',
                               'DEVICE_ID', 'MODULE_TYPE_0x60', 'MODULE_TYPE_0x88')

        serial = self.connection.device_get_module_serial_number_str(SuperK.DEVICE_ID)
        if serial and serial != record.serial:
            self.raise_exception(f'SuperK serial number mismatch, '
                                 f'{serial} != {record.serial}')

        self.disconnect = self._disconnect

        # different SuperK's have different mainboard registry values
        self.MODULE_TYPE = self.connection.device_get_type(SuperK.DEVICE_ID)
        if self.MODULE_TYPE == SuperK.MODULE_TYPE_0x60:
            self.ID = ID60
            self.MODES = {
                'Constant current': OperatingModes.CONSTANT_CURRENT,
                'Current modulation': OperatingModes.MODULATED_CURRENT,
                'Power lock': OperatingModes.POWER_LOCK,
            }
        elif self.MODULE_TYPE == SuperK.MODULE_TYPE_0x88:
            self.ID = ID88
            self.MODES = {
                'Constant current': OperatingModes.CONSTANT_CURRENT,
                'Power lock': OperatingModes.POWER_LOCK,
            }
        else:
            self.raise_exception(f'Unsupported module type 0x{self.MODULE_TYPE:x}')

        status = self.connection.get_port_status()
        if status != NKT.PortStatusTypes.PortReady:
            self.raise_exception(f'{self.alias!r} port status is {status!r}')

        self.ensure_interlock_ok()
        if record.connection.properties.get('lock_front_panel', False):
            self.lock_front_panel(True)

        if not SuperK._callbacks_registered:
            self.signaler = register_callbacks(self)
            SuperK._callbacks_registered = True

        self.set_user_text(kwargs.get('user_text', 'In use by Joe'))

    def emission(self, enable: bool) -> None:
        """Turn the laser emission on or off.

        Args:
            enable: Whether to turn the laser emission on or off.
        """
        state, text = (3, 'on') if enable else (0, 'off')
        self.logger.info(f'turn {self.alias!r} emission {text}')
        try:
            self.connection.register_write_u8(SuperK.DEVICE_ID, self.ID.EMISSION, state)
        except OSError as e:
            error = str(e)
        else:
            self.emission_changed.emit(enable)
            self.maybe_emit_notification(emission=enable)
            return

        self.raise_exception(f'Cannot turn the {self.alias!r} emission {text}\n{error}')

    def enable_constant_current_mode(self) -> None:
        """Set the laser to be in constant current mode."""
        self.set_operating_mode(OperatingModes.CONSTANT_CURRENT)

    def enable_constant_power_mode(self) -> None:
        """Set the laser to be in constant power mode."""
        self.set_operating_mode(OperatingModes.CONSTANT_POWER)

    def enable_modulated_current_mode(self) -> None:
        """Set the laser to be in modulated current mode."""
        self.set_operating_mode(OperatingModes.MODULATED_CURRENT)

    def enable_modulated_power_mode(self) -> None:
        """Set the laser to be in modulated power mode."""
        self.set_operating_mode(OperatingModes.MODULATED_POWER)

    def enable_power_lock_mode(self) -> None:
        """Set the laser to be power lock (external feedback) mode."""
        self.set_operating_mode(OperatingModes.POWER_LOCK)

    def ensure_interlock_ok(self) -> bool:
        """Make sure that the interlock is okay.

        Raises an exception if it is not okay, and it cannot be reset.
        """
        status = self.connection.register_read_u16(SuperK.DEVICE_ID, self.ID.INTERLOCK)
        if status == 2:
            self.logger.info(f'{self.alias!r} interlock is okay')
            return True

        if status == 1:  # then requires an interlock reset
            self.logger.info(f'resetting the {self.alias!r} interlock... ')
            status = self.connection.register_write_read_u16(SuperK.DEVICE_ID, self.ID.INTERLOCK, 1)
            if status == 2:
                self.logger.info(f'{self.alias!r} interlock is okay')
                return True

        self.raise_exception(
            f'Invalid {self.alias!r} interlock status code {status}. '
            f'Is the key in the off position?'
        )

    def get_current_level(self) -> float:
        """Returns the constant/modulated current level of the laser."""
        # the documentation indicates that there is a scaling factor of 0.1
        return self.connection.register_read_u16(SuperK.DEVICE_ID, self.ID.CURRENT_LEVEL) * 0.1

    def get_feedback_level(self) -> float:
        """Get the power lock (external feedback) level of the laser."""
        return self.get_current_level()

    def get_operating_mode(self) -> OperatingModes:
        """Returns the operating mode of the laser."""
        if self.MODULE_TYPE == SuperK.MODULE_TYPE_0x60:
            read = self.connection.register_read_u16
        else:
            read = self.connection.register_read_u8
        return OperatingModes(read(SuperK.DEVICE_ID, self.ID.MODE))

    def get_operating_modes(self) -> dict[str, OperatingModes]:
        """Get all supported operating modes of the laser."""
        return self.MODES

    def get_power_level(self) -> float:
        """Returns the constant/modulated power level of the laser."""
        if self.MODULE_TYPE == SuperK.MODULE_TYPE_0x88:
            self.logger.warning(f'the {self.alias!r} does not '
                                f'support power-level mode')
            return nan

        # the documentation indicates that there is a scaling factor of 0.1
        return 0.1 * self.connection.register_read_u16(
            SuperK.DEVICE_ID,
            self.ID.POWER_LEVEL # noqa: Unresolved attribute reference 'POWER_LEVEL' for class 'ID88'
        )

    def get_temperature(self) -> float:
        """Returns the temperature of the laser."""
        # the documentation indicates that there is a scaling factor of 0.1
        return 0.1 * self.connection.register_read_s16(
            SuperK.DEVICE_ID, self.ID.INLET_TEMPERATURE)

    def get_user_text(self) -> str:
        """Returns the custom user-text value."""
        return self.connection.register_read_ascii(SuperK.DEVICE_ID, self.ID.USER_TEXT)

    def is_constant_current_mode(self) -> bool:
        """Whether the laser in constant current mode."""
        return self.get_operating_mode() == OperatingModes.CONSTANT_CURRENT

    def is_constant_power_mode(self) -> bool:
        """Whether the laser in constant power mode."""
        return self.get_operating_mode() == OperatingModes.CONSTANT_POWER

    def is_emission_on(self) -> bool:
        """Check if the laser emission is on or off."""
        return bool(self.connection.register_read_u8(SuperK.DEVICE_ID, self.ID.EMISSION))

    def is_modulated_current_mode(self) -> bool:
        """Whether the laser in modulated current mode."""
        return self.get_operating_mode() == OperatingModes.MODULATED_CURRENT

    def is_modulated_power_mode(self) -> bool:
        """Whether the laser in modulated power mode."""
        return self.get_operating_mode() == OperatingModes.MODULATED_POWER

    def is_power_lock_mode(self) -> bool:
        """Whether the laser in power lock (external feedback) mode."""
        return self.get_operating_mode() == OperatingModes.POWER_LOCK

    def lock_front_panel(self, lock: bool) -> bool:
        """Lock the front panel so that the level cannot be changed manually.

        Args:
            lock: Whether to lock (True) or unlock (False) the front panel.

        Returns:
            Whether the request to (un)lock the front panel was successful.
            A laser with a module type 0x88 does not permit the front panel
            to be (un)locked and therefore this method will always return
            False for this laser.
        """
        text = 'lock' if lock else 'unlock'
        if self.MODULE_TYPE == SuperK.MODULE_TYPE_0x88:
            self.logger.warning(f'the {self.alias!r} does not support {text}ing the front panel')
            return False

        try:
            self.connection.register_write_u8(SuperK.FRONT_PANEL_ID, ID61.PANEL_LOCK, int(lock))
        except OSError as e:
            self.logger.error(f'Cannot {text} the front panel of the {self.alias!r}, '
                              f'{e.__class__.__name__}: {e}')
            return False

        self.maybe_emit_notification(locked=bool(lock))
        self.logger.info(f'{text}ed the front panel of the {self.alias!r}')
        return True

    def set_current_level(self, percentage: float) -> float:
        """Set the constant/modulated current level of the laser.

        Args:
            percentage: The current level as a percentage 0 - 100 (resolution 0.1).

        Returns:
            The actual current level that the laser is at.
        """
        self.logger.info(f'set {self.alias!r} current level to {percentage}%')
        return self._set_current_level(percentage)

    def set_feedback_level(self, percentage: float) -> float:
        """Set the power-lock (external feedback) level of the laser.

        Args:
            percentage: The power-lock level as a percentage 0 - 100 (resolution 0.1).

        Returns:
            The power-lock level that the laser is at.
        """
        self.logger.info(f'set {self.alias!r} power-lock level to {percentage}%')
        return self._set_current_level(percentage)

    def set_operating_mode(self, mode: int | str | OperatingModes) -> None:
        """Set the operating mode of the laser.

        Args:
            mode: The operating mode. Can be an :class:`OperatingModes` value or member name.
        """
        m = self.convert_to_enum(mode, OperatingModes, to_upper=True)
        self.emission(False)
        if self.connection.register_write_read_u16(SuperK.DEVICE_ID, self.ID.MODE, m) != m:
            self.raise_exception(f'Cannot set {self.alias!r} to {m!r}')
        self.mode_changed.emit(m)
        self.maybe_emit_notification(mode=m)
        self.logger.info(f'set {self.alias!r} to {m!r}')

        # the value of the level can change when the mode changes
        # it can take some time for the get_*_level() function to return the correct value
        sleep(0.2)
        if m == OperatingModes.CONSTANT_POWER or m == OperatingModes.MODULATED_POWER:
            level = self.get_power_level()
        else:
            level = self.get_current_level()  # valid for POWER_LOCK mode as well

        self.level_changed.emit(level)
        self.maybe_emit_notification(level=level)

    def set_power_level(self, percentage: float) -> float:
        """Set the constant/modulated power level of the laser.

        Args:
            percentage: The power level as a percentage 0 - 100 (resolution 0.1).

        Returns:
            The actual power level that the laser is at.
        """
        if percentage < 0 or percentage > 100:
            self.raise_exception(
                f'Invalid {self.alias!r} power level of {percentage}. '
                f'Must be in range [0, 100].'
            )

        if self.MODULE_TYPE == SuperK.MODULE_TYPE_0x88:
            self.logger.error(f'the {self.alias!r} does not support power-level mode')
            return nan

        # the documentation indicates that there is a scaling factor of 0.1
        self.logger.info(f'set {self.alias!r} power level to {percentage}%')
        val = self.connection.register_write_read_u16(
            SuperK.DEVICE_ID,
            self.ID.POWER_LEVEL,  # noqa: Unresolved attribute reference 'POWER_LEVEL' for class 'ID88'
            int(percentage * 10)
        )
        actual = float(val) * 0.1
        self.level_changed.emit(actual)
        self.maybe_emit_notification(level=actual)
        return actual

    def set_user_text(self, text: str) -> str:
        """Set the custom user-text value.

        Args:
            text: The text to write to the laser's firmware. Only ASCII
                characters are allowed. The maximum number of characters is 20
                for the laser with module type 0x60 and 240 characters for
                module type 0x88. The laser with module type 0x60 can display
                the text on the front panel (if selected from the menu option).

        Returns:
            The text that was actually stored in the laser's firmware.
        """
        if not text and self.MODULE_TYPE == SuperK.MODULE_TYPE_0x88:
            # module type 0x88 requires at least 1 character to be written
            text = ' '
        self.logger.info(f'set the {self.alias!r} front-panel text to {text!r}')
        return self.connection.register_write_read_ascii(SuperK.DEVICE_ID, self.ID.USER_TEXT, text, False)

    def _disconnect(self):
        """Unlock the front panel, set the user text to an empty string and close the port."""
        self.lock_front_panel(False)
        self.set_user_text('')
        self.connection.disconnect()

    def _set_current_level(self, percentage: float) -> float:
        if percentage < 0 or percentage > 100:
            self.raise_exception(
                f'Invalid {self.alias!r} current level of {percentage}. '
                f'Must be in the range [0, 100].'
            )

        # the documentation indicates that there is a scaling factor of 0.1
        val = self.connection.register_write_read_u16(SuperK.DEVICE_ID, self.ID.CURRENT_LEVEL, int(percentage * 10))
        actual = float(val) * 0.1
        self.level_changed.emit(actual)
        self.maybe_emit_notification(level=actual)
        return actual


class Signaler(QtCore.QObject):
    """Qt Signaler for callbacks that are received from the DLL."""

    # {'port': bytes, 'dev_id': int, 'status': int, 'data': bytes}
    device_status_changed: QtCore.SignalInstance = Signal(dict)

    # {'port': bytes, 'dev_id': int, 'reg_id': int,
    #  'reg_status': int, 'reg_type': int, 'data': bytes}
    register_status_changed: QtCore.SignalInstance = Signal(dict)

    # {'port': bytes, 'status': int, 'cur_scan': int, 'max_scan': int, 'device': int}
    port_status_changed: QtCore.SignalInstance = Signal(dict)

    def __init__(self, device: SuperK) -> None:
        super().__init__()
        self.device = device

    def maybe_emit_notification(self, *args, **kwargs) -> None:
        """Notify all linked Clients."""
        self.device.maybe_emit_notification(*args, **kwargs)


def register_callbacks(superk: SuperK) -> Signaler:
    """Register the callbacks from the DLL."""

    def get_data(length: int, address: int) -> bytes:
        try:
            return bytes((c_ubyte * length).from_address(address))  # noqa: Array[c_ubyte] is iterable
        except ValueError:
            return b''

    @NKT.DeviceStatusCallback
    def device_status_callback(port: bytes, dev_id: int, status: int,
                               length: int, address: int) -> None:
        d = {
            'port': port.decode(),
            'dev_id': dev_id,
            'status': NKT.DeviceStatusTypes(status),
            'data': int(hexlify(get_data(length, address)))
        }
        logger.debug('SuperK device_status_callback: %s', d)
        signaler.device_status_changed.emit(d)
        signaler.maybe_emit_notification(**d)

    @NKT.RegisterStatusCallback
    def register_status_callback(port: bytes, dev_id: int, reg_id: int, reg_status: int,
                                 reg_type: int, length: int, address: int) -> None:
        d = {
            'port': port.decode(),
            'dev_id': dev_id,
            'reg_id': reg_id,
            'reg_status': NKT.RegisterStatusTypes(reg_status),
            'reg_type': NKT.RegisterDataTypes(reg_type),
            'data': get_data(length, address)
        }
        logger.debug('SuperK register_status_callback: %s', d)
        signaler.register_status_changed.emit(d)
        signaler.maybe_emit_notification(**d)

    @NKT.PortStatusCallback
    def port_status_callback(port: bytes, status: int, cur_scan: int,
                             max_scan: int, device: int) -> None:
        d = {
            'port': port.decode(),
            'status': NKT.PortStatusTypes(status),
            'cur_scan': cur_scan,
            'max_scan': max_scan,
            'device': device
        }
        logger.debug('SuperK port_status_callback: %s', d)
        signaler.port_status_changed.emit(d)
        signaler.maybe_emit_notification(**d)

    signaler = Signaler(superk)
    signaler.device_status_callback = device_status_callback
    signaler.register_status_callback = register_status_callback
    signaler.port_status_callback = port_status_callback

    superk.connection.device_create(SuperK.FRONT_PANEL_ID, True)

    # register the callbacks
    NKT.set_callback_device_status(signaler.device_status_callback)
    NKT.set_callback_register_status(signaler.register_status_callback)
    NKT.set_callback_port_status(signaler.port_status_callback)

    return signaler
