"""
Test that photons/equipment/idq_time_controller.py is working properly.
"""
import numpy as np

import connect

app, dev = connect.device('idq', 'Is it safe to control the Time Controller?')

dev.load('INIT')

settings = dev.configure_device(clock='internal', mode='fast')
assert settings.clock == dev.Clock.INTERNAL
assert settings.mode == dev.Mode.HIGH_SPEED

settings = dev.configure_start(threshold=0.5, delay=1e-9)
assert settings.enabled is False
assert settings.coupling == dev.Coupling.DC
assert settings.edge == dev.Edge.RISING
assert settings.select == dev.Select.UNSHAPED
assert settings.duration == 1.0
assert settings.delay == 1e-9
assert settings.mode == dev.Mode.CYCLE
assert settings.threshold == 0.499712

settings = dev.configure_delay(block=1, address=None)
assert settings.address is None
assert settings.value == 0

settings = dev.configure_delay(block=1, address='none', value=1e-9)
assert settings.address is None
assert settings.value == 1e-9

settings = dev.configure_delay(block=2, address=0, value=10e-12)
assert settings.address == 'START'
assert settings.value == 10e-12

settings = dev.configure_delay(block=2, address='START')
assert settings.address == 'START'

settings = dev.configure_delay(block=2, address='star')
assert settings.address == 'START'

settings = dev.configure_delay(block=3, address=1)
assert settings.address == 'INPUT1'

settings = dev.configure_delay(block=3, address='INPU1')
assert settings.address == 'INPUT1'

settings = dev.configure_delay(block=1, address='INPUT1')
assert settings.address == 'INPUT1'

settings = dev.configure_histogram(channel=2, ref='input1')
assert settings.channel == 2
assert settings.ref == 'TSCO5'
assert settings.stop == 'TSCO5'
assert settings.enabler == 'TSGE8'
assert settings.minimum == 0.0
assert settings.maximum == 1e-6
assert settings.bin_count == 10000
assert settings.bin_width == 1e-10

settings = dev.configure_histogram(channel=1, ref=2, stop=3, bin_count=12345, bin_width=600e-12)
assert settings.channel == 1
assert settings.ref == 'TSCO6'
assert settings.stop == 'TSCO7'
assert settings.enabler == 'TSGE8'
assert settings.minimum == 0.0
assert settings.maximum == 7.407e-6
assert settings.bin_count == 12345
assert settings.bin_width == 600e-12

for ch in [1, 2, 3, 4]:
    settings = dev.configure_input(channel=ch, delay=500e-12)
    assert settings.enabled is False
    assert settings.coupling == dev.Coupling.DC
    assert settings.channel == ch
    assert settings.edge == dev.Edge.RISING
    assert settings.select == dev.Select.UNSHAPED
    assert settings.resync_policy == dev.ResyncPolicy.AUTO
    assert settings.duration == 1.0
    assert settings.delay == 500e-12
    assert settings.mode == dev.Mode.CYCLE
    assert settings.threshold == 0.999424

dev.configure_input(channel=2, duration=0.1, enabled=True)
samples = dev.count_edges(channel=2, nsamples=10, allow_zero=True)
assert samples.mean == 0
assert samples.stdev == 0
assert samples.size == 10
dev.configure_input(channel=2)

dev.configure_start(duration=0.1, enabled=True)
samples = dev.count_edges(channel=0, nsamples=10, allow_zero=True)
assert samples.mean == 0
assert samples.stdev == 0
assert samples.size == 10
dev.configure_start()

assert isinstance(dev.has_high_resolution_error(channel=1), bool)

dev.clear_high_resolution_error(channel=1)

dev.load('HISTO')

data = dev.start_stop(duration=1)
assert isinstance(data.hist1, np.ndarray)
assert isinstance(data.hist2['timestamps'], np.ndarray)
assert isinstance(data.hist3['counts'], np.ndarray)
assert isinstance(data.hist4, np.ndarray)

app.disconnect_equipment()
