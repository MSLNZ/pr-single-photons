# -*- coding: utf-8 -*-
import json
import locale
import math
import sys

import numpy as np
import pytest

from photons import Samples
from photons.samples import Format
from photons.samples import order_of_magnitude
from photons.samples import parse
from photons.samples import si_prefix_factor

original_loc = locale.setlocale(locale.LC_NUMERIC)


@pytest.mark.parametrize(
    'samples',
    ['1,2,3',
     '1,2,3\r',
     '1,2,3\n',
     '1,2,3\r\n',
     '1,  2.0,      3.000000',
     ['1', '2', '3'],
     ['1', '2', '3\r'],
     ['1', '2', '3\n'],
     ['1', '2', '3\r\n'],
     ['1', '  2.0', '      3.000000'],
     [1, 2, 3],
     [1.0, 2.0, 3.0],
     (1, 2, 3),
     {1, 2, 3},
     {1: 'a', 2: 'b', 3: 'c'},
     np.array([1.0, 2.0, 3.0])])
def test_types(samples):
    s = Samples(samples)
    assert np.array_equal(s.samples, np.array([1.0, 2.0, 3.0]))
    assert s.samples.dtype == np.float64


@pytest.mark.parametrize('samples', [True, 1, 1.0, 1.0j])
def test_not_iterable(samples):
    with pytest.raises(TypeError, match='not iterable'):
        Samples(samples)


def test_wrong_dimensions():
    with pytest.raises(ValueError, match='only 1D arrays are allowed'):
        Samples(np.empty((10, 2)))


def test_kwargs():
    # if mean, std or size is specified then they must be a keyword argument
    with pytest.raises(TypeError, match='1 to 2 positional arguments'):
        Samples(np.arange(10), 1.0)
    with pytest.raises(TypeError, match='1 to 2 positional arguments'):
        Samples(np.arange(10), 1.0, 1.0)
    with pytest.raises(TypeError, match='1 to 2 positional arguments'):
        Samples(np.arange(10), 1.0, 1.0, 1.0)
    with pytest.raises(TypeError, match='1 to 2 positional arguments'):
        Samples(np.arange(10), 1.0, mean=1.0)
    with pytest.raises(TypeError, match='1 to 2 positional arguments'):
        Samples(np.arange(10), 1.0, std=1.0)
    with pytest.raises(TypeError, match='1 to 2 positional arguments'):
        Samples(np.arange(10), 1.0, size=1)

    # specifying overload is okay
    Samples(np.arange(10), overload=1)


def test_ndarray_attrib():
    s = Samples(range(10))
    assert s.max() == 9
    assert s.min() == 0
    assert s.dtype == np.float64


@pytest.mark.parametrize(
    ('samples', 'mean', 'std', 'size'),
    [([0], 0.0, 0.0, 0),
     ([0], None, 0.0, 0),
     ([0], 0.0, None, 0),
     ([], 0.0, 0.0, None),
     ([], None, None, 0),
     ([], None, 0.0, None),
     ([], 0.0, None, None)])
def test_sample_mean_std_size(samples, mean, std, size):
    with pytest.raises(ValueError, match='Cannot specify samples and the mean, std or size'):
        Samples(samples, mean=mean, std=std, size=size)


def test_mean_std(recwarn):
    s = Samples()
    assert isinstance(s.mean, float)
    assert isinstance(s.std, float)
    assert isinstance(s.relative_std, float)
    assert s.samples.size == 0
    assert math.isnan(s.mean)
    assert math.isnan(s.std)
    assert math.isnan(s.stdom)
    assert math.isnan(s.relative_std)
    assert math.isnan(s.variance)

    for samples in [[], (), {}, '', '\r', '\r\n']:
        s = Samples(samples)
        assert s.samples.size == 0
        assert math.isnan(s.mean)
        assert math.isnan(s.std)
        assert math.isnan(s.stdom)
        assert math.isnan(s.relative_std)
        assert math.isnan(s.variance)

    for samples in [[1], '1']:
        s = Samples(samples)
        assert np.array_equal(s.samples, np.array([1.0]))
        assert s.mean == 1.0
        assert math.isnan(s.std)
        assert math.isnan(s.stdom)
        assert math.isnan(s.relative_std)
        assert math.isnan(s.variance)

    s = Samples(range(10))
    assert s.mean == pytest.approx(4.5)
    assert s.std == pytest.approx(3.02765035409749)
    assert s.stdom == pytest.approx(0.9574271077563375)
    assert s.relative_std == pytest.approx(67.2811189799443)
    assert s.variance == pytest.approx(9.166666666666655)

    s = Samples(mean=9.9)
    assert s.samples.size == 0
    assert s.mean == 9.9
    assert math.isnan(s.std)
    assert math.isnan(s.stdom)
    assert math.isnan(s.relative_std)
    assert math.isnan(s.variance)

    s = Samples(std=9.9)
    assert s.samples.size == 0
    assert math.isnan(s.mean)
    assert s.std == 9.9
    assert math.isnan(s.relative_std)
    assert math.isnan(s.stdom)
    assert s.variance == 9.9 ** 2

    s = Samples(mean=9.9, std=1.1)
    assert s.samples.size == 0
    assert s.mean == 9.9
    assert s.std == 1.1
    assert s.relative_std == 100.0 * (1.1 / 9.9)
    assert s.variance == 1.1 ** 2

    s = Samples(mean=0.0, std=1.0)
    assert s.samples.size == 0
    assert s.mean == 0.0
    assert s.std == 1.0
    assert math.isnan(s.stdom)
    assert math.isnan(s.relative_std)
    assert s.variance == 1.0

    for mean in (100, -100):
        s = Samples(mean=mean, overload=99)
        assert s.samples.size == 0
        assert math.isnan(s.mean)
        assert math.isnan(s.std)
        assert math.isnan(s.stdom)
        assert math.isnan(s.relative_std)
        assert math.isnan(s.variance)

    s = Samples(mean=1e100, std=1e99, overload=math.inf)
    assert s.samples.size == 0
    assert s.mean == 1e100
    assert s.std == 1e99
    assert math.isnan(s.stdom)
    assert s.relative_std == 10.
    assert s.variance == 1e99 * 1e99

    assert len(recwarn) == 0


@pytest.mark.parametrize(
    ('arg', 'kwargs', 'expected'),
    [((), {}, 'Samples(mean=nan, std=nan, size=0)'),
     ([1], {}, 'Samples(mean=1.0, std=nan, size=1)'),
     (None, {'mean': 9.9, 'std': 1.1}, 'Samples(mean=9.9, std=1.1, size=0)'),
     ([2]*10, {}, 'Samples(mean=2.0, std=0.0, size=10)'),
     ])
def test_repr_str(arg, kwargs, expected):
    s = Samples(arg, **kwargs)
    assert repr(s) == expected
    assert str(s) == expected
    assert f'{s!r}' == expected
    assert f'{s!s}' == expected


@pytest.mark.parametrize(
    'format_spec',
    ['A',  # invalid <type> or <fill> without <align>
     '-5.2A',  # invalid <type>
     '.',  # <decimal> without <precision>
     '2.f',  # <decimal> without <precision>
     '===',  # multiple <fill> characters
     '**<.4G',  # multiple <fill> characters
     '<<<.4G',  # multiple <fill> characters
     '#+.2f',  # <hash> before <sign>
     '0#.2f',  # <digit> before <hash>
     ',3.2f',  # <grouping> before <width>
     '0-.4G',  # <sign> after <zero>
     '#-.4G',  # <sign> after <hash>
     '=7^2,.3f',  # <width> before <align>
     '=^20,3f',  # <width> after <grouping> or forgot the <decimal> before <precision>
     '!5.2f',  # invalid <sign> character
     '5!.2f',  # invalid <grouping> character
     '!.2f',  # <fill> without <align> or invalid <sign> character
     '5.2fA',  # invalid <option> character and too many builtin fields
     'BP',  # two modes specified
     'LU',  # two styles specified
     'SB',  # <si> before <mode>
     'SL',  # <si> before <style>
     'Sf',  # <si> before <type>
     ])
def test_parse_raises(format_spec):
    with pytest.raises(ValueError):
        parse(format_spec)


