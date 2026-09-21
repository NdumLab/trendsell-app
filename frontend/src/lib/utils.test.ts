import { describe, expect, it } from 'vitest';
import { formatCompact, formatMoney } from '@/lib/utils';

/** Review finding 6: a saved USD 8.40 quote displayed as `US$8`. The stored amount was
 *  right; the shared formatter forced zero decimals on every currency. */
describe('money formatting', () => {
  it('keeps the cents of a supplier quote', () => {
    expect(formatMoney(8.4, 'USD')).toContain('8.40');
    expect(formatMoney(10.075, 'USD')).toContain('10.08');
  });

  it('keeps the minor unit for per-unit naira economics', () => {
    expect(formatMoney(1234.5)).toContain('1,234.50');
  });

  it('still rounds summary figures where the minor unit is noise', () => {
    expect(formatCompact(1234.56)).toContain('1,235');
    expect(formatCompact(1234.56)).not.toContain('.');
  });

  it('formats negative amounts without losing precision', () => {
    expect(formatMoney(-8.4, 'USD')).toContain('8.40');
    expect(formatMoney(-8.4, 'USD')).toMatch(/-|\(/);
  });

  it('names the currency it was given', () => {
    expect(formatMoney(1, 'USD')).not.toBe(formatMoney(1, 'NGN'));
  });
});
