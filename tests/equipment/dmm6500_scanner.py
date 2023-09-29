"""
Test that communication with a DMM6500 scanner card is working properly.
"""
import threading

import connect

previous = []

app, dmm = connect.device(
    'dmm-scan',
    'Is it safe to test this DMM?'
)

ch1 = dmm.create_scanner_channel(1, range='def', nplc=0.01, auto_zero=1)
ch2 = dmm.create_scanner_channel(2, range='max', nplc=1, auto_zero='ON')
ch3 = dmm.create_scanner_channel(3, range='auto', auto_zero='off', nplc=0.1)
ch4 = dmm.create_scanner_channel(4, range='min', auto_zero=0, nplc=0.02)
settings = dmm.configure_scanner(ch1, ch2, ch3, ch4)
assert settings['ch1'].auto_range is dmm.Auto.OFF
assert settings['ch1'].auto_zero is dmm.Auto.ON
assert settings['ch1'].function is dmm.Function.DCV
assert settings['ch1'].nplc == 0.01
assert settings['ch1'].nsamples == 10
assert settings['ch1'].range == 1000.0
assert settings['ch1'].trigger.auto_delay is False
assert settings['ch1'].trigger.count == 1
assert settings['ch1'].trigger.delay == 0.0
assert settings['ch1'].trigger.edge is dmm.Edge.FALLING
assert settings['ch1'].trigger.mode is dmm.Mode.IMMEDIATE
assert settings['ch2'].auto_range is dmm.Auto.OFF
assert settings['ch2'].auto_zero is dmm.Auto.ON
assert settings['ch2'].function is dmm.Function.DCV
assert settings['ch2'].nplc == 1.0
assert settings['ch2'].nsamples == 10
assert settings['ch2'].range == 1000.0
assert settings['ch2'].trigger.auto_delay is False
assert settings['ch2'].trigger.count == 1
assert settings['ch2'].trigger.delay == 0.0
assert settings['ch2'].trigger.edge is dmm.Edge.FALLING
assert settings['ch2'].trigger.mode is dmm.Mode.IMMEDIATE
assert settings['ch3'].auto_range is dmm.Auto.ON
assert settings['ch3'].auto_zero is dmm.Auto.OFF
assert settings['ch3'].function is dmm.Function.DCV
assert settings['ch3'].nplc == 0.1
assert settings['ch3'].nsamples == 10
assert settings['ch3'].range == 1000.0
assert settings['ch3'].trigger.auto_delay is False
assert settings['ch3'].trigger.count == 1
assert settings['ch3'].trigger.delay == 0.0
assert settings['ch3'].trigger.edge is dmm.Edge.FALLING
assert settings['ch3'].trigger.mode is dmm.Mode.IMMEDIATE
assert settings['ch4'].auto_range is dmm.Auto.OFF
assert settings['ch4'].auto_zero is dmm.Auto.OFF
assert settings['ch4'].function is dmm.Function.DCV
assert settings['ch4'].nplc == 0.02
assert settings['ch4'].nsamples == 10
assert settings['ch4'].range == 0.1
assert settings['ch4'].trigger.auto_delay is False
assert settings['ch4'].trigger.count == 1
assert settings['ch4'].trigger.delay == 0.0
assert settings['ch4'].trigger.edge is dmm.Edge.FALLING
assert settings['ch4'].trigger.mode is dmm.Mode.IMMEDIATE

channels = (1, 3, 5)
settings = dmm.configure_scanner(*channels)
for ch, (k, v) in zip(channels, settings.items()):
    assert k == f'ch{ch}'
    assert v.auto_range is dmm.Auto.OFF
    assert v.auto_zero is dmm.Auto.ON
    assert v.function is dmm.Function.DCV
    assert v.nplc == 10.0
    assert v.nsamples == 10
    assert v.range == 10.0
    assert v.trigger.auto_delay is False
    assert v.trigger.count == 1
    assert v.trigger.delay == 0.0
    assert v.trigger.edge is dmm.Edge.FALLING
    assert v.trigger.mode is dmm.Mode.IMMEDIATE