def test_parse():
    # also call the builtin format(float, format_spec) to verify
    # that the formatting.parse function is okay
    def _parse(format_spec, check=True):
        if check:  # must ignore for the custom fields
            format(1.0, format_spec)
        return parse(format_spec)

    def expect(**kwargs):
        out = {
            'fill': None, 'align': None, 'sign': None, 'hash': None,
            'zero': None, 'width': None, 'grouping': None, 'precision': None,
            'type': None, 'mode': None, 'style': None, 'si': None
        }
        out.update(**kwargs)
        return out

    # check the builtin-supported fields
    assert _parse('G') == expect(type='G')
    assert _parse('=') == expect(align='=')
    assert _parse(' =') == expect(fill=' ', align='=')
    assert _parse('<<') == expect(fill='<', align='<')
    assert _parse(' 10.1') == expect(sign=' ', width='10', precision='1')
    assert _parse('0') == expect(zero='0')
    assert _parse('0.0') == expect(zero='0', precision='0')
    assert _parse('02') == expect(zero='0', width='2')
    assert _parse('02.0') == expect(zero='0', width='2', precision='0')
    assert _parse('.10') == expect(precision='10')
    assert _parse('07.2f') == expect(zero='0', width='7', precision='2', type='f')
    assert _parse('*<-06,.4E') == expect(
        fill='*', align='<', sign='-', zero='0', width='6', grouping=',',
        precision='4', type='E')

    # custom fields
    assert _parse('B', False) == expect(mode='B')
    assert _parse('U', False) == expect(style='U')
    assert _parse('S', False) == expect(si='S')
    assert _parse('GB', False) == expect(type='G', mode='B')
    assert _parse('GBL', False) == expect(type='G', mode='B', style='L')
    assert _parse('.2U', False) == expect(precision='2', style='U')
    assert _parse('9P', False) == expect(width='9', mode='P')
    assert _parse('.7', False) == expect(precision='7')
    assert _parse('e', False) == expect(type='e')
    assert _parse('.2f', False) == expect(precision='2', type='f')
    assert _parse('.2fP', False) == expect(precision='2', type='f', mode='P')
    assert _parse(' ^16.4fL', False) == expect(
        fill=' ', align='^', width='16', precision='4', type='f', style='L')
    assert _parse('^^03S', False) == expect(
        fill='^', align='^', zero='0', width='3', si='S')
    assert _parse('^^03BUS', False) == expect(
        fill='^', align='^', zero='0', width='3', mode='B', style='U', si='S')
    assert _parse('^^03gBS', False) == expect(
        fill='^', align='^', zero='0', width='3', type='g', mode='B', si='S')
    assert _parse('^^03gB', False) == expect(
        fill='^', align='^', zero='0', width='3', type='g', mode='B')
    assert _parse('*> #011,.2gL', False) == expect(
        fill='*', align='>', sign=' ', hash='#', zero='0', width='11', grouping=',',
        precision='2', type='g', style='L')


def test_format_class():
    f = Format(**parse(''))
    assert repr(f) == "Format(format_spec='.2fB')"
    assert str(f) == "Format(format_spec='.2fB')"
    assert f.digits == 2

    f = Format(**parse('*> #020,.3gPL'))
    assert repr(f) == "Format(format_spec='*> #020,.3gPL')"
    assert f.digits == 3

    f = Format(**parse('+10eS'))
    assert repr(f) == "Format(format_spec='+10.2eBS')"
    assert f.digits == 2

    f = Format(**parse('.1U'))
    assert repr(f) == "Format(format_spec='.1fBU')"
    assert f.digits == 1

    f = Format(**parse(''))
    number = 123.456789
    assert f.value(number, precision=4, type='f', sign=' ') == f'{number: .4f}'

    f = Format(**parse('+.4'))
    number = 123.456789
    assert f.value(number), f'{number:+.4f}'

    f = Format(**parse('*>+20.4'))
    number = 123.456789
    assert f.result(f.value(number)) == f'{number:*>+20.4f}'

    f = Format(**parse('+.4e'))
    number = 123.456789
    assert f.value(number) == f'{number:+.4e}'

    f = Format(**parse(',.0'))
    number = 123456789
    assert f.value(number) == f'{number:,.0f}'


@pytest.mark.parametrize(
    ('value', 'expected'),
    [(0.000000000000000123456789, -16),
     (0.00000000000000123456789, -15),
     (0.0000000000000123456789, -14),
     (0.000000000000123456789, -13),
     (0.00000000000123456789, -12),
     (0.0000000000123456789, -11),
     (0.000000000123456789, -10),
     (0.00000000123456789, -9),
     (0.0000000123456789, -8),
     (0.000000123456789, -7),
     (0.00000123456789, -6),
     (0.0000123456789, -5),
     (0.000123456789, -4),
     (0.00123456789, -3),
     (0.0123456789, -2),
     (0.123456789, -1),
     (0, 0),
     (1.23456789, 0),
     (12.3456789, 1),
     (123.456789, 2),
     (1234.56789, 3),
     (12345.6789, 4),
     (123456.789, 5),
     (1234567.89, 6),
     (12345678.9, 7),
     (123456789., 8),
     (1234567890., 9),
     (12345678900., 10),
     (123456789000., 11),
     (1234567890000., 12),
     (12345678900000., 13),
     (123456789000000., 14),
     (1234567890000000., 15),
     (12345678900000000., 16)])
def test_order_of_magnitude(value, expected):
    assert order_of_magnitude(value) == expected
    assert order_of_magnitude(-value) == expected


def test_nan_inf():
    s = Samples(mean=np.inf, std=np.inf)
    assert f'{s}' == 'inf(inf)'
    assert f'{s:B}' == 'inf(inf)'
    assert f'{s:P}' == 'inf+/-inf'
    for t in ['f', 'g', 'e']:
        assert f'{s:{t}}' == 'inf(inf)'
    for t in ['F', 'G', 'E']:
        assert f'{s:{t}}' == 'INF(INF)'
    for t in ['f', 'g', 'e']:
        assert f'{s:{t}P}' == 'inf+/-inf'
    for t in ['F', 'G', 'E']:
        assert f'{s:{t}P}' == 'INF+/-INF'

    s = Samples(mean=np.inf, std=np.nan)
    assert f'{s}' == 'inf(nan)'
    assert f'{s:B}' == 'inf(nan)'
    assert f'{s:P}' == 'inf+/-nan'
    for t in ['f', 'g', 'e']:
        assert f'{s:{t}}' == 'inf(nan)'
    for t in ['F', 'G', 'E']:
        assert f'{s:{t}}' == 'INF(NAN)'
    for t in ['f', 'g', 'e']:
        assert f'{s:{t}P}' == 'inf+/-nan'
    for t in ['F', 'G', 'E']:
        assert f'{s:{t}P}' == 'INF+/-NAN'

    s = Samples(mean=-np.inf, std=np.nan)
    assert f'{s}' == '-inf(nan)'
    assert f'{s:B}' == '-inf(nan)'
    assert f'{s:P}' == '-inf+/-nan'
    for t in ['f', 'g', 'e']:
        assert f'{s:{t}}' == '-inf(nan)'
    for t in ['F', 'G', 'E']:
        assert f'{s:{t}}' == '-INF(NAN)'
    for t in ['f', 'g', 'e']:
        assert f'{s:{t}P}' == '-inf+/-nan'
    for t in ['F', 'G', 'E']:
        assert f'{s:{t}P}' == '-INF+/-NAN'

    s = Samples(mean=np.nan, std=np.inf)
    assert f'{s}' == 'nan(inf)'
    assert f'{s:B}' == 'nan(inf)'
    assert f'{s:P}' == 'nan+/-inf'
    for t in ['f', 'g', 'e']:
        assert f'{s:{t}}' == 'nan(inf)'
    for t in ['F', 'G', 'E']:
        assert f'{s:{t}}' == 'NAN(INF)'
    for t in ['f', 'g', 'e']:
        assert f'{s:{t}P}' == 'nan+/-inf'
    for t in ['F', 'G', 'E']:
        assert f'{s:{t}P}' == 'NAN+/-INF'

    s = Samples()
    assert f'{s}' == 'nan(nan)'
    assert f'{s:B}' == 'nan(nan)'
    assert f'{s:P}' == 'nan+/-nan'
    for t in ['f', 'g', 'e']:
        assert f'{s:{t}}' == 'nan(nan)'
    for t in ['F', 'G', 'E']:
        assert f'{s:{t}}' == 'NAN(NAN)'
    for t in ['f', 'g', 'e']:
        assert f'{s:{t}P}' == 'nan+/-nan'
    for t in ['F', 'G', 'E']:
        assert f'{s:{t}P}' == 'NAN+/-NAN'

    s = Samples(mean=3.14159)
    assert f'{s}' == '3.14(nan)'
    assert f'{s:B}' == '3.14(nan)'
    assert f'{s:P}' == '3.14+/-nan'
    assert f'{s:f}' == '3.14(nan)'
    assert f'{s:e}' == '3.14(nan)e+00'
    assert f'{s:g}' == '3.1(nan)'
    assert f'{s:F}' == '3.14(NAN)'
    assert f'{s:E}' == '3.14(NAN)E+00'
    assert f'{s:G}' == '3.1(NAN)'
    assert f'{s:fP}' == '3.14+/-nan'
    assert f'{s:eP}' == '(3.14+/-nan)e+00'
    assert f'{s:gP}' == '3.1+/-nan'
    assert f'{s:FP}' == '3.14+/-NAN'
    assert f'{s:EP}' == '(3.14+/-NAN)E+00'
    assert f'{s:GP}' == '3.1+/-NAN'
    assert f'{s:.4f}' == '3.1416(nan)'
    assert f'{s:.4e}' == '3.1416(nan)e+00'
    assert f'{s:.4g}' == '3.142(nan)'
    assert f'{s:.4F}' == '3.1416(NAN)'
    assert f'{s:.4E}' == '3.1416(NAN)E+00'
    assert f'{s:.4G}' == '3.142(NAN)'
    assert f'{s:.4fP}' == '3.1416+/-nan'
    assert f'{s:.4eP}' == '(3.1416+/-nan)e+00'
    assert f'{s:.4gP}' == '3.142+/-nan'
    assert f'{s:.4FP}' == '3.1416+/-NAN'
    assert f'{s:.4EP}' == '(3.1416+/-NAN)E+00'
    assert f'{s:.4GP}' == '3.142+/-NAN'
    assert f'{s:.4}' == '3.1416(nan)'
    assert f'{s:.4B}' == '3.1416(nan)'
    assert f'{s:.4P}' == '3.1416+/-nan'

    s = Samples(mean=3.141e8, std=np.inf)
    assert f'{s}' == '314100000.00(inf)'
    assert f'{s: .1F}' == ' 314100000.0(INF)'
    assert f'{s: .1e}' == ' 3.1(inf)e+08'
    assert f'{s: .4E}' == ' 3.1410(INF)E+08'
    assert f'{s: .1FP}' == ' 314100000.0+/-INF'
    assert f'{s:.1eP}' == '(3.1+/-inf)e+08'
    assert f'{s: .4EP}' == '( 3.1410+/-INF)E+08'

    s = Samples(mean=3.141, std=np.nan)
    assert f'{s}' == '3.14(nan)'
    assert f'{s: F}' == ' 3.14(NAN)'
    assert f'{s:.1F}' == '3.1(NAN)'
    assert f'{s:.1FP}' == '3.1+/-NAN'

    s = Samples(mean=np.nan, std=3.141)
    assert f'{s}' == 'nan(3.141)'
    assert f'{s:P}' == 'nan+/-3.141'
    assert f'{s: F}' == ' NAN(3.141)'

    s = Samples(mean=np.nan, std=3.141e8)
    assert f'{s}' == 'nan(314100000)'
    assert f'{s:P}' == 'nan+/-314100000'
    assert f'{s: E}' == ' NAN(3)E+08'
    assert f'{s:+e}' == '+nan(3)e+08'
    assert f'{s: EP}' == '( NAN+/-3)E+08'
    assert f'{s:+eP}' == '(+nan+/-3)e+08'

    s = Samples(mean=1.8667540e8)
    assert f'{s:.3S}' == '187(nan) M'
    assert f'{s:.3PS}' == '187+/-nan M'

    s = Samples(mean=1.8667540e4)
    assert f'{s:S}' == '19(nan) k'
    assert f'{s:.6PS}' == '18.6675+/-nan k'

    s = Samples(mean=1.8667540e-6)
    assert f'{s:.1US}' == '2(nan) µ'
    assert f'{s: .2PS}' == ' 1.9+/-nan u'
    assert f'{s:.5PUS}' == '1.8668±nan µ'


