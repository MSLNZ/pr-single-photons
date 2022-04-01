"""
Communicate with a DAQ from National Instruments.
"""
import warnings
from typing import (
    Union,
    List,
    Tuple,
)

import numpy as np
import nidaqmx.constants
from msl.qt import Signal

from . import (
    BaseEquipment,
    equipment,
)
from ..utils import ave_std


class Trigger(object):

    def __init__(self,
                 channel: int,
                 device_name: str, *,
                 delay: float = 0,
                 hysteresis: float = 0,
                 level: float = None,
                 rising: bool = True):
        """Configure a trigger event.

        Parameters
        ----------
        channel : :class:`int` or :class:`str`
            Either a PFI or an AI channel number to use as the trigger source.
        device_name : :class:`str`
            The name of the device (e.g., Dev1).
        delay : :class:`float`, optional
            The time (in seconds) between the trigger event and when to
            acquire/generate samples. Can be < 0 to acquire/generate samples
            before the trigger event (only if the NIDAQ task supports it).
        hysteresis : :class:`float`, optional
            Specifies a hysteresis level in the units of the measurement.
            Only applicable for an analog trigger.
        level : :class:`float`, optional
            The voltage level to use for the trigger signal. Whether this value
            is set decides whether the trigger source is from a digital or an
            analog channel. If :data`None` then `channel` refers to a PFI
            channel (a digital trigger). Otherwise, `channel` refers to an
            AI channel (an analog trigger).
        rising : :class:`bool`, optional
            Whether to use the rising or falling edge(slope) of the
            digital(analog) trigger signal.
        """
        self._delay = delay
        self._level = level
        self._hysteresis = hysteresis
        if level is None:  # digital trigger
            self._kwargs = {
                'trigger_source': f'/{device_name}/PFI{channel}',
                'trigger_edge': NIDAQ.Edge.RISING if rising else NIDAQ.Edge.FALLING
            }
        else:  # analog trigger
            self._kwargs = {
                'trigger_source': f'/{device_name}/APFI{channel}',
                'trigger_slope': NIDAQ.Slope.RISING if rising else NIDAQ.Slope.FALLING,
                'trigger_level': level
            }

    def __repr__(self):
        kwargs = ', '.join(f'{k[8:]}={v}' for k, v in self._kwargs.items())
        rep = f'Trigger<{kwargs}>'
        if self._delay != 0:
            rep = rep.rstrip('>') + f', delay={self._delay}>'
        if self._hysteresis != 0:
            rep = rep.rstrip('>') + f', hysteresis={self._hysteresis}>'
        return rep

    def add(self, task: nidaqmx.Task) -> None:
        """Add this trigger to a task.

        Parameters
        ----------
        task : :class:`~nidaqmx.Task`
            The task to add the trigger event to.
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
            return

        t = task.triggers.start_trigger
        if self._level is None:
            t.cfg_dig_edge_start_trig(**self._kwargs)
        else:
            t.cfg_anlg_edge_start_trig(**self._kwargs)
            if self._hysteresis != 0:
                t.anlg_edge_hyst = self._hysteresis

        if self._delay > 0:
            t.delay_units = NIDAQ.DigitalWidthUnits.SECONDS
            t.delay = self._delay


@equipment(manufacturer=r'National Instruments', model=r'USB-6361')
class NIDAQ(BaseEquipment):

    Task = nidaqmx.Task

    WAIT_INFINITELY = nidaqmx.constants.WAIT_INFINITELY
    Edge = nidaqmx.constants.Edge
    Slope = nidaqmx.constants.Slope
    DigitalWidthUnits = nidaqmx.constants.DigitalWidthUnits
    CountDirection = nidaqmx.constants.CountDirection
    AcquisitionType = nidaqmx.constants.AcquisitionType
    TriggerType = nidaqmx.constants.TriggerType
    Level = nidaqmx.constants.Level
    LineGrouping = nidaqmx.constants.LineGrouping
    TerminalConfiguration = nidaqmx.constants.TerminalConfiguration

    counts_changed = Signal(float, float)  # (average, stdev)

    def __init__(self, app, record, *, demo=None):
        """Communicate with a DAQ from National Instruments.

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
        super(NIDAQ, self).__init__(app, record, demo=demo)
        self.DEV = record.connection.address
        self._tasks = []

    def analog_in(self,
                  channel: Union[int, str], *,
                  config: int = None,
                  duration: float = None,
                  maximum: float = 10,
                  minimum: float = -10,
                  nsamples: int = 1,
                  rate: float = 1000,
                  timeout: float = 10,
                  trigger: Trigger = None) -> Tuple[np.ndarray, float]:
        """Read the voltage(s) of the analog-input channel(s).

        Parameters
        ----------
        channel : :class:`int` or :class:`str`
            The channel number(s) (e.g., channel=0, channel='0:7').
        config : :class:`int`, optional
            Specifies the input terminal configuration for the channel,
            see :class:`~nidaqmx.constants.TerminalConfiguration`.
        duration : :class:`float`, optional
            The number of seconds to read voltages for. If specified then
            this value is used instead of `nsamples`.
        maximum : :class:`float`, optional
            The maximum voltage that is expected to be measured.
        minimum : :class:`float`, optional
            The minimum voltage that is expected to be measured.
        nsamples : :class:`int`, optional
            The number of samples per channel to read. If a `duration` is
            also specified then that value is used instead of `nsamples`.
        rate : :class:`float`, optional
            The sample rate in Hz.
        timeout : :class:`float`, optional
            The maximum number of seconds to wait for the task to finish.
            Set to -1 to wait forever.
        trigger : :class:`.Trigger`, optional
            The trigger settings to use. See :meth:`.trigger`.

        Returns
        -------
        :class:`numpy.ndarray`
            The voltage(s) of the requested analog-input channel(s).
        :class:`float`
            The time interval between samples (i.e., dt).

        Examples
        --------
        Read the value of a single analog input channel
        >>> analog_in(0)
        (array([-0.48746041]), 0.001)
        >>> analog_in(0, nsamples=5)
        (array([-0.44944232, -0.45040888, -0.45137544, -0.45556387, -0.45298637]), 0.001)

        Read the values of multiple analog input channels
        >>> analog_in('0:3')
        (array([[0.29932077],
               [2.40384965],
               [0.94627278],
               [0.389211  ]]), 0.001)
        >>> analog_in('0:3', nsamples=4)
        (array([[ 0.03512726,  0.03770475,  0.03867132,  0.03512726],
               [-0.1675285 ,  0.17527869, -0.17171693,  0.17237901],
               [ 0.08248878,  0.12243999,  0.00741916,  0.07991128],
               [ 0.08861033,  0.09859814,  0.05832474,  0.06831254]]), 0.001)
       """
        if config is None:
            config = NIDAQ.TerminalConfiguration.BAL_DIFF
        if duration is not None:
            nsamples = round(duration * rate)

        with self.Task() as task:
            task.ai_channels.add_ai_voltage_chan(
                f'/{self.DEV}/ai{channel}',
                terminal_config=config,
                min_val=minimum,
                max_val=maximum,
            )
            if nsamples > 1 or trigger is not None:
                self.logger.info(f'{self.alias!r} set analog-input timing to {rate} Hz')
                task.timing.cfg_samp_clk_timing(rate, samps_per_chan=nsamples)
            if trigger is not None:
                self.logger.info(f'{self.alias!r} add {trigger} to analog-input task')
                trigger.add(task)
            data = task.read(number_of_samples_per_channel=nsamples, timeout=timeout)
            return np.asarray(data), 1.0/task.timing.samp_clk_rate

    def analog_out(self,
                   channel: Union[int, str],
                   voltage: Union[float, List[float], List[List[float]], np.ndarray], *,
                   rate: float = 1000,
                   timeout: float = 10,
                   trigger: Trigger = None,
                   wait: bool = True) -> nidaqmx.Task:
        """Write the voltage(s) to the analog-output channel(s).

        Parameters
        ----------
        channel : :class:`int` or :class:`str`
            The channel number(s) (e.g., channel=0, channel='0:1').
        voltage : :class:`float`, :class:`list` or :class:`~numpy.ndarray`
            The voltage(s) to output.
        rate : :class:`float`, optional
            The sample rate in Hz.
        timeout : :class:`float`, optional
            The maximum number of seconds to wait for the task to finish.
            Set to -1 to wait forever.
        trigger : :class:`.Trigger`, optional
            The trigger settings to use. See :meth:`.trigger`.
        wait : :class:`bool`, optional
            Whether to wait for the task to finish. If enabled then also
            closes the task when it is finished.

        Returns
        -------
        :class:`~nidaqmx.Task`
            The analog-output task.

        Examples
        --------
        Write to a single analog-output channel
        >>> analog_out(0, 1.123)

        Write to multiple analog-output channels
        >>> analog_out('0:1', [0.2, -1.2])
        >>> analog_out('0:1', [[0.2, 0.1, 0.], [-0.1, 0., 0.1]])
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
        task = self.Task()
        self._tasks.append(task)
        task.ao_channels.add_ao_voltage_chan(ao, min_val=min_val, max_val=max_val)

        samps_per_chan = array.size // task.number_of_channels
        if samps_per_chan > 1 or trigger is not None:
            self.logger.info(f'{self.alias!r} set analog-output timing to {rate} Hz '
                             f'with {samps_per_chan} samples/channel')
            task.timing.cfg_samp_clk_timing(rate, samps_per_chan=samps_per_chan)

        if trigger is not None:
            self.logger.info(f'{self.alias!r} add {trigger} to analog-output task')
            trigger.add(task)

        if array.size <= 25:
            a2s = np.array2string(array, max_line_width=1000, separator=',')
            arr_str = a2s.replace('\n', '')
            self.logger.info(f'{self.alias!r} set {ao} to {arr_str}')
        else:
            self.logger.info(f'{self.alias!r} set {ao} with {array.shape} samples')

        written = task.write(array, auto_start=True, timeout=timeout)
        assert written == samps_per_chan
        if wait:
            try:
                task.wait_until_done(timeout=timeout)
            finally:
                task.close()
                self._tasks.remove(task)
        return task

    def close_all_tasks(self) -> None:
        """Close all tasks that have been created."""
        for task in self._tasks:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', ResourceWarning)
                task.close()
        self._tasks.clear()

    def count_edges(self,
                    pfi: int,
                    duration: float, *,
                    repeat: int = 1,
                    rising: bool = True) -> Tuple[float, float]:
        """Count the number of edges per second.

        Parameters
        ----------
        pfi : :class:`int`
            The PFI terminal number that has the input signal connected to it.
        duration : :class:`float`
            The number of seconds to count edges for.
        repeat : :class:`int`, optional
            The number of times to repeat the measurement.
        rising : :class:`bool`, optional
            If :data:`True` then count rising edges, otherwise count falling edges.

        Returns
        -------
        :class:`float`
            The average number of counts per second that were detected.
        :class:`float`
            The standard deviation.
        """
        cps = np.full((repeat,), np.nan, dtype=np.float)
        duration = float(duration)

        # using a Counter Output task as a gate for the Counter Input task
        edge = self.Edge.RISING if rising else self.Edge.FALLING

        # add a small delay to make sure that the CI task has started and is waiting for the CO gate pulse
        co_task_delay = 0.01

        for index in range(repeat):
            with self.Task() as co_task:
                co_task.co_channels.add_co_pulse_chan_time(
                    # if the channel is changed then also update Ctr1InternalOutput below
                    f'/{self.DEV}/ctr1',
                    high_time=duration,
                    # The value of low_time shouldn't matter and that is why it is made to be large.
                    # It doesn't matter since Implicit Timing is FINITE with 1 sample and
                    # because idle_state=LOW the CO task finishes after high_time seconds.
                    low_time=1000.,
                    idle_state=self.Level.LOW,
                    initial_delay=co_task_delay,
                )
                co_task.timing.cfg_implicit_timing(
                    sample_mode=self.AcquisitionType.FINITE,
                    samps_per_chan=1,
                )
                with self.Task() as ci_task:
                    # create the Counter Input channel
                    channel = ci_task.ci_channels.add_ci_count_edges_chan(
                        f'/{self.DEV}/ctr0',
                        edge=edge,
                        initial_count=0,
                        count_direction=self.CountDirection.COUNT_UP
                    )
                    # let the channel know which PFI port has the input signal attached to it
                    channel.ci_count_edges_term = f'/{self.DEV}/PFI{pfi}'
                    # only increment the value when the ctr1 output counter is TTL high
                    ci_task.triggers.pause_trigger.trig_type = self.TriggerType.DIGITAL_LEVEL
                    ci_task.triggers.pause_trigger.dig_lvl_when = self.Level.LOW
                    # the digital level source is internally connected to the CO task output -> ctr1
                    ci_task.triggers.pause_trigger.dig_lvl_src = f'/{self.DEV}/Ctr1InternalOutput'

                    # must start the CI task before the CO task
                    ci_task.start()
                    co_task.start()
                    co_task.wait_until_done(timeout=duration + co_task_delay + 1.0)
                    count = channel.ci_count
                    self.logger.info(f'{self.alias!r} counted {count} {edge.name} edges in {duration} second(s)')
                    cps[index] = count / duration

        ave, stdev = ave_std(cps)
        self.counts_changed.emit(ave, stdev)
        self.emit_notification(ave, stdev)
        return ave, stdev

    def digital_in(self,
                   line: Union[int, str], *,
                   port: int = 1) -> Union[bool, List[bool]]:
        """Read the state of the digital-input channel(s).

        Parameters
        ----------
        line : :class:`int` or :class:`str`
            The line number(s) (e.g., line=1, line='0:7').
        port : :class:`int`, optional
            The port number.

        Returns
        -------
         :class:`bool` or :class:`list` of :class:`bool`
            Whether the requested digital input channel(s) are HIGH or LOW.

        Examples
        --------
        Read the state of a single digital-input channel (P1.0)
        >>> digital_in(0)
        False

        Read the state of a single digital-input channel (P0.2)
        >>> digital_in(2, port=0)
        True

        Read the state of multiple digital-input channels (P1.0-7)
        >>> digital_in('0:7')
        [False, False, True, False, False, False, False, True]
        """
        with self.Task() as task:
            task.di_channels.add_di_chan(
                f'/{self.DEV}/port{port}/line{line}',
                line_grouping=NIDAQ.LineGrouping.CHAN_PER_LINE
            )
            return task.read()

    def digital_out(self,
                    line: Union[int, str],
                    state: Union[bool, List[bool], List[List[bool]]], *,
                    port: int = 1,
                    rate: float = 1000,
                    timeout: float = 10,
                    wait: bool = True) -> nidaqmx.Task:
        """Write the state of digital-output channels(s).

        Parameters
        ----------
        line : :class:`int` or :class:`str`
            The line number(s) (e.g., line=1, line='0:7').
        state : :class:`bool` or :class:`list` of :class:`bool`
            Whether to set the specified line(s) to HIGH or LOW.
        port : :class:`int`, optional
            The port number.
        rate : :class:`float`, optional
            The sample rate in Hz. The rate parameter is used when multiple
            samples per channel are specfied. The required lines must support
            buffered operations otherwise an excpetion will be raised. For a
            NI USB-6361 device, the available buffered lines are in port=0.
        timeout : :class:`float`, optional
            The maximum number of seconds to wait for the task to finish.
            Set to -1 to wait forever.
        wait : :class:`bool`, optional
            Whether to wait for the task to finish. If enabled then also
            closes the task when it is finished.

        Returns
        -------
        :class:`~nidaqmx.Task`
            The digital-output task.

        Examples
        --------
        Set the state of a single digital-output channel (P1.0)
        >>> digital_out(0, True)

        Set multiple digital-output channels to be in the same state (P2.0-7)
        >>> digital_out('0:7', False, port=2)

        Set the state of multiple digital-output channels (P1.2-4)
        >>> digital_out('2:4', [False, True, True])

        Set an output sequence on a single channel (P0.0). Each state is written every 0.1 ms
        >>> digital_out(0, [True, False, False, True, False, False, False, True, True, False], port=0, rate=10)
        """
        lines = f'/{self.DEV}/port{port}/line{line}'
        task = self.Task()
        self._tasks.append(task)
        task.do_channels.add_do_chan(lines, line_grouping=NIDAQ.LineGrouping.CHAN_PER_LINE)

        samps_per_chan = 1
        num_channels = task.number_of_channels
        if isinstance(state, bool):
            if num_channels > 1:
                state = [state] * num_channels
        elif num_channels == 1:
            samps_per_chan = len(state)
        elif isinstance(state[0], (list, tuple)):
            samps_per_chan = len(state[0])

        if samps_per_chan > 1:
            self.logger.info(f'{self.alias!r} set digital-output timing to {rate} Hz '
                             f'with {samps_per_chan} samples/channel')
            task.timing.cfg_samp_clk_timing(rate, samps_per_chan=samps_per_chan)

        self.logger.info(f'{self.alias!r} set {lines} to {state}')
        written = task.write(state, auto_start=True, timeout=timeout)
        assert written == samps_per_chan
        if wait:
            try:
                task.wait_until_done(timeout=timeout)
            finally:
                task.close()
                self._tasks.remove(task)
        return task

    def digital_out_read(self,
                         line: Union[int, str], *,
                         port: int = 1) -> Union[bool, List[bool]]:
        """Read the state of digital-output channel(s).

        Parameters
        ----------
        line : :class:`int` or :class:`str`
            The line number(s) (e.g., line=1, line='0:7').
        port : :class:`int`, optional
            The port number.

        Returns
        -------
         :class:`bool` or :class:`list` of :class:`bool`
            Whether the requested digital-output channel(s) are HIGH or LOW.

        Examples
        --------
        Read the state of a single digital-output channel (P1.0)
        >>> digital_out_read(0)
        True

        Read the state of a single digital-output channel (P0.5)
        >>> digital_out_read(5, port=0)
        False

        Read the state of multiple digital-output channels (P1.0-7)
        >>> digital_out_read('0:7')
        [False, True, True, False, True, False, False, False]
        """
        with self.Task() as task:
            task.do_channels.add_do_chan(
                f'/{self.DEV}/port{port}/line{line}',
                line_grouping=NIDAQ.LineGrouping.CHAN_PER_LINE
            )
            return task.read()

    def pulse(self,
              pfi: int,
              duration: float, *,
              ctr: int = 1,
              delay: float = 0,
              npulses: int = 1,
              state: bool = True,
              timeout: float = 10,
              wait: bool = True) -> nidaqmx.Task:
        """Generate one (or more) digital pulse(s).

        If `state` is :data:`True` then the `pfi` terminal will output 0V
        for `delay` seconds, generate `npulses` +5V pulse(s) (each with a width
        of `duration` seconds) and then remain at 0V when the task is done.

        If `state` is :data:`False` then the `pfi` terminal will output +5V
        for `delay` seconds, generate `npulses` 0V pulse(s) (each with a width
        of `duration` seconds) and then remain at +5V when the task is done.

        Parameters
        ----------
        pfi : :class:`int`
            The PFI terminal number to output the pulse(s) from.
        duration : :class:`float`
            The duration (width) of each pulse, in seconds.
        ctr : :class:`int`, optional
            The counter terminal number to use for timing.
        delay : :class:`float`, optional
            The number of seconds to wait before generating the first pulse.
        npulses : :class:`int`, optional
            The number of pulses to generate.
        state : :class:`bool`, optional
            Whether to generate HIGH or LOW pulse(s).
        timeout : :class:`float`, optional
            The maximum number of seconds to wait for the task to finish.
            Set to -1 to wait forever.
        wait : :class:`bool`, optional
            Whether to wait for the task to finish. If enabled then also
            closes the task when it is finished.

        Returns
        -------
        :class:`~nidaqmx.Task`
            The task.

        Examples
        --------
        Generate a single HIGH pulse for 0.1 seconds from PFI2
        >>> pulse(2, 0.1)
        """
        if state:
            idle_state, state_str = self.Level.LOW, 'HIGH'
        else:
            idle_state, state_str = self.Level.HIGH, 'LOW'

        task = self.Task()
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
                sample_mode=self.AcquisitionType.FINITE,
                samps_per_chan=npulses,
            )
        self.logger.info(f'{self.alias!r} generating {npulses} {state_str} pulse(s) '
                         f'after {delay} second(s)')
        task.start()
        if wait:
            try:
                task.wait_until_done(timeout=timeout)
            finally:
                task.close()
                self._tasks.remove(task)
        return task

    def trigger(self, channel: int, **kwargs) -> Trigger:
        """Create a new :class:`.Trigger` instance.

        Parameters
        ----------
        channel : :class:`int`
            Either a PFI or an AI channel number to use as the trigger source.
        kwargs
            All additional keyword arguments are passed to :class:`.Trigger`.

        Returns
        -------
        :class:`.Trigger`
            The trigger settings.
        """
        return Trigger(channel, self.DEV, **kwargs)

    @staticmethod
    def time_array(dt: float, n: Union[int, np.ndarray]) -> np.ndarray:
        """Create an array based on a sampling time.

        Parameters
        ----------
        dt : :class:`float`
            The sampling time.
        n : :class:`int` or :class:`numpy.ndarray`
            The number of samples. If a :class:`numpy.ndarray` then
            the `size` attribute is used to determine the number of samples.

        Returns
        -------
        :class:`numpy.ndarray`
            The array (e.g., [0, dt, 2*dt, 3*dt, ..., (n-1)*dt]).
        """
        num = n if isinstance(n, int) else n.size
        return np.linspace(0., dt*num, num=num, endpoint=False, dtype=float)

    @staticmethod
    def wait_until_done(*tasks: nidaqmx.Task, timeout: float = 10.0) -> None:
        """Wait until all tasks are done and then close each task.

        Parameters
        ----------
        tasks : :class:`nidaqmx.Task`
            The task(s) to wait for.
        timeout : :class:`float`, optional
            The number of seconds to wait for each task to finish.
            Set to -1 to wait forever.
        """
        for task in tasks:
            task.wait_until_done(timeout=timeout)
            task.close()
