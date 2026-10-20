import type { paths } from './generated-api';

export type Health = paths['/api/v1/healthz']['get']['responses'][200]['content']['application/json'];

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  try {
    const response = await fetch('/api/v1/healthz', { signal, credentials: 'same-origin' });
    if (!response.ok) throw new Error();
    const data: unknown = await response.json();
    if (typeof data !== 'object' || data === null || !('status' in data) || data.status !== 'ok') {
      throw new Error();
    }
    return { status: 'ok' };
  } catch {
    throw new Error('Health check unavailable');
  }
}
