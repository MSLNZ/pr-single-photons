"""
Test that photons/equipment/nidaq.py is working properly.
"""
import math
from time import perf_counter

import numpy as np
import pytest
from nidaqmx.errors import DaqError

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

#
# Digital Input
#
assert daq.digital_in(0) is False
assert daq.digital_in(0, port=0) is False
assert daq.digital_in(0, port=2) is False
assert daq.digital_in('3:5') == [False] * 3
assert daq.digital_in('0:7') == [False] * 8

#
# Analog Input
#
data, dt = daq.analog_in(0)
assert data.shape == (1,)
assert dt == 0.001

data, dt = daq.analog_in(0, nsamples=2, rate=10)
assert data.shape == (2,)
assert dt == 0.1

# only 1 sample is acquired, so the `rate` keyword argument is ignored
data, dt = daq.analog_in('0:3', rate=1)
assert data.shape == (4, 1)
assert dt == 0.001

data, dt = daq.analog_in('0:3', nsamples=2, rate=100e3)
assert data.shape == (4, 2)
assert dt == 1e-5

data, dt = daq.analog_in('0:7', duration=1, rate=100)
assert data.shape == (8, 100)
assert dt == 0.01
x = np.asarray([i*dt for i in range(100)])
x2 = daq.time_array(dt, 100)
assert np.array_equal(x, x2)

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
daq.analog_out('0', [0., 0.1, 0.2], rate=1)
assert perf_counter() - t0 > 2.0

values = np.sin(np.linspace(0, 2*np.pi, 1000))
daq.analog_out(0, values, rate=1e5)

daq.analog_out('0:1', [[0.], [0.]])

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


app.disconnect_equipment()
