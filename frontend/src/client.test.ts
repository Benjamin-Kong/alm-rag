// SRS-027/040: generated request types, credential headers and safe failures.
import { expect, test, vi } from 'vitest';
import { ApiClient } from './client';

test('encodes identifiers and uses same-origin typed requests', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => [] });
  const client = new ApiClient({ apiKey: 'synthetic-key', csrf: 'synthetic-csrf' }, fetcher);
  await client.jobEvents('id/with space');
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/jobs/id%2Fwith%20space/events');
  await client.createKey({ name: 'reader', project_uids: ['p1'], permissions: ['project_read'] });
  const options = fetcher.mock.calls[1][1];
  expect(options.credentials).toBe('same-origin');
  expect(options.headers['X-API-Key']).toBe('synthetic-key');
  expect(options.headers['X-CSRF-Token']).toBe('synthetic-csrf');
});

test('never echoes error bodies or transport exceptions', async () => {
  const rejected = new ApiClient({}, vi.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({ secret: 'private-value' }) }));
  await expect(rejected.projects()).rejects.toThrow('Request failed (403)');
  const unavailable = new ApiClient({}, vi.fn().mockRejectedValue(new Error('private-value')));
  await expect(unavailable.projects()).rejects.toThrow('Service unavailable');
});
