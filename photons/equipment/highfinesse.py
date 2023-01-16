"""
Communicate with a Wavemeter or Laser Spectrum Analyser from HighFinesse.
"""
import enum
import os
import time
from subprocess import Popen

import numpy as np
from msl.equipment import EquipmentRecord
from msl.equipment.connection import Connection
from msl.equipment.resources import register
from msl.loadlib import Client64
from msl.loadlib import Server32Error

from .base import BaseEquipment
from .base import equipment
from .highfinesse_sdk import WLMData32


@register(manufacturer=r'High\s?Finesse')
class WLMData64(Connection):

    def __init__(self, record: EquipmentRecord) -> None:
        """Wrapper around the :class:`~photons.equipment.highfinesse_sdk.WLMData32` class.

        Args:
            record: The equipment record.
        """
        self._client, self._exe = None, None
        super().__init__(record)

        self._client = Client64(os.path.join(os.path.dirname(__file__), 'highfinesse_sdk.py'))
        self._request32 = self._client.request32

        # the SDK address is the path to the HighFinesse executable (wlm_ws5.exe or LSA.exe)
        exe = record.connection.address[5:]
        if not os.path.isfile(exe):
            raise FileNotFoundError(f'Cannot find {exe}')
        self._exe = Popen(exe, cwd=os.path.dirname(exe))

        timeout = 20
        t0 = time.time()
        while True:
            count = self._request32('get_wlm_count')
            if count > 0:
                # Even if no HighFinesse devices are found, the get_wlm_count()
                # function may still return 1.
                #
                # Calling get_wlm_version() below is supposed to raise ErrWlmMissing
                # if no devices are found, but it does not.
                #
                # Read the temperature to verify that a device is indeed available.
                while True:
                    try:
                        self._request32('temperature')
                        break
                    except Server32Error:
                        if time.time() - t0 > timeout:
                            count = 0
                            break
                        time.sleep(0.5)
                break
            if time.time() - t0 > timeout:
                break
            time.sleep(0.5)

        if count == 0:
            raise TimeoutError('A wavemeter or laser spectrum analyser was not found')

        exe_serial = str(self._request32('get_wlm_version')['serial_number'])
        if exe_serial != record.serial:
            raise ValueError(f'Serial number mismatch. '
                             f'Expected {record.serial}, got {exe_serial}')

    def __getattr__(self, item):
        def request(*args, **kwargs):
            return self._request32(item, *args, **kwargs)
        return request

    def disconnect(self) -> None:
        """Disconnect from the device."""
        if not self._client:
            return

        stdout, stderr = self._client.shutdown_server32()
        stdout.close()
        stderr.close()
        self._client = None

        if self._exe is not None:
            self._exe.returncode = 0
            self._exe.terminate()
            self._exe = None

        self.log_debug(f'Disconnected from {self.equipment_record.connection}')


class Range(enum.IntEnum):
    """Wavelength ranges that are supported."""
    nm245_325 = 0
    nm320_420 = 1
    nm410_610 = 2
    nm600_1190 = 3


class RangeModel(enum.IntEnum):
    """Range models that are supported."""
    OLD = 65535
    ORDER = 65534
    WAVELENGTH = 65533


