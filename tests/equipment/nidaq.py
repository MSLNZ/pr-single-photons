"""
Test that photons/equipment/nidaq.py is working properly.
"""
import math
from time import (
    perf_counter,
    sleep,
)

import numpy as np
import pytest
from nidaqmx.errors import DaqError
from scipy.optimize import curve_fit

import connect

app, daq = connect.device(
    'daq-ni',
    f'Is it safe to control NI-DAQ? '
    f'Ideally, nothing should be connected to the terminals.'
)

#
# Digital Output
#
daq.digital_out('0:7', False)
assert daq.digital_out_read('0:7') == [False] * 8

daq.digital_out(1, True)
assert daq.digital_out_read(1) is True
assert daq.digital_out_read('1:3') == [True, False, False]

daq.digital_out(0, [False, False, True, False, True, True], port=0)
assert daq.digital_out_read(0, port=0) is True

daq.digital_out('2:4', True)
assert daq.digital_out_read(2) is True
assert daq.digital_out_read('3') is True
assert daq.digital_out_read(4) is True
assert daq.digital_out_read('0:7') == [False, True, True, True, True, False, False, False]

daq.digital_out('2:7', [False, False, True, False, True, True])
assert daq.digital_out_read('0:7') == [False, True, False, False, True, False, True, True]

states = [[True, False, True, False], [False, True, False, True]]
daq.digital_out('0:1', states, port=0)
assert daq.digital_out_read('0:1', port=0) == [False, True]

for port in [0, 1, 2]:
    daq.digital_out('0:7', False, port=port)
    for i in range(8):
        assert daq.digital_out_read(i, port=port) is False


lines = f'/{daq.DEV}/port0/line0:7,/{daq.DEV}/port1/line0:7,/{daq.DEV}/port2/line0:7'
daq.digital_out(lines, False)
assert daq.digital_out_read(lines) == [False] * (3 * 8)

#
# Digital Input
#
assert daq.digital_in(0) is False
assert daq.digital_in(0, port=0) is False
assert daq.digital_in(0, port=2) is False
assert daq.digital_in('3:5') == [False] * 3
assert daq.digital_in('0:7') == [False] * 8
assert daq.digital_in(lines) == [False] * (3 * 8)

#
# Analog Input
#
data, dt = daq.analog_in(0)
assert data.shape == (1,)
assert dt == 0.001

data, dt = daq.analog_in(0, nsamples=2, timing=daq.timing(rate=10))
assert data.shape == (2,)
assert dt == 0.1

# only 1 sample is acquired, so the `rate` keyword argument is ignored
data, dt = daq.analog_in('0:3', timing=daq.timing(rate=1))
assert data.shape == (4, 1)
assert dt == 0.001

data, dt = daq.analog_in('0:3', nsamples=2, timing=daq.timing(rate=100e3))
assert data.shape == (4, 2)
assert dt == 1e-5

data, dt = daq.analog_in('0:7', duration=1, timing=daq.timing(rate=100))
assert data.shape == (8, 100), data.shape
assert dt == 0.01
x = np.asarray([i*dt for i in range(100)])
x2 = daq.time_array(100, dt)
assert np.array_equal(x, x2)


# register a callback
def ai_callback(task_handle, every_n_samples_event_type, number_of_samples, callback_data):
    app.logger.info(f'AI callback: {task.read(number_of_samples_per_channel=number_of_samples)}')
    return 0


task, dt = daq.analog_in(0, timing=daq.timing(finite=False), wait=False)
task.register_every_n_samples_acquired_into_buffer_event(5, ai_callback)
task.start()
sleep(1)
task.stop()
daq.close_all_tasks()

#
# Analog Output (the analog_out method has an internal assert statement)
#
daq.analog_out(0, 0)
daq.analog_out(0, 0.1)
daq.analog_out(0, [-0.1])
daq.analog_out(0, [-0.2, -0.1, 0., 0.1, 0.2])
daq.analog_out('0:1', np.array([0.1, -0.1]))
daq.analog_out('0:1', [0., 0.])
daq.analog_out('0:1', [[-0.2, -0.1, 0., 0.1, 0.2], [0.2, 0.1, 0., -0.1, -0.2]])

t0 = perf_counter()
daq.analog_out('0', [0., 0.1, 0.2], timing=daq.timing(rate=1))
assert perf_counter() - t0 > 2.0

values = np.sin(np.linspace(0, 2*np.pi, 1000))
daq.analog_out(0, values, timing=daq.timing(rate=1e5))

