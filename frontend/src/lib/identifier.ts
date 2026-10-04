/** Identifier parsing only. TrendSell never fetches a user-supplied URL, so hosts and shapes are allowlisted.
 *  Mirrors backend/app/security.py:resolve_input; both sides are held to contracts/identifier_cases.json. */
const AMAZON_US_HOSTS = ['amazon.com', 'www.amazon.com'];
export const UNSUPPORTED_INPUT = 'Enter a 10-character ASIN or an Amazon US product link, such as https://www.amazon.com/dp/B0XXXXXXXX. Short links and other sources are not supported yet.';

export function parseAmazon(input: string): string {
  const value = input.trim();
  if (/^[a-z0-9]{10}$/i.test(value)) return value.toUpperCase();
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || !AMAZON_US_HOSTS.includes(url.hostname) || url.username || url.password || (url.port && url.port !== '443')) throw Error();
    const asin = url.pathname.match(/\/(?:dp|gp\/product)\/([a-z0-9]{10})(?:\/|$)/i)?.[1];
    if (!asin) throw Error();
    return asin.toUpperCase();
  } catch {
    throw new Error(UNSUPPORTED_INPUT);
  }
}
