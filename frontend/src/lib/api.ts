const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
/** Called whenever any request comes back 401, so an ended session is handled in one
 *  place rather than per screen (action plan P04). */
let onUnauthorized: (() => void) | null = null;
export const setUnauthorizedHandler = (handler: (() => void) | null) => { onUnauthorized = handler; };

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}/api/v1${path}`, { ...options, credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'TrendSell', ...options.headers }, signal: options.signal || AbortSignal.timeout(15000) });
  } catch { throw new ApiError(0, 'Cannot reach the workspace service. Check the connection and try again.'); }
  const body = await response.json().catch(() => null);
  if (response.status === 401) onUnauthorized?.();
  if (!response.ok) {
    const detail = body?.detail;
    throw new ApiError(response.status, typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e: { msg: string }) => e.msg).join('; ') : 'The request could not be completed.');
  }
  return body as T;
}
export const post = <T,>(path: string, body: unknown, key?: string) => api<T>(path, { method: 'POST', body: JSON.stringify(body), headers: key ? { 'Idempotency-Key': key } : {} });
