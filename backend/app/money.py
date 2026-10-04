"""Deterministic decimal arithmetic shared with the browser (action plan T04).

The review found the client and the server disagreeing on money: with a supplier cost
of 10.075 Python reported 10.08 and JavaScript 10.07. Python was rounding the *decimal*
value while JavaScript rounded the *binary* double, and no amount of ``Number.EPSILON``
makes those agree for every accepted input.

Both sides now run the same algorithm on scaled integers instead:

* every value is an integer number of 1e-12 units (Python ``int``, JavaScript ``BigInt``);
* a numeric input is converted through its shortest round-tripping decimal string, which
  ``repr()`` and JavaScript's ``String()`` both produce, so the same JSON number becomes
  the same scaled integer on both sides;
* multiplication, division and quantisation round half away from zero at a fixed scale.

Accepted precision: inputs carrying more than ``PLACES`` decimal places are rounded
half away from zero to that scale before any arithmetic runs. Results are quantised to
2 decimal places for money and percentages.

``frontend/src/lib/money.ts`` is the line-by-line mirror of this module; the parity
cases in ``contracts/`` hold them together.
"""

PLACES = 12
UNIT = 10 ** PLACES
MONEY_PLACES = 2


def div_round(numerator, denominator):
    """Integer division rounding halves away from zero. The one rounding rule here."""
    if denominator == 0:
        raise ZeroDivisionError('decimal division by zero')
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    if numerator >= 0:
        return (2 * numerator + denominator) // (2 * denominator)
    return -((-2 * numerator + denominator) // (2 * denominator))


def from_decimal_string(text):
    """Scale a decimal literal, with or without an exponent, to PLACES places."""
    text = text.strip()
    sign = 1
    if text[:1] in {'+', '-'}:
        sign = -1 if text[0] == '-' else 1
        text = text[1:]
    mantissa, _, exponent_text = text.replace('E', 'e').partition('e')
    exponent = int(exponent_text) if exponent_text else 0
    whole, _, fraction = mantissa.partition('.')
    digits = f'{whole}{fraction}' or '0'
    if not digits.isdigit():
        raise ValueError(f'not a decimal literal: {text!r}')
    shift = PLACES - (len(fraction) - exponent)
    if shift >= 0:
        return sign * int(digits) * 10 ** shift
    return sign * div_round(int(digits), 10 ** -shift)


def parse(value):
    """A Python number or decimal string as a scaled integer."""
    if isinstance(value, bool):
        raise TypeError('a boolean is not a decimal value')
    if isinstance(value, int):
        return value * UNIT
    if isinstance(value, str):
        return from_decimal_string(value)
    return from_decimal_string(repr(float(value)))


def mul(a, b):
    return div_round(a * b, UNIT)


def div(a, b):
    return div_round(a * UNIT, b)


def quantize(value, places=MONEY_PLACES):
    """Round to `places` decimal places, still expressed at the internal scale."""
    step = 10 ** (PLACES - places)
    return div_round(value, step) * step


def to_float(value):
    """A quantised scaled integer as the float that serialises to the same decimal."""
    sign = '-' if value < 0 else ''
    digits = str(abs(value)).rjust(PLACES + 1, '0')
    return float(f'{sign}{digits[:-PLACES]}.{digits[-PLACES:]}')


def money(value):
    """The public helper: quantise to 2 places and return a JSON-safe float."""
    return to_float(quantize(value))


def ceil_units(value):
    """The smallest integer greater than or equal to a scaled value."""
    whole, remainder = divmod(value, UNIT)
    return whole + (1 if remainder else 0)
