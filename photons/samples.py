"""
A formatting-friendly convenience class for 1-D sample data.
"""
import locale
import math
import re
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from GTC import type_a
from GTC import ureal
from GTC.lib import UncertainReal

# The regular expression to parse a format specification (format_spec)
# with additional (and optional) characters at the end for custom fields.
#
# format_spec ::= [[fill]align][sign][#][0][width][grouping][.precision][type][mode][style][si]
# https://docs.python.org/3/library/string.html#format-specification-mini-language
_format_spec_regex = re.compile(
    # the builtin grammar fields
    r'((?P<fill>.)(?=[<>=^]))?'
    r'(?P<align>[<>=^])?'
    r'(?P<sign>[ +-])?'
    r'(?P<hash>#)?'
    r'(?P<zero>0)?'
    r'(?P<width>\d+)?'
    r'(?P<grouping>[_,])?'
    r'((\.)(?P<precision>\d+))?'
    r'(?P<type>[bcdeEfFgGnosxX%])?'

    # Bracket or Plus-minus
    # NOTE: these characters cannot be in <type>
    r'(?P<mode>[BP])?'

    # Latex or Unicode
    # NOTE: these characters cannot be in <type> nor <mode>
    r'(?P<style>[LU])?'

    # SI prefix
    # NOTE: this character cannot be in <type>, <mode> nor <style>
    r'(?P<si>S)?'

    # the regex must match until the end of the string
    r'$'
)

_exponent_regex = re.compile(r'[eE][+-]\d+')

_si_map = {i*3: c for i, c in enumerate('qryzafpnum kMGTPEZYRQ', start=-10)}

_unicode_superscripts = {
    ord('+'): '\u207A',
    ord('-'): '\u207B',
    ord('0'): '\u2070',
    ord('1'): '\u00B9',
    ord('2'): '\u00B2',
    ord('3'): '\u00B3',
    ord('4'): '\u2074',
    ord('5'): '\u2075',
    ord('6'): '\u2076',
    ord('7'): '\u2077',
    ord('8'): '\u2078',
    ord('9'): '\u2079',
}


def order_of_magnitude(value: float) -> int:
    """Returns the order of magnitude of `value`."""
    if value == 0:
        return 0
    return int(math.floor(math.log10(math.fabs(value))))


def parse(format_spec: str) -> dict[str, str]:
    """Parse a format specification into its grammar fields."""
    match = _format_spec_regex.match(format_spec)
    if not match:
        raise ValueError(f'Invalid format specifier {format_spec!r}')
    return match.groupdict()


def si_prefix_factor(exponent: int) -> tuple[str, float]:
    """Returns the SI prefix and scaling factor.

    Args:
        exponent: The exponent, e.g., 10 ** exponent
    """
    mod = exponent % 3
    prefix = _si_map.get(exponent - mod)
    factor = 10. ** mod
    if exponent < 0 and prefix is None:
        prefix = 'q'
        factor = 10. ** (exponent + 30)
    elif 0 <= exponent < 3:
        prefix = ''
    elif prefix is None:
        prefix = 'Q'
        factor = 10. ** (exponent - 30)
    return prefix, factor


@dataclass
class Rounded:
    """Represents a rounded value."""
    value: float
    precision: int
    type: str
    exponent: int
    suffix: str


