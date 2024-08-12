"""
DAQ from National Instruments.
"""
import warnings

import nidaqmx.constants
import numpy as np
from msl.equipment import EquipmentRecord
from msl.equipment.connection_nidaq import ConnectionNIDAQ
from msl.qt import QtCore
from msl.qt import Signal
from scipy.signal import sawtooth
from scipy.signal import square

from .base import BaseEquipment
from .base import equipment
from ..samples import Samples

Task = nidaqmx.Task

Edge = nidaqmx.constants.Edge
Slope = nidaqmx.constants.Slope
DigitalWidthUnits = nidaqmx.constants.DigitalWidthUnits
CountDirection = nidaqmx.constants.CountDirection
AcquisitionType = nidaqmx.constants.AcquisitionType
TriggerType = nidaqmx.constants.TriggerType
Level = nidaqmx.constants.Level
LineGrouping = nidaqmx.constants.LineGrouping
TerminalConfiguration = nidaqmx.constants.TerminalConfiguration
TimeUnits = nidaqmx.constants.TimeUnits

AnalogSingleChannelReader = nidaqmx.stream_readers.AnalogSingleChannelReader
AnalogMultiChannelReader = nidaqmx.stream_readers.AnalogMultiChannelReader
CounterReader = nidaqmx.stream_readers.CounterReader


class Timing:

    def __init__(self, **kwargs) -> None:
        """Do not instantiate this class directly. Use :meth:`NIDAQ.timing`."""
        self._samples_per_channel = 1
        self._source = kwargs['source']
        self._rate = kwargs['rate']
        if kwargs['rising']:
            self._active_edge = Edge.RISING
        else:
            self._active_edge = Edge.FALLING
        if kwargs['finite']:
            self._sample_mode = AcquisitionType.FINITE
        else:
            self._sample_mode = AcquisitionType.CONTINUOUS

        settings = [
            f'rate={self._rate}',
            f'edge={self._active_edge.name}',
            f'mode={self._sample_mode.name}',
        ]
        if self._source:
            settings.append(f'source={self._source}')
        self._settings = ', '.join(settings)

    def __repr__(self) -> str:
        return f'Timing<{self._settings}>'

    def add_to(self, task: Task) -> None:
        """Add the timing configuration to a task.

        Args:
            task: The task to add the timing configuration to.
        """
        task.timing.cfg_samp_clk_timing(
            self._rate,
            source=self._source,
            active_edge=self._active_edge,
            sample_mode=self._sample_mode,
            samps_per_chan=self._samples_per_channel
        )

    @property
    def rate(self) -> float:
        """Returns the sample rate (in Hz)."""
        return self._rate

    @property
    def sample_mode(self) -> AcquisitionType:
        """Returns the sample mode."""
        return self._sample_mode

    @property
    def samples_per_channel(self) -> int:
        """Returns the number of samples per channel to acquire or generate."""
        return self._samples_per_channel

    @samples_per_channel.setter
    def samples_per_channel(self, value):
        self._samples_per_channel = int(value)


class Trigger:

    def __init__(self, **kwargs) -> None:
        """Do not instantiate this class directly. Use :meth:`NIDAQ.trigger`."""
        self._delay = kwargs['delay']
        self._level = kwargs['level']
        self._hysteresis = kwargs['hysteresis']
        self._retriggerable = kwargs['retriggerable']
        settings = [f'source={kwargs["source"]}']
        if self._level is None:
            # digital trigger
            edge = Edge.RISING if kwargs['rising'] else Edge.FALLING
            self._kwargs = {
                'trigger_source':  kwargs['source'],
                'trigger_edge': edge
            }
            settings.append(f'edge={edge.name}')
        else:
            # analog trigger
            slope = Slope.RISING if kwargs['rising'] else Slope.FALLING
            self._kwargs = {
                'trigger_source': kwargs['source'],
                'trigger_slope': slope,
                'trigger_level': self._level
            }
            settings.extend([f'slope={slope.name}, level={self._level}'])

        if self._delay != 0:
            settings.append(f'delay={self._delay}')
        if self._retriggerable:
            settings.append(f'retriggerable=True')
        if self._hysteresis != 0:
            settings.append(f'hysteresis={self._hysteresis}')

        self._settings = ', '.join(settings)

    def __repr__(self) -> str:
        return f'Trigger<{self._settings}>'

    def add_to(self, task: Task) -> None:
        """Add this trigger to a task.

        Args:
            task: The task to add the trigger event to.
        """
        if self._delay < 0:
            pre = round(task.timing.samp_clk_rate * abs(self._delay))
            t = task.triggers.reference_trigger
            if self._level is None:
                t.cfg_dig_edge_ref_trig(pretrigger_samples=pre, **self._kwargs)
            else:
                t.cfg_anlg_edge_ref_trig(pretrigger_samples=pre, **self._kwargs)
                if self._hysteresis != 0:
                    t.anlg_edge_hyst = self._hysteresis
            if self._retriggerable:
                t.retriggerable = True
        else:
            t = task.triggers.start_trigger
            if self._level is None:
                t.cfg_dig_edge_start_trig(**self._kwargs)
            else:
                t.cfg_anlg_edge_start_trig(**self._kwargs)
                if self._hysteresis != 0:
                    t.anlg_edge_hyst = self._hysteresis

            if self._delay > 0:
                t.delay_units = DigitalWidthUnits.SECONDS
                t.delay = self._delay

            if self._retriggerable:
                t.retriggerable = True


