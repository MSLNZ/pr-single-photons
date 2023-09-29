import json

import pytest

from photons.equipment.dmm import Auto
from photons.equipment.dmm import Edge
from photons.equipment.dmm import Function
from photons.equipment.dmm import Mode
from photons.equipment.dmm import Range
from photons.equipment.dmm import Settings
from photons.equipment.dmm import Trigger
from photons.equipment.dmm_6500 import Keithley6500


@pytest.mark.parametrize('value', [Auto.ON, True, 1, '1', 'on', 'On'])
def test_auto_on(value):
    assert Auto(value) == Auto.ON


@pytest.mark.parametrize('value', [Auto.OFF, False, 0, '0', 'off', 'Off'])
def test_auto_off(value):
    assert Auto(value) == Auto.OFF


@pytest.mark.parametrize('value', [Auto.ONCE, 2, '2', 'once', 'Once'])
def test_auto_once(value):
    assert Auto(value) == Auto.ONCE


@pytest.mark.parametrize('value', [None, -1, 3, 2.5, 'invalid'])
def test_auto_invalid(value):
    with pytest.raises(ValueError):
        Auto(value)


@pytest.mark.parametrize(
    'value', [Edge.RISING, 'rising', 'Rising', 'ris', 'positive', 'Positive', 'Pos'])
def test_edge_rising(value):
    assert Edge(value) == Edge.RISING


@pytest.mark.parametrize(
    'value', [Edge.FALLING, 'falling', 'Falling', 'fall', 'negative', 'Negative', 'Neg'])
def test_edge_falling(value):
    assert Edge(value) == Edge.FALLING


@pytest.mark.parametrize(
    'value', [Edge.BOTH, 'both', 'Both', 'either', 'Either'])
def test_edge_both(value):
    assert Edge(value) == Edge.BOTH


@pytest.mark.parametrize('value', [None, 0, 1.5, 'invalid'])
def test_edge_invalid(value):
    with pytest.raises(ValueError):
        Edge(value)


@pytest.mark.parametrize(
    'value', [Function.DCV, 'dcv', 'DCV', 'volt', 'VOLT', 'volt:DC', 'VOLT:DC'])
def test_function_dcv(value):
    assert Function(value) == Function.DCV


@pytest.mark.parametrize(
    'value', [Function.DCI, 'dci', 'DCI', 'curr', 'CURR', 'curr:DC', 'CURR:DC'])
def test_function_dci(value):
    assert Function(value) == Function.DCI


@pytest.mark.parametrize('value', [None, 0, 1.5, 'invalid'])
def test_function_invalid(value):
    with pytest.raises(ValueError):
        Function(value)


@pytest.mark.parametrize(
    'value', [Mode.IMMEDIATE, None, 'imm', 'immediate', 'IMM', 'IMMEDIATE'])
def test_trigger_imm(value):
    assert Mode(value) == Mode.IMMEDIATE


@pytest.mark.parametrize(
    'value', [Mode.BUS, 'bus', 'Bus', 'command', 'comm', 'COMMAND', 'COMM'])
def test_trigger_imm(value):
    assert Mode(value) == Mode.BUS


@pytest.mark.parametrize('value', [0, 1.5, 'invalid'])
def test_trigger_invalid(value):
    with pytest.raises(ValueError):
        Mode(value)


def test_settings():
    def assert_all(s):
        assert isinstance(s.auto_range, Auto)
        assert s.auto_range == Auto.ON
        assert isinstance(s.auto_zero, Auto)
        assert s.auto_zero == Auto.ONCE
        assert isinstance(s.function, Function)
        assert s.function == Function.DCI
        assert isinstance(s.nplc, float)
        assert s.nplc == 1.0
        assert isinstance(s.nsamples, int)
        assert s.nsamples == 20
        assert isinstance(s.range, float)
        assert s.range == 3.0
        assert isinstance(s.trigger, Trigger)
        assert isinstance(s.trigger.auto_delay, bool)
        assert s.trigger.auto_delay is False
        assert isinstance(s.trigger.count, int)
        assert s.trigger.count == 5
        assert isinstance(s.trigger.delay, float)
        assert s.trigger.delay == 0.0
        assert isinstance(s.trigger.edge, Edge)
        assert s.trigger.edge == Edge.RISING
        assert isinstance(s.trigger.mode, Mode)
        assert s.trigger.mode == Mode.EXTERNAL

    trigger = Trigger(auto_delay=False, count=5, delay=0, edge='positive', mode='external')
    settings = Settings(auto_range=True, auto_zero=2, function='dci', nplc=1,
                        nsamples=20, range=3, trigger=trigger)

    assert_all(settings)

    settings2 = Settings(**json.loads(json.dumps(settings.to_json())))
    assert_all(settings2)


@pytest.mark.parametrize('value', [Range.AUTO, 'auto', 'Auto', 'AUTO'])
def test_range_auto(value):
    assert Range(value) == Range.AUTO


@pytest.mark.parametrize('value', [Range.MINIMUM, 'min', 'Min', 'minimum', 'Minimum'])
def test_range_minimum(value):
    assert Range(value) == Range.MINIMUM


@pytest.mark.parametrize('value', [Range.MAXIMUM, 'max', 'Max', 'maximum', 'Maximum'])
def test_range_maximum(value):
    assert Range(value) == Range.MAXIMUM


@pytest.mark.parametrize('value', [Range.DEFAULT, 'def', 'Def', 'default', 'Default'])
def test_range_default(value):
    assert Range(value) == Range.DEFAULT


@pytest.mark.parametrize('value', [None, 0, 1.5, 'invalid'])
def test_range_invalid(value):
    with pytest.raises(ValueError):
        Range(value)