daq.analog_out('0:1', [0., 0.])

#
# Read Analog Output
#
values, dt = daq.analog_out_read(0)
assert dt == 0.001
assert values.size == 1
assert values[0] == pytest.approx(0.0, abs=0.005)
values, dt = daq.analog_out_read(1)
assert dt == 0.001
assert values.size == 1
assert values[0] == pytest.approx(0.0, abs=0.005)
values, dt = daq.analog_out_read('0:1')
assert dt == 0.001
assert values.shape == (2, 1)
assert values[0, 0] == pytest.approx(0.0, abs=0.005)
assert values[1, 0] == pytest.approx(0.0, abs=0.005)

daq.analog_out('0:1', [-1.1, 0.21])
values, dt = daq.analog_out_read(0)
assert dt == 0.001
assert values.size == 1
assert values[0] == pytest.approx(-1.1, abs=0.005)
values, dt = daq.analog_out_read(1)
assert dt == 0.001
assert values.size == 1
assert values[0] == pytest.approx(0.21, abs=0.005)
values, dt = daq.analog_out_read('0:1')
assert dt == 0.001
assert values.shape == (2, 1)
assert values[0, 0] == pytest.approx(-1.1, abs=0.005)
assert values[1, 0] == pytest.approx(0.21, abs=0.005)
values, _ = daq.analog_out_read('0:0')
assert values.shape == (1,)
assert values[0] == pytest.approx(-1.1, abs=0.005)
values, _ = daq.analog_out_read('1:1')
assert values.shape == (1,)
assert values[0] == pytest.approx(0.21, abs=0.005)


values, dt = daq.analog_out_read(0, nsamples=10, timing=daq.timing(rate=10))
assert dt == 0.1
assert values.shape == (10,)
for value in values:
    assert value == pytest.approx(-1.1, abs=0.005)

values, dt = daq.analog_out_read(1, nsamples=100)
assert dt == 0.001
assert values.shape == (100,)
for value in values:
    assert value == pytest.approx(0.21, abs=0.005)

values, dt = daq.analog_out_read('0:1', nsamples=5, timing=daq.timing(rate=1e5))
assert dt == 0.00001
assert values.shape == (2, 5)
for value in values[0, :]:
    assert value == pytest.approx(-1.1, abs=0.005)
for value in values[1, :]:
    assert value == pytest.approx(0.21, abs=0.005)

daq.analog_out('0:1', [0., 0.])
values, _ = daq.analog_out_read(0)
assert values[0] == pytest.approx(0.0, abs=0.005)
values, _ = daq.analog_out_read(1)
assert values[0] == pytest.approx(0.0, abs=0.005)
values, _ = daq.analog_out_read('0:1')
assert values[0, 0] == pytest.approx(0.0, abs=0.005)
assert values[1, 0] == pytest.approx(0.0, abs=0.005)

#
# Count edges
#
ave, std = daq.count_edges(0, 1.0)
assert ave == 0
assert math.isnan(std)

#
# Pulse
#
t0 = perf_counter()
daq.pulse(0, 0.1)
t1 = perf_counter() - t0
assert t1 < 0.16

t0 = perf_counter()
daq.pulse(0, 0.1, npulses=10)
t1 = perf_counter() - t0
assert 1.9 < t1 < 2.1

daq.pulse(2, 0.1, ctr=0, state=False)
assert daq.digital_out_read(2)
daq.pulse(2, 0.1, ctr=0)
assert not daq.digital_out_read(2)

t0 = perf_counter()
daq.pulse(0, 0.1, delay=1)
t1 = perf_counter() - t0
assert 1.1 < t1 < 1.2

daq.pulse(0, 0.1, state=True)
assert not daq.digital_out_read(0)
daq.pulse(0, 0.1, state=False)
assert daq.digital_out_read(0)

task = daq.pulse(0, 1.0, wait=False)
while not task.is_task_done():
    app.logger.info(f'AI0: {daq.analog_in(0)[0]}')
app.logger.info('pulse task is done')
task.close()

assert not daq.digital_out_read(0)
assert not daq.digital_out_read(2)

#
# Triggering Analog Input
#

# the nsamples must be > 1 error
message = r'Property: DAQmx_SampQuant_SampPerChan'
with pytest.raises(DaqError, match=message):
    daq.analog_in(0, trigger=daq.trigger(0, level=0.0))
with pytest.raises(DaqError, match=message):
    daq.analog_in(0, trigger=daq.trigger(0))