@equipment(manufacturer=r'National Instruments', model=r'USB-6361')
class NIDAQ(BaseEquipment):

    connection: ConnectionNIDAQ

    counts_changed: QtCore.SignalInstance = Signal(Samples)

    Task = Task
    WAIT_INFINITELY = nidaqmx.constants.WAIT_INFINITELY

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """DAQ from National Instruments.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)
        self.DEV: str = record.connection.address
        self._tasks: list[Task] = []
        self.ignore_attributes('DEV', 'counts_changed',
                               'Task', 'WAIT_INFINITELY')

    def analog_in(self,
                  channel: int | str,
                  *,
                  config: int | str = 'DIFF',
                  duration: float = None,
                  maximum: float = 10,
                  minimum: float = -10,
                  nsamples: int = 1,
                  timeout: float = 10,
                  timing: Timing = None,
                  trigger: Trigger = None,
                  wait: bool = True) -> tuple[np.ndarray | Task, float]:
        """Read the voltage(s) of the analog-input channel(s).

        Args:
            channel: The analog-input channel number(s), e.g.,
                channel=0, channel='0:7'.
            config: Specifies the input terminal configuration for the channel,
                see :class:`~nidaqmx.constants.TerminalConfiguration`.
            duration: The number of seconds to read voltages for. If specified
                then this value is used instead of `nsamples`.
            maximum: The maximum voltage that is expected to be measured.
            minimum: The minimum voltage that is expected to be measured.
            nsamples: The number of samples per channel to read. If a `duration`
                is also specified then that value is used instead of `nsamples`.
            timeout: The maximum number of seconds to wait for the task to finish.
                Set to -1 to wait forever.
            timing: The timing settings to use. See :meth:`.timing`.
            trigger: The trigger settings to use. See :meth:`.trigger`.
            wait: Whether to wait for the task to finish. If enabled then also
                closes the task when it is finished.

        Returns:
            If `wait` is True then the voltage(s) of the requested analog-input
            channel(s) and the time interval between samples (i.e., dt) are
            returned. Otherwise, the analog-input task, which has *not* been
            started yet and the time interval between samples are returned.
            Not starting the task allows one to register a callback before
            starting the task.

        Examples:

            .. suppress-unresolved-reference-daq:
                >>> daq = NIDAQ()

            Read the value of a single analog-input channel

            >>> daq.analog_in(0)
            (array([-0.48746041]), 0.001)
            >>> daq.analog_in(6, nsamples=5)
            (array([-0.44944232, -0.45040888, -0.45137544, -0.45556387, -0.45298637]), 0.001)

            Read the values of multiple analog-input channels

            >>> daq.analog_in('0:3', nsamples=4)
            (array([[ 0.03512726,  0.03770475,  0.03867132,  0.03512726],
                   [-0.1675285 ,  0.17527869, -0.17171693,  0.17237901],
                   [ 0.08248878,  0.12243999,  0.00741916,  0.07991128],
                   [ 0.08861033,  0.09859814,  0.05832474,  0.06831254]]), 0.001)
       """
        if isinstance(channel, str) and channel.startswith(f'/{self.DEV}'):
            ai_channel = channel
        else:
            ai_channel = f'/{self.DEV}/ai{channel}'

        tc = self.convert_to_enum(config, TerminalConfiguration, to_upper=True)

        task = NIDAQ.Task()
        self._tasks.append(task)
        task.ai_channels.add_ai_voltage_chan(
            ai_channel,
            terminal_config=tc,
            min_val=minimum,
            max_val=maximum,
        )

        if timing is None:
            timing = self.timing()

        if duration is None:
            timing.samples_per_channel = nsamples
        else:
            timing.samples_per_channel = round(duration * timing.rate)

        self._maybe_set_timing_and_trigger(task, timing, trigger, 'analog-input')

        dt = 1.0 / task.timing.samp_clk_rate
        if wait:
            samples_per_channel = timing.samples_per_channel
            num_channels = task.number_of_channels
            if num_channels == 1:
                data = np.empty((samples_per_channel,), dtype=float)
                reader = AnalogSingleChannelReader(task.in_stream)
            else:
                data = np.empty((num_channels, samples_per_channel), dtype=float)
                reader = AnalogMultiChannelReader(task.in_stream)
            try:
                reader.read_many_sample(
                    data,
                    number_of_samples_per_channel=samples_per_channel,
                    timeout=timeout,
                )
                task.read()
            finally:
                task.close()
                self._tasks.remove(task)
            return data, dt
        return task, dt

    def analog_out(self,
                   channel: int | str,
                   voltage: float | list[float] | list[list[float]] | np.ndarray,
                   *,
                   auto_start: bool = True,
                   timeout: float = 10,
                   timing: Timing = None,
                   trigger: Trigger = None,
                   wait: bool = True) -> Task:
        """Write the voltage(s) to the analog-output channel(s).

        Args:
            channel: The analog-output channel number(s), e.g., channel=0, channel='0:1'.
            voltage: The voltage(s) to output.
            auto_start: Whether to automatically start the task.
            timeout: The maximum number of seconds to wait for the task to finish.
                Set to -1 to wait forever.
            timing: The timing settings to use. See :meth:`.timing`.
            trigger: The trigger settings to use. See :meth:`.trigger`.
            wait: Whether to wait for the task to finish. If enabled then also
                closes the task when it is finished.

        Returns:
            The analog-output task.

        Examples:

            .. suppress-unresolved-reference-daq:
                >>> daq = NIDAQ()

            Write to a single analog-output channel

            >>> daq.analog_out(0, 1.123)

            Write to multiple analog-output channels

            >>> daq.analog_out('0:1', [0.2, -1.2])
            >>> daq.analog_out('0:1', [[0.2, 0.1, 0.], [-0.1, 0., 0.1]])
        """
        if isinstance(voltage, (float, int)):
            array = np.array([voltage], dtype=float)
        else:
            array = np.asarray(voltage)

        min_val = np.min(array)
        max_val = np.max(array)
        if max_val == min_val:
            max_val += 0.1

        ao = f'/{self.DEV}/ao{channel}'
        task = NIDAQ.Task()
        self._tasks.append(task)

        task.ao_channels.add_ao_voltage_chan(ao, min_val=min_val, max_val=max_val)

        if timing is None:
            timing = self.timing()
        timing.samples_per_channel = array.size // task.number_of_channels

        self._maybe_set_timing_and_trigger(task, timing, trigger, 'analog-output')

        self.logger.info(f'{self.alias!r} set {ao} with {array.shape} samples')

        written = task.write(array, auto_start=auto_start, timeout=timeout)
        assert written == timing.samples_per_channel
        if wait:
            try:
                task.wait_until_done(timeout=timeout)
            finally:
                task.close()
                self._tasks.remove(task)
        return task

    def analog_out_read(self,
                        channel: int | str,
                        **kwargs) -> tuple[np.ndarray | Task, float]:
        """Read the output voltage(s) from the analog-output channel(s).

        Args:
            channel: The analog-output channel number(s), e.g., channel=0, channel='0:1'.
            **kwargs: All keyword arguments are passed to :meth:`.analog_in`.

        Returns:
            If `wait` is True then the voltage(s) of the requested analog-output
            channel(s) and the time interval between samples (i.e., dt) are
            returned. Otherwise, the analog-output task, which has *not* been
            started yet and the time interval between samples are returned.
            Not starting the task allows one to register a callback before
            starting the task.

        Examples:

            .. suppress-unresolved-reference-daq:
                >>> daq = NIDAQ()

            Read a single value from an analog-output channel

            >>> daq.analog_out_read(0)
            (array([-1.09800537]), 0.001)

            Read multiple values from multiple analog-output channels

            >>> daq.analog_out_read('0:1', nsamples=4)
            (array([[-1.09832756, -1.09736099, -1.09800537, -1.09736099],
                   [ 0.21168585,  0.21233022,  0.21200803,  0.21168585]]), 0.001)
        """
        def name(index):
            return f'/{self.DEV}/_ao{index}_vs_aognd'

        if isinstance(channel, str) and ':' in channel:
            start, end = map(int, channel.split(':'))
            assert end >= start
            channels = [name(ch) for ch in range(start, end+1, 1)]
            ao_channels = ','.join(channels)
        else:
            ao_channels = name(channel)

        return self.analog_in(ao_channels, **kwargs)

    def close_all_tasks(self) -> None:
        """Close all tasks."""
        with warnings.catch_warnings():
            # closing an already-closed task indicates a ResourceWarning
            warnings.simplefilter('ignore', ResourceWarning)
            for task in self._tasks:
                task.close()
        self._tasks.clear()

    def count_edges(self,
                    pfi: int,
                    duration: float,
                    *,
                    nsamples: int = 1,
                    rising: bool = True) -> Samples:
        """Count the number of edges per second.

        Args:
            pfi: The PFI terminal number.
            duration: The number of seconds to count edges for.
            nsamples: The number of times to count edges for `duration` seconds.
            rising: Whether to count rising edges, otherwise count falling edges.

        Returns:
            The number of edges per second.
        """
        cps = np.full((nsamples,), -2**63, dtype=np.int64)

        # using a Counter Output task as a gate for the Counter Input task
        edge = Edge.RISING if rising else Edge.FALLING

        # add a small delay to make sure that the CI task has started and
        # is waiting for the CO gate pulse
        co_task_delay = 0.01

        ctr_src = 0
        ctr_gate = 1

        self.logger.info(f'{self.alias!r} start counting edges ...')

        for index in range(nsamples):
            with NIDAQ.Task() as co_task, NIDAQ.Task() as ci_task:
                co_task.co_channels.add_co_pulse_chan_time(
                    f'/{self.DEV}/ctr{ctr_gate}',
                    high_time=duration,
                    # The value of low_time doesn't matter and that is why it is large
                    low_time=1000.,
                    idle_state=Level.LOW,
                    initial_delay=co_task_delay,
                )
                co_task.timing.cfg_implicit_timing(
                    sample_mode=AcquisitionType.FINITE,
                    samps_per_chan=1,
                )

                channel = ci_task.ci_channels.add_ci_count_edges_chan(
                    f'/{self.DEV}/ctr{ctr_src}',
                    edge=edge,
                    initial_count=0,
                    count_direction=CountDirection.COUNT_UP
                )
                # redirect the CI channel to the PFI terminal that has the
                # input signal connected to it
                channel.ci_count_edges_term = f'/{self.DEV}/PFI{pfi}'

                # only increment the counter when the gate output is HIGH
                pt = ci_task.triggers.pause_trigger
                pt.trig_type = TriggerType.DIGITAL_LEVEL
                pt.dig_lvl_when = Level.LOW
                # the digital level source is internally connected to the CO task output
                pt.dig_lvl_src = f'/{self.DEV}/Ctr{ctr_gate}InternalOutput'

                # must start the CI task before the CO task
                ci_task.start()
                co_task.start()
                co_task.wait_until_done(timeout=duration + co_task_delay + 5.0)
                count = channel.ci_count
                cps[index] = count / duration

        self.logger.info(
            f'{self.alias!r} counted {np.array2string(cps, max_line_width=1000)} '
            f'{edge.name} edges/second in {duration}-second intervals')

        s = Samples(cps)
        self.counts_changed.emit(s)
        self.maybe_emit_notification(**s.to_json())
        return s

    def digital_in(self,
                   lines: int | str,
                   *,
                   port: int = 1) -> bool | list[bool]:
        """Read the state of the digital-input channel(s).

        Args:
            lines: The line number(s) (e.g., line=1, line='0:7',
                line='/Dev1/port0/line0:7,/Dev1/port1/line0:3').
            port: The port number.

        Returns:
            Whether the requested digital input channel(s) are HIGH or LOW.

        Examples:

            .. suppress-unresolved-reference-daq:
                >>> daq = NIDAQ()

            Read the state of a single digital-input channel (P1.0)

            >>> daq.digital_in(0)
            False

            Read the state of a single digital-input channel (P0.2)

            >>> daq.digital_in(2, port=0)
            True

            Read the state of multiple digital-input channels (P1.0-7)

            >>> daq.digital_in('0:7')
            [False, False, True, False, False, False, False, True]
        """
        with NIDAQ.Task() as task:
            task.di_channels.add_di_chan(
                self._generate_digital_lines(lines, port),
                line_grouping=LineGrouping.CHAN_PER_LINE
            )
            return task.read()

    def digital_out(self,
                    lines: int | str,
                    state: bool | list[bool] | list[list[bool]],
                    *,
                    auto_start: bool = True,
                    port: int = 1,
                    timeout: float = 10,
                    timing: Timing = None,
                    trigger: Trigger = None,
                    wait: bool = True) -> Task:
        """Write the state of digital-output channels(s).

        Args:
            lines: The line number(s) (e.g., line=1, line='0:7',
                line='/Dev1/port0/line0:7,/Dev1/port1/line0:3').
            state: Whether to set the specified line(s) to HIGH or LOW.
            auto_start: Whether to automatically start the task.
            port: The port number.
            timeout: The maximum number of seconds to wait for the task to finish.
                Set to -1 to wait forever.
            timing: The timing settings to use. See :meth:`.timing`.
            trigger: The trigger settings to use. See :meth:`.trigger`.
            wait: Whether to wait for the task to finish. If enabled then also
                closes the task when it is finished.

        Returns:
            The digital-output task.

        Examples:

            .. suppress-unresolved-reference-daq:
                >>> daq = NIDAQ()

            Set the state of a single digital-output channel (P1.0)

            >>> daq.digital_out(0, True)

            Set multiple digital-output channels to be in the same state (P2.0-7)

            >>> daq.digital_out('0:7', False, port=2)

            Set the state of multiple digital-output channels (P1.2-4)

            >>> daq.digital_out('2:4', [False, True, True])
        """
        lines = self._generate_digital_lines(lines, port)

        task = NIDAQ.Task()
        self._tasks.append(task)

        task.do_channels.add_do_chan(
            lines,
            line_grouping=LineGrouping.CHAN_PER_LINE
        )

        n = 1
        num_channels = task.number_of_channels
        if isinstance(state, bool):
            if num_channels > 1:
                state = [state] * num_channels
        elif num_channels == 1:
            n = len(state)
        elif isinstance(state[0], (list, tuple)):
            n = len(state[0])  # noqa: state[0] is a list[bool]

        if timing is None:
            timing = self.timing()
        timing.samples_per_channel = n

        self._maybe_set_timing_and_trigger(task, timing, trigger, 'digital-output')

        self.logger.info(f'{self.alias!r} set {lines} to {state}')
        written = task.write(state, auto_start=auto_start, timeout=timeout)
        assert written == n
        if wait:
            try:
                task.wait_until_done(timeout=timeout)
            finally:
                task.close()
                self._tasks.remove(task)
        return task

    def digital_out_read(self,
                         lines: int | str,
                         *,
                         port: int = 1) -> bool | list[bool]:
        """Read the state of digital-output channel(s).

        Args:
            lines: The line number(s) (e.g., line=1, line='0:7',
                line='/Dev1/port0/line0:7,/Dev1/port1/line0:3').
            port: The port number.

        Returns:
            Whether the requested digital-output channel(s) are HIGH or LOW.

        Examples:

            .. suppress-unresolved-reference-daq:
                >>> daq = NIDAQ()

            Read the state of a single digital-output channel (P1.0)

            >>> daq.digital_out_read(0)
            True

            Read the state of a single digital-output channel (P0.5)

            >>> daq.digital_out_read(5, port=0)
            False

            Read the state of multiple digital-output channels (P1.0-7)

            >>> daq.digital_out_read('0:7')
            [False, True, True, False, True, False, False, False]
        """
        with NIDAQ.Task() as task:
            task.do_channels.add_do_chan(
                self._generate_digital_lines(lines, port),
                line_grouping=LineGrouping.CHAN_PER_LINE
            )
            return task.read()

    def edge_separation(self,
                        start: int,
                        stop: int,
                        *,
                        maximum: float = 1.0,
                        minimum: float = 100e-9,
                        nsamples: int = 10,
                        start_edge: int | str = 'RISING',
                        stop_edge: int | str = 'FALLING',
                        timeout: float = 10) -> Samples:
        """Get the duration, in seconds, between two edges.

        Args:
            start: The PFI terminal number to use for the start time, t=0.
            stop: The PFI terminal number to use for the stop time, t=dt.
                Can be same as `start` provided that `start_edge` and `stop_edge`
                are different values.
            maximum: The maximum time, in seconds, between the start-stop edges
                that is expected.
            minimum: The minimum time, in seconds, between the start-stop edges
                that is expected.
            nsamples: The number of start-stop samples to acquire.
            start_edge: Specifies on which edge to start each measurement.
                See :class:`~nidaqmx.constants.Edge` for allowed values.
            stop_edge: Specifies on which edge to stop each measurement.
                See :class:`~nidaqmx.constants.Edge` for allowed values.
            timeout: The maximum number of seconds to wait for the task to finish.
                Set to -1 to wait forever.

        Returns:
            The duration(s), in seconds, between the start-stop edges.
        """
        first_edge = self.convert_to_enum(start_edge, Edge, to_upper=True)
        second_edge = self.convert_to_enum(stop_edge, Edge, to_upper=True)
        data = np.empty((nsamples,), dtype=float)
        with NIDAQ.Task() as task:
            channel = task.ci_channels.add_ci_two_edge_sep_chan(
                f'/{self.DEV}/ctr0',
                min_val=minimum,
                max_val=maximum,
                units=TimeUnits.SECONDS,
                first_edge=first_edge,
                second_edge=second_edge
            )
            channel.ci_two_edge_sep_first_term = f'/{self.DEV}/PFI{start}'
            channel.ci_two_edge_sep_second_term = f'/{self.DEV}/PFI{stop}'

            task.timing.cfg_implicit_timing(
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=2*nsamples  # the buffer size
            )

            reader = CounterReader(task.in_stream)
            reader.read_many_sample_double(
                data,
                number_of_samples_per_channel=nsamples,
                timeout=timeout,
            )
            return Samples(data)

    def function_generator(self,
                           channel: int | str,
                           *,
                           amplitude: float = 1,
                           duty: float = 0.5,
                           frequency: float = 1000,
                           offset: float = 0,
                           nsamples: int = 1000,
                           phase: float = 0,
                           preview: bool = False,
                           symmetry: float = 1.0,
                           trigger: Trigger = None,
                           waveform: str = 'sine') -> Task | np.ndarray:
        """Generate a waveform.

        Args:
            channel: The analog-output channel number(s), e.g., channel=0,
                channel='0:1'.
            amplitude: The zero-to-peak amplitude of the waveform to generate
                in volts. Zero and negative values are valid.
            duty: The duty cycle of the square wave. Must be in the interval
                [0, 1]. Only used if `waveform` is ``square``.
            frequency: The frequency of the waveform to generate, in Hz.
            offset: The voltage offset of the waveform to generate.
            nsamples: The number of voltage samples per waveform period.
            phase: The phase of the waveform, in degrees.
            preview: Whether to return a :class:`~numpy.ndarray` of a single
                period of the waveform voltages.
            symmetry: The symmetry of the ramp. Corresponds to the ratio of
                the rising portion of the ramp to the ramp period. For example,
                a symmetry of 0.5 corresponds to a triangle wave. Must be in
                the interval [0, 1]. Only used if `waveform` is ``ramp``.
            trigger: The trigger settings to use. See :meth:`.trigger`.
            waveform: Specifies the kind of waveform to generate. Can be:
                sine, square, ramp, triangle, sawtooth.

        Returns:
            The analog-output task or a single period of the waveform if
            `preview` is True.
        """
        x0 = np.pi * phase / 180.0
        x = np.linspace(x0, 2.0 * np.pi + x0, num=nsamples, endpoint=False)
        match waveform.upper():
            case 'SINE':
                signal = np.sin(x)
            case 'SQUARE':
                signal = square(x, duty=duty)
            case 'RAMP':
                signal = sawtooth(x + np.pi/2.0, width=symmetry)
            case 'TRIANGLE':
                signal = sawtooth(x + np.pi/2.0, width=0.5)
            case 'SAWTOOTH':
                signal = sawtooth(x + np.pi, width=1.0)
            case _:
                raise ValueError(f'Unsupported waveform {waveform!r}')

        voltages = amplitude * signal + offset
        if preview:
            return voltages

        timing = self.timing(finite=False, rate=nsamples * frequency, rising=False)
        return self.analog_out(channel, voltages, timing=timing, trigger=trigger, wait=False)

    def info(self) -> dict[str, int]:
        """Returns the driver information about the NIDAQ board."""
        version = self.connection.version
        return {
            'driver_version_major': version.major_version,
            'driver_version_minor': version.minor_version,
            'driver_version_update': version.update_version,
        }

    def pulse(self,
              pfi: int,
              duration: float,
              *,
              ctr: int = 1,
              delay: float = 0,
              npulses: int = 1,
              state: bool = True,
              timeout: float = -1,
              wait: bool = True) -> Task:
        """Generate one (or more) digital pulse(s).

        If `state` is True then the `pfi` terminal will output 0V
        for `delay` seconds, generate `npulses` +5V pulse(s) (each with a width
        of `duration` seconds) and then remain at 0V when the task is done.

        If `state` is False then the `pfi` terminal will output +5V
        for `delay` seconds, generate `npulses` 0V pulse(s) (each with a width
        of `duration` seconds) and then remain at +5V when the task is done.

        Args:
            pfi: The PFI terminal number to output the pulse(s) from.
            duration: The duration (width) of each pulse, in seconds.
            ctr: The counter terminal number to use for timing.
            delay: The number of seconds to wait before generating the first pulse.
            npulses: The number of pulses to generate.
            state: Whether to generate HIGH or LOW pulse(s).
            timeout: The maximum number of seconds to wait for the task to finish.
                Set to -1 to wait forever.
            wait: Whether to wait for the task to finish. If enabled then also
                closes the task when it is finished.

        Returns:
            The task.

        Examples:

            .. suppress-unresolved-reference-daq:
                >>> daq = NIDAQ()

            Generate a single HIGH pulse for 0.1 seconds from PFI2

            >>> daq.pulse(2, 0.1)
        """
        if state:
            idle_state, state_str = Level.LOW, 'HIGH'
        else:
            idle_state, state_str = Level.HIGH, 'LOW'

        task = NIDAQ.Task()
        self._tasks.append(task)
        co_channel = task.co_channels.add_co_pulse_chan_time(
            f'/{self.DEV}/ctr{ctr}',
            high_time=duration,
            low_time=duration,
            idle_state=idle_state,
            initial_delay=delay,
        )
        co_channel.co_pulse_term = f'/{self.DEV}/PFI{pfi}'
        if npulses > 1:
            task.timing.cfg_implicit_timing(
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=npulses,
            )
        self.logger.info(f'{self.alias!r} generating {npulses} {state_str} '
                         f'pulse(s) [duration={duration}, delay={delay}]')
        task.start()
        if wait:
            try:
                task.wait_until_done(timeout=timeout)
            finally:
                task.close()
                self._tasks.remove(task)
        return task

    def storm(self, camera: int, sequence: dict) -> Task:
        """Create a task for STORM/PALM acquisition.

        For example, for a 4-frame sequence controlling two lasers::

            sequence = {
              'port0/line0': [True, False, False, False],
              'port0/line1': [False, True, True, True]
            }

        Args:
            camera: The PFI terminal number that the camera's Fire signal
                is connect to.
            sequence: The keys are the digital-output terminals that turn the
                laser pulses on/off and the values represent the state of the
                lasers in each frame.

        Returns:
            The task.
        """
        lines = ','.join(f'/{self.DEV}/{key}' for key in sequence)
        data = [value for value in sequence.values()]
        timing = self.timing(
            rate=10000,  # maximum expected rate of the camera's Fire signal
            finite=False,
            rising=False,
            pfi=camera
        )
        timing.samples_per_channel = len(data[0])
        return self.digital_out(lines, data, timing=timing, wait=False)

    def timing(self,
               *,
               finite: bool = True,
               pfi: int = None,
               rate: float = 1000,
               rising: bool = True) -> Timing:
        """Configure and return the sample clock to add to a task.

        Args:
            finite: Whether to acquire/generate a continuous or a finite number
                of samples.
            pfi: The PFI terminal number to use as the external sample clock.
                If not specified then uses the default onboard clock of the device.
            rate: The sampling rate in Hz. If you specify an external sample clock
                (i.e., a value for `pfi`) then set the `rate` to be the maximum
                expected rate of the external clock.
            rising: Whether to acquire/generate samples on the rising or falling
                edge of the sample clock.

        Returns:
            The timing instance.
        """
        source = '' if pfi is None else f'/{self.DEV}/PFI{pfi}'
        return Timing(finite=finite, source=source, rate=rate, rising=rising)

    def trigger(self,
                source: int | str,
                *,
                delay: float = 0,
                hysteresis: float = 0,
                level: float = None,
                retriggerable: bool = False,
                rising: bool = True) -> Trigger:
        """Configure and return a trigger to add to a task.

        Args:
            source: Either a PFI or an AI channel number or a
                `terminal name <https://www.ni.com/docs/en-US/bundle/ni-daqmx/page/mxcncpts/termnames.html>`_
                to use as the trigger source.
            delay: The time (in seconds) between the trigger event and when to
                acquire/generate samples. Can be < 0 to acquire/generate samples
                before the trigger event (only if the NIDAQ task supports it).
            hysteresis: A hysteresis level (in volts). Only applicable for an
                analog trigger.
            level: The voltage level to use for the trigger signal. Whether this
                value is set decides whether the trigger source is from a digital
                or an analog channel. If None then `channel` refers to a PFI
                channel (a digital trigger), otherwise, `channel` refers to an
                AI channel (an analog trigger).
            retriggerable: Whether the task can be retriggered.
            rising: Whether to use the rising or falling edge(slope) of the
                digital(analog) trigger signal.

        Returns:
            The trigger instance.
        """
        if not isinstance(source, str):
            if level is None:
                source = f'/{self.DEV}/PFI{source}'
            else:
                source = f'/{self.DEV}/APFI{source}'
        if not source.startswith(f'/{self.DEV}/'):
            source = f'/{self.DEV}/{source}'
        return Trigger(source=source, delay=delay, hysteresis=hysteresis,
                       level=level, retriggerable=retriggerable, rising=rising)

    @staticmethod
    def time_array(n: int | np.ndarray, dt: float) -> np.ndarray:
        """Create an array based on a sampling time.

        Args:
            n: The number of samples. If an array of voltage samples is
                passed in, then the returned time array will have the
                appropriate size.
            dt: The sampling time.

        Returns:
            The array (e.g., [0, dt, 2*dt, 3*dt, ..., (n-1)*dt]).
        """
        num = n.shape[-1] if isinstance(n, np.ndarray) else n
        return np.linspace(0., dt*num, num=num, endpoint=False, dtype=float)

    @staticmethod
    def wait_until_done(*tasks: Task, timeout: float = 10.0) -> None:
        """Wait until all tasks are done and then close each task.

        Args:
            tasks: The task(s) to wait for.
            timeout: The number of seconds to wait for each task to finish.
                Set to -1 to wait forever.
        """
        for task in tasks:
            task.wait_until_done(timeout=timeout)
            task.close()

    def _maybe_set_timing_and_trigger(self,
                                      task: Task,
                                      timing: Timing,
                                      trigger: Trigger,
                                      task_type: str) -> None:
        """(Maybe) Configure timing and triggering for a task."""
        if timing.samples_per_channel > 1 or \
                timing.sample_mode == AcquisitionType.CONTINUOUS or \
                trigger is not None:
            self.logger.info(f'{self.alias!r} set {timing} for the {task_type} task')
            timing.add_to(task)

        if trigger is not None:
            self.logger.info(f'{self.alias!r} set {trigger} for the {task_type} task')
            trigger.add_to(task)

    def _generate_digital_lines(self, lines: int | str, port: int) -> str:
        if isinstance(lines, str) and lines.startswith(f'/{self.DEV}'):
            return lines
        return f'/{self.DEV}/port{port}/line{lines}'