def test_bracket_type_f():
    s = Samples(mean=1.23456789, std=0.0123456789)
    assert f'{s:.1}' == '1.23(1)'
    assert f'{s:.2f}' == '1.235(12)'
    assert f'{s:.3}' == '1.2346(123)'
    assert f'{s:.9F}' == '1.2345678900(123456789)'
    assert f'{s:.14f}' == '1.234567890000000(12345678900000)'

    factor = 10 ** -20
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:> 39.4f}' == '      0.0000000000000000000123457(1235)'

    factor = 10 ** -19
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:> 39.4f}' == '       0.000000000000000000123457(1235)'

    factor = 10 ** -18
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:< 39.4f}' == ' 0.00000000000000000123457(1235)       '

    factor = 10 ** -12
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:-^39.4f}' == '-------0.00000000000123457(1235)-------'

    factor = 10 ** -6
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:19.4f}' == '0.00000123457(1235)'

    s = Samples(mean=1.23456789, std=0.0123456789)
    assert f'{s:> 15.4f}' == '  1.23457(1235)'

    factor = 10 ** 1
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:> 15.4f}' == '  12.3457(1235)'

    factor = 10 ** 2
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:> 15.4f}' == ' 123.457(1.235)'

    factor = 10 ** 3
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:> 15.4f}' == ' 1234.57(12.35)'

    factor = 10 ** 4
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:> 15.4f}' == ' 12345.7(123.5)'

    factor = 10 ** 5
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:> 15.4f}' == '   123457(1235)'

    factor = 10 ** 6
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s: >+20.4f}' == '     +1234570(12350)'

    factor = 10 ** 7
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:> 16.4f}' == ' 12345700(123500)'

    factor = 10 ** 8
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:.4}' == '123457000(1235000)'

    factor = 10 ** 18
    s = Samples(mean=1.23456789 * factor, std=0.0123456789 * factor)
    assert f'{s:.4}' == '1234570000000000000(12350000000000000)'

    s = Samples(mean=1.23456789, std=1234.56789)
    assert f'{s: .2}' == ' 0(1200)'

    s = Samples(mean=1.23456789, std=123.456789)
    assert f'{s:.2}' == '0(120)'

    s = Samples(mean=1.23456789, std=12.3456789)
    assert f'{s: }' == ' 1(12)'

    s = Samples(mean=1.23456789, std=1.23456789)
    assert f'{s:}' == '1.2(1.2)'

    s = Samples(mean=1.23456789, std=0.123456789)
    assert f'{s}' == '1.23(12)'

    s = Samples(mean=1.23456789, std=0.0123456789)
    assert f'{s}' == '1.235(12)'

    s = Samples(mean=1.23456789, std=0.00123456789)
    assert f'{s}' == '1.2346(12)'

    s = Samples(mean=1.23456789, std=0.000123456789)
    assert f'{s}' == '1.23457(12)'

    s = Samples(mean=1.23456789, std=0.000000123456789)
    assert f'{s}' == '1.23456789(12)'

    s = Samples(mean=1.23456789, std=0.000000000123456789)
    assert f'{s}' == '1.23456789000(12)'

    s = Samples(mean=1.23456789e-4, std=0.000000000123456789)
    assert f'{s}' == '0.00012345679(12)'

    s = Samples(mean=1.23456789e4, std=0.000000123456789)
    assert f'{s}' == '12345.67890000(12)'

    s = Samples(mean=1.23456789, std=0.0123456789)
    assert f'{s:.1}' == '1.23(1)'

    s = Samples(mean=1.23456789, std=0.0123456789)
    assert f'{s}' == '1.235(12)'

    s = Samples(mean=123456789., std=1234.56789)
    assert f'{s:.6e}' == '1.2345678900(123457)e+08'
    assert f'{s:.1f}' == '123457000(1000)'

    s = Samples(mean=1.23456789, std=0.12345)
    assert f'{s:.1}' == '1.2(1)'
    assert f'{s:.4}' == '1.2346(1235)'

    s = Samples(mean=1.23456789, std=0.945)
    assert f'{s:.1f}' == '1.2(9)'

    s = Samples(mean=-1.23456789, std=0.945)
    assert f'{s:.2f}' == '-1.23(94)'

    s = Samples(mean=1.23456789, std=0.95)
    assert f'{s:.1}' == '1.2(9)'
    assert f'{s:+.3f}' == '+1.235(950)'

    s = Samples(mean=1.23456789, std=0.951)
    assert f'{s:.1f}' == '1(1)'
    assert f'{s:.2f}' == '1.23(95)'
    assert f'{s:.3f}' == '1.235(951)'

    s = Samples(mean=1.23456789, std=0.999999999999)
    assert f'{s:.1}' == '1(1)'
    assert f'{s:.2}' == '1.2(1.0)'
    assert f'{s:.5}' == '1.2346(1.0000)'

    s = Samples(mean=1.23456789, std=1.5)
    assert f'{s:.1}' == '1(2)'

    s = Samples(mean=1.23456789, std=9.5)
    assert f'{s:.1f}' == '0(10)'

    s = Samples(mean=1.23456789, std=10.00)
    assert f'{s:.1f}' == '0(10)'

    s = Samples(mean=123.456789, std=0.321)
    assert f'{s:.1f}' == '123.5(3)'
    assert f'{s}' == '123.46(32)'

    s = Samples(mean=123.456789, std=0.95)
    assert f'{s:.1}' == '123.5(9)'
    assert f'{s:.3f}' == '123.457(950)'

    s = Samples(mean=123.456789, std=0.951)
    assert f'{s:.1}' == '123(1)'
    assert f'{s:.4}' == '123.4568(9510)'

    s = Samples(mean=123.456789, std=0.999999999999999)
    assert f'{s:.1f}' == '123(1)'

    s = Samples(mean=-123.456789, std=0.999999999999999)
    assert f'{s:.6}' == '-123.45679(1.00000)'

    s = Samples(mean=0.9876, std=0.1234)
    assert f'{s:.1f}' == '1.0(1)'
    assert f'{s:.3f}' == '0.988(123)'

    s = Samples(mean=0.000003512, std=0.00000006551)
    assert f'{s:.1}' == '0.00000351(7)'
    assert f'{s}' == '0.000003512(66)'

    s = Samples(mean=0.000003512, std=0.0000008177)
    assert f'{s:.1f}' == '0.0000035(8)'
    assert f'{s:.3}' == '0.000003512(818)'

    s = Samples(mean=0.000003512, std=0.000009773)
    assert f'{s:.1}' == '0.00000(1)'
    assert f'{s:.4}' == '0.000003512(9773)'

    s = Samples(mean=0.000003512, std=0.00001241)
    assert f'{s:.1}' == '0.00000(1)'
    assert f'{s}' == '0.000004(12)'

    s = Samples(mean=0.000003512, std=0.0009998)
    assert f'{s:.1}' == '0.000(1)'
    assert f'{s:.4f}' == '0.0000035(9998)'

    s = Samples(mean=0.000003512, std=0.006563)
    assert f'{s:.1f}' == '0.000(7)'
    assert f'{s:}' == '0.0000(66)'

    s = Samples(mean=0.000003512, std=0.09564)
    assert f'{s:.1}' == '0.0(1)'
    assert f'{s:.4f}' == '0.00000(9564)'

    s = Samples(mean=0.000003512, std=0.7772)
    assert f'{s:.1}' == '0.0(8)'

    s = Samples(mean=0.000003512, std=9.75)
    assert f'{s:.1}' == '0(10)'

    s = Samples(mean=0.000003512, std=33.97)
    assert f'{s:.1}' == '0(30)'

    s = Samples(mean=0.000003512, std=715.5)
    assert f'{s:.1}' == '0(700)'
    assert f'{s:.5f}' == '0.00(715.50)'

    s = Samples(mean=0.07567, std=0.00000007018)
    assert f'{s:.1f}' == '0.07567000(7)'
    assert f'{s:.5}' == '0.075670000000(70180)'

    s = Samples(mean=0.07567, std=0.0000003645)
    assert f'{s:.1}' == '0.0756700(4)'

    s = Samples(mean=-0.07567, std=0.0000003645)
    assert f'{s:.3f}' == '-0.075670000(365)'

    s = Samples(mean=0.07567, std=0.000005527)
    assert f'{s:.1}' == '0.075670(6)'
    assert f'{s: .2F}' == ' 0.0756700(55)'

    s = Samples(mean=0.07567, std=0.00004429)
    assert f'{s:.1f}' == '0.07567(4)'
    assert f'{s}' == '0.075670(44)'

    s = Samples(mean=0.07567, std=0.0008017)
    assert f'{s:.1}' == '0.0757(8)'
    assert f'{s:.3}' == '0.075670(802)'

    s = Samples(mean=0.07567, std=0.006854)
    assert f'{s:.1}' == '0.076(7)'
    assert f'{s:.4}' == '0.075670(6854)'

    s = Samples(mean=0.07567, std=0.06982)
    assert f'{s:.1}' == '0.08(7)'
    assert f'{s}' == '0.076(70)'

    s = Samples(mean=0.07567, std=0.7382)
    assert f'{s:.1}' == '0.1(7)'
    assert f'{s:.3}' == '0.076(738)'

    s = Samples(mean=0.07567, std=7.436)
    assert f'{s:.1}' == '0(7)'
    assert f'{s}' == '0.1(7.4)'

    s = Samples(mean=0.07567, std=48.75)
    assert f'{s:.1}' == '0(50)'
    assert f'{s:.3}' == '0.1(48.8)'

    s = Samples(mean=0.07567, std=487.9)
    assert f'{s:.1}' == '0(500)'
    assert f'{s:.5f}' == '0.08(487.90)'

    s = Samples(mean=8.545, std=0.00000007513)
    assert f'{s:.1}' == '8.54500000(8)'
    assert f'{s}' == '8.545000000(75)'

    s = Samples(mean=8.545, std=0.000009935)
    assert f'{s:.1}' == '8.54500(1)'
    assert f'{s:.2}' == '8.5450000(99)'

    s = Samples(mean=8.545, std=0.003243)
    assert f'{s:.1}' == '8.545(3)'
    assert f'{s:.3}' == '8.54500(324)'

    s = Samples(mean=8.545, std=0.0812)
    assert f'{s:.1}' == '8.54(8)'
    assert f'{s}' == '8.545(81)'

    s = Samples(mean=8.545, std=0.4293)
    assert f'{s:.1}' == '8.5(4)'
    assert f'{s:.4}' == '8.5450(4293)'

    s = Samples(mean=8.545, std=6.177)
    assert f'{s:.1}' == '9(6)'
    assert f'{s:.2}' == '8.5(6.2)'
    assert f'{s:.3}' == '8.54(6.18)'
    assert f'{s:.4}' == '8.545(6.177)'
    assert f'{s:.7}' == '8.545000(6.177000)'

    s = Samples(mean=8.545, std=26.02)
    assert f'{s:.1}' == '10(30)'
    assert f'{s:.3}' == '8.5(26.0)'

    s = Samples(mean=8.545, std=406.1)
    assert f'{s:.1}' == '0(400)'
    assert f'{s:.3}' == '9(406)'

    s = Samples(mean=8.545, std=3614.0)
    assert f'{s:.1}' == '0(4000)'
    assert f'{s:.5f}' == '8.5(3614.0)'

    s = Samples(mean=89.95, std=0.00000006815)
    assert f'{s:.1}' == '89.95000000(7)'
    assert f'{s:.4}' == '89.95000000000(6815)'

    s = Samples(mean=89.95, std=0.0000002651)
    assert f'{s:.1}' == '89.9500000(3)'
    assert f'{s}' == '89.95000000(27)'

    s = Samples(mean=89.95, std=0.0001458)
    assert f'{s:.1}' == '89.9500(1)'
    assert f'{s:.4f}' == '89.9500000(1458)'

    s = Samples(mean=89.95, std=0.009532)
    assert f'{s:.1}' == '89.95(1)'
    assert f'{s}' == '89.9500(95)'

    s = Samples(mean=89.95, std=0.09781)
    assert f'{s:.1}' == '90.0(1)'
    assert f'{s:.2f}' == '89.950(98)'

    s = Samples(mean=89.95, std=0.7335)
    assert f'{s:.1}' == '90.0(7)'
    assert f'{s:.2}' == '89.95(73)'
    assert f'{s:.3}' == '89.950(734)'

    s = Samples(mean=89.95, std=3.547)
    assert f'{s:.1}' == '90(4)'
    assert f'{s:.2}' == '90.0(3.5)'
    assert f'{s:.3}' == '89.95(3.55)'
    assert f'{s:.4}' == '89.950(3.547)'

    s = Samples(mean=89.95, std=31.4)
    assert f'{s:.1}' == '90(30)'
    assert f'{s:.2f}' == '90(31)'
    assert f'{s:.3}' == '90.0(31.4)'

    s = Samples(mean=89.95, std=623.1)
    assert f'{s:.1}' == '100(600)'
    assert f'{s}' == '90(620)'

    s = Samples(mean=89.95, std=2019.0)
    assert f'{s:.1}' == '0(2000)'
    assert f'{s:.3}' == '90(2020)'

    s = Samples(mean=89.95, std=94600.0)
    assert f'{s:.1}' == '0(90000)'
    assert f'{s:.3}' == '100(94600)'

    s = Samples(mean=58740.0, std=0.00000001402)
    assert f'{s:.1}' == '58740.00000000(1)'
    assert f'{s}' == '58740.000000000(14)'

    s = Samples(mean=58740.0, std=0.000000975)
    assert f'{s:.1}' == '58740.000000(1)'
    assert f'{s}' == '58740.00000000(97)'

    s = Samples(mean=58740.0, std=0.0001811)
    assert f'{s:.1}' == '58740.0000(2)'
    assert f'{s:.4f}' == '58740.0000000(1811)'

    s = Samples(mean=58740.0, std=0.04937)
    assert f'{s:.1}' == '58740.00(5)'
    assert f'{s:.2}' == '58740.000(49)'

    s = Samples(mean=58740.0, std=0.6406)
    assert f'{s:.1}' == '58740.0(6)'
    assert f'{s:.3}' == '58740.000(641)'

    s = Samples(mean=58740.0, std=9.357)
    assert f'{s:.1}' == '58740(9)'
    assert f'{s}' == '58740.0(9.4)'

    s = Samples(mean=58740.0, std=99.67)
    assert f'{s:.1f}' == '58700(100)'
    assert f'{s}' == '58740(100)'
    assert f'{s:.3}' == '58740.0(99.7)'

    s = Samples(mean=58740.0, std=454.6)
    assert f'{s:.1}' == '58700(500)'
    assert f'{s:.3f}' == '58740(455)'

    s = Samples(mean=58740.0, std=1052.0)
    assert f'{s:.1}' == '59000(1000)'
    assert f'{s}' == '58700(1100)'

    s = Samples(mean=58740.0, std=87840.0)
    assert f'{s:.1}' == '60000(90000)'
    assert f'{s:.3f}' == '58700(87800)'

    s = Samples(mean=58740.0, std=5266000.0)
    assert f'{s:.1f}' == '0(5000000)'
    assert f'{s:.4f}' == '59000(5266000)'

    s = Samples(mean=58740.0, std=97769999.0)
    assert f'{s:.1}' == '0(100000000)'
    assert f'{s}' == '0(98000000)'
    assert f'{s:.5}' == '59000(97770000)'


