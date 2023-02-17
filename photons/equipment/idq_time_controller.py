"""
Time Controller from ID Quantique.
"""
import warnings
from dataclasses import dataclass
from enum import Enum
from math import ceil
from time import perf_counter
from time import sleep
from typing import Sequence

import numpy as np
from msl.equipment import EquipmentRecord
from msl.equipment.connection_zeromq import ConnectionZeroMQ
from msl.qt import QtCore
from msl.qt import Signal

from .base import BaseEquipment
from .base import equipment
from ..samples import Samples


class Clock(Enum):
    INTERNAL = 'INTERNAL'
    EXTERNAL = 'EXTERNAL'
    INT = 'INTERNAL'
    EXT = 'EXTERNAL'


class Coupling(Enum):
    AC = 'AC'
    DC = 'DC'


class Edge(Enum):
    RISING = 'RISING'
    FALLING = 'FALLING'


class Mode(Enum):
    ACCUMULATE = 'ACCUM'
    ACCUM = 'ACCUM'
    CYCLE = 'CYCLE'
    NIM = 'NIM'
    TTL = 'TTL'
    HIGH_SPEED = 'LOWRES'
    HIGH_RESOLUTION = 'HIRES'
    LOW_SPEED = 'HIRES'
    LOW_RESOLUTION = 'LOWRES'
    FAST = 'LOWRES'
    SLOW = 'HIRES'


class ResyncPolicy(Enum):
    AUTO = 'AUTO'
    MANUAL = 'MANUAL'


class Select(Enum):
    LOOP = 'LOOP'
    OUTPUT = 'OUTPUT'
    SHAPED = 'SHAPED'
    UNSHAPED = 'UNSHAPED'


@dataclass
class DelaySettings:
    address: str
    value: float

    def to_json(self) -> dict[str, str | float]:
        """Return the settings as a JSON serializable object."""
        return {'address': self.address, 'value': self.value}


@dataclass
class DeviceSettings:
    clock: Clock
    mode: Mode

    def to_json(self) -> dict[str, str]:
        """Return the settings as a JSON serializable object."""
        return {'clock': self.clock.value, 'mode': self.mode.value}


@dataclass
class Histogram:
    hist1: np.ndarray
    hist2: np.ndarray
    hist3: np.ndarray
    hist4: np.ndarray

    def to_json(self) -> dict[str, list]:
        """Return the histogram data as a JSON serializable object."""
        return {  # noqa:  tolist() returns a list
            'hist1': self.hist1.tolist(),
            'hist2': self.hist2.tolist(),
            'hist3': self.hist3.tolist(),
            'hist4': self.hist4.tolist(),
        }


@dataclass
class HistogramSettings:
    channel: int
    ref: str
    stop: str
    enabler: str
    minimum: float
    maximum: float
    bin_count: int
    bin_width: float

    def to_json(self) -> dict[str, str | int | float]:
        """Return the settings as a JSON serializable object."""
        return {
            'channel': self.channel,
            'ref': self.ref,
            'stop': self.stop,
            'enabler': self.enabler,
            'minimum': self.minimum,
            'maximum': self.maximum,
            'bin_count': self.bin_count,
            'bin_width': self.bin_width
        }


@dataclass
class InputSettings:
    channel: int
    coupling: Coupling
    edge: Edge
    enabled: bool
    delay: float
    duration: float
    mode: Mode
    resync_policy: ResyncPolicy
    select: Select
    threshold: float

    def to_json(self) -> dict[str, str | bool | int | float]:
        """Return the settings as a JSON serializable object."""
        return {
            'channel': self.channel,
            'coupling': self.coupling.value,
            'edge': self.edge.value,
            'enabled': self.enabled,
            'delay': self.delay,
            'duration': self.duration,
            'mode': self.mode.value,
            'resync_policy': self.resync_policy.value,
            'select': self.select.value,
            'threshold': self.threshold
        }