class Format:

    def __init__(self, **kwargs) -> None:
        """Format specification."""

        # builtin grammar fields
        self.fill: str = kwargs['fill'] or ''
        self.align: str = kwargs['align'] or ''
        self.sign: str = kwargs['sign'] or ''
        self.hash: str = kwargs['hash'] or ''
        self.zero: str = kwargs['zero'] or ''
        self.width: str = kwargs['width'] or ''
        self.grouping: str = kwargs['grouping'] or ''
        self.precision = int(kwargs['precision'] or 2)
        self.type: str = kwargs['type'] or 'f'

        if self.type == 'n' and self.grouping:
            raise ValueError(f"Cannot use 'n' and grouping={self.grouping!r}")

        # custom grammar fields
        self.mode: str = kwargs['mode'] or 'B'
        self.style: str = kwargs['style'] or ''
        self.si: str = kwargs['si'] or ''

        if self.si:
            self.type = 'e'

        # these attributes are used when rounding
        self.digits = self.precision
        self.u_exponent = 0

        # keeps a record of whether the Format was created for
        # an uncertain number with an uncertainty of 0, NaN or INF
        self.nonzero_and_finite = True

    def __repr__(self) -> str:
        # Use .digits instead of .precision in the result
        spec = f'{self.fill}{self.align}{self.sign}{self.hash}{self.zero}' \
               f'{self.width}{self.grouping}.{self.digits}{self.type}' \
               f'{self.mode}{self.style}{self.si}'
        return f'Format(format_spec={spec!r})'

    def result(self, text: str) -> str:
        """Format `text` using the fill, align, zero and width fields."""
        fmt = f'{self.fill}{self.align}{self.zero}{self.width}'
        return f'{text:{fmt}s}'

    def uncertainty(self,
                    uncertainty: float,
                    *,
                    hash: str = None,  # noqa: Shadows built-in name 'hash'
                    type: str | None = 'f',  # noqa: Shadows built-in name 'type'
                    precision: int = None) -> str:
        """Format `uncertainty` using the hash, grouping, precision and type fields.

        Args:
            uncertainty: The uncertainty to format.
            hash: Can be either # or '' (an empty string)
            type: Can be one of: e, E, f, F, g, G, n
            precision: Indicates how many digits should be displayed after
                the decimal point for presentation types f and F, or before
                and after the decimal point for presentation types g or G.

        Returns:
            The `uncertainty` formatted.
        """
        return self.value(
            uncertainty, hash=hash, type=type, sign='', precision=precision)

    def update(self, std: float) -> None:
        """Update the `precision` and `u_exponent` attributes.

        Args:
            std: The standard uncertainty of the samples.
        """
        if std == 0 or not math.isfinite(std):
            self.nonzero_and_finite = False
            return

        exponent = order_of_magnitude(std)
        if exponent - self.precision + 1 >= 0:
            self.precision = 0
        else:
            self.precision = int(self.precision - exponent + 1)

        u_exponent = exponent - self.digits + 1

        # edge case, for example, if 0.099 then round to 0.1
        rounded = round(std, -u_exponent)
        e_rounded = order_of_magnitude(rounded)
        if e_rounded > exponent:
            u_exponent += 1

        self.u_exponent = u_exponent

    def value(self,
              value: float,
              *,
              hash: str = None,  # noqa: Shadows built-in name 'hash'
              type: str = None,  # noqa: Shadows built-in name 'type'
              sign: str = None,
              precision: int = None) -> str:
        """Format `value` using the sign, hash, grouping, precision and type fields.

        Args:
            value: The value to format.
            hash: Can be either # or '' (an empty string)
            type: Can be one of: e, E, f, F, g, G, n
            sign: Can be one of: +, -, ' ' (a space)
            precision: Indicates how many digits should be displayed after
                the decimal point for presentation types f and F, or before
                and after the decimal point for presentation types g or G.

        Returns:
            The `value` formatted.
        """
        if sign is None:
            sign = self.sign

        if precision is None:
            precision = self.precision

        if type is None:
            type = self.type  # noqa: Shadows built-in name 'type'

        if hash is None:
            hash = self.hash  # noqa: Shadows built-in name 'hash'

        if type == 'n':
            fmt = f'%{sign}{hash}.{precision}f'
            return locale.format_string(fmt, value, grouping=True)

        return f'{value:{sign}{hash}{self.grouping}.{precision}{type}}'


