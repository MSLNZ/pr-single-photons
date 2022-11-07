"""
Test that communication with a DMM is working properly.
"""
import math

import connect

app, dmm = connect.device(
    'dmm-34465a',
    'Is it safe to test this DMM?'
)

settings = dmm.settings()
assert len(settings) == 11
assert 'auto_range' in settings
assert 'auto_zero' in settings
assert 'function' in settings
assert 'nplc' in settings
assert 'nsamples' in settings
assert 'range' in settings
assert 'trigger_count' in settings
assert 'trigger_delay' in settings
assert 'trigger_delay_auto' in settings
assert 'trigger_edge' in settings
assert 'trigger_mode' in settings

assert dmm.acquisition_time() < 1.0

settings = dmm.configure()
assert settings['auto_range'] == 'OFF'
assert settings['auto_zero'] == 'ON'
assert settings['function'] == 'VOLTAGE'
assert settings['nplc'] == 10.0
assert settings['nsamples'] == 10
assert settings['range'] == 10.0
assert settings['trigger_count'] == 1
assert settings['trigger_delay'] < 0.002
assert settings['trigger_delay_auto'] is True
assert settings['trigger_edge'] == 'FALLING'
assert settings['trigger_mode'] == 'BUS'

settings = dmm.configure(
    function='current', range=0.001, nsamples=20,
    nplc=0.2, auto_zero=False, trigger='imm', ntriggers=2, delay=1)
assert settings['auto_range'] == 'OFF'
assert settings['auto_zero'] == 'OFF'
assert settings['function'] == 'CURRENT'
assert settings['nplc'] == 0.2
assert settings['nsamples'] == 20
assert settings['range'] == 1e-3
assert settings['trigger_count'] == 2
assert settings['trigger_delay'] == 1.0
assert settings['trigger_delay_auto'] is False
assert settings['trigger_edge'] == 'FALLING'
assert settings['trigger_mode'] == 'IMMEDIATE'

settings = dmm.configure(function='dcv', auto_zero=False, range='auto')
assert settings['auto_range'] == 'ON'
assert settings['auto_zero'] == 'OFF'
assert settings['function'] == 'VOLTAGE'
assert settings['nplc'] == 10.0
assert settings['nsamples'] == 10
assert settings['range'] == 10.0
assert settings['trigger_count'] == 1
assert settings['trigger_delay'] < 0.002
assert settings['trigger_delay_auto'] is True
assert settings['trigger_edge'] == 'FALLING'
assert settings['trigger_mode'] == 'BUS'

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