def test_std_is_zero():
    m = 1.23456789
    s = Samples(mean=m, std=0)
    assert f'{s}' == f'{m:.2f}'
    assert f'{s:.4}' == f'{m:.4f}'
    assert f'{s:g}' == f'{m:.2g}'
    assert f'{s:.5g}' == f'{m:.5g}'
    assert f'{s:E}' == f'{m:.2E}'
    assert f'{s:.1E}' == f'{m:.1E}'

    s = Samples(mean=123.456e6, std=0)
    assert f'{s:S}' == '120 M'
    assert f'{s:>+20.4S}' == '            +123.5 M'


def test_bracket_type_e_ureal():
    s = Samples(mean=1.23456789, std=0.0001)
    assert f'{s:.1e}' == '1.2346(1)e+00'
    assert f'{s:.3e}' == '1.234568(100)e+00'

    s = Samples(mean=1.23456789, std=0.96)
    assert f'{s:.1e}' == '1(1)e+00'
    assert f'{s:.2e}' == '1.23(96)e+00'

    s = Samples(mean=1.23456789, std=1.0)
    assert f'{s:.1e}' == '1(1)e+00'
    assert f'{s:.3e}' == '1.23(1.00)e+00'

    s = Samples(mean=123.456789, std=0.1)
    assert f'{s:.1e}' == '1.235(1)e+02'
    assert f'{s:.4e}' == '1.234568(1000)e+02'

    s = Samples(mean=123.456789, std=0.950)
    assert f'{s:.1e}' == '1.235(9)e+02'
    assert f'{s:.2e}' == '1.2346(95)e+02'

    s = Samples(mean=123.456789, std=0.951)
    assert f'{s:.1e}' == '1.23(1)e+02'
    assert f'{s:.3e}' == '1.23457(951)e+02'

    s = Samples(mean=123.456789, std=1.0)
    assert f'{s:.1e}' == '1.23(1)e+02'
    assert f'{s:E}' == '1.235(10)E+02'

    s = Samples(mean=123.456789, std=9.123)
    assert f'{s:.1e}' == '1.23(9)e+02'
    assert f'{s:.4e}' == '1.23457(9123)e+02'

    s = Samples(mean=123.456789, std=9.9)
    assert f'{s:.1e}' == '1.2(1)e+02'
    assert f'{s:e}' == '1.235(99)e+02'

    s = Samples(mean=123.456789, std=94.9)
    assert f'{s:.1e}' == '1.2(9)e+02'
    assert f'{s:.3e}' == '1.235(949)e+02'

    s = Samples(mean=-1.23456789, std=0.0123456789)
    assert f'{s:.1e}' == '-1.23(1)e+00'
    assert f'{s:.5e}' == '-1.234568(12346)e+00'

    s = Samples(mean=1.257e-6, std=0.00007453e-6)
    assert f'{s:.1e}' == '1.25700(7)e-06'
    assert f'{s:+.3E}' == '+1.2570000(745)E-06'

    s = Samples(mean=1.257e-6, std=0.00909262e-6)
    assert f'{s:.1e}' == '1.257(9)e-06'
    assert f'{s:e}' == '1.2570(91)e-06'

    s = Samples(mean=1.257e-6, std=0.1174e-6)
    assert f'{s:.1e}' == '1.3(1)e-06'
    assert f'{s:.3e}' == '1.257(117)e-06'

    s = Samples(mean=1.257e-6, std=7.287e-6)
    assert f'{s:.1e}' == '1(7)e-06'
    assert f'{s:.4e}' == '1.257(7.287)e-06'

    s = Samples(mean=1.257e-6, std=67.27e-6)
    assert f'{s:.1e}' == '0(7)e-05'
    assert f'{s:E}' == '0.1(6.7)E-05'

    s = Samples(mean=1.257e-6, std=124.1e-6)
    assert f'{s:.1e}' == '0(1)e-04'
    assert f'{s:.2e}' == '0.0(1.2)e-04'

    s = Samples(mean=1.257e-6, std=4583.0e-6)
    assert f'{s:.1e}' == '0(5)e-03'
    assert f'{s:.3e}' == '0.00(4.58)e-03'

    s = Samples(mean=1.257e-6, std=74743.0e-6)
    assert f'{s:.1e}' == '0(7)e-02'

    s = Samples(mean=1.257e-6, std=4575432.0e-6)
    assert f'{s:.1e}' == '0(5)e+00'

    s = Samples(mean=7.394e-3, std=0.00002659e-3)
    assert f'{s:.1e}' == '7.39400(3)e-03'
    assert f'{s:.3e}' == '7.3940000(266)e-03'

    s = Samples(mean=7.394e-3, std=0.0007031e-3)
    assert f'{s:.1E}' == '7.3940(7)E-03'
    assert f'{s:e}' == '7.39400(70)e-03'

    s = Samples(mean=7.394e-3, std=0.003659e-3)
    assert f'{s:.1e}' == '7.394(4)e-03'
    assert f'{s:.2e}' == '7.3940(37)e-03'

    s = Samples(mean=7.394e-3, std=0.04227e-3)
    assert f'{s:.1e}' == '7.39(4)e-03'
    assert f'{s:.4e}' == '7.39400(4227)e-03'

    s = Samples(mean=7.394e-3, std=0.9072e-3)
    assert f'{s:.1e}' == '7.4(9)e-03'
    assert f'{s:.3e}' == '7.394(907)e-03'

    s = Samples(mean=7.394e-3, std=4.577e-3)
    assert f'{s:.1e}' == '7(5)e-03'
    assert f'{s:.2e}' == '7.4(4.6)e-03'

    s = Samples(mean=7.394e-3, std=93.41e-3)
    assert f'{s:.1e}' == '1(9)e-02'
    assert f'{s:.3e}' == '0.74(9.34)e-02'

    s = Samples(mean=7.394e-3, std=421.0e-3)
    assert f'{s:.1e}' == '0(4)e-01'
    assert f'{s:e}' == '0.1(4.2)e-01'

    s = Samples(mean=7.394e-3, std=9492.0e-3)
    assert f'{s:.1e}' == '0(9)e+00'
    assert f'{s:.3e}' == '0.01(9.49)e+00'

    s = Samples(mean=7.394e-3, std=39860.0e-3)
    assert f'{s:.1e}' == '0(4)e+01'
    assert f'{s:e}' == '0.0(4.0)e+01'

    s = Samples(mean=2.675e-2, std=0.0000019e-2)
    assert f'{s:.1e}' == '2.675000(2)e-02'
    assert f'{s:.3e}' == '2.67500000(190)e-02'

    s = Samples(mean=2.675e-2, std=0.00975e-2)
    assert f'{s:.1e}' == '2.67(1)e-02'
    assert f'{s:.3e}' == '2.67500(975)e-02'

    s = Samples(mean=2.675e-2, std=0.08942e-2)
    assert f'{s:.1e}' == '2.67(9)e-02'
    assert f'{s:e}' == '2.675(89)e-02'

    s = Samples(mean=2.675e-2, std=0.8453e-2)
    assert f'{s:.1e}' == '2.7(8)e-02'
    assert f'{s:e}' == '2.67(85)e-02'

    s = Samples(mean=2.675e-2, std=8.577e-2)
    assert f'{s:.1e}' == '3(9)e-02'
    assert f'{s:E}' == '2.7(8.6)E-02'
    assert f'{s:.3E}' == '2.67(8.58)E-02'

    s = Samples(mean=2.675e-2, std=12.37e-2)
    assert f'{s:.1e}' == '0(1)e-01'
    assert f'{s:.3e}' == '0.27(1.24)e-01'

    s = Samples(mean=2.675e-2, std=226.5e-2)
    assert f'{s:.1e}' == '0(2)e+00'
    assert f'{s:.4e}' == '0.027(2.265)e+00'

    s = Samples(mean=2.675e-2, std=964900.0e-2)
    assert f'{s:.1e}' == '0(1)e+04'
    assert f'{s:.6e}' == '0.00003(9.64900)e+03'

    s = Samples(mean=0.9767, std=0.00000001084)
    assert f'{s:.1e}' == '9.7670000(1)e-01'
    assert f'{s:.3e}' == '9.767000000(108)e-01'

    s = Samples(mean=0.9767, std=0.0000009797)
    assert f'{s:.1e}' == '9.76700(1)e-01'
    assert f'{s:e}' == '9.7670000(98)e-01'

    s = Samples(mean=0.9767, std=0.004542)
    assert f'{s:.1e}' == '9.77(5)e-01'
    assert f'{s:.5e}' == '9.767000(45420)e-01'

    s = Samples(mean=0.9767, std=0.02781)
    assert f'{s:+.1e}' == '+9.8(3)e-01'

    s = Samples(mean=-0.9767, std=0.02781)
    assert f'{s:.3e}' == '-9.767(278)e-01'

    s = Samples(mean=0.9767, std=0.4764)
    assert f'{s:.1e}' == '1.0(5)e+00'
    assert f'{s:e}' == '9.8(4.8)e-01'
    assert f'{s:.3e}' == '9.77(4.76)e-01'
    assert f'{s:.4e}' == '9.767(4.764)e-01'

    s = Samples(mean=0.9767, std=4.083)
    assert f'{s:.1e}' == '1(4)e+00'
    assert f'{s:.3e}' == '0.98(4.08)e+00'

    s = Samples(mean=0.9767, std=45.14)
    assert f'{s:.1e}' == '0(5)e+01'
    assert f'{s:.4e}' == '0.098(4.514)e+01'

    s = Samples(mean=0.9767, std=692500.)
    assert f'{s:.1e}' == '0(7)e+05'
    assert f'{s:.3e}' == '0.00(6.92)e+05'

    s = Samples(mean=2.952, std=0.00000006986)
    assert f'{s:.1e}' == '2.95200000(7)e+00'
    assert f'{s:.5e}' == '2.952000000000(69860)e+00'

    s = Samples(mean=2.952, std=0.04441)
    assert f'{s:.1e}' == '2.95(4)e+00'
    assert f'{s:.3e}' == '2.9520(444)e+00'

    s = Samples(mean=2.952, std=0.1758)
    assert f'{s:.1e}' == '3.0(2)e+00'
    assert f'{s:.3e}' == '2.952(176)e+00'

    s = Samples(mean=2.952, std=1.331)
    assert f'{s:.1e}' == '3(1)e+00'
    assert f'{s:e}' == '3.0(1.3)e+00'

    s = Samples(mean=2.952, std=34.6)
    assert f'{s:.1e}' == '0(3)e+01'
    assert f'{s:.3e}' == '0.30(3.46)e+01'

    s = Samples(mean=2.952, std=46280.)
    assert f'{s:.1e}' == '0(5)e+04'
    assert f'{s:.5e}' == '0.0003(4.6280)e+04'

    s = Samples(mean=96.34984, std=0.00000002628)
    assert f'{s:.1e}' == '9.634984000(3)e+01'
    assert f'{s:.3e}' == '9.63498400000(263)e+01'

    s = Samples(mean=96.34984, std=0.00008999)
    assert f'{s:.1e}' == '9.634984(9)e+01'
    assert f'{s:.3e}' == '9.63498400(900)e+01'

    s = Samples(mean=96.34984, std=0.3981)
    assert f'{s:.1e}' == '9.63(4)e+01'
    assert f'{s:.4e}' == '9.63498(3981)e+01'

    s = Samples(mean=96.34984, std=7.17)
    assert f'{s:.1e}' == '9.6(7)e+01'
    assert f'{s:.3e}' == '9.635(717)e+01'

    s = Samples(mean=96.34984, std=1074.0)
    assert f'{s:.1e}' == '0(1)e+03'
    assert f'{s:.3e}' == '0.10(1.07)e+03'

    s = Samples(mean=92270.0, std=0.00000004531)
    assert f'{s:.1e}' == '9.227000000000(5)e+04'
    assert f'{s:.3e}' == '9.22700000000000(453)e+04'

    s = Samples(mean=92270., std=0.007862)
    assert f'{s:.1e}' == '9.2270000(8)e+04'
    assert f'{s:e}' == '9.22700000(79)e+04'

    s = Samples(mean=92270., std=0.2076)
    assert f'{s:.1e}' == '9.22700(2)e+04'
    assert f'{s:.3e}' == '9.2270000(208)e+04'

    s = Samples(mean=92270., std=2.202)
    assert f'{s:.1e}' == '9.2270(2)e+04'
    assert f'{s:.3e}' == '9.227000(220)e+04'

    s = Samples(mean=92270., std=49.12)
    assert f'{s:.1e}' == '9.227(5)e+04'
    assert f'{s:.4e}' == '9.227000(4912)e+04'

    s = Samples(mean=92270., std=19990.)
    assert f'{s:.1e}' == '9(2)e+04'
    assert f'{s:.6e}' == '9.22700(1.99900)e+04'

    s = Samples(mean=92270., std=740800.)
    assert f'{s:.1e}' == '1(7)e+05'
    assert f'{s:.3e}' == '0.92(7.41)e+05'

    s = Samples(mean=92270., std=1380000.)
    assert f'{s:.1e}' == '0(1)e+06'
    assert f'{s:.5e}' == '0.0923(1.3800)e+06'

    s = Samples(mean=92270., std=29030000.)
    assert f'{s:.1e}' == '0(3)e+07'
    assert f'{s:.7e}' == '0.009227(2.903000)e+07'