class Samples:

    def __init__(self,
                 samples: str | Sequence[str | int | float] | np.ndarray = None,
                 *,
                 mean: float = None,
                 stdev: float = None,
                 size: int = None,
                 overload: float | None = 1e30) -> None:
        """Convenience class for a 1-D array of data samples.

        Calculates the mean, standard deviation, variance, relative standard
        deviation and standard deviation of the mean of the samples.

        Args:
            samples: The samples. If a string then in CSV format.
            mean: If specified, then it is not calculated from the `samples`.
            stdev: If specified, then it is not calculated from the `samples`.
            size: If specified, then it is not determined from the `samples`.
            overload: For some devices, like a DMM, if the input signal is greater
                than the present range can measure, the device returns a large
                value (e.g., 9.9E+37) to indicate a measurement overload. If the
                absolute value of the mean is greater than `overload` then the
                mean and standard deviation become NaN. Setting `overload` to
                :data:`None` disables this check.
        """
        if samples is not None and any(a is not None for a in (mean, stdev, size)):
            raise ValueError('Cannot specify samples and the mean, stdev or size')

        if isinstance(samples, str):
            stripped = samples.rstrip()
            if stripped:
                self._samples = np.array(stripped.split(','), dtype=float)
            else:
                self._samples = np.empty(0)
        elif isinstance(samples, np.ndarray):
            self._samples = samples
        elif samples is None:
            self._samples = np.empty(0)
        else:
            self._samples = np.asarray(list(map(float, samples)))  # noqa: samples cannot be None

        if self._samples.ndim != 1:
            raise ValueError('only 1D arrays are allowed')

        self._size = self._samples.size if size is None else size
        self._overload = overload
        self._stdev = stdev

        if mean is not None:
            self._mean = self._check_overload(mean)
        else:
            self._mean = None

    def __iter__(self):
        return iter((self.mean, self.stdev))

    def __format__(self, format_spec) -> str:
        fmt = Format(**parse(format_spec))
        fmt.update(self.stdom)
        return fmt.result(_stylize(self._to_string(fmt), fmt))

    def __getattr__(self, item):
        """Pass all other attributes to the ndarray."""
        return getattr(self._samples, item)

    def __repr__(self) -> str:
        return f'Samples(mean={self.mean}, stdev={self.stdev}, size={self.size})'

    def _check_overload(self, mean: float) -> float:
        if self._overload is None:
            return mean

        if math.isfinite(mean) and abs(mean) > self._overload:
            self._stdev = math.nan
            return math.nan

        return mean

    def _to_string(self, fmt: Format) -> str:
        """Convert to a formatted string."""
        x, u = self.mean, self.stdom
        if u == 0:
            if fmt.si:
                fmt.update(x)
                r = _round(x, fmt)
                x_str = fmt.value(r.value, precision=r.precision, type=r.type)
                v_str = f'{x_str}{r.suffix}'
            else:
                v_str = fmt.value(x)
            return fmt.result(v_str)

        u_finite = math.isfinite(u)
        x_finite = math.isfinite(x)
        if not (u_finite and x_finite):
            si_prefix = ''
            if fmt.si and x_finite:
                fmt.update(x)
                r = _round(x, fmt)
                si_prefix = r.suffix
                x_str = fmt.value(r.value, precision=r.precision, type=r.type)
            else:
                x_str = fmt.value(x)

            u_str = fmt.uncertainty(u, type=None)

            if fmt.mode == 'B':
                result = f'{x_str}({u_str}){si_prefix}'
            else:
                result = f'{x_str}+/-{u_str}{si_prefix}'

            # move an exponential term (if it exists) to the end of the string
            exp = _exponent_regex.search(result)
            if exp:
                start, end = exp.span()
                s1, s2, s3 = result[:start], result[end:], exp.group()
                if fmt.mode == 'B':
                    result = f'{s1}{s2}{s3}'
                else:
                    result = f'({s1}{s2}){s3}'

            return result

        x_rounded, u_rounded = _round_samples(x, u, fmt)

        u_r = u_rounded.value
        precision = x_rounded.precision

        x_str = fmt.value(x_rounded.value, precision=precision, type=x_rounded.type)

        if fmt.mode == 'P':  # Plus-minus mode
            u_str = fmt.uncertainty(u_r, precision=precision)
            x_u_str = f'{x_str}+/-{u_str}'
            if x_rounded.suffix:
                return f'({x_u_str}){x_rounded.suffix}'
            return x_u_str

        # Bracket mode
        oom = order_of_magnitude(u_r)
        if precision > 0 and oom >= 0:
            # the uncertainty straddles the decimal point so
            # keep the decimal point in the result
            u_str = fmt.uncertainty(u_r, precision=precision, type=u_rounded.type)
        else:
            hash_, type_ = None, u_rounded.type
            if oom < 0:
                if fmt.hash:
                    hash_ = ''
                else:
                    type_ = 'f'
            u_str = fmt.uncertainty(round(u_r * 10. ** precision),
                                    precision=0, type=type_, hash=hash_)

        return f'{x_str}({u_str}){x_rounded.suffix}'

    @property
    def mean(self) -> float:
        """Returns the mean."""
        if self._mean is not None:
            return self._mean

        mean = float(np.mean(self._samples)) if self._size > 0 else math.nan
        self._mean = self._check_overload(mean)
        return self._mean

    @property
    def overload(self) -> float | None:
        """Returns the overload value."""
        return self._overload

    @property
    def relative_stdev(self) -> float:
        """Returns the relative standard deviation."""
        try:
            return 100.0 * (self.stdev / self.mean)
        except ZeroDivisionError:
            return math.nan

    @property
    def relative_stdom(self) -> float:
        """Returns the relative standard deviation of the mean."""
        try:
            return 100.0 * (self.stdom / self.mean)
        except ZeroDivisionError:
            return math.nan

    @property
    def samples(self) -> np.ndarray:
        """Returns the samples."""
        return self._samples

    @property
    def size(self) -> int:
        """Returns the number of samples."""
        return self._size

    @property
    def stdev(self) -> float:
        """Returns the sample standard deviation."""
        if self._stdev is not None:
            return self._stdev

        self._stdev = float(np.std(self._samples, ddof=1)) if self._size > 1 else math.nan
        return self._stdev

    @property
    def stdom(self) -> float:
        """Returns the standard deviation of the mean."""
        try:
            return self.stdev / math.sqrt(self._size)
        except ZeroDivisionError:
            return math.nan

    def to_json(self) -> dict[str, float]:
        """Allows for this class to be JSON serializable with msl-network."""
        return {
            'mean': self.mean,
            'stdev': self.stdev,
            'size': self._size,
            'overload': self._overload
        }

    def to_ureal(self,
                 *,
                 label: str = None,
                 delta: float = None,
                 truncated: bool = False) -> UncertainReal:
        """Convert to an uncertain-real number.

        Args:
            label: The label to associate with the uncertain number.
            delta: The digitization step size (only valid if the samples are digitized).
            truncated: Whether the digitized samples were truncated or rounded.
                Only used if `delta` is not :data:`None`.

        Returns:
            The samples as an uncertain-real number.
        """
        if delta is not None:
            return type_a.estimate_digitized(
                self._samples, delta, label=label, truncate=truncated)

        if self._samples.size > 0:
            return type_a.estimate(self._samples, label=label)

        return ureal(self.mean, self.stdom, df=self._size-1, label=label,
                     independent=True)

    @property
    def variance(self) -> float:
        """Returns the sample variance."""
        return self.stdev * self.stdev


