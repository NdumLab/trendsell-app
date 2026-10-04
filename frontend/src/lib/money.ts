/** Deterministic decimal arithmetic shared with the API (action plan T04).
 *
 *  The review found the browser and the server disagreeing on money: with a supplier
 *  cost of 10.075 Python reported 10.08 and JavaScript 10.07. Python rounded the
 *  *decimal* value; JavaScript rounded the *binary* double, and `Number.EPSILON` does
 *  not close that gap for every accepted input.
 *
 *  Both sides now run the same algorithm on scaled integers instead:
 *  every value is an integer number of 1e-12 units (`bigint` here, `int` in Python);
 *  a number is converted through its shortest round-tripping decimal string, which
 *  `String()` and Python's `repr()` both produce, so the same JSON number becomes the
 *  same scaled integer on both sides; multiplication, division and quantisation round
 *  half away from zero at a fixed scale.
 *
 *  Accepted precision: inputs carrying more than PLACES decimal places are rounded half
 *  away from zero to that scale before any arithmetic runs. Results are quantised to two
 *  decimal places for money and percentages.
 *
 *  `backend/app/money.py` is the line-by-line mirror of this module; the parity cases in
 *  `contracts/` hold them together. */

export const PLACES = 12n;
export const UNIT = 10n ** PLACES;
const MONEY_PLACES = 2n;

/** Integer division rounding halves away from zero. The one rounding rule here. */
export function divRound(numerator: bigint, denominator: bigint): bigint {
  if (denominator === 0n) throw new Error('decimal division by zero');
  let n = numerator, d = denominator;
  if (d < 0n) { n = -n; d = -d; }
  if (n >= 0n) return (2n * n + d) / (2n * d);
  return -((-2n * n + d) / (2n * d));
}

/** Scale a decimal literal, with or without an exponent, to PLACES places. */
export function fromDecimalString(text: string): bigint {
  let body = text.trim();
  let sign = 1n;
  if (body[0] === '+' || body[0] === '-') { if (body[0] === '-') sign = -1n; body = body.slice(1); }
  const [mantissa, exponentText] = body.replace('E', 'e').split('e');
  const exponent = exponentText ? Number(exponentText) : 0;
  const [whole, fraction = ''] = mantissa.split('.');
  const digits = `${whole}${fraction}` || '0';
  if (!/^\d+$/.test(digits) || !Number.isInteger(exponent)) throw new Error(`not a decimal literal: ${text}`);
  const shift = Number(PLACES) - (fraction.length - exponent);
  if (shift >= 0) return sign * BigInt(digits) * 10n ** BigInt(shift);
  return sign * divRound(BigInt(digits), 10n ** BigInt(-shift));
}

/** A JavaScript number or decimal string as a scaled integer. */
export function parse(value: number | string): bigint {
  if (typeof value === 'string') return fromDecimalString(value);
  if (!Number.isFinite(value)) throw new Error(`not a finite number: ${value}`);
  return fromDecimalString(String(value));
}

export const mul = (a: bigint, b: bigint) => divRound(a * b, UNIT);
export const div = (a: bigint, b: bigint) => divRound(a * UNIT, b);

/** Round to `places` decimal places, still expressed at the internal scale. */
export function quantize(value: bigint, places: bigint = MONEY_PLACES): bigint {
  const step = 10n ** (PLACES - places);
  return divRound(value, step) * step;
}

/** A quantised scaled integer as the number that serialises to the same decimal. */
export function toNumber(value: bigint): number {
  const sign = value < 0n ? '-' : '';
  const digits = (value < 0n ? -value : value).toString().padStart(Number(PLACES) + 1, '0');
  const cut = digits.length - Number(PLACES);
  return Number(`${sign}${digits.slice(0, cut)}.${digits.slice(cut)}`);
}

/** The public helper: quantise to two places and return a JSON-safe number. */
export const money = (value: bigint) => toNumber(quantize(value));

/** The smallest integer greater than or equal to a scaled value. */
export function ceilUnits(value: bigint): number {
  const whole = value / UNIT, remainder = value % UNIT;
  // BigInt division truncates toward zero, so a negative remainder already rounded up.
  return Number(remainder > 0n ? whole + 1n : whole);
}