def test_type_g():
    s = Samples(mean=43.842, std=0.0123)
    assert f'{s:.1g}' == '43.84(1)'

    s = Samples(mean=4384.2, std=1.23)
    assert f'{s:.3g}' == '4384.20(1.23)'
    assert f'{s:.1G}' == '4.384(1)E+03'

    s = Samples(mean=123456789., std=1234.56789)
    assert f'{s:.4g}' == '1.23456789(1235)e+08'
    assert f'{s:.2G}' == '1.234568(12)E+08'

    s = Samples(mean=7.2524e-8, std=5.429e-10)
    assert f'{s:.2g}' == '7.252(54)e-08'
    assert f'{s:.1G}' == '7.25(5)E-08'

    s = Samples(mean=7.2524e4, std=5.429e3)
    assert f'{s:.4G}' == '7.2524(5429)E+04'
    assert f'{s:.1g}' == '7.3(5)e+04'


def test_to_json():
    s = json.loads(json.dumps(Samples().to_json()))
    assert math.isnan(s['mean'])
    assert math.isnan(s['std'])
    assert s['size'] == 0
    assert s['overload'] == 1e30

    s = json.loads(json.dumps(Samples(mean=1, std=0.1).to_json()))
    assert s['mean'] == 1.0
    assert s['std'] == 0.1
    assert s['size'] == 0
    assert s['overload'] == 1e30

    s = json.loads(json.dumps(Samples(mean=1, std=0.1, size=10).to_json()))
    assert s['mean'] == 1.0
    assert s['std'] == 0.1
    assert s['size'] == 10
    assert s['overload'] == 1e30

    s = json.loads(json.dumps(Samples('1, 2, 3', overload=10).to_json()))
    assert s['mean'] == 2.0
    assert s['std'] == 1.0
    assert s['size'] == 3
    assert s['overload'] == 10

    s1 = Samples('1, 2, 3', overload=10)
    s2 = Samples(**s1.to_json())
    assert s1.mean == s2.mean
    assert s1.std == s2.std
    assert s1.stdom == s2.stdom
    assert s1.variance == s2.variance
    assert s1.size == s2.size
    assert s1.overload == s2.overload

    s1 = Samples(mean=1.0, std=0.5, size=27, overload=1.0)
    s2 = Samples(**s1.to_json())
    assert s1.mean == 1.0
    assert s1.std == 0.5
    assert s1.size == 27
    assert s1.overload == 1.0
    assert s1.mean == s2.mean
    assert s1.std == s2.std
    assert s1.stdom == s2.stdom
    assert s1.variance == s2.variance
    assert s1.size == s2.size
    assert s1.overload == s2.overload


