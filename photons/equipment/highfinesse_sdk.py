"""
Wrapper around the 32-bit wlmData.dll library from HighFinesse.
"""
from __future__ import annotations

from ctypes import c_bool
from ctypes import c_double
from ctypes import c_long
from ctypes import c_ulong
from ctypes import c_ushort
from ctypes import c_void_p
from time import perf_counter

from msl.loadlib import Server32

ERROR_CODES = {
    -1: 'ErrNoSignal: The wavemeter has not detected any signal',
    -2: 'ErrBadSignal: The wavemeter has not detected a calculable signal',
    -3: 'ErrLowSignal: The signal is too small to be calculated properly',
    -4: 'ErrBigSignal: The signal is too large to be calculated properly',
    -5: 'ErrWlmMissing: The wavemeter is not active',
    -6: 'ErrNotAvailable: This function is not available for this wavemeter version',
    -7: 'InfNothingChanged',
    -8: 'ErrNoPulse: The detected signal could not be divided into separate pulses',
    -13: 'ErrDiv0: Division by Zero',
    -14: 'ErrOutOfRange',
    -15: 'ErrUnitNotAvailable',
    -1000: 'ErrTempNotMeasured',
    -1006: 'ErrTempNotAvailable',
    -1005: 'ErrTempWlmMissing',
    -1000000006: 'ErrDistanceNotAvailable',
    -1000000005: 'ErrDistanceWlmMissing',
}

SET_ERROR_CODES = {
    -1: 'ResERR_WlmMissing',
    -2: 'ResERR_CouldNotSet',
    -3: 'ResERR_ParmOutOfRange',
    -4: 'ResERR_WlmOutOfResources',
    -5: 'ResERR_WlmInternalError',
    -6: 'ResERR_NotAvailable',
    -7: 'ResERR_WlmBusy',
    -8: 'ResERR_NotInMeasurementMode',
    -9: 'ResERR_OnlyInMeasurementMode',
    -10: 'ResERR_ChannelNotAvailable',
    -11: 'ResERR_ChannelTemporarilyNotAvailable',
    -12: 'ResERR_CalOptionNotAvailable',
    -13: 'ResERR_CalWavelengthOutOfRange',
    -14: 'ResERR_BadCalibrationSignal',
    -15: 'ResERR_UnitNotAvailable',
}


def check(r: bool | int | float) -> bool | int | float:
    """Check the result for an error.

    Returns the result if there is no error.
    """
    if r < 0:
        raise RuntimeError(ERROR_CODES.get(r, f'Undefined error code: {r}'))
    return r


def check_set(r: int | float) -> int | float:
    """Check the result of a "Set*" function for an error.

    Returns the result if there is no error.
    """
    if r < 0:
        raise RuntimeError(SET_ERROR_CODES.get(r, f'Undefined error code: {r}'))
    return r