def _round(value: float, fmt: Format, exponent: int = None) -> Rounded:
    """Round `value` to the appropriate number of significant digits."""
    if not fmt.si and not (fmt.nonzero_and_finite or math.isfinite(value)):
        return Rounded(value=value, precision=fmt.precision,
                       type=fmt.type, exponent=0, suffix='')

    if exponent is None:
        exponent = order_of_magnitude(value)

    _type = fmt.type
    f_or_g_as_f = (_type in 'fF') or \
                  ((_type in 'gGn') and
                   (-4 <= exponent < exponent - fmt.u_exponent))

    if f_or_g_as_f:
        factor = 1.0
        digits = -fmt.u_exponent
        precision = max(digits, 0)
        suffix = ''
    elif _type == '%':
        factor = 0.01
        digits = -fmt.u_exponent - 2
        precision = max(digits, 0)
        suffix = '%'
    else:
        factor = 10. ** exponent
        digits = max(exponent - fmt.u_exponent, 0)
        precision = digits
        suffix = f'{factor:.0{_type}}'[1:]

    if _type in 'eg%':
        _type = 'f'
    elif _type in 'EG':
        _type = 'F'

    if fmt.si:
        prefix, si_factor = si_prefix_factor(exponent)
        n = order_of_magnitude(si_factor)
        precision = max(0, precision - n)
        val = round(value * si_factor / factor, digits - n)
        suffix = f' {prefix}' if prefix else ''
    else:
        val = round(value / factor, digits)

    return Rounded(value=val, precision=precision, type=_type,
                   exponent=exponent, suffix=suffix)


def _round_samples(x: float, u: float, fmt: Format) -> tuple[Rounded, Rounded]:
    """Round the samples.

    This function ensures that both x and u get scaled by the same factor.
    """
    maximum = round(max(math.fabs(x), u), -fmt.u_exponent)
    rounded = _round(maximum, fmt)
    x_rounded = _round(x, fmt, exponent=rounded.exponent)
    u_rounded = _round(u, fmt, exponent=rounded.exponent)
    return x_rounded, u_rounded


def _stylize(text: str, fmt: Format) -> str:
    """Apply the formatting style to `text`."""
    if not fmt.style or not text:
        return text

    exponent = ''
    exp_number = None
    exp_match = _exponent_regex.search(text)
    if exp_match:
        # don't care whether it starts with e or E and
        # don't want to include the + symbol
        group = exp_match.group()
        exp_number = int(group[1:])

    if fmt.style == 'U':
        if exp_match and exp_number != 0:
            e = f'{exp_number}'
            translated = e.translate(_unicode_superscripts)
            exponent = f'\u00D710{translated}'

        replacements = [
            ('+/-', '\u00B1'),
            ('u', '\u00B5')
        ]

    elif fmt.style == 'L':
        if exp_match and exp_number != 0:
            exponent = fr'\times10^{{{exp_number}}}'

        replacements = [
            ('(', r'\left('),
            (')', r'\right)'),
            ('nan', r'\mathrm{NaN}'),
            ('NAN', r'\mathrm{NaN}'),
            ('inf', r'\infty'),  # must come before 'INF'
            ('INF', r'\infty'),
            ('%', r'\%'),
        ]

    else:
        assert False, 'should not get here'

    if exp_match:
        start, end = exp_match.span()
        s1, s2, s3 = text[:start], exponent, text[end:]
        text = f'{s1}{s2}{s3}'

    for old, new in replacements:
        text = text.replace(old, new)

    return text