def test_unicode():
    s = Samples(mean=18.5424, std=0.94271)

    for t in ['f', 'F']:
        assert f'{s:{t}U}' == '18.54(94)'

    for t in ['e', 'E']:
        assert f'{s:{t}U}' == '1.854(94)×10¹'

    s = Samples(mean=1.23456789, std=0.123456789)
    assert f'{s:.3eU}' == '1.235(123)'

    factor = 1e-6
    s = Samples(mean=1.23456789 * factor, std=0.123456789 * factor)
    assert f'{s:.3EU}' == '1.235(123)×10⁻⁶'

    factor = 1e12
    s = Samples(mean=1.23456789 * factor, std=0.123456789 * factor)
    assert f'{s:.3EU}' == '1.235(123)×10¹²'

    factor = 1e100
    s = Samples(mean=1.23456789 * factor, std=0.123456789 * factor)
    assert f'{s:.3eU}' == 'nan(nan)'
    s = Samples(mean=1.23456789 * factor, std=0.123456789 * factor, overload=math.inf)
    assert f'{s:.3eU}' == '1.235(123)×10¹⁰⁰'

    factor = 1e-100
    s = Samples(mean=1.23456789 * factor, std=0.123456789 * factor)
    assert f'{s:.3EU}' == '1.235(123)×10⁻¹⁰⁰'


def test_hash_symbol():
    s = Samples(mean=5.4, std=1.2)
    assert f'{s:#.1}' == '5.(1.)'
    assert f'{s:#}' == '5.4(1.2)'

    s = Samples(mean=1, std=0.001)
    assert f'{s:#.1}' == '1.000(1)'

    s = Samples(mean=1, std=0.1)
    assert f'{s:#.1}' == '1.0(1)'

    s = Samples(mean=1, std=1)
    assert f'{s:.1}' == '1(1)'
    assert f'{s:#.1}' == '1.(1.)'

    s = Samples(mean=1, std=0.9876)
    assert f'{s:#.1}' == '1.(1.)'

    s = Samples(mean=1, std=0.9876)
    assert f'{s:#.2f}' == '1.00(99)'

    s = Samples(mean=1, std=10)
    assert f'{s:#.1}' == '0.(10.)'

    s = Samples(mean=1, std=1000)
    assert f'{s:#.1}' == '0.(1000.)'

    s = Samples(mean=12345, std=9876)
    assert f'{s:#e}' == '1.23(99)e+04'
    assert f'{s:#}' == '12300.(9900.)'

    s = Samples(mean=10, std=10)
    assert f'{s:#.1E}' == '1.(1.)E+01'


def test_grouping_field():
    s = Samples(mean=123456789, std=123456)
    assert f'{s:,.6}' == '123,456,789(123,456)'
    assert f'{s:,}' == '123,460,000(120,000)'
    assert f'{s:_.1}' == '123_500_000(100_000)'


def test_zero_field():
    s = Samples(mean=1.342, std=0.0041)
    assert f'{s:015.1}' == '1.342(4)0000000'
    assert f'{s:>+024.3}' == '00000000000+1.34200(410)'