class WLMData32(Server32):

    def __init__(self, host: str, port: int) -> None:
        """Wrapper around the 32-bit wlmData.dll library from HighFinesse."""
        super().__init__(r'C:\Windows\System32\wlmData.dll', 'windll', host, port)

        signatures = [
            ('ConvertUnit', c_double, (c_double, c_long, c_long)),
            ('GetAnalysisMode', c_bool, (c_bool,)),
            ('GetExposureMode', c_bool, (c_bool,)),
            ('GetExposureNum', c_long, (c_long, c_long, c_long)),
            ('GetFrequency', c_double, (c_double,)),
            ('GetFrequency2', c_double, (c_double,)),
            ('GetFrequencyNum', c_double, (c_long, c_double)),
            ('GetLinewidth', c_double, (c_long, c_double)),
            ('GetLinewidthMode', c_bool, (c_bool,)),
            ('GetPatternDataNum', c_long, (c_long, c_long, c_void_p)),
            ('GetPatternItemCount', c_long, (c_long,)),
            ('GetPatternItemSize', c_long, (c_long,)),
            ('GetPatternNum', c_long, (c_long, c_long)),
            ('GetPulseMode', c_ushort, (c_ushort,)),
            ('GetRange', c_ushort, (c_ushort,)),
            ('GetTemperature', c_double, (c_double,)),
            ('GetWideMode', c_ushort, (c_ushort,)),
            ('GetWLMCount', c_long, (c_long,)),
            ('GetWLMVersion', c_ulong, (c_long,)),
            ('GetWavelength', c_double, (c_double,)),
            ('GetWavelength2', c_double, (c_double,)),
            ('GetWavelengthNum', c_double, (c_long, c_double)),
            ('Instantiate', c_long, (c_long, c_long, c_long, c_long)),
            ('Operation', c_long, (c_ushort,)),
            ('SetAnalysisMode', c_long, (c_bool,)),
            ('SetExposureMode', c_long, (c_bool,)),
            ('SetExposureNum', c_long, (c_long, c_long, c_long)),
            ('SetLinewidthMode', c_long, (c_bool,)),
            ('SetPattern', c_long, (c_long, c_long)),
            ('SetPulseMode', c_long, (c_ushort,)),
            ('SetRange', c_long, (c_ushort,)),
            ('SetWideMode', c_long, (c_ushort,)),
        ]
        for name, res, args in signatures:
            fcn = getattr(self.lib, name)
            fcn.argtypes = args
            fcn.restype = res

    def convert_unit(self, value: float, frm: int, to: int) -> float:
        """Convert a value into a representation of another unit.

        Args:
            value: The value to convert. Must be >= 0.
            frm: The unit index of that `value` is currently in.
            to: The unit index to convert `value` to.
        """
        return check(self.lib.ConvertUnit(value, frm, to))

    def get_analysis_mode(self) -> bool:
        """Whether analysis mode is enabled or disabled."""
        # the input argument to GetAnalysisMode is reserved for future use
        return check(self.lib.GetAnalysisMode(False))

    def get_auto_exposure_mode(self) -> bool:
        """Whether auto-exposure mode is enabled or disabled."""
        # the input argument to GetExposureMode is reserved for future use
        return check(self.lib.GetExposureMode(False))

    def get_exposure_time(self, channel: int = 1, index: int = 1) -> int:
        """Returns the exposure time (in ms).

        Args:
            channel: The signal channel for devices with a multichannel switcher.
                Should be set to 1 for devices that do not have this option.
            index: The CCD array index for devices with more than one CCD array.
                Can be 1 or 2. For devices with only one CCD array set the
                value to be 1.
        """
        return check(self.lib.GetExposureNum(channel, index, 0))

    def get_linewidth(self, index: int) -> float:
        """Returns the linewidth in the specified unit.

        Args:
            index: The unit to return the linewidth in.
        """
        # the second argument to GetLinewidth is reserved for future use
        ret = check(self.lib.GetLinewidth(index, 0.0))
        if ret == 0:
            raise RuntimeError(
                'The linewidth has a value of 0. '
                'Make sure you have enabled linewidth mode.'
            )
        return ret

    def get_linewidth_mode(self) -> bool:
        """Whether linewidth mode is enabled or disabled."""
        # the input argument to GetLinewidthMode is reserved for future use
        return bool(check(self.lib.GetLinewidthMode(False)))

    def get_pattern_data(self, index: int, channel: int = 1) -> list[int]:
        """Returns the interferometer pattern data.

        Args:
            index: The index of the data type to receive.

                * 0 - Fizeau interferometers or diffraction grating
                * 1 - Additional long interferometer or grating analyzing versions (spectrum analysis)
                * 2 - Fizeau interferometers that support double pulses
                * 3 - Additional interferometer for second pulse

            channel: Identifies the switcher channel number. Versions without
                a switcher must use 1.

        Returns:
            The interferometer pattern data.
        """
        check_set(self.lib.SetPattern(index, 1))  # cPatternEnable = 1
        size = self.lib.GetPatternItemSize(index)
        if size == 2:
            data_type = c_ushort
        elif size == 4:
            data_type = c_ulong  # DWORD
        else:
            raise RuntimeError('Expected a byte size of 2 or 4 from GetPatternItemSize')
        count = self.lib.GetPatternItemCount(index)
        array = (data_type * count)()
        res = self.lib.GetPatternDataNum(channel, index, array)
        if res == 0:
            raise RuntimeError('Cannot get the interferometer pattern data')
        return list(array)

    def get_pulse_mode(self) -> int:
        """Returns the pulse mode."""
        # the input argument to GetPulseMode is reserved for future use
        return self.lib.GetPulseMode(0)

    def get_range(self) -> int:
        """Returns the wavelength range that is selected."""
        # the input argument to GetRange is reserved for future use
        return self.lib.GetRange(0)

    def get_wide_mode(self) -> int:
        """Returns the measurement precision mode."""
        # the input argument to GetWideMode is reserved for future use
        return self.lib.GetWideMode(0)

    def get_wlm_count(self) -> int:
        """Returns the number of wavemeter and spectrum-analyser
        applications that are running."""
        # the input argument to GetWLMCount is reserved for future use
        return self.lib.GetWLMCount(0)

    def get_wlm_version(self) -> dict[str, int]:
        """Returns version information about the device."""
        return {
            'device_type': check(self.lib.GetWLMVersion(0)),
            'serial_number': check(self.lib.GetWLMVersion(1)),
            'software_revision': check(self.lib.GetWLMVersion(2)),
            'software_compilation': check(self.lib.GetWLMVersion(3)),
        }

    def instantiate(self, rfc: int, mode: int, p1: int, p2: int) -> int:
        """Checks whether the Wavelength Meter or Laser Spectrum Analyser
        server application is running, changes the return mode of the
        measurement values, installs/removes an extended exporting mechanism,
        changes the appearance of the server application window or
        starts/terminates the server application.

        See the manual for more details about the input parameters.

        Returns:
            If the function succeeds and at least one Wavelength Meter or
            Laser Spectrum Analyser is active or terminated due to this
            instantiating operation the function returns a value greater
            than 0, else 0.
        """
        return self.lib.Instantiate(rfc, mode, p1, p2)

    def operation(self, mode: int) -> int:
        """Set the operation mode.

        Args:
            mode: Controls how a measurement or file accessing activity will be
                started or stopped. See manual for more details.
        """
        return check_set(self.lib.Operation(mode))

    def set_analysis_mode(self, mode: bool) -> None:
        """Set the analysis mode.

        Args:
            mode: Whether to enable (True) or disable (False) analysis mode.
        """
        check_set(self.lib.SetAnalysisMode(mode))

    def set_auto_exposure_mode(self, mode: bool) -> None:
        """Set the auto-exposure mode.

        Args:
            mode: Whether to enable (True) or disable (False) auto-exposure mode.
        """
        check_set(self.lib.SetExposureMode(mode))

    def set_exposure_time(self, ms: int, channel: int = 1, index: int = 1):
        """Set the exposure time.

        Args:
            ms: The exposure time, in ms.
            channel: The signal channel for devices with a multichannel switcher.
                Should be set to 1 for devices that do not have this option.
            index: The CCD array index for devices with more than one CCD array.
                Can be 1 or 2. For devices with only one CCD array set the
                value to be 1.
        """
        check_set(self.lib.SetExposureNum(channel, index, ms))

    def set_linewidth_mode(self, mode: bool) -> None:
        """Set the linewidth mode.

        Args:
            mode: Whether to enable (True) or disable (False) linewidth mode.
        """
        check_set(self.lib.SetLinewidthMode(mode))

    def set_pulse_mode(self, mode: int) -> None:
        """Set the pulse mode.

        Args:
            mode: The pulse mode (e.g., 0=CW, 1=Pulsed).
        """
        check_set(self.lib.SetPulseMode(mode))

    def set_range(self, value: int) -> None:
        """Set the wavelength range.

        Args:
            value: The enum value of the wavelength range.
        """
        check_set(self.lib.SetRange(value))

    def set_wide_mode(self, mode: int) -> None:
        """Set the measurement precision mode.

        Args:
            mode: The precision mode (e.g., 0=fine, 1=wide, 2=grating analysis).
        """
        check_set(self.lib.SetWideMode(mode))

    def temperature(self) -> float:
        """Returns the temperature of the device, in Celsius."""
        return check(self.lib.GetTemperature(0.0))

    def wait(self, duration: float, timeout: float = 30) -> None:
        """Wait for a valid wavelength to be measured and for the exposure time to be stable.

        Args:
            duration: The number of seconds the device must be stable for.
            timeout: The maximum number of seconds to wait.
        """
        # this method assumes that the default arguments to
        #  get_exposure_time() and self.wavelength() are okay
        previous = self.get_exposure_time()
        t_stable = perf_counter()
        t_start = t_stable
        while True:
            t = perf_counter()
            if t - t_start > timeout:
                raise TimeoutError(f'Timeout after {timeout} seconds')

            try:
                self.wavelength()
            except RuntimeError:
                t_stable = perf_counter()
                continue

            current = self.get_exposure_time()
            if current != previous:
                previous = current
                t_stable = perf_counter()

            if t - t_stable >= duration:
                break

    def wavelength(self, number: int = 0) -> float:
        """Returns the wavelength (in nm)

        Args:
            number: The signal number (1 to 8) if the wavemeter has a multichannel
                switcher or contains the double-pulse option. For wavemeters
                without these options set to 0.
        """
        # the second argument to GetWavelengthNum is reserved for future use
        ret = check(self.lib.GetWavelengthNum(number, 0.0))
        if ret == 0:
            raise RuntimeError(
                f'The wavelength has a value of 0.\n'
                f'Are you reading the appropriate channel number? (number={number})'
            )
        return ret