@equipment(manufacturer=r'High\s?Finesse')
class HighFinesse(BaseEquipment):

    connection: WLMData32

    Range = Range
    RangeModel = RangeModel

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Communicate with a Wavemeter or Laser Spectrum Analyser from HighFinesse.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)
        self.ignore_attributes('Range', 'RangeModel')

    def get_analysis_mode(self) -> bool:
        """Whether analysis mode is enabled or disabled."""
        return self.connection.get_analysis_mode()

    def get_auto_exposure_mode(self) -> bool:
        """Whether auto-exposure mode is enabled or disabled."""
        return self.connection.get_auto_exposure_mode()

    def get_exposure_time(self) -> int:
        """Returns the exposure time, in milliseconds."""
        return self.connection.get_exposure_time()

    def get_pattern_data(self, index: int = 0, timeout: float = 10) -> np.ndarray | list[int]:
        """Returns the interferometer pattern data.

        If this class is running as a Service, a list is returned.

        Args:
            index: The index of the data type to receive.

                * 0 - Fizeau interferometers or diffraction grating
                * 1 - Additional long interferometer or grating analyzing versions (spectrum analysis)
                * 2 - Fizeau interferometers that support double pulses
                * 3 - Additional interferometer for second pulse

            timeout: The number of seconds to wait for the pattern data to be available.
        """
        # It can take a few seconds for data to be available
        # after SetPattern() is initially enabled, so keep trying
        # until non-zero values are returned
        t0 = time.time()
        while True:
            array = self.connection.get_pattern_data(index)
            if sum(array[:10]) > 0:
                if self.running_as_service:
                    return array
                return np.asarray(array)
            if time.time() - t0 > timeout:
                raise TimeoutError(f'Could not get pattern data within {timeout} seconds')
            time.sleep(0.1)

    def get_pulse_mode(self) -> bool:
        """Returns whether pulse mode is enabled (False=CW, True=Pulsed)."""
        return bool(self.connection.get_pulse_mode())

    def get_wavelength_range(self) -> Range | RangeModel | int:
        """Returns the currently-selected wavelength range or range model."""
        r = self.connection.get_range()
        try:
            return Range(r)
        except ValueError:
            try:
                return RangeModel(r)
            except ValueError:
                return r

    def get_wide_mode(self) -> bool:
        """Returns the measurement precision mode (False=fine, True=wide)."""
        return bool(self.connection.get_wide_mode())

    def linewidth(self, in_air: bool = True) -> float:
        """Returns the linewidth, in nm.

        Args:
            in_air: Whether to return the linewidth value in air (True) or vacuum (False).
        """
        return self.connection.get_linewidth(in_air)

    def set_analysis_mode(self, mode: bool) -> None:
        """Whether to enable or disable analysis mode.

        Args:
            mode: Enable (True) or disable (False) analysis mode.
        """
        text = 'enable' if mode else 'disable'
        self.logger.info(f'{text} analysis mode of {self.alias!r}')
        self.connection.set_analysis_mode(mode)

    def set_auto_exposure_mode(self, mode: bool) -> None:
        """Whether to enable or disable auto-exposure mode.

        Args:
            mode: Enable (True) or disable (False) auto-exposure mode.
        """
        text = 'enable' if mode else 'disable'
        self.logger.info(f'{text} auto-exposure mode of {self.alias!r}')
        self.connection.set_auto_exposure_mode(mode)

    def set_exposure_time(self, ms: int) -> None:
        """Set the exposure time, in milliseconds.

        This method will disable auto-exposure mode.

        Args:
            ms: The exposure time, in milliseconds.
        """
        self.set_auto_exposure_mode(False)
        self.logger.info(f'set exposure time to {ms} ms for {self.alias!r}')
        self.connection.set_exposure_time(ms)

    def set_linewidth_mode(self, mode: bool) -> None:
        """Whether to enable or disable linewidth mode.

        Args:
            mode: Enable (True) or disable (False) linewidth mode.
        """
        text = 'enable' if mode else 'disable'
        self.logger.info(f'{text} linewidth mode of {self.alias!r}')
        self.connection.set_linewidth_mode(mode)

    def set_pulse_mode(self, mode: int | bool) -> None:
        """Set the pulse mode.

        Args:
            mode: CW=0|False, Pulsed=1|True
        """
        m = 'Pulsed' if mode else 'CW'
        self.logger.info(f'set pulse mode to {m!r} for {self.alias!r}')
        self.connection.set_pulse_mode(mode)

    def set_wavelength_range(self, value: Range | int) -> None:
        """Set the wavelength range.

        .. important::

           The :meth:`.set_wavelength_range_model` must be called before
           this method is called in order to select the range model.

        Args:
            value: If the range model is :attr:`.RangeModel.ORDER`, the
                wavelength range is set by a :class:`.Range` enum value.
                If the range model is :attr:`.RangeModel.WAVELENGTH`, the
                wavelength range is set by a wavelength value, in nm, as an
                :class:`int` data type.
        """
        if isinstance(value, Range):
            self.logger.info(f'set wavelength range to {value!r} for {self.alias!r}')
            r = value.value
        else:
            self.logger.info(f'set wavelength range to {value} nm for {self.alias!r}')
            r = value
        self.connection.set_range(r)

    def set_wavelength_range_model(self, model: RangeModel | int) -> None:
        """Set the wavelength range model.

        Args:
            model: The wavelength range model.
        """
        m = self.convert_to_enum(model, RangeModel, to_upper=True)
        self.logger.info(f'set wavelength range model to {m!r} for {self.alias!r}')
        self.connection.set_range(m.value)  # noqa: Expected type 'int', got '() -> int' instead

    def set_wide_mode(self, mode: bool) -> None:
        """Set the measurement precision mode.

        Args:
            mode: The precision mode (e.g., False=fine, True=wide).
        """
        m = 'wide' if mode else 'fine'
        self.logger.info(f'set precision to {m!r} mode for {self.alias!r}')
        self.connection.set_wide_mode(mode)

    def start_measurement(self) -> None:
        """Start measurements."""
        self.logger.info(f'start measurements for {self.alias!r}')
        ret = self.connection.operation(2)
        if ret < 0:
            self.raise_exception(f'Cannot start measurements, error code {ret}')

    def stop_measurement(self) -> None:
        """Stop all measurements."""
        self.logger.info(f'stop measurements for {self.alias!r}')
        ret = self.connection.operation(0)
        if ret < 0:
            self.raise_exception(f'Cannot stop measurements, error code {ret}')

    def temperature(self) -> float:
        """Get the temperature inside the optical unit, in Celsius."""
        return self.connection.temperature()

    def wait(self, stable: float, timeout: float = 30) -> None:
        """Wait for a valid wavelength to be measured and for the exposure time to be stable.

        Args:
            stable: The number of seconds the device must be stable for.
            timeout: The maximum number of seconds to wait.
        """
        self.logger.info(f'wait for {self.alias!r} to stabilize ...')
        try:
            self.connection.wait(stable, timeout=timeout)
        except Server32Error as e:
            self.logger.error(e.value)
            raise
        self.logger.info(f'{self.alias!r} stable')

    def wavelength(self, in_air: bool = True) -> float:
        """Returns the wavelength, in nanometers.

        Args:
            in_air: Whether to return the wavelength in air (True) or vacuum (False).
        """
        w = self.connection.wavelength(number=1)
        if in_air:
            # cReturnWavelengthVac = 0
            # cReturnWavelengthAir = 1
            return self.connection.convert_unit(w, 0, 1)
        return w

    @staticmethod
    def wavelength_ranges() -> dict[str, int]:
        """Returns the available wavelength ranges for the Laser Spectrum Analyser."""
        return {'245-325nm': Range.nm245_325,
                '320-420nm': Range.nm320_420,
                '410-610nm': Range.nm410_610,
                '600-1190nm': Range.nm600_1190}

    @staticmethod
    def wavelength_range_models() -> dict[str, int]:
        """Returns the available wavelength range models for the Laser Spectrum Analyser."""
        return {'old': RangeModel.OLD,
                'order': RangeModel.ORDER,
                'wavelength': RangeModel.WAVELENGTH}
