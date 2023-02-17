import json

import numpy as np

import photons.equipment.idq_time_controller as tc


def test_delay_settings():
    ds1 = tc.DelaySettings(address='START', value=1e-9)
    assert ds1.address == 'START'
    assert ds1.value == 1e-9
    kwargs = json.loads(json.dumps(ds1.to_json()))
    ds2 = tc.DelaySettings(**kwargs)
    assert ds2.address == 'START'
    assert ds2.value == 1e-9


def test_device_settings():
    ds1 = tc.DeviceSettings(clock=tc.Clock.EXTERNAL, mode=tc.Mode.HIGH_SPEED)
    assert ds1.clock.value == 'EXTERNAL'
    assert ds1.mode.name == 'HIGH_SPEED'
    kwargs = json.loads(json.dumps(ds1.to_json()))
    ds2 = tc.DeviceSettings(clock=tc.Clock(kwargs['clock']), mode=tc.Mode(kwargs['mode']))
    assert ds2.clock.value == 'EXTERNAL'
    assert ds2.mode.name == 'HIGH_SPEED'


def test_histogram():
    dtype = [('timestamps', float), ('counts', np.uint64)]
    h = tc.Histogram(
        hist1=np.array([(1, 1242), (2, 3219)], dtype=dtype),
        hist2=np.array([(1, 1242), (2, 3219), (3, 8213)], dtype=dtype),
        hist3=np.array([(1, 1), (2, 2), (3, 3), (4, 4)], dtype=dtype),
        hist4=np.array([(1, 1242)], dtype=dtype),
    )
    assert h.hist1.shape == (2,)
    assert h.hist2.shape == (3,)
    assert h.hist3.shape == (4,)
    assert h.hist4.shape == (1,)

    kwargs = json.loads(json.dumps(h.to_json()))
    assert isinstance(kwargs['hist1'], list)
    assert isinstance(kwargs['hist2'], list)
    assert isinstance(kwargs['hist3'], list)
    assert isinstance(kwargs['hist4'], list)


def test_histogram_settings():
    hs1 = tc.HistogramSettings(
        channel=1,
        ref='TSCO5',
        stop='NONE',
        enabler='TSGE8',
        minimum=0,
        maximum=1e-6,
        bin_count=10000,
        bin_width=100e-12
    )
    assert hs1.channel == 1
    assert hs1.ref == 'TSCO5'
    assert hs1.stop == 'NONE'
    assert hs1.enabler == 'TSGE8'
    assert hs1.minimum == 0
    assert hs1.maximum == 1e-6
    assert hs1.bin_count == 10000
    assert hs1.bin_width == 100e-12

    kwargs = json.loads(json.dumps(hs1.to_json()))
    hs2 = tc.HistogramSettings(**kwargs)
    assert hs2.channel == 1
    assert hs2.ref == 'TSCO5'
    assert hs2.stop == 'NONE'
    assert hs2.enabler == 'TSGE8'
    assert hs2.minimum == 0
    assert hs2.maximum == 1e-6
    assert hs2.bin_count == 10000
    assert hs2.bin_width == 100e-12


def test_input_settings():
    is1 = tc.InputSettings(
        channel=1,
        coupling=tc.Coupling.DC,
        edge=tc.Edge.RISING,
        enabled=True,
        delay=0,
        duration=0.5,
        mode=tc.Mode.CYCLE,
        resync_policy=tc.ResyncPolicy.AUTO,
        select=tc.Select.UNSHAPED,
        threshold=0.9,
    )
    assert is1.channel == 1
    assert is1.coupling.name == 'DC'
    assert is1.edge.value == 'RISING'
    assert is1.enabled is True
    assert is1.delay == 0
    assert is1.duration == 0.5
    assert is1.mode.name == 'CYCLE'
    assert is1.resync_policy.value == 'AUTO'
    assert is1.select.name == 'UNSHAPED'
    assert is1.threshold == 0.9

    kwargs = json.loads(json.dumps(is1.to_json()))
    is2 = tc.InputSettings(**kwargs)
    assert is2.channel == 1
    assert is2.coupling == 'DC'
    assert is2.edge == 'RISING'
    assert is2.enabled is True
    assert is2.delay == 0
    assert is2.duration == 0.5
    assert is2.mode == 'CYCLE'
    assert is2.resync_policy == 'AUTO'
    assert is2.select == 'UNSHAPED'
    assert is2.threshold == 0.9


def test_start_settings():
    ss1 = tc.StartSettings(
        coupling=tc.Coupling.DC,
        edge=tc.Edge.RISING,
        enabled=True,
        delay=0,
        duration=0.5,
        mode=tc.Mode.CYCLE,
        select=tc.Select.UNSHAPED,
        threshold=0.9,
    )
    assert ss1.coupling.name == 'DC'
    assert ss1.edge.value == 'RISING'
    assert ss1.enabled is True
    assert ss1.delay == 0
    assert ss1.duration == 0.5
    assert ss1.mode.name == 'CYCLE'
    assert ss1.select.name == 'UNSHAPED'
    assert ss1.threshold == 0.9

    kwargs = json.loads(json.dumps(ss1.to_json()))
    ss2 = tc.StartSettings(**kwargs)
    assert ss2.coupling == 'DC'
    assert ss2.edge == 'RISING'
    assert ss2.enabled is True
    assert ss2.delay == 0
    assert ss2.duration == 0.5
    assert ss2.mode == 'CYCLE'
    assert ss2.select == 'UNSHAPED'
    assert ss2.threshold == 0.9
