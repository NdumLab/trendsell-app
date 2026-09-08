import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
export const cn = (...values: ClassValue[]) => twMerge(clsx(values));
/** Detailed money: the currency's own precision, so USD 8.40 is not shown as US$8 (action plan T04).
 *  Use this for anything a user compares or re-enters — quotes, per-unit economics, targets. */
export const formatMoney = (value: number, currency = 'NGN') => new Intl.NumberFormat('en-NG', { style: 'currency', currency }).format(value);
/** Rounded money for summary figures where the minor unit is noise, such as total order cash. */
export const formatCompact = (value: number, currency = 'NGN') => new Intl.NumberFormat('en-NG', { style: 'currency', currency, maximumFractionDigits: 0 }).format(value);
export const dateTime = (value?: string | null) => value ? new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : 'Never collected';
export const relativeTime = (value: string) => {
  const hours = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 3600000));
  return hours < 1 ? 'Less than an hour ago' : hours < 24 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`;
};
export function download(name: string, body: string, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const a = document.createElement('a'); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function stored<T>(key: string, fallback: T): T {
  try { const parsed = JSON.parse(localStorage.getItem(key) || 'null'); return parsed === null ? fallback : parsed; } catch { return fallback; }
}
