import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { parseAmazon, UNSUPPORTED_INPUT } from '@/lib/identifier';

const contract = JSON.parse(readFileSync(new URL('../../../contracts/identifier_cases.json', import.meta.url), 'utf8')) as
  { accepted: { input: string; asin: string; why: string }[]; rejected: { input: string; why: string }[] };

describe('capture identifier contract', () => {
  it.each(contract.accepted.map(c => [c.why, c] as const))('accepts %s', (_why, testCase) => {
    expect(parseAmazon(testCase.input)).toBe(testCase.asin);
  });

  it.each(contract.rejected.map(c => [c.why, c] as const))('rejects %s', (_why, testCase) => {
    expect(() => parseAmazon(testCase.input)).toThrow(UNSUPPORTED_INPUT);
  });

  it('explains what is supported instead of failing silently', () => {
    expect(UNSUPPORTED_INPUT).toContain('amazon.com/dp/');
    expect(UNSUPPORTED_INPUT).toContain('ASIN');
  });
});
