"""
An oscilloscope from Rigol.
"""
from typing import Literal

import numpy as np

from .base import equipment
from .oscilloscope import Oscilloscope


@equipment(manufacturer=r'Rigol', model=r'DS\d{4}Z?')
class RigolOscilloscope(Oscilloscope):
    """An oscilloscope from Rigol."""

    def _check(self, command: str) -> None:
        """Write the command and then check for errors."""
        reply = self.connection.query(f'{command};:SYSTEM:ERROR?')
        if not reply.startswith('0,'):
            self.raise_exception(reply)

    def _configure(self, command: str) -> None:
        """Log the configuration command, write the command and then check for errors."""
        self.logger.info(f'configure {self.alias!r} using {command!r}')
        self._check(command)

    def clear(self) -> None:
        """Clears the event registers and the error queue."""
        self.logger.info(f'clear {self.alias!r}')
        self._check('*CLS')

    def configure_channel(self,
                          channel: int,
                          *,
                          bw_limit: bool = False,
                          coupling: Literal['DC', 'AC', 'GND'] = 'DC',
                          enable: bool = True,
                          invert: bool = False,
                          offset: float = 0,
                          probe: float = 1,
                          scale: float = 1) -> None:
        """Configure a channel.

        Args:
            channel: The channel number.
            bw_limit: Whether to enable or disable the bandwidth limit.
            coupling: The coupling mode (either DC, AC or GND).
            enable: Whether to enable or disable the channel.
            invert: Whether to invert the waveform.
            offset: The vertical offset [Volts].
            probe: The probe ratio. Only discrete values are allowed (see manual).
            scale: The vertical scale [Volts/div].
        """
        bwl = '20M' if bw_limit else 'OFF'
        display = 'ON' if enable else 'OFF'
        invert = 'ON' if invert else 'OFF'
        self._configure(
            f':CHANNEL{channel}:BWLIMIT {bwl};'
            f':CHANNEL{channel}:COUPLING {coupling};'
            f':CHANNEL{channel}:DISPLAY {display};'
            f':CHANNEL{channel}:INVERT {invert};'
            f':CHANNEL{channel}:PROBE {probe};'
            f':CHANNEL{channel}:SCALE {scale};'
            f':CHANNEL{channel}:OFFSET {offset}'  # must come after SCALE
        )

    def configure_timebase(self,
                           *,
                           mode: Literal['MAIN', 'XY', 'ROLL'] = 'MAIN',
                           offset: float = 0,
                           scale: float = 1e-6) -> None:
        """Configure the timebase.

        Args:
            mode: The timebase mode (either MAIN, XY or ROLL).
            offset: The horizontal offset [seconds].
            scale: The horizontal scale [seconds/div].
        """
        self._configure(
            f':TIMEBASE:MODE {mode};'
            f':TIMEBASE:SCALE {scale};'
            f':TIMEBASE:OFFSET {offset}'  # must come after SCALE
        )

    def configure_trigger(self,
                          *,
                          channel: int | str = 1,
                          coupling: Literal['AC', 'DC', 'LFReject', 'HFReject'] = 'DC',
                          holdoff: float = 16e-9,
                          level: float = 0,
                          noise_reject: bool = True,
                          slope: Literal['POS', 'NEG', 'RFAL'] = 'POS',
                          sweep: Literal['AUTO', 'NORMAL', 'SINGLE'] = 'AUTO') -> None:
        """Configure the Edge trigger.

        Args:
            channel: The channel to use as the trigger source.
            coupling: The trigger coupling type (either AC, DC, LFReject or HFReject).
            holdoff: The trigger holdoff time [seconds].
            level: The voltage level to trigger at.
            noise_reject: Whether to enable or disable noise rejection.
            slope: The slope edge to trigger on (either POS, NEG or RFAL).
            sweep: The sweep mode (either AUTO, NORMAL or SINGLE).
        """
        reject = 'ON' if noise_reject else 'OFF'
        source = channel if isinstance(channel, str) else f'CHAN{channel}'
        self._configure(
            f':TRIGGER:MODE EDGE;'
            f':TRIGGER:EDGE:SOURCE {source};'
            f':TRIGGER:EDGE:SLOPE {slope};'
            f':TRIGGER:EDGE:LEVEL {level};'
            f':TRIGGER:COUPLING {coupling};'
            f':TRIGGER:HOLDOFF {holdoff};'
            f':TRIGGER:SWEEP {sweep};'
            f':TRIGGER:NREJECT {reject}'
        )

    def run(self) -> None:
        """Start acquiring waveform data."""
        self.logger.info(f'start {self.alias!r}')
        self._check(':RUN')

    def single(self) -> None:
        """Capture and display a single acquisition."""
        self.logger.info(f'single shot {self.alias!r}')
        self._check(':SINGLE')

    def software_trigger(self) -> None:
        """Send a trigger signal."""
        self.logger.info(f'software trigger {self.alias!r}')
        self._check(':TFORCE')

    def stop(self) -> None:
        """Stop acquiring waveform data."""
        self.logger.info(f'stop {self.alias!r}')
        self._check(':STOP')

    def waveform(self,
                 *channels: int | str,
                 displayed: bool = True) -> np.ndarray:
        """Get the waveform data.

        Args:
            *channels: The channel(s) to read (e.g., 1, 'CHAN1', 'channel1', 'D6').
            displayed: Whether to read the waveform data displayed on the screen
                or from internal memory. If reading from internal memory then
                :meth:`.stop` is called prior to reading the data.

        Returns:
            The waveform data.
        """
        if not channels:
            self.raise_exception('Must specify the channel(s) to read')

        if displayed:
            chunk_size = 1200
            mode = 'NORMAL'
        else:
            # A maximum of 250000 points can be read per ":WAV:DATA?" query
            # when ":WAV:FORM BYTE" is used
            chunk_size = 250000
            mode = 'RAW'
            self.stop()

        data = []
        names = []
        for c in channels:
            source = c.upper() if isinstance(c, str) else f'CHAN{c}'
            cmd = f':WAVEFORM:SOURCE {source};' \
                  f':WAVEFORM:MODE {mode};' \
                  f':WAVEFORM:FORMAT BYTE'
            self._check(cmd)

            pre = self.connection.query(':WAVEFORM:PREAMBLE?').split(',')
            fmt, typ, npts, nave = map(int, pre[:4])
            dx, x0, x_ref, dy, y0, y_ref = map(float, pre[4:])

            assert fmt == 0

            self.logger.info(f'get {source!r} waveform data from {self.alias!r}')

            raw = np.empty(npts, dtype=np.uint8)
            start, stop = 1, chunk_size
            while start < npts:
                cmd = f':WAVEFORM:START {start};' \
                      f':WAVEFORM:STOP {stop};' \
                      f':WAVEFORM:DATA?'
                raw[start-1:stop] = self.connection.query(cmd, dtype=np.uint8, fmt='ieee')
                start = stop + 1
                stop = min(stop + chunk_size, npts)

            if not data:
                t = x0 + np.arange(raw.size) * dx
                data.append(t)
                names.append('t')

            volts = (raw - y0 - y_ref) * dy
            data.append(volts)
            if source.startswith('C'):
                names.append(f'ch{source[-1]}')
            else:
                names.append(source)

        return np.core.records.fromarrays(data, names=','.join(names))
