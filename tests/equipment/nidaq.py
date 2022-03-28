"""
Test that photons/equipment/nidaq.py is working properly.
"""
import math

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
assert daq.analog_in(0).shape == (1,)
assert daq.analog_in(0, n=5).shape == (5,)
assert daq.analog_in('0:3').shape == (4, 1)
assert daq.analog_in('0:7', n=25).shape == (8, 25)

#
# Analog Output
#
assert daq.analog_out(0, 0) == 1
assert daq.analog_out(0, 1.2) == 1
assert daq.analog_out(0, [-0.5]) == 1
assert daq.analog_out(0, [-2, -1, 0, 1, 2]) == 5
assert daq.analog_out('0:1', np.array([0.1, -0.1])) == 1
assert daq.analog_out('0:1', [0., 0.]) == 1

#
# Count edges
#
ave, std = daq.count_edges(1)
assert ave == 0
assert math.isnan(std)

app.disconnect_equipment()
