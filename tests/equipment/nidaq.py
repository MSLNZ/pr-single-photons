"""
Test that photons/equipment/nidaq.py is working properly.
"""
import math
from time import perf_counter

import numpy as np

import connect

port = 1
port_str = str(port)

app, daq = connect.device(
    'daq-ni',
    f'Is it safe to control NI-DAQ? '
    f'Nothing should be connected to the digital port={port} '
    f'nor to the analog output terminals.'
)

#
# Digital Output
#
daq.digital_out(False, port, '0:7')
assert daq.digital_out_read(port, '0:7') == [False] * 8

daq.digital_out(True, port, 1)
assert daq.digital_out_read(port, 1) is True
assert daq.digital_out_read(port, '1:3') == [True, False, False]

daq.digital_out(True, port_str, '2:4')
assert daq.digital_out_read(port, 2) is True
assert daq.digital_out_read(port, '3') is True
assert daq.digital_out_read(port_str, 4) is True
assert daq.digital_out_read(port, '0:7') == [False, True, True, True, True, False, False, False]

daq.digital_out([False, False, True, False, True, True], port_str, '2:7')
assert daq.digital_out_read(port, '0:7') == [False, True, False, False, True, False, True, True]

daq.digital_out(False, port, '0:7')
for i in range(8):
    assert daq.digital_out_read(port, i) is False

#
# Digital Input
#
assert daq.digital_in(port, 1) is False
assert daq.digital_in(port_str, '0:7') == [False] * 8

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
# Analog Output
#
assert daq.analog_out(0, 0) == 1
assert daq.analog_out(0, 0.1) == 1
assert daq.analog_out(0, [-0.1]) == 1
assert daq.analog_out(0, [-0.2, -0.1, 0., 0.1, 0.2]) == 5
assert daq.analog_out('0:1', np.array([0.1, -0.1])) == 1
assert daq.analog_out('0:1', [0., 0.]) == 1
assert daq.analog_out('0:1', [[-0.2, -0.1, 0., 0.1, 0.2], [0.2, 0.1, 0., -0.1, -0.2]]) == 5

t0 = perf_counter()
assert daq.analog_out('0', [0., 0.1, 0.2], rate=1) == 3
assert perf_counter() - t0 > 2.0

values = np.sin(np.linspace(0, 2*np.pi, 1000))
assert daq.analog_out(0, values, rate=1e5) == 1000

assert daq.analog_out('0:1', [[0.], [0.]]) == 1

#
# Count edges
#
ave, std = daq.count_edges(1)
assert ave == 0
assert math.isnan(std)

app.disconnect_equipment()
