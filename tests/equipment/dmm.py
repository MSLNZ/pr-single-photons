"""
Test that communication with a DMM is working properly.
"""
import json
import threading

import connect

previous = None

app, dmm = connect.device(
    'dmm-scan',
    'Is it safe to test this DMM?'
)

settings = dmm.configure()
assert abs(dmm.acquisition_time(settings=settings) - 4.0) < 2e-3
assert settings.auto_range is dmm.Auto.OFF
assert settings.auto_zero is dmm.Auto.ON
assert settings.function is dmm.Function.DCV
assert settings.nplc == 10.0
assert settings.nsamples == 10
assert settings.range == 10.0
assert settings.trigger.count == 1
assert settings.trigger.delay < 0.002
assert settings.trigger.edge is dmm.Edge.FALLING
assert settings.trigger.mode is dmm.Mode.IMMEDIATE
if dmm.record.model in ('3458A', 'DMM6500'):
    assert settings.trigger.auto_delay is False
else:
    assert settings.trigger.auto_delay is True
json.dumps(settings.to_json())
dmm.zero()

settings = dmm.configure(
    function='dci', range=0.01, nsamples=20,
    nplc=1, auto_zero=False, trigger='bus', ntriggers=2, delay=1)
assert settings.auto_range is dmm.Auto.OFF
assert settings.auto_zero is dmm.Auto.OFF
assert settings.function is dmm.Function.DCI
assert settings.nplc == 1.0
assert settings.nsamples == 20
assert settings.range == 1e-2
assert settings.trigger.count == 2
assert abs(settings.trigger.delay - 1) < 1e-6
assert settings.trigger.auto_delay is False
assert settings.trigger.edge is dmm.Edge.FALLING
assert settings.trigger.mode is dmm.Mode.BUS
json.dumps(settings.to_json())

if dmm.record.model in ['3458A', '34401A']:
    edge = 'FALLING'
else:
    edge = 'RISING'
settings = dmm.configure(
    function='volt:dc', auto_zero=False, range=1, trigger='ext', edge=edge)
assert settings.auto_range is dmm.Auto.OFF
assert settings.auto_zero is dmm.Auto.OFF
assert settings.function is dmm.Function.DCV
assert settings.nplc == 10.0
assert settings.nsamples == 10
assert settings.range == 1.0
assert settings.trigger.count == 1
assert settings.trigger.delay < 0.002
assert settings.trigger.edge == edge
assert settings.trigger.mode is dmm.Mode.EXTERNAL
if dmm.record.model in ('3458A', 'DMM6500'):
    assert settings.trigger.auto_delay is False
else:
    assert settings.trigger.auto_delay is True
json.dumps(settings.to_json())

if dmm.record.model == '3458A':
    range_str = ['auto']
else:
    range_str = ['auto', 'def', 'min', 'max']
for r in range_str:
    dmm.configure(range=r)


def check_samples(current, *, expected_size=10):
    global previous
    dmm.check_errors()
    assert current.size == expected_size
    if previous is not None:
        for i, value in enumerate(previous):
            assert value != current[i]
        assert current.mean != previous.mean
        assert current.stdev != previous.stdev
    previous = current


# immediate trigger mode
dmm.clear()
dmm.reset()
dmm.configure(trigger=None)
while True:
    dmm.logger.info('Initiate? (Y/n) ')
    if input() == 'n':
        break
    dmm.initiate()
    samples = dmm.fetch()
    check_samples(samples)

# software trigger mode
dmm.clear()
dmm.reset()
dmm.configure(trigger='bus')
while True:
    dmm.initiate()
    dmm.logger.info('Software trigger? (Y/n) ')
    if input() == 'n':
        dmm.abort()
        break
    dmm.trigger()
    samples = dmm.fetch()
    check_samples(samples)

# external trigger mode
daq = None
while True:
    dmm.logger.info('Test external trigger mode using NIDAQ...')
    dmm.logger.info('Specify 3 values "PFI NSAMPLES NTRIGGERS" or hit Enter to ignore test:')
    reply = input()
    if not reply:
        break

    pfi, nsamples, ntriggers = map(int, reply.split())

    if daq is None:
        daq = app.connect_equipment('daq-ni')

    dmm.clear()
    dmm.reset()
    settings = dmm.configure(trigger='ext', ntriggers=ntriggers,
                             nsamples=nsamples, auto_zero=False)
    sleep = round(0.2 + dmm.acquisition_time(settings=settings, all_triggers=False), 1)

    def create_trigger_pulses():
        for i in range(ntriggers):
            app.logger.info(f'external trigger {i + 1} of {ntriggers}')
            daq.pulse(pfi, 0.1, state=False)
            app.sleep(sleep)

    while True:
        dmm.initiate()

        dmm.logger.info('External trigger? (Y/n) ')
        if input() == 'n':
            dmm.abort()
            break
        thread = threading.Thread(target=create_trigger_pulses)
        thread.start()

        samples = dmm.fetch()
        check_samples(samples, expected_size=ntriggers * nsamples)
        thread.join()

try:
    assert dmm.temperature() > 10
except AttributeError:
    pass

app.disconnect_equipment()
