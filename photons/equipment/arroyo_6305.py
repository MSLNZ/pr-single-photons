"""
ComboSource 6305 laser-diode controller from Arroyo Instruments.
"""
import time

from msl.equipment import EquipmentRecord
from msl.equipment.connection_message_based import ConnectionMessageBased

from .base import BaseEquipment
from .base import equipment


@equipment(manufacturer='Arroyo Instruments', model='6305')
class ComboSource(BaseEquipment):

    connection: ConnectionMessageBased

    # status flags
    CURRENT_LIMIT = 1 << 0
    VOLTAGE_LIMIT = 1 << 1
    SENSOR_LIMIT = 1 << 2
    PHOTODIODE_CURRENT_LIMIT = 1 << 2
    PHOTODIODE_POWER_LIMIT = 1 << 3
    TEMPERATURE_HIGH_LIMIT = 1 << 3
    TEMPERATURE_LOW_LIMIT = 1 << 4
    INTERLOCK_DISABLED = 1 << 4
    SENSOR_SHORTED = 1 << 5
    SENSOR_OPEN = 1 << 6
    OPEN_CIRCUIT = 1 << 7
    LASER_SHORT_CIRCUIT = 1 << 8
    OUT_OF_TOLERANCE = 1 << 9
    OUTPUT_ON = 1 << 10
    THERMAL_RUN_AWAY = 1 << 12
    R_LIMIT = 1 << 13
    T_LIMIT = 1 << 14

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """ComboSource 6305 laser-diode controller from Arroyo Instruments.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)
        self._strict: bool = True

        props = record.connection.properties
        if props.get('clear', True):
            self.clear()
        if props.get('check_interlock', True):
            if self.condition_register_laser() & ComboSource.INTERLOCK_DISABLED:
                self.raise_exception(
                    'Interlock disabled. Turn the key to the On position.'
                )

    def clear(self) -> None:
        """Clears the standard event status register, all event registers, and the error queue."""
        self.logger.info(f'send *CLS to {self.alias!r}')
        self.connection.write('*CLS')

    def condition_register_laser(self) -> int:
        """Returns the condition-register value of the laser.

        +-------+-------+--------------------------+
        |  Bit  | Value | Description              |
        +=======+=======+==========================+
        |   0   |     1 | Current limit            |
        +-------+-------+--------------------------+
        |   1   |     2 | Voltage limit            |
        +-------+-------+--------------------------+
        |   2   |     4 | Photodiode current limit |
        +-------+-------+--------------------------+
        |   3   |     8 | Photodiode power limit   |
        +-------+-------+--------------------------+
        |   4   |    16 | Interlock disabled       |
        +-------+-------+--------------------------+
        |   5   |    32 | Unused                   |
        +-------+-------+--------------------------+
        |   6   |    64 | Unused                   |
        +-------+-------+--------------------------+
        |   7   |   128 | Laser open circuit       |
        +-------+-------+--------------------------+
        |   8   |   256 | Laser short circuit      |
        +-------+-------+--------------------------+
        |   9   |   512 | Out of tolerance         |
        +-------+-------+--------------------------+
        |  10   |  1024 | Output on                |
        +-------+-------+--------------------------+
        |  11   |  2048 | Unused                   |
        +-------+-------+--------------------------+
        |  12   |  4096 | Unused                   |
        +-------+-------+--------------------------+
        |  13   |  8192 | R limit                  |
        +-------+-------+--------------------------+
        |  14   | 16384 | T limit                  |
        +-------+-------+--------------------------+
        |  15   | 32768 | Unused                   |
        +-------+-------+--------------------------+
        """
        return int(self.connection.query('LASER:COND?'))

    def condition_register_tec(self) -> int:
        """Returns the condition-register value of the TEC.

        +-------+-------+--------------------------+
        |  Bit  | Value | Description              |
        +=======+=======+==========================+
        |   0   |     1 | Current limit            |
        +-------+-------+--------------------------+
        |   1   |     2 | Voltage limit            |
        +-------+-------+--------------------------+
        |   2   |     4 | Sensor limit             |
        +-------+-------+--------------------------+
        |   3   |     8 | Temperature high limit   |
        +-------+-------+--------------------------+
        |   4   |    16 | Temperature low limit    |
        +-------+-------+--------------------------+
        |   5   |    32 | Sensor shorted           |
        +-------+-------+--------------------------+
        |   6   |    64 | Sensor open              |
        +-------+-------+--------------------------+
        |   7   |   128 | TEC open circuit         |
        +-------+-------+--------------------------+
        |   8   |   256 | Unused                   |
        +-------+-------+--------------------------+
        |   9   |   512 | Out of tolerance         |
        +-------+-------+--------------------------+
        |  10   |  1024 | Output on                |
        +-------+-------+--------------------------+
        |  11   |  2048 | Unused                   |
        +-------+-------+--------------------------+
        |  12   |  4096 | Thermal run-away         |
        +-------+-------+--------------------------+
        |  13   |  8192 | Unused                   |
        +-------+-------+--------------------------+
        |  14   | 16384 | Unused                   |
        +-------+-------+--------------------------+
        |  15   | 32768 | Unused                   |
        +-------+-------+--------------------------+
        """
        return int(self.connection.query('TEC:COND?'))

    def disable_error_checking(self) -> None:
        """Disable error checking."""
        self._strict = False

    def enable_error_checking(self) -> None:
        """Enable error checking."""
        self._strict = True

    def get_laser_current(self) -> float:
        """Returns the applied current (in milliamps) to the laser diode."""
        return float(self.connection.query('LASER:LDI?'))

    def get_laser_current_setpoint(self) -> float:
        """Returns the setpoint current (in milliamps) of the laser diode."""
        return float(self.connection.query('LASER:SET:LDI?'))

    def get_laser_temperature(self) -> float:
        """Returns the temperature (in Celsius) of the laser diode."""
        return float(self.connection.query('TEC:T?'))

    def get_laser_tolerance(self) -> tuple[float, float]:
        """Returns the `tolerance` (in milliamps) and the time window
        (in seconds) that is required to achieve `tolerance`."""
        tol, window = self.connection.query('LASER:TOLERANCE?').split(',')
        return float(tol), float(window)

    def get_tec_temperature_setpoint(self) -> float:
        """Returns the setpoint temperature of the TEC."""
        return float(self.connection.query('TEC:SET:T?'))

    def get_tec_tolerance(self) -> tuple[float, float]:
        """Returns the `tolerance` value (in Celsius) and the time window
        (in seconds) that is required to achieve `tolerance`."""
        tol, window = self.connection.query('TEC:TOLERANCE?').split(',')
        return float(tol), float(window)

    def is_laser_enabled(self) -> bool:
        """Checks if the laser is lasing."""
        return self.connection.query('LASER:OUTPUT?').rstrip() == '1'

    def is_tec_enabled(self) -> bool:
        """Checks if the TEC is enabled or disabled."""
        return self.connection.query('TEC:OUTPUT?').rstrip() == '1'

    def laser_off(self) -> None:
        """Turn the laser output off."""
        self.logger.info(f'turn off the {self.alias!r} laser output')
        self._check('LASER:OUTPUT 0')

    def laser_on(self, *, wait: bool = True, timeout: float = 120) -> None:
        """Turn the laser output on.

        Args:
            wait: Whether to wait for the laser diode current and temperature
                to stabilize before returning to the calling program.
            timeout: The maximum number of seconds to wait before raising
                an exception.
        """
        self.logger.info(f'turn on the {self.alias!r} laser output')
        self._check('LASER:OUTPUT 1')
        if wait:
            self.wait(timeout=timeout)

    def photodiode_current(self) -> float:
        """Returns the current (in uA) of the monitoring photodiode."""
        return float(self.connection.query('LASER:MDI?'))

    def set_laser_current(self,
                          milliamps: float,
                          *,
                          wait: bool = True,
                          timeout: float = 120) -> None:
        """Set the laser diode current.

        Args:
            milliamps: The laser diode setpoint current, in mA.
            wait: Whether to wait for the laser diode current and temperature
                to stabilize before returning to the calling program.
            timeout: The maximum number of seconds to wait before raising
                an exception.
        """
        self.logger.info(f'set {self.alias!r} laser current to {milliamps} mA')
        self._check(f'LASER:LDI {milliamps}')
        if wait:
            self.wait(timeout=timeout)

    def set_laser_tolerance(self, tolerance: float, duration: float) -> None:
        """Set the laser tolerance criteria.

        Allows control over when the output of the laser driver is considered
        in tolerance (or stable), in order to satisfy the tolerance condition
        of the operation complete definition.

        Args:
            tolerance: Tolerance value (in milliamps) for the measured laser
                diode current to be within the setpoint. Must be between 0 and 100.
            duration: The measured current must be within the setpoint value
                plus or minus the `tolerance` value for `duration` seconds.
                Must be between 0.1 and 50 seconds.
        """
        self.logger.info(f'set {self.alias!r} laser tolerance '
                         f'to {tolerance} mA for {duration} seconds')
        self._check(f'LASER:TOLERANCE {tolerance},{duration}')

    def set_tec_temperature(self,
                            celsius: float,
                            *,
                            wait: bool = True,
                            timeout: float = 120) -> None:
        """Set the laser diode current.

        Args:
            celsius: The TEC temperature, in Celsius.
            wait: Whether to wait for the laser diode current and temperature
                to stabilize before returning to the calling program.
            timeout: The maximum number of seconds to wait before raising
                an exception.
        """
        self.logger.info(f'set {self.alias!r} TEC temperature to {celsius} degC')
        self._check(f'TEC:T {celsius}')
        if wait:
            self.wait(timeout=timeout)

    def set_tec_tolerance(self, tolerance: float, duration: float) -> None:
        """Set the TEC tolerance criteria.

        Allows control over when the output of the temperature controller
        is considered in tolerance (or stable), in order to satisfy the
        tolerance condition of the operation complete definition.

        Args:
            tolerance: Tolerance value, in Celsius, for the measured laser
                temperature to be within the setpoint. Must be between 0.01 and 10.
            duration: The measured temperature must be within the setpoint value
                plus or minus the `tolerance` value for `duration` seconds.
                Must be between 0.1 and 50 seconds.
        """
        self.logger.info(f'set {self.alias!r} TEC tolerance to '
                         f'{tolerance} degC for {duration} seconds')
        self._check(f'TEC:TOLERANCE {tolerance},{duration}')

    def tec_off(self) -> None:
        """Disable TEC control."""
        self.logger.info(f'turn off TEC control for {self.alias!r}')
        self._check('TEC:OUTPUT 0')

    def tec_on(self, *, wait: bool = True, timeout: float = 120) -> None:
        """Enable TEC control.

        Args:
            wait: Whether to wait for the laser diode current and temperature
                to stabilize before returning to the calling program.
            timeout: The maximum number of seconds to wait before raising
                an exception.
        """
        self.logger.info(f'turn on TEC control for {self.alias!r}')
        self._check('TEC:OUTPUT 1')
        if wait:
            self.wait(timeout=timeout)

    def wait(self, timeout: float = 120) -> None:
        """Wait for the laser diode current and temperature to be stable.

        The condition-register value must be okay and the laser diode current
        and temperature values must be within tolerance of the setpoint value.

        Args:
            timeout: The maximum number of seconds to wait before raising
                an exception.
        """
        self.logger.info(f'wait for {self.alias!r} to stabilize ...')

        registers = []

        tec_enabled = self.is_tec_enabled()
        if tec_enabled:
            tec_setpoint = self.setpoint_tec()
            tec_tol, tec_duration = self.get_tec_tolerance()
            registers.append(self.condition_register_tec)
        else:
            tec_setpoint = tec_tol = tec_duration = -1

        laser_enabled = self.is_laser_enabled()
        if laser_enabled:
            laser_setpoint = self.setpoint_laser()
            laser_tol, laser_duration = self.get_laser_tolerance()
            registers.append(self.condition_register_laser)
        else:
            laser_setpoint = laser_tol = laser_duration = -1

        # check the tolerances
        temperature_ok = not tec_enabled
        current_ok = not laser_enabled
        t0 = time.time()
        time_tec_out_of_bounds = t0
        time_laser_out_of_bounds = t0
        while True:
            t = time.time()
            if t - t0 > timeout:
                self.raise_exception(f'Timeout after {timeout} seconds')
            if not temperature_ok:
                if abs(self.get_laser_temperature() - tec_setpoint) > tec_tol:
                    time_tec_out_of_bounds = t
                temperature_ok = t - time_tec_out_of_bounds >= tec_duration
            if not current_ok:
                if abs(self.get_laser_current() - laser_setpoint) > laser_tol:
                    time_laser_out_of_bounds = t
                current_ok = t - time_laser_out_of_bounds >= laser_duration
            if temperature_ok and current_ok:
                break
            time.sleep(0.1)

        # check the condition registers
        for register in registers:
            while True:
                value = register()
                if not(value & self.OUT_OF_TOLERANCE) and (value & self.OUTPUT_ON):
                    break
                if time.time() - t0 > timeout:
                    self.raise_exception(f'Timeout after {timeout} seconds')
                time.sleep(0.1)

        self.logger.info(f'{self.alias!r} stable')

    def _check(self, command: str) -> None:
        reply = self.connection.query(f'{command};ERRSTR?').rstrip()
        if self._strict and reply != '0':
            self.raise_exception(f'command={command!r}, reply={reply!r}')
