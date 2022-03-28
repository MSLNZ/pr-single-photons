"""
Test that communication with a DMM is working properly.
"""
import math

import connect

app, dmm = connect.device(
    'dmm-34465a',
    'Is it safe to communicate with this DMM?'
)

info = dmm.info()
assert 'auto_range' in info
assert 'auto_zero' in info
assert 'function' in info
assert 'nplc' in info
assert 'nsamples' in info
assert 'range' in info
assert 'trigger_count' in info
assert 'trigger_delay' in info
assert 'trigger_delay_auto' in info
assert 'trigger_edge' in info
assert 'trigger_mode' in info

assert dmm.acquisition_time() < 1.0

info = dmm.configure()
assert info['auto_range'] == 'OFF'
assert info['auto_zero'] == 'ON'
assert info['function'] == 'VOLTAGE'
assert info['nplc'] == 10.0
assert info['nsamples'] == 10
assert info['range'] == 10.0
assert info['trigger_count'] == 1
assert info['trigger_delay'] < 0.002
assert info['trigger_delay_auto'] is True
assert info['trigger_edge'] == 'FALLING'
assert info['trigger_mode'] == 'BUS'

info = dmm.configure(function='current', range=0.001, nsamples=20,
                     nplc=0.2, auto_zero=False, trigger='imm', ntriggers=2, delay=1)
assert info['auto_range'] == 'OFF'
assert info['auto_zero'] == 'OFF'
assert info['function'] == 'CURRENT'
assert info['nplc'] == 0.2
assert info['nsamples'] == 20
assert info['range'] == 1e-3
assert info['trigger_count'] == 2
assert info['trigger_delay'] == 1.0
assert info['trigger_delay_auto'] is False
assert info['trigger_edge'] == 'FALLING'
assert info['trigger_mode'] == 'IMMEDIATE'

info = dmm.configure(function='dcv', auto_zero=False, range='auto')
assert info['auto_range'] == 'ON'
assert info['auto_zero'] == 'OFF'
assert info['function'] == 'VOLTAGE'
assert info['nplc'] == 10.0
assert info['nsamples'] == 10
assert info['range'] == 10.0
assert info['trigger_count'] == 1
assert info['trigger_delay'] < 0.002
assert info['trigger_delay_auto'] is True
assert info['trigger_edge'] == 'FALLING'
assert info['trigger_mode'] == 'BUS'

dmm.bus_trigger()
ave, std = dmm.fetch()
assert not math.isnan(ave)
assert not math.isnan(std)

dmm.configure(function='dci', range='1 uA', nsamples=1)
dmm.software_trigger()
ave, std = dmm.fetch()
assert not math.isnan(ave)
assert math.isnan(std)

dmm.reset()
dmm.clear()

app.disconnect_equipment()