ch1 = dmm.create_scanner_channel(1, auto_zero='once')
settings = dmm.configure_scanner(ch1)
assert settings['ch1'].auto_range is dmm.Auto.OFF
assert settings['ch1'].auto_zero is dmm.Auto.OFF
assert settings['ch1'].function is dmm.Function.DCV
assert settings['ch1'].nplc == 10.0
assert settings['ch1'].nsamples == 10
assert settings['ch1'].range == 10.0
assert settings['ch1'].trigger.auto_delay is False
assert settings['ch1'].trigger.count == 1
assert settings['ch1'].trigger.delay == 0.0
assert settings['ch1'].trigger.edge is dmm.Edge.FALLING
assert settings['ch1'].trigger.mode is dmm.Mode.IMMEDIATE


def check_samples(current, *, expected_size=10):
    global previous
    dmm.check_errors()
    assert len(current) == 4
    if previous:
        for i, c in enumerate(current):
            assert c.size == expected_size
            p = previous[i]
            for j in range(min(c.size, p.size)):
                assert c[j] != p[j]
            assert c.mean != p.mean
            assert c.stdev != p.stdev
    previous = current


ch1 = dmm.create_scanner_channel(1, range=10, auto_zero='off')
ch2 = dmm.create_scanner_channel(2, range=100, auto_zero='off')
ch3 = ch2.copy(3)
ch4 = ch1.copy(4)

# immediate trigger mode
dmm.clear()
dmm.reset()
dmm.configure_scanner(ch1, ch2, ch3, ch4, trigger=None)
dmm.zero()
while True:
    dmm.logger.info('Initiate? (Y/n) ')
    if input() == 'n':
        break
    dmm.initiate()
    samples = dmm.fetch_scanner()
    check_samples(samples)

# software trigger mode
nsamples = 3
dmm.clear()
dmm.reset()
settings = dmm.configure_scanner(ch1, ch2, ch3, ch4, trigger='bus', nsamples=nsamples)
ntriggers = len(settings) * nsamples
sleep = round(0.2 + dmm.acquisition_time(settings=settings['ch1']), 1)
dmm.zero()
while True:
    dmm.initiate()
    dmm.logger.info('Software trigger? (Y/n) ')
    if input() == 'n':
        dmm.abort()
        break
    for ti in range(ntriggers):
        app.logger.info(f'bus trigger {ti + 1} of {ntriggers}')
        dmm.trigger()
        app.sleep(sleep)
    samples = dmm.fetch_scanner()
    check_samples(samples, expected_size=nsamples)

# external trigger mode
daq = None
while True:
    dmm.logger.info('Test external trigger mode using NIDAQ...')
    dmm.logger.info('Specify 2 values "PFI NSAMPLES" or hit Enter to ignore test:')
    reply = input()
    if not reply:
        break

    pfi, nsamples = map(int, reply.split())

    if daq is None:
        daq = app.connect_equipment('daq-ni')

    dmm.clear()
    dmm.reset()
    settings = dmm.configure_scanner(ch1, ch2, ch3, ch4, trigger='ext', nsamples=nsamples)
    ntriggers = len(settings) * nsamples
    sleep = round(0.2 + dmm.acquisition_time(settings=settings['ch1']), 1)

    def create_trigger_pulses():
        for i in range(ntriggers):
            app.logger.info(f'external trigger {i + 1} of {ntriggers}')
            daq.pulse(pfi, 0.1, state=False)
            app.sleep(sleep)

    dmm.zero()
    while True:
        dmm.initiate()

        dmm.logger.info('External trigger? (Y/n) ')
        if input() == 'n':
            dmm.abort()
            break
        thread = threading.Thread(target=create_trigger_pulses)
        thread.start()

        samples = dmm.fetch_scanner()
        check_samples(samples, expected_size=nsamples)
        thread.join()

app.disconnect_equipment()
