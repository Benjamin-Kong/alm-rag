// SRS-038/040: M1 console foundation; full operational UI remains M5.
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { App } from './App';
import { getHealth } from './health';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
test('checks same-origin liveness and shows accessible status', async () => {
 const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) });
 vi.stubGlobal('fetch', fetcher); render(<App />);
 expect(screen.getByRole('status').textContent).toContain('Checking');
 await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Available'));
 expect(fetcher.mock.calls[0][0]).toBe('/api/v1/healthz');
 expect(screen.getByRole('heading', {level: 1}).textContent).toContain('ALM RAG');
});
test.each([{ok:false,json:async()=>({secret:'private-test-value'})},{ok:true,json:async()=>({status:'<script>private-test-value</script>'})}])('fails closed without rendering server payload', async response => {
 vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response)); render(<App />);
 await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Unavailable'));
 expect(document.body.textContent).not.toContain('private-test-value');
});
test('network errors become safe errors', async () => {
 vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private-test-value')));
 await expect(getHealth()).rejects.toThrow('Health check unavailable');
});