@dataclass
class StartSettings:
    coupling: Coupling
    edge: Edge
    enabled: bool
    delay: float
    duration: float
    mode: Mode
    select: Select
    threshold: float

    def to_json(self) -> dict[str, str | bool | float]:
        """Return the settings as a JSON serializable object."""
        return {
            'coupling': self.coupling.value,
            'edge': self.edge.value,
            'enabled': self.enabled,
            'delay': self.delay,
            'duration': self.duration,
            'mode': self.mode.value,
            'select': self.select.value,
            'threshold': self.threshold
        }


@equipment(manufacturer=r'ID\s*Q', model=r'ID900')
class IDQTimeController(BaseEquipment):

    Clock: Clock = Clock
    Coupling: Coupling = Coupling
    Edge: Edge = Edge
    Mode: Mode = Mode
    ResyncPolicy: ResyncPolicy = ResyncPolicy
    Select: Select = Select

    connection: ConnectionZeroMQ

    counts_changed: QtCore.SignalInstance = Signal(Samples)

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Time Controller from ID Quantique.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)
        self.ignore_attributes('counts_changed')
        cfg = kwargs.get('config')
        if cfg is not None:
            self.load(cfg)

    def _check_channel(self, channel: int) -> None:
        """Check that the channel number is valid, raises an exception if invalid."""
        if channel < 1 or channel > 4:
            self.raise_exception(f'The channel number must be 1, 2, 3 or 4 (got {channel})')

    def _check_delay_block(self, block: int) -> None:
        if block < 1 or block > 8:
            self.raise_exception(f'The DELAY block number must be '
                                 f'between 1 and 8 (got {block})')

    def _check_delay_value(self, *, delay: float, stacklevel: int) -> None:
        """Check the delay value."""
        if delay < 0 or delay > 1:
            self.raise_exception(f'The delay must be between '
                                 f'0 and 1 second (got {delay})')

        if delay > 4e-6:
            warnings.warn(
                'Delay >4us, there is no guarantee it will work',
                UserWarning,
                stacklevel=stacklevel)

    def _config_start_or_input(self, **kwargs) -> None:
        """Common to both configure_start and configure_input."""
        if kwargs['duration'] < 0.001 or kwargs['duration'] > 65.535:
            self.raise_exception(f'The duration must be between '
                                 f'0.001 and 65.535 seconds (got {kwargs["duration"]})')

        self._check_delay_value(delay=kwargs['delay'], stacklevel=4)

        enable = 'ON' if kwargs['enabled'] else 'OFF'
        coupling = self.convert_to_enum(kwargs['coupling'], Coupling, to_upper=True)
        edge = self.convert_to_enum(kwargs['edge'], Edge, to_upper=True)
        mode = self.convert_to_enum(kwargs['mode'], Mode, to_upper=True)
        select = self.convert_to_enum(kwargs['select'], Select, to_upper=True)

        if kwargs['resync_policy'] is not None:
            policy = self.convert_to_enum(kwargs['resync_policy'], ResyncPolicy, to_upper=True)
            resync_policy = f'RESYNCPOLICY {policy.value};'
        else:
            # the START command does not support RESYNCPOLICY
            resync_policy = ''

        ms = round(kwargs['duration'] * 1e3)  # convert to milliseconds
        ps = round(kwargs['delay'] * 1e12)  # convert to picoseconds

        cmd = f'{kwargs["type"]}:ENABLE {enable};' \
              f'COUPLING {coupling.value};' \
              f'EDGE {edge.value};' \
              f'THRESHOLD {kwargs["threshold"]}V;' \
              f'SELECT {select.value};' \
              f'{resync_policy}' \
              f':{kwargs["type"]}:COUNTER:INTEGRATIONTIME {ms};' \
              f'MODE {mode.value};' \
              f'{kwargs["delay_cmd"]} {ps}'

        self.logger.info(f'configure {self.alias!r} {kwargs["type"]} settings with {cmd!r}')

        reply = self.connection.query(cmd)
        if reply.endswith('SCPI_ERR_PARAM_TYPE') or reply.endswith('SCPI_ERR_INVALID_CMD'):
            self.raise_exception(reply)

    def clear_high_resolution_error(self, channel: int) -> None:
        """Clear the high-resolution error for an input channel.

        Args:
            channel: The input channel number (1, 2, 3 or 4).
        """
        self._check_channel(channel)
        self.logger.info(f'clear {self.alias!r} high-resolution error for INPUT{channel}')
        reply = self.connection.query(f'INPUT{channel}:HIRES:ERROR:CLEAR')
        if reply != 'Cleared Highres errors':
            self.raise_exception('Could not clear the high-resolution error')

    def configure_delay(self,
                        *,
                        block: int,
                        address: int | str | None,
                        value: float = 0) -> DelaySettings:
        """Configure the settings for a DELAY block.

        Args:
            block: The DELAY block number (1 through 8).
            address: The address to link the DELAY to. Can be an INPUT
                channel number (e.g., 1 or 'INPUT1'), 'START' or None.
            value: The delay value, in seconds.

        Returns:
            The DELAY settings that were read from the device after the
            settings were written.
        """
        self._check_delay_block(block)

        address_map = {
            None: 'NONE',
            0: 'STAR',
            1: 'INPU1',
            2: 'INPU2',
            3: 'INPU3',
            4: 'INPU4',
            'NONE': 'NONE',
            'STAR': 'STAR',
            'START': 'STAR',
            'INPU1': 'INPU1',
            'INPU2': 'INPU2',
            'INPU3': 'INPU3',
            'INPU4': 'INPU4',
            'INPUT1': 'INPU1',
            'INPUT2': 'INPU2',
            'INPUT3': 'INPU3',
            'INPUT4': 'INPU4',
        }

        if isinstance(address, str):
            address = address.upper()

        link = address_map.get(address)
        if link is None:
            self.raise_exception(f'Invalid DELAY address {address!r}')

        self._check_delay_value(delay=value, stacklevel=3)
        ps = round(value * 1e12)  # convert to picoseconds
        cmd = f'DELAY{block}:INPORT:LINK {link};:DELAY{block}:VALUE {ps}'
        self.logger.info(f'configure {self.alias!r} DELAY block with {cmd!r}')

        reply = self.connection.query(cmd)
        if reply.startswith('No') or \
                reply.endswith('SCPI_ERR_PARAM_TYPE') or \
                reply.endswith('SCPI_ERR_INVALID_CMD'):
            self.raise_exception(reply)
        return self.settings_delay(block)

    def configure_device(self, *, clock: Clock | str, mode: Mode | str) -> DeviceSettings:
        """Configure the DEVICE settings.

        Args:
            clock: Use the internal or external clock.
            mode: The resolution mode (high speed or high resolution).

        Returns:
            The DEVICE settings that were read from the device after the
            settings were written.
        """
        sync = self.convert_to_enum(clock, Clock, to_upper=True)
        mode = self.convert_to_enum(mode, Mode, to_upper=True)
        if mode not in (Mode.HIGH_SPEED, Mode.HIGH_RESOLUTION):
            self.raise_exception(f'Invalid device resolution mode {mode.value!r}')

        cmd = f'DEVICE:SYNC {sync.value};RESOLUTION {mode.value}'
        self.logger.info(f'configure {self.alias!r} DEVICE settings with {cmd!r}')

        reply = self.connection.query(cmd)
        if reply.endswith('SCPI_ERR_PARAM_TYPE') or reply.endswith('SCPI_ERR_INVALID_CMD'):
            self.raise_exception(reply)
        return self.settings_device()

    def configure_histogram(self,
                            *,
                            channel: int,
                            ref: int | str | None,
                            stop: int | str | None = None,
                            enabler: str = 'TSGE8',
                            minimum: float = 0,
                            maximum: float = 1e-6,
                            bin_count: int | None = None,
                            bin_width: float = 100e-12) -> HistogramSettings:
        """Configure a HISTOGRAM channel.

        Args:
            channel: The HISTOGRAM channel number (1, 2, 3 or 4).
            ref: The INPUT channel number (0[START], 1, 2, 3 or 4) or
                the name of the reference channel (e.g., 'TSCO5')
            stop: The INPUT channel number (0[START], 1, 2, 3 or 4) or
                the name of the stop channel (e.g., 'TSCO5'). If not specified,
                then the value of `ref` is used.
            enabler: The timestamp-generator block that determines when
                data acquisition begins and ends.
            minimum: Minimum time value, in seconds.
            maximum: Maximum time value, in seconds.
            bin_count: The number of time bins. If specified, then `maximum`
                is ignored. Must be between 1 and 16384.
            bin_width: The time-bin width, in seconds.

        Returns:
            The HISTOGRAM settings that were read from the device after the
            settings were written.
        """
        self._check_channel(channel)

        if bin_width < 100e-12 or bin_width > 1e-3:
            self.raise_exception(f'The bin width must be between '
                                 f'100 ps and 1 ms (got {bin_width})')

        if minimum < 0:
            self.raise_exception(f'The minimum time must be >0 (got {minimum})')

        if bin_count is None:
            bin_count = ceil((maximum - minimum) / bin_width)

        if bin_count < 1 or bin_count > 16384:
            self.raise_exception(f'Invalid bin count, {bin_count}. '
                                 f'Must be between 1 and 16384.')

        if isinstance(ref, str):
            ref = ref.upper()

        if stop is None:
            stop = ref

        input_map = {
            None: 'NONE',
            0: 'STAR',
            1: 'TSCO5',
            2: 'TSCO6',
            3: 'TSCO7',
            4: 'TSCO8',
            'START': 'STAR',
            'INPUT1': 'TSCO5',
            'INPUT2': 'TSCO6',
            'INPUT3': 'TSCO7',
            'INPUT4': 'TSCO8',
        }

        ref_link = input_map.get(ref, ref)
        stop_link = input_map.get(stop, stop)

        # convert to picoseconds
        min_ps = ceil(minimum * 1e12)
        width_ps = ceil(bin_width * 1e12)

        cmd = f':HIST{channel}:INPORT:STOP:LINK {stop_link};' \
              f':HIST{channel}:INPORT:REF:LINK {ref_link};' \
              f':HIST{channel}:INPORT:ENAB:LINK {enabler};' \
              f':HIST{channel}:MINIMUM {min_ps};' \
              f':HIST{channel}:BWIDTH {width_ps};' \
              f':HIST{channel}:BCOUNT {bin_count};' \
              f':RAW{channel}:INPORT:STOP:LINK {stop_link};' \
              f':RAW{channel}:INPORT:REF:LINK {ref_link}'

        self.logger.info(f'configure {self.alias!r} HISTOGRAM{channel} settings with {cmd!r}')

        reply = self.connection.query(cmd)
        if 'No connection' in reply or \
                reply.endswith('SCPI_ERR_PARAM_TYPE') or \
                reply.endswith('SCPI_ERR_INVALID_CMD'):
            self.raise_exception(reply)
        return self.settings_histogram(channel)

    def configure_input(self,
                        *,
                        channel: int,
                        coupling: Coupling | str = Coupling.DC,
                        delay: float = 0,
                        duration: float = 1,
                        edge: Edge | str = Edge.RISING,
                        enabled: bool = False,
                        mode: Mode | str = Mode.CYCLE,
                        resync_policy: ResyncPolicy | str = ResyncPolicy.AUTO,
                        select: Select | str = Select.UNSHAPED,
                        threshold: float = 1) -> InputSettings:
        """Configure an INPUT channel.

        Args:
            channel: The input channel number (1, 2, 3 or 4).
            coupling: Either AC or DC coupling.
            delay: The delay, in seconds, to add to the timestamp when an edge
                is detected. Must be between 0 and 1 second.
            duration: The number of seconds to count edges (integration time).
                Must be between 0.001 and 65.535 seconds.
            edge: The discriminator edge, either RISING or FALLING.
            enabled: Whether the channel is enabled or disabled.
            mode: The counter mode (either CYCLE or ACCUMULATE).
            resync_policy: The resync policy.
            select: Select what feeds the INPUT block.
            threshold: The discriminator threshold value, in volts.

        Returns:
            The INPUT settings that were read from the device after the
            settings were written.
        """
        self._check_channel(channel)
        kwargs = {
            'coupling': coupling,
            'delay': delay,
            'delay_cmd': f':DELAY{channel}:INPORT:LINK INPU{channel};:DELAY{channel}:VALUE',
            'duration': duration,
            'edge': edge,
            'enabled': enabled,
            'mode': mode,
            'resync_policy': resync_policy,
            'select': select,
            'threshold': threshold,
            'type': f'INPUT{channel}',
        }
        self._config_start_or_input(**kwargs)
        return self.settings_input(channel)

    def configure_start(self,
                        *,
                        coupling: Coupling | str = Coupling.DC,
                        delay: float = 0,
                        edge: Edge | str = Edge.RISING,
                        enabled: bool = False,
                        duration: float = 1,
                        mode: Mode | str = Mode.CYCLE,
                        select: Select | str = Select.UNSHAPED,
                        threshold: float = 1) -> StartSettings:
        """Configure the START channel.

        Args:
            coupling: Either AC or DC coupling.
            delay: The delay, in seconds, to add to the timestamp when an edge
                is detected. Must be between 0 and 1 second.
            edge: The discriminator edge, either RISING or FALLING.
            enabled: Whether the channel is enabled or disabled.
            duration: The number of seconds to count edges (integration time).
                Must be between 0.001 and 65.535 seconds.
            mode: The counter mode (either CYCLE or ACCUMULATE).
            select: Select what feeds the START block.
            threshold: The discriminator threshold value, in volts.

        Returns:
            The START settings that were read from the device after the
            settings were written.
        """
        kwargs = {
            'coupling': coupling,
            'delay': delay,
            'delay_cmd': ':START:DELAY',
            'duration': duration,
            'edge': edge,
            'enabled': enabled,
            'mode': mode,
            'resync_policy': None,
            'select': select,
            'threshold': threshold,
            'type': f'START',
        }
        self._config_start_or_input(**kwargs)
        return self.settings_start()

    def count_edges(self,
                    *,
                    channel: int,
                    allow_zero: bool = False,
                    nsamples: int = 1) -> Samples:
        """Count the number of edges per second.

        Args:
            channel: The input channel number (e.g., 0[START], 1, 2, 3 or 4).
            allow_zero: Whether to allow zero edges per second to be counted.
                Querying the COUNTER? value from the device immediately returns
                the value that is stored in the device's memory. After resetting
                the device (i.e., the value returned by COUNTER? is 0) Python
                sleeps for `duration` seconds (see :meth:`.configure_input`)
                before querying COUNTER?. Since the computer clock and the device
                clock are not synced it is possible that COUNTER? is queried before
                the device writes a value to memory. If zero edges are detected
                and `allow_zero` is :data:`False` then this method will block until
                at least 1 edge is detected.
            nsamples: The number of samples to acquire.

        Returns:
            The number of edges per second.
        """
        if channel == 0:
            settings = self.settings_start()
            reset_cmd = 'START:COUNTER:RESET'
            count_cmd = 'START:COUNTER?'
            where = 'START'
        else:
            settings = self.settings_input(channel)
            reset_cmd = f'INPUT{channel}:COUNTER:RESET'
            count_cmd = f'INPUT{channel}:COUNTER?'
            where = f'INPUT{channel}'

        if not settings.enabled:
            self.raise_exception(f'Channel {where} is not enabled')

        cps = np.full((nsamples,), -2 ** 63, dtype=np.int64)
        duration = settings.duration
        query = self.connection.query

        self.logger.info(f'{self.alias!r} start counting edges on {where} ...')
        for index in range(nsamples):
            if query(reset_cmd) != 'Counter value set to 0 ':
                self.raise_exception('Could not reset the counter')
            sleep(duration)
            while True:
                counts = int(query(count_cmd))
                if counts > 0 or allow_zero:
                    break
                sleep(0.01)
            cps[index] = counts / duration

        self.logger.info(
            f'{self.alias!r} counted {np.array2string(cps, max_line_width=1000)} '
            f'{settings.edge.name} edges/second in {duration}-second intervals')

        s = Samples(cps)
        self.counts_changed.emit(s)
        self.maybe_emit_notification(**s.to_json())
        return s

    def has_high_resolution_error(self, channel: int) -> bool:
        """Check if an input channel has a high-resolution error.

        Args:
            channel: The input channel number (1, 2, 3 or 4).

        Returns:
            Whether the specified channel has a high-resolution error.
        """
        self._check_channel(channel)
        reply = self.connection.query(f'INPUT{channel}:HIRES:ERROR?')
        return int(reply) == 1

    def load(self, config: str) -> None:
        """Load a pre-defined configuration.

        Args:
            config: The configuration to load ('INIT', 'HISTO', 'COUNT', or 'BLANK').
        """
        self.logger.info(f'{self.alias!r} load configuration {config!r}')
        reply = self.connection.query(f'DEVICE:CONFIGURATION:LOAD {config}')
        if reply.endswith('SCPI_ERR_PARAM_TYPE') or reply.endswith('SCPI_ERR_INVALID_CMD'):
            self.raise_exception(f'Could not load configuration {config!r}')

    def recalibrate(self) -> None:
        """Recalibrate the Time Controller."""
        self.logger.info(f'recalibrating {self.alias!r}')
        reply = self.connection.query('DEVICE:SAMPLING:RECALIBRATE')
        if 'failed' in reply:
            self.raise_exception(reply)

    def settings_delay(self, block: int) -> DelaySettings:
        """Get the settings of a DELAY block.

        Args:
            block: The DELAY block number (1 through 8).
        """
        self._check_delay_block(block)
        address_map = {
            'NONE': None,
            'STAR': 'START',
            'INPU1': 'INPUT1',
            'INPU2': 'INPUT2',
            'INPU3': 'INPUT3',
            'INPU4': 'INPUT4',
        }
        reply = self.connection.query(f'DELAY{block}:STATE?')
        value, address = reply.rstrip(';').split(';')
        return DelaySettings(
            address=address_map[address[10:].upper()],
            value=round(float(value[12:].rstrip('TB')) * 1e-12, 12))

    def settings_device(self) -> DeviceSettings:
        """Get the DEVICE settings."""
        reply = self.connection.query('DEVICE:STATE?')
        sync, res = reply.upper().split(';')
        return DeviceSettings(
            clock=self.convert_to_enum(sync[12:], Clock),
            mode=self.convert_to_enum(res[4:], Mode)
        )

    def settings_histogram(self, channel: int) -> HistogramSettings:
        """Get the settings of a HISTOGRAM channel.

        Args:
            channel: The HISTOGRAM channel number (1, 2, 3 or 4).
        """
        self._check_channel(channel)
        reply = self.connection.query(f':HIST{channel}:STATE?')
        stop, ref, enab, _min, width, count = reply.rstrip(';').split(';')
        bin_count = int(count[7:])
        bin_width = round(float(width[5:].rstrip('TB')) * 1e-12, 12)
        minimum = round(float(_min[11:].rstrip('TB')) * 1e-12, 12)
        return HistogramSettings(
            channel=channel,
            ref=ref[23:],
            stop=stop[23:],
            enabler=enab[24:],
            minimum=minimum,
            maximum=round(minimum + (bin_width * bin_count), 12),
            bin_width=bin_width,
            bin_count=bin_count)

    def settings_input(self, channel: int) -> InputSettings:
        """Get the settings of an INPUT channel.

        Args:
            channel: The INPUT channel number (1, 2, 3 or 4).
        """
        self._check_channel(channel)
        reply = self.connection.query(f'INPUT{channel}:STATE?;:DELAY{channel}:VALUE?')
        enab, coup, edge, thre, sel, resy, time, mode, delay = reply.upper().split(';')
        return InputSettings(
            channel=channel,
            coupling=self.convert_to_enum(coup[5:], Coupling),
            edge=self.convert_to_enum(edge[5:], Edge),
            enabled=enab.endswith('ON'),
            delay=round(float(delay.rstrip('TB')) * 1e-12, 12),
            duration=round(float(time[30:].rstrip('TB')) * 1e-3, 3),
            mode=self.convert_to_enum(mode[5:], Mode),
            resync_policy=self.convert_to_enum(resy[5:], ResyncPolicy),
            select=self.convert_to_enum(sel[5:], Select),
            threshold=float(thre[5:].rstrip('V')))

    def settings_start(self) -> StartSettings:
        """Get the settings of the START channel."""
        reply = self.connection.query('START:STATE?')
        enab, coup, edge, thre, sel, delay, time, mode = reply.upper().split(';')
        return StartSettings(
            coupling=self.convert_to_enum(coup[5:], Coupling),
            edge=self.convert_to_enum(edge[5:], Edge),
            enabled=enab.endswith('ON'),
            delay=round(float(delay[5:].rstrip('TB')) * 1e-12, 12),
            duration=round(float(time[30:].rstrip('TB')) * 1e-3, 3),
            mode=self.convert_to_enum(mode[5:], Mode),
            select=self.convert_to_enum(sel[5:], Select),
            threshold=float(thre[5:].rstrip('V')))

    def start_stop(self,
                   *,
                   clear: bool = True,
                   duration: float = 30,
                   enabler: str = 'TSGE8',
                   min_events: int | Sequence[int] = 0,
                   timeout: float | None = None) -> Histogram:
        """Acquire a start-stop histogram of the duration between two edges.

        Args:
            clear: Whether to clear the histogram data before acquiring data.
            duration: The number of seconds to acquire data for.
            enabler: The timestamp-generator block that determines when
                data acquisition begins and ends.
            min_events: The minimum number of start-stop events, on each
                histogram channel, that must occur before returning to the
                calling program. If specified, then iteratively acquires data
                for `duration` seconds until the specified number of events
                has occurred.
            timeout: The maximum number of seconds to wait for `min_events`
                to occur. If a timeout occurs, the data that has been
                acquired is returned (an error is not raised).

        Returns:
            The histogram data.
        """
        channels = (1, 2, 3, 4)
        done = [False, False, False, False]

        if isinstance(min_events, int):
            min_events = [min_events for _ in channels]

        if len(min_events) != len(channels):
            self.raise_exception(f'Length of min_events sequence must be '
                                 f'{len(channels)}, (got {len(min_events)})')

        timestamps = []
        for c in channels:
            s = self.settings_histogram(c)
            bin_center = (s.minimum + s.bin_width) / 2.0
            timestamps.append(bin_center + (np.arange(s.bin_count) * s.bin_width))

        def gate(action):
            r = self.connection.query(f':{enabler}:ENABLE {action}')
            if not r.endswith(action):
                self.raise_exception(f'Cannot turn {action} {enabler}')

        if clear:
            self.logger.info(f'clear {self.alias!r} HISTOGRAM')
            gate('OFF')
            for c in channels:
                reply = self.connection.query(f':HIST{c}:FLUSH')
                if reply != 'Flushed Histogram!':
                    self.raise_exception(f'Cannot clear HIST{c}')

        counts = [np.empty(0)] * len(channels)
        t0 = perf_counter()
        while not all(done):
            self.logger.info(f'{self.alias!r} waiting for {duration} second(s) for HISTOGRAM data ...')
            gate('ON')
            sleep(duration)
            gate('OFF')
            for i, c in enumerate(channels):
                reply = self.connection.query(f':HIST{c}:DATA?')
                counts[i] = np.fromstring(reply[1:-1], sep=',', dtype=np.uint64)
                if (not done[i]) and (np.sum(counts[i]) >= min_events[i]):
                    done[i] = True
            if timeout and perf_counter() - t0 > timeout:
                self.logger.warning(f'{self.alias!r} timed out after '
                                    f'{timeout} seconds waiting for HISTOGRAM data')
                break

        self.logger.info(f'{self.alias!r} finished acquiring HISTOGRAM data')

        f = np.core.records.fromarrays
        return Histogram(
            hist1=f([timestamps[0], counts[0]], names=['timestamps', 'counts']),
            hist2=f([timestamps[1], counts[1]], names=['timestamps', 'counts']),
            hist3=f([timestamps[2], counts[2]], names=['timestamps', 'counts']),
            hist4=f([timestamps[3], counts[3]], names=['timestamps', 'counts']),
        )