def test_latex():
    s = Samples(mean=1.23456789, std=0.123456789)
    assert f'{s:.3eL}' == r'1.235\left(123\right)'

    factor = 1e-6
    s = Samples(mean=1.23456789 * factor, std=0.123456789 * factor)
    assert f'{s:.3EL}' == r'1.235\left(123\right)\times10^{-6}'

    factor = 1e12
    s = Samples(mean=1.23456789 * factor, std=0.123456789 * factor)
    assert f'{s:.3EL}' == r'1.235\left(123\right)\times10^{12}'

    factor = 1e100
    s = Samples(mean=1.23456789 * factor, std=0.123456789 * factor)
    assert f'{s:.3eL}' == r'\mathrm{NaN}\left(\mathrm{NaN}\right)'
    s = Samples(mean=1.23456789 * factor, std=0.123456789 * factor, overload=math.inf)
    assert f'{s:.3eL}' == r'1.235\left(123\right)\times10^{100}'

    factor = 1e-100
    s = Samples(mean=1.23456789 * factor, std=0.123456789 * factor)
    assert f'{s:.3EL}' == r'1.235\left(123\right)\times10^{-100}'

    s = Samples(mean=3.14159)
    assert f'{s:fL}' == r'3.14\left(\mathrm{NaN}\right)'
    assert f'{s:.4fL}' == r'3.1416\left(\mathrm{NaN}\right)'

    s = Samples(std=3.142)
    assert f'{s:L}' == r'\mathrm{NaN}\left(3.142\right)'

    s = Samples(mean=-np.inf, std=np.inf)
    assert f'{s:FL}' == r'-\infty\left(\infty\right)'


def test_percent_type():
    s = Samples(mean=0.1548175123, std=0.0123456)
    assert f'{s:.1%}' == '15(1)%'
    assert f'{s:.4%}' == '15.482(1.235)%'
    assert f'{s:.3%L}' == r'15.48\left(1.23\right)\%'

    s = Samples(mean=0.1548175123, std=0.000123456)
    assert f'{s:%L}' == r'15.482\left(12\right)\%'
    assert f'{s:%U}' == '15.482(12)%'


def test_plus_minus():
    s = Samples(mean=1.0, std=0.000123456789)
    assert f'{s:+.4fP}' == '+1.0000000+/-0.0001235'

    s = Samples(mean=7.2524, std=0.0032153)
    assert f'{s:.4fP}' == '7.252400+/-0.003215'

    s = Samples(mean=-1.2345, std=123.456789)
    assert f'{s:12.5fP}' == '-1.23+/-123.46'

    s = Samples(mean=1.5431384e-8, std=4.32856e-12)
    assert f'{s:P}' == '0.0000000154314+/-0.0000000000043'
    assert f'{s:eP}' == '(1.54314+/-0.00043)e-08'

    s = Samples(mean=1.5431384e7, std=4.32856e6)
    assert f'{s:.1P}' == '15000000+/-4000000'
    assert f'{s:P}' == '15400000+/-4300000'
    assert f'{s:.5P}' == '15431400+/-4328600'
    assert f'{s:eP}' == '(1.54+/-0.43)e+07'
    assert f'{s: .3eP}' == '( 1.543+/-0.433)e+07'
    assert f'{s:< 30.3eP}' == '( 1.543+/-0.433)e+07          '
    assert f'{s:>30.3eP}' == '           (1.543+/-0.433)e+07'
    assert f'{s:.>30.3eP}' == '...........(1.543+/-0.433)e+07'


def test_si_prefix_factor():
    prefix, factor = si_prefix_factor(-30)
    assert prefix == 'y'
    assert factor == 1e-6

    prefix, factor = si_prefix_factor(-29)
    assert prefix == 'y'
    assert factor == 1e-5

    prefix, factor = si_prefix_factor(-28)
    assert prefix == 'y'
    assert factor == 1e-4

    prefix, factor = si_prefix_factor(-27)
    assert prefix == 'y'
    assert factor == 1e-3

    prefix, factor = si_prefix_factor(-26)
    assert prefix == 'y'
    assert factor == 1e-2

    prefix, factor = si_prefix_factor(-25)
    assert prefix == 'y'
    assert factor == 1e-1

    prefix, factor = si_prefix_factor(-24)
    assert prefix == 'y'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(-23)
    assert prefix == 'y'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(-22)
    assert prefix == 'y'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(-21)
    assert prefix == 'z'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(-20)
    assert prefix == 'z'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(-19)
    assert prefix == 'z'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(-18)
    assert prefix == 'a'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(-17)
    assert prefix == 'a'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(-16)
    assert prefix == 'a'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(-15)
    assert prefix == 'f'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(-14)
    assert prefix == 'f'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(-13)
    assert prefix == 'f'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(-12)
    assert prefix == 'p'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(-11)
    assert prefix == 'p'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(-10)
    assert prefix == 'p'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(-9)
    assert prefix == 'n'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(-8)
    assert prefix == 'n'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(-7)
    assert prefix == 'n'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(-6)
    assert prefix == 'u'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(-5)
    assert prefix == 'u'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(-4)
    assert prefix == 'u'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(-3)
    assert prefix == 'm'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(-2)
    assert prefix == 'm'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(-1)
    assert prefix == 'm'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(0)
    assert prefix == ''
    assert factor == 1e0

    prefix, factor = si_prefix_factor(1)
    assert prefix == ''
    assert factor == 1e1

    prefix, factor = si_prefix_factor(2)
    assert prefix == ''
    assert factor == 1e2

    prefix, factor = si_prefix_factor(3)
    assert prefix == 'k'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(4)
    assert prefix == 'k'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(5)
    assert prefix == 'k'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(6)
    assert prefix == 'M'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(7)
    assert prefix == 'M'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(8)
    assert prefix == 'M'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(9)
    assert prefix == 'G'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(10)
    assert prefix == 'G'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(11)
    assert prefix == 'G'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(12)
    assert prefix == 'T'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(13)
    assert prefix == 'T'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(14)
    assert prefix == 'T'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(15)
    assert prefix == 'P'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(16)
    assert prefix == 'P'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(17)
    assert prefix == 'P'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(18)
    assert prefix == 'E'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(19)
    assert prefix == 'E'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(20)
    assert prefix == 'E'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(21)
    assert prefix == 'Z'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(22)
    assert prefix == 'Z'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(23)
    assert prefix == 'Z'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(24)
    assert prefix == 'Y'
    assert factor == 1e0

    prefix, factor = si_prefix_factor(25)
    assert prefix == 'Y'
    assert factor == 1e1

    prefix, factor = si_prefix_factor(26)
    assert prefix == 'Y'
    assert factor == 1e2

    prefix, factor = si_prefix_factor(27)
    assert prefix == 'Y'
    assert factor == 1e3

    prefix, factor = si_prefix_factor(28)
    assert prefix == 'Y'
    assert factor == 1e4

    prefix, factor = si_prefix_factor(29)
    assert prefix == 'Y'
    assert factor == 1e5

    prefix, factor = si_prefix_factor(30)
    assert prefix == 'Y'
    assert factor == 1e6


