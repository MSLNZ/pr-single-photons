"""
Communicate with a DAQ from National Instruments.
"""
from typing import (
    Union,
    List,
    Tuple,
)

import numpy as np
from nidaqmx.constants import (
    Edge,
    CountDirection,
    AcquisitionType,
    TimeUnits,
    TriggerType,
    Level,
    LineGrouping,
    TerminalConfiguration,
)
from msl.qt import Signal

from . import (
    BaseEquipment,
    equipment,
)
from ..utils import ave_std


@equipment(manufacturer=r'National Instruments', model=r'USB-6361')
class NIDAQ(BaseEquipment):

    Edge = Edge
    CountDirection = CountDirection
    AcquisitionType = AcquisitionType
    TimeUnits = TimeUnits
    TriggerType = TriggerType
    Level = Level
    LineGrouping = LineGrouping
    TerminalConfiguration = TerminalConfiguration

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
        self.Task = self.connection.Task

    def analog_in(self,
                  channel: Union[int, str], *,
                  nsamples: int = 1,
                  minimum: float = -10,
                  maximum: float = 10,
                  terminal: int = None,
                  rate: float = 1000,
                  duration: float = None) -> Tuple[np.ndarray, float]:
        """Read the voltage(s) of analog input channel(s).

        Parameters
        ----------
        channel : :class:`int` or :class:`str`
            The channel number(s) (e.g., channel=0, channel='0:7').
        nsamples : :class:`int`, optional
            The number of samples per channel to read. If a `duration` is
            also specified then that value is used instead of `nsamples`.
        minimum : :class:`float`, optional
            The minimum voltage that is expected to be measured.
        maximum : :class:`float`, optional
            The maximum voltage that is expected to be measured.
        terminal : :class:`int`, optional
            Specifies the input terminal configuration for the channel,
            see :class:`~nidaqmx.constants.TerminalConfiguration`
        rate : :class:`float`, optional
            The sample rate in Hz.
        duration : :class:`float`, optional
            The number of seconds to read voltages for. If specified then
            this value is used instead of `nsamples`.

        Returns
        -------
        :class:`numpy.ndarray`
            The voltage(s) of the requested analog input channel(s).
        :class:`float`
            The time interval between samples, i.e., dt.

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
        if terminal is None:
            terminal = TerminalConfiguration.BAL_DIFF
        if duration is not None:
            nsamples = round(duration * rate)

        ai = f'{self.DEV}/ai{channel}'
        with self.Task() as task:
            task.ai_channels.add_ai_voltage_chan(
                ai,
                terminal_config=terminal,
                min_val=minimum,
                max_val=maximum,
            )
            if nsamples > 1:
                task.timing.cfg_samp_clk_timing(rate, samps_per_chan=nsamples)
            data = task.read(number_of_samples_per_channel=nsamples)
            return np.asarray(data), 1.0/task.timing.samp_clk_rate

    def analog_out(self,
                   channel: Union[int, str],
                   voltage: Union[float, List[float], np.ndarray],
                   rate: float = 1000) -> int:
        """Write the voltage(s) to analog output channel(s).

        Parameters
        ----------
        channel : :class:`int` or :class:`str`
            The channel number(s) (e.g., channel=0, channel='0:1').
        voltage : :class:`float`, :class:`list` or :class:`~numpy.ndarray`
            The voltage(s) to output.
        rate : :class:`float`, optional
            The sample rate in Hz.

        Returns
        -------
        :class:`int`
            The actual number of values (per channel) that were successfully written.

        Examples
        --------
        Write to a single analog output channel
        >>> analog_out(0, 1.123)
        1

        Write to multiple analog output channels
        >>> analog_out('0:1', [0.2, -1.2])
        1
        >>> analog_out('0:1', [[0.2, 0.1, 0.], [-0.1, 0., 0.1]])
        3
        """
        if isinstance(voltage, (float, int)):
            array = np.array([voltage], dtype=float)
        else:
            array = np.asarray(voltage)

        min_val = np.min(array)
        max_val = np.max(array)
        if max_val == min_val:
            max_val += 0.1

        ao = f'{self.DEV}/ao{channel}'
        with self.Task() as task:
            task.ao_channels.add_ao_voltage_chan(ao, min_val=min_val, max_val=max_val)

            samps_per_chan = array.size // len(task.channels.channel_names)
            if samps_per_chan > 1:
                task.timing.cfg_samp_clk_timing(rate, samps_per_chan=samps_per_chan)

            if samps_per_chan == 1:
                self.logger.info(f'{self.alias!r} set {ao} to {voltage}')
            elif array.size <= 100:
                arr_str = np.array2string(array, max_line_width=1000, separator=',')
                arr_str = arr_str.replace('\n', '')
                self.logger.info(f'{self.alias!r} set {ao} at rate {rate} Hz to {arr_str}')
            else:
                self.logger.info(f'{self.alias!r} set {ao} at rate {rate} Hz with {array.shape} samples')

            n = task.write(array, auto_start=True)
            task.wait_until_done()
            return n

    def count_edges(self,
                    duration: float, *,
                    rising: bool = True,
                    pfi: int = 0,
                    repeat: int = 1) -> tuple:
        """Count the number of edges per second.

        Parameters
        ----------
        duration : :class:`float`
            The number of seconds to count edges for.
        rising : :class:`bool`, optional
            If :data:`True` then count rising edges, otherwise count falling edges.
        pfi : :class:`int`, optional
            The ``PFI`` terminal number that has the input signal connected to it.
        repeat : :class:`int`, optional
            The number of times to repeat the measurement.

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
                   port: Union[int, str],
                   line: Union[int, str]) -> Union[bool, List[bool]]:
        """Read the state of digital input channel(s).

        Parameters
        ----------
        port : :class:`int` or :class:`str`
            The port number.
        line : :class:`int` or :class:`str`
            The line number(s) (e.g., line=1, line='0:7').

        Returns
        -------
         :class:`bool` or :class:`list` of :class:`bool`
            Whether the requested digital input channel(s) are HIGH or LOW.

        Examples
        --------
        Read the state of a single digital input channel
        >>> digital_in(1, 1)
        False

        Read the state of multiple digital input channels
        >>> digital_in(1, '0:7')
        [False, False, True, False, False, False, False, True]
        """
        lines = f'{self.DEV}/port{port}/line{line}'
        with self.Task() as task:
            task.di_channels.add_di_chan(lines, line_grouping=LineGrouping.CHAN_PER_LINE)
            return task.read()

    def digital_out(self,
                    state: bool,
                    port: Union[int, str],
                    line: Union[int, str]) -> None:
        """Write the state of digital output channel(s).

        Parameters
        ----------
        state : :class:`bool` or :class:`list` of :class:`bool`
            Whether to set the specified digital output channel(s) HIGH or LOW.
        port : :class:`int` or :class:`str`
            The port number.
        line : :class:`int` or :class:`str`
            The line number(s).

        Examples
        --------
        Set the state of a single digital output channel
        >>> digital_out(True, 1, 1)

        Set multiple digital output channels to be in the same state
        >>> digital_out(False, 1, '0:7')

        Set the state of multiple digital output channels
        >>> digital_out([False, True, True], 1, '2:4')
        """
        lines = f'{self.DEV}/port{port}/line{line}'
        with self.Task() as task:
            task.do_channels.add_do_chan(lines, line_grouping=LineGrouping.CHAN_PER_LINE)
            num_channels = len(task.channels.channel_names)
            if isinstance(state, bool) and num_channels > 1:
                state = [state] * num_channels
            assert task.write(state) == 1  # check that it was successful
            task.wait_until_done()
            self.logger.info(f'{self.alias!r} set {lines} to {state}')

    def digital_out_read(self,
                         port: Union[int, str],
                         line: Union[int, str]) -> Union[bool, List[bool]]:
        """Read the state of digital output channel(s).

        Parameters
        ----------
        port : :class:`int` or :class:`str`
            The port number.
        line : :class:`int` or :class:`str`
            The line number(s) (e.g., line=1, line='0:7').

        Returns
        -------
         :class:`bool` or :class:`list` of :class:`bool`
            Whether the requested digital output channel(s) are HIGH or LOW.

        Examples
        --------
        Read the state of a single digital output channel
        >>> digital_out_read(1, 1)
        True

        Read the state of multiple digital output channels
        >>> digital_out_read(1, '0:7')
        [False, True, True, False, True, False, False, False]
        """
        lines = f'{self.DEV}/port{port}/line{line}'
        with self.Task() as task:
            task.do_channels.add_do_chan(lines, line_grouping=LineGrouping.CHAN_PER_LINE)
            return task.read()