# ideally the following would work if there was a trigger signal

message = r'Some or all of the samples requested have not yet been acquired'
with pytest.raises(DaqError, match=message):
    daq.analog_in(0, nsamples=2, timeout=1, trigger=daq.trigger(0, level=0.0))
with pytest.raises(DaqError, match=message):
    daq.analog_in(0, nsamples=2, timeout=1, trigger=daq.trigger(0, level=0.0, delay=0.1))
with pytest.raises(DaqError, match=message):
    daq.analog_in(0, nsamples=2, timeout=1, trigger=daq.trigger(0))
with pytest.raises(DaqError, match=message):
    daq.analog_in(0, nsamples=2, timeout=1, trigger=daq.trigger(0, delay=0.1))

message = r'Reading relative to the reference trigger or relative to the start of ' \
          r'pretrigger samples position before the acquisition is complete.'
with pytest.raises(DaqError, match=message):
    daq.analog_in(0, nsamples=200, timeout=1, trigger=daq.trigger(0, level=0.0, delay=-0.1))
with pytest.raises(DaqError, match=message):
    daq.analog_in(0, nsamples=200, timeout=1, trigger=daq.trigger(0, delay=-0.1))

#
# Triggering Analog Output
#

# need to specify > 1 voltage samples to output
message = r'Set the Buffer Size to greater than 0'
with pytest.raises(DaqError, match=message):
    daq.analog_out(0, 0, trigger=daq.trigger(0, level=0.0))
daq.close_all_tasks()
with pytest.raises(DaqError, match=message):
    daq.analog_out(0, 0, trigger=daq.trigger(0))
daq.close_all_tasks()

# ideally the following would work if there was a trigger signal

message = r'Wait Until Done did not indicate that the task ' \
          r'was done within the specified timeout.'
with pytest.raises(DaqError, match=message):
    daq.analog_out(0, [0, 0], timeout=1, trigger=daq.trigger(0, level=0.0))
with pytest.raises(DaqError, match=message):
    daq.analog_out(0, [0, 0], timeout=1, trigger=daq.trigger(0, level=0.0, delay=0.1))
with pytest.raises(DaqError, match=message):
    daq.analog_out(0, [0, 0], timeout=1, trigger=daq.trigger(0))
with pytest.raises(DaqError, match=message):
    daq.analog_out(0, [0, 0], timeout=1, trigger=daq.trigger(0, delay=0.1))

#
# STORM/PALM
#
sequence = {
    'port0/line0': [True, False, False, False],
    'port0/line1': [False, True, True, True]
}
task = daq.storm(0, sequence=sequence)
sleep(1)
daq.close_all_tasks()


#
# Edge separation
#
message = r'Cannot measure two-edge separation with both the first and second terminal set to the same signal'
with pytest.raises(DaqError, match=message):
    daq.edge_separation(0, 0, stop_edge='rising', timeout=1)

message = r'Some or all of the samples requested have not yet been acquired'
with pytest.raises(DaqError, match=message):
    daq.edge_separation(0, 1, timeout=1)
with pytest.raises(DaqError, match=message):
    daq.edge_separation(0, 1, start_edge='rising', stop_edge=daq.Edge.RISING, timeout=1)


#
# Function generator
#
amp, freq, phase, offset = [0.4, 982.2, 61.2, 0.1]

# initialize the first output voltage
y0 = amp * np.sin(np.pi * phase / 180.) + offset
daq.analog_out(0, y0)

# trigger the function generator when the analog_out_read task starts
daq.function_generator(0, trigger=daq.trigger('ai/StartTrigger'),
                       amplitude=amp, frequency=freq, offset=offset, phase=phase)

# make the function generator wait a bit
sleep(0.1)

out = daq.analog_out_read(0, nsamples=1000, timing=daq.timing(rate=1e5))
times = daq.time_array(*out)


def sin(t, *args):
    a, f, p, o = args
    return a * np.sin(2.0 * np.pi * f * t + p) + o


params, covariance = curve_fit(sin, times, out[0], p0=[1, 1e3, 0, 0])
assert params[0] == pytest.approx(amp, rel=0.001)
assert params[1] == pytest.approx(freq, rel=0.005)
assert params[2] == pytest.approx(phase * np.pi / 180., rel=0.02)
assert params[3] == pytest.approx(offset, rel=0.05)

assert y0 == pytest.approx(out[0][0], abs=0.0006)

daq.close_all_tasks()
daq.analog_out('0:1', [0.0, 0.0])

app.disconnect_equipment()