def test_si():
    s = Samples(mean=4.638174e-30, std=0.0635119e-30)
    assert f'{s:.2S}' == '0.000004638(64) y'
    assert f'{s:.1PS}' == '(0.00000464+/-0.00000006) y'

    s = Samples(mean=9.092349e-25, std=0.0038964e-25)
    assert f'{s:.3S}' == '0.909235(390) y'
    assert f'{s:PS}' == '(0.90923+/-0.00039) y'

    s = Samples(mean=5.206637324e-24, std=0.415002e-24)
    assert f'{s:.1S}' == '5.2(4) y'
    assert f'{s:.5PS}' == '(5.20664+/-0.41500) y'

    s = Samples(mean=9.6490243e-22, std=0.058476272e-22)
    assert f'{s:.4S}' == '964.902(5.848) y'
    assert f'{s:.1PS}' == '(965+/-6) y'

    s = Samples(mean=6.2860846e-20, std=0.02709243e-20)
    assert f'{s:S}' == '62.86(27) z'
    assert f'{s:PS}' == '(62.86+/-0.27) z'

    s = Samples(mean=5.2032008e-17, std=0.00084681469e-17)
    assert f'{s:S}' == '52.0320(85) a'
    assert f'{s:PS}' == '(52.0320+/-0.0085) a'

    s = Samples(mean=8.541971e-15, std=1.93486e-15)
    assert f'{s:.3S}' == '8.54(1.93) f'
    assert f'{s:.1PS}' == '(9+/-2) f'

    s = Samples(mean=8.541971e-14, std=1.93486e-14)
    assert f'{s:.3S}' == '85.4(19.3) f'
    assert f'{s:.1PS}' == '(90+/-20) f'

    s = Samples(mean=8.125524e-10, std=0.043966e-10)
    assert f'{s:.1S}' == '813(4) p'
    assert f'{s:.4PS}' == '(812.552+/-4.397) p'

    s = Samples(mean=1.7540272e-9, std=6.5160764e-9)
    assert f'{s:.3S}' == '1.75(6.52) n'
    assert f'{s:.3FS}' == '1.75(6.52) n'
    assert f'{s:.4PS}' == '(1.754+/-6.516) n'

    s = Samples(mean=4.5569880e-7, std=0.004160764e-7)
    assert f'{s:.1S}' == '455.7(4) n'
    assert f'{s:PS}' == '(455.70+/-0.42) n'

    s = Samples(mean=9.2863e-4, std=0.70230056610e-4)
    assert f'{s:S}' == '929(70) u'
    assert f'{s:US}' == '929(70) µ'
    assert f'{s:.6PS}' == '(928.6300+/-70.2301) u'
    assert f'{s:.6PUS}' == '(928.6300±70.2301) µ'
    assert f'{s:.2fUS}' == '929(70) µ'
    assert f'{s:.6PUS}' == '(928.6300±70.2301) µ'

    s = Samples(mean=5.6996491e-2, std=0.5302890e-2)
    assert f'{s:.4S}' == '56.996(5.303) m'
    assert f'{s:.1PS}' == '(57+/-5) m'

    s = Samples(mean=2.69364683, std=0.00236666)
    assert f'{s:BUS}' == '2.6936(24)'
    assert f'{s:.3PS}' == '2.69365+/-0.00237'

    s = Samples(mean=4.4733994e2, std=0.1085692e2)
    assert f'{s:.1S}' == '450(10)'
    assert f'{s:.4PS}' == '447.34+/-10.86'

    s = Samples(mean=8.50987467e4, std=0.6095151e4)
    assert f'{s:S}' == '85.1(6.1) k'
    assert f'{s:.1PS}' == '(85+/-6) k'

    s = Samples(mean=1.8e6, std=0.0453589e6)
    assert f'{s:.4S}' == '1.80000(4536) M'
    assert f'{s:.3PUS}' == '(1.8000±0.0454) M'

    s = Samples(mean=1.8667540e8, std=0.00771431e8)
    assert f'{s:.3S}' == '186.675(771) M'
    assert f'{s:.3PS}' == '(186.675+/-0.771) M'

    s = Samples(mean=7.789499e9, std=0.7852736e9)
    assert f'{s:.1S}' == '7.8(8) G'
    assert f'{s:PS}' == '(7.79+/-0.79) G'

    s = Samples(mean=2.2038646e13, std=12.743090e13)
    assert f'{s:.1S}' == '0(100) T'
    assert f'{s:.2fPS}' == '(20+/-130) T'

    s = Samples(mean=6.084734e16, std=1.2485885e16)
    assert f'{s:.3S}' == '60.8(12.5) P'
    assert f'{s:PS}' == '(61+/-12) P'

    s = Samples(mean=7.66790e18, std=0.05647e18)
    assert f'{s:.4S}' == '7.66790(5647) E'
    assert f'{s:.6PS}' == '(7.6679000+/-0.0564700) E'

    s = Samples(mean=3.273545e22, std=0.004964854e22)
    assert f'{s:.1S}' == '32.74(5) Z'
    assert f'{s:.1PS}' == '(32.74+/-0.05) Z'

    s = Samples(mean=1.638324e27, std=0.773148e27)
    assert f'{s:S}' == '1640(770) Y'
    assert f'{s:.4PS}' == '(1638.3+/-773.1) Y'


def test_iterable():
    s = Samples(mean=1.2, std=0.32)
    mean, std = s
    assert mean == 1.2
    assert std == 0.32
    assert 'mean={}, std={}'.format(*s) == 'mean=1.2, std=0.32'


def test_type_n_raises():
    # can't specify both grouping and n
    s = Samples()
    with pytest.raises(ValueError):
        f'{s:_n}'
    with pytest.raises(ValueError):
        f'{s:,n}'


def test_type_n_swiss():
    # this locale is interesting because it can have non-ascii characters
    if sys.platform == 'win32':
        loc = 'German_Switzerland'
    elif sys.platform == 'darwin':
        loc = 'de_CH'
    else:
        loc = 'de_CH.utf8'
    locale.setlocale(locale.LC_NUMERIC, loc)

    s = Samples(mean=1.23456789, std=0.987654321)
    if sys.platform == 'darwin':
        assert f'{s:n}' == '1,23(99)'
    else:
        assert f'{s:n}' == '1.23(99)'

    s = Samples(mean=1.2345678987e6, std=0.987654321)
    if sys.platform == 'darwin':
        assert f'{s:.4n}' == '1234567,8987(9877)'
    else:
        assert f'{s:.4n}' == '1’234’567.8987(9877)'

    s = Samples(mean=12345.6789, std=9876.54321)
    if sys.platform == 'darwin':
        assert f'{s:.8n}' == '12345,6789(9876,5432)'
    else:
        assert f'{s:.8n}' == '12’345.6789(9’876.5432)'

    locale.setlocale(locale.LC_NUMERIC, original_loc)


def test_type_n_german():
    if sys.platform == 'win32':
        loc = 'German_Germany'
    elif sys.platform == 'darwin':
        loc = 'de_DE'
    else:
        loc = 'de_DE.utf8'
    locale.setlocale(locale.LC_NUMERIC, loc)

    s = Samples(mean=1.23456789, std=0.987654321)
    assert f'{s:n}' == '1,23(99)'

    s = Samples(mean=1.2345678987e6, std=0.987654321)
    if sys.platform == 'darwin':
        assert f'{s:.4n}' == '1234567,8987(9877)'
    else:
        assert f'{s:.4n}' == '1.234.567,8987(9877)'

    s = Samples(mean=12345.6789, std=9876.54321)
    if sys.platform == 'darwin':
        assert f'{s:.8n}' == '12345,6789(9876,5432)'
    else:
        assert f'{s:.8n}' == '12.345,6789(9.876,5432)'

    s = Samples(mean=2345, std=1234)
    assert f'{s:#.1n}' == '2,(1,)e+03'

    s = Samples(mean=12345, std=9876)
    assert f'{s: #n}' == ' 1,23(99)e+04'

    locale.setlocale(locale.LC_NUMERIC, original_loc)


def test_type_n_india():
    # this locale is interesting because it can have a different
    # 'grouping' for the 'thousands_sep' key
    if sys.platform == 'win32':
        loc = 'English_India'
    elif sys.platform == 'darwin':
        loc = 'hi_IN.ISCII-DEV'
    else:
        loc = 'en_IN.utf8'
    locale.setlocale(locale.LC_NUMERIC, loc)

    s = Samples(mean=1.23456789, std=0.987654321)
    assert f'{s:n}' == '1.23(99)'

    s = Samples(mean=1.2345678987e6, std=0.987654321)
    if sys.platform == 'darwin':
        assert f'{s:.4n}' == '12,345,67.8987(9877)'
    else:
        assert f'{s:.4n}' == '12,34,567.8987(9877)'

    s = Samples(mean=12345.6789, std=9876.54321)
    if sys.platform == 'darwin':
        assert f'{s:.8n}' == '123,45.6789(98,76.5432)'
    else:
        assert f'{s:.8n}' == '12,345.6789(9,876.5432)'

    locale.setlocale(locale.LC_NUMERIC, original_loc)


def test_type_n_kiwi():
    # make sure the native locale for MSL is good
    if sys.platform == 'win32':
        loc = 'English_New Zealand'
    elif sys.platform == 'darwin':
        loc = 'en_NZ'
    else:
        loc = 'en_NZ.utf8'
    locale.setlocale(locale.LC_NUMERIC, loc)

    s = Samples(mean=1.23456789, std=0.987654321)
    assert f'{s:n}' == '1.23(99)'

    s = Samples(mean=1.2345678987e6, std=0.987654321)
    assert f'{s:.4n}' == '1,234,567.8987(9877)'

    s = Samples(mean=12345.6789, std=9876.54321)
    assert f'{s:.8n}' == '12,345.6789(9,876.5432)'

    s = Samples(mean=12345.6789, std=9876.54321)
    assert f'{s:+.8n}' == '+12,345.6789(9,876.5432)'

    locale.setlocale(locale.LC_NUMERIC, original_loc)


def test_type_n_afrikaans():
    # this locale is interesting because it can have non-ascii characters
    if sys.platform == 'win32':
        loc = 'English_South Africa'
    elif sys.platform == 'darwin':
        loc = 'af_ZA'
    else:
        loc = 'en_ZA.utf8'
    locale.setlocale(locale.LC_NUMERIC, loc)

    s = Samples(mean=1.23456789, std=0.987654321)
    if sys.platform.startswith('linux'):
        assert f'{s:n}' == '1.23(99)'
    else:
        assert f'{s:n}' == '1,23(99)'

    s = Samples(mean=1.2345678987e6, std=0.987654321)
    if sys.platform == 'win32':
        assert f'{s:.4n}' == '1\xa0234\xa0567,8987(9877)'
    elif sys.platform == 'darwin':
        assert f'{s:.4n}' == '1.234.567,8987(9877)'
    else:
        assert f'{s:.4n}' == '1,234,567.8987(9877)'

    s = Samples(mean=12345.6789, std=9876.54321)
    if sys.platform == 'win32':
        assert f'{s:.8n}' == '12\xa0345,6789(9\xa0876,5432)'
    elif sys.platform == 'darwin':
        assert f'{s:.8n}' == '12.345,6789(9.876,5432)'
    else:
        assert f'{s:.8n}' == '12,345.6789(9,876.5432)'

    locale.setlocale(locale.LC_NUMERIC, original_loc)